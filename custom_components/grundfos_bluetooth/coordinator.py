"""DataUpdateCoordinator for Grundfos Bluetooth."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from bleak import BleakScanner
from bleak.backends.device import BLEDevice

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

        # Try up to 2 times in case device disconnected
        for attempt in range(2):
            try:
                # Ensure device is connected
                if not self.device or not self.device.is_connected:
                    await self._ensure_connection()

                if not self.device or not self.device.is_connected:
                    raise UpdateFailed("Device not connected")

                # Read pump status
                await self.device.read_pump_status()

                # Get current data
                data = self.device.get_data()

                _LOGGER.debug("Updated data: %s", data)
                return data

            except (RuntimeError, UpdateFailed) as err:
                _LOGGER.warning("Error on attempt %d: %s", attempt + 1, err)

                # Reset connection state for retry
                if self.device:
                    self.device.client = None
                self._ble_device = None

                # If this was the last attempt, raise the error
                if attempt == 1:
                    _LOGGER.error("Error updating data after retries: %s", err)
                    raise UpdateFailed(f"Error communicating with device: {err}") from err

                # Wait a bit before retrying
                await asyncio.sleep(1)

        # Should never reach here, but just in case
        raise UpdateFailed("Failed to update data")

    async def _ensure_connection(self) -> None:
        """Ensure the device is connected."""
        # If device is not connected, always rescan to get fresh BLEDevice object
        if not self.device or not self.device.is_connected:
            _LOGGER.debug("Scanning for device %s", self.device_address)
            self._ble_device = await BleakScanner.find_device_by_address(
                self.device_address, timeout=10.0
            )

            if not self._ble_device:
                raise UpdateFailed(f"Device {self.device_address} not found")

        if not self.device:
            self.device = GrundfosDevice(self._ble_device)
        else:
            # Update existing device with fresh BLEDevice object
            self.device.ble_device = self._ble_device

        if not self.device.is_connected:
            _LOGGER.debug("Connecting to device")
            connected = await self.device.connect()
            if not connected:
                raise UpdateFailed("Failed to connect to device")

            # Read device info only on first connect (device info doesn't change)
            if not self._device_info_read:
                _LOGGER.debug("Reading device info for the first time")
                await self.device.read_device_info()
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
