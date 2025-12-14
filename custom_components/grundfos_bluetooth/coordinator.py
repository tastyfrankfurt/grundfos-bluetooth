"""DataUpdateCoordinator for Grundfos Bluetooth."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from bleak.backends.device import BLEDevice

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .grundfos_device import GrundfosDevice

_LOGGER = logging.getLogger(__name__)


class GrundfosDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Grundfos data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.device_address = entry.data[CONF_ADDRESS]
        self.device: GrundfosDevice | None = None
        self._ble_device: BLEDevice | None = None
        self._device_info_read: bool = False  # Track if device info has been read

        # Get scan interval from options, fallback to default
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        # Check if the config entry is disabled
        if self.entry.disabled_by is not None:
            _LOGGER.debug("Config entry is disabled, skipping update")
            raise UpdateFailed("Integration is disabled")

        # Try up to 3 times in case device disconnected
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Ensure device is connected
                if not self.device or not self.device.is_connected:
                    _LOGGER.debug("Device not connected, attempting to connect (attempt %d/%d)",
                                 attempt + 1, max_attempts)
                    await self._ensure_connection()

                if not self.device or not self.device.is_connected:
                    raise UpdateFailed("Device not connected after connection attempt")

                # Read pump status
                _LOGGER.debug("Reading pump status")
                await self.device.read_pump_status()

                # Get current data
                data = self.device.get_data()

                if not data:
                    _LOGGER.warning("No data received from device")
                    # Don't fail completely, just return empty dict for now
                    return {}

                _LOGGER.debug("Successfully updated data: %s", data)

                # Disconnect after successful read
                if self.device and self.device.is_connected:
                    try:
                        await self.device.disconnect()
                        _LOGGER.debug("Disconnected after successful data read")
                    except Exception as disconnect_err:
                        _LOGGER.debug("Error during disconnect: %s", disconnect_err)

                return data

            except (RuntimeError, UpdateFailed) as err:
                _LOGGER.warning("Error on attempt %d/%d: %s", attempt + 1, max_attempts, err)

                # Reset connection state for retry
                if self.device:
                    try:
                        # Disconnect cleanly
                        if self.device.is_connected:
                            await self.device.disconnect()
                    except Exception as disconnect_err:
                        _LOGGER.debug("Error during disconnect cleanup: %s", disconnect_err)
                    finally:
                        # Clear client reference to force fresh connection on retry
                        if self.device:
                            self.device.client = None

                self._ble_device = None

                # If this was the last attempt, raise the error
                if attempt == max_attempts - 1:
                    _LOGGER.error("Error updating data after %d attempts: %s", max_attempts, err)
                    raise UpdateFailed(f"Error communicating with device: {err}") from err

                # Wait progressively longer before retrying (exponential backoff)
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                _LOGGER.debug("Waiting %d seconds before retry", wait_time)
                await asyncio.sleep(wait_time)

        # Should never reach here, but just in case
        raise UpdateFailed("Failed to update data after all attempts")

    async def _ensure_connection(self) -> None:
        """Ensure the device is connected."""
        # If device is not connected, get fresh BLEDevice object from Home Assistant
        if not self.device or not self.device.is_connected:
            _LOGGER.info("Device not connected, scanning for %s", self.device_address)

            # Use Home Assistant's bluetooth integration to get the device
            # This properly integrates with HA's bluetooth manager and proxies
            self._ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.device_address, connectable=True
            )

            if not self._ble_device:
                _LOGGER.warning(
                    "Device %s not found in Home Assistant bluetooth cache, "
                    "waiting for discovery...",
                    self.device_address
                )
                # Wait a bit and try again - device might be discovered soon
                await asyncio.sleep(2)
                self._ble_device = bluetooth.async_ble_device_from_address(
                    self.hass, self.device_address, connectable=True
                )

            if not self._ble_device:
                raise UpdateFailed(
                    f"Device {self.device_address} not found. Ensure it is in range and "
                    f"bluetooth is working properly."
                )

        if not self.device:
            self.device = GrundfosDevice(self._ble_device)
        else:
            # Update existing device with fresh BLEDevice object
            self.device.ble_device = self._ble_device

        if not self.device.is_connected:
            _LOGGER.info("Connecting to device %s", self.device_address)
            connected = await self.device.connect()
            if not connected:
                raise UpdateFailed("Failed to connect to device")

            # Give connection time to stabilize (reduced from 1.5s to 0.5s)
            _LOGGER.debug("Waiting for connection to stabilize")
            await asyncio.sleep(0.5)

            # Verify connection is still active after stabilization delay
            if not self.device.is_connected:
                raise UpdateFailed("Device disconnected during stabilization period")

            # Read device info only on first connect (device info doesn't change)
            # Also re-read if data is empty (device object was recreated)
            device_data = self.device.get_data()
            if not self._device_info_read or not device_data:
                if not device_data:
                    _LOGGER.info("Device data is empty, re-reading device info")
                else:
                    _LOGGER.info("Reading device info for the first time")

                # Read standard GATT characteristics (manufacturer, model, firmware)
                await self.device.read_device_info()

                # Read custom device info (device_name and serial_number via custom commands)
                await self.device.read_custom_device_info()

                self._device_info_read = True
            else:
                _LOGGER.debug("Skipping device info read (already read previously)")

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.debug("Shutting down coordinator for %s", self.device_address)

        # Disconnect from device if connected
        if self.device:
            try:
                await self.device.disconnect()
            except Exception as ex:
                _LOGGER.warning("Error disconnecting device during shutdown: %s", ex)
            finally:
                self.device = None

        # Clear BLE device reference
        self._ble_device = None

        _LOGGER.debug("Coordinator shutdown complete")
