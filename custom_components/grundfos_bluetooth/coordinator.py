"""DataUpdateCoordinator for Grundfos Bluetooth."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from bleak import BleakScanner
from bleak.backends.device import BLEDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
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

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
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

        except Exception as err:
            _LOGGER.error("Error updating data: %s", err)
            raise UpdateFailed(f"Error communicating with device: {err}") from err

    async def _ensure_connection(self) -> None:
        """Ensure the device is connected."""
        if not self._ble_device:
            # Scan for device
            _LOGGER.debug("Scanning for device %s", self.device_address)
            self._ble_device = await BleakScanner.find_device_by_address(
                self.device_address, timeout=10.0
            )

            if not self._ble_device:
                raise UpdateFailed(f"Device {self.device_address} not found")

        if not self.device:
            self.device = GrundfosDevice(self._ble_device)

        if not self.device.is_connected:
            _LOGGER.debug("Connecting to device")
            connected = await self.device.connect()
            if not connected:
                raise UpdateFailed("Failed to connect to device")

            # Read device info on first connect
            await self.device.read_device_info()

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        if self.device:
            await self.device.disconnect()
