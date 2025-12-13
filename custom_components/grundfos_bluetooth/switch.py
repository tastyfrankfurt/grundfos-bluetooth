"""Switch platform for Grundfos Bluetooth."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GrundfosDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Grundfos switches."""
    coordinator: GrundfosDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Add pump control switch
    async_add_entities([GrundfosPumpSwitch(coordinator, entry)])


class GrundfosPumpSwitch(CoordinatorEntity[GrundfosDataUpdateCoordinator], SwitchEntity):
    """Switch to control the pump."""

    def __init__(
        self,
        coordinator: GrundfosDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_name = "Pump Control"
        self._attr_unique_id = f"{entry.entry_id}_pump_control"
        self._is_on = False

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get("name", "Grundfos Pump"),
            manufacturer="Grundfos",
            model=coordinator.data.get("model", "Unknown"),
            sw_version=coordinator.data.get("firmware"),
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # Send turn on command to pump
        # This will need to be reverse-engineered from btsnoop
        # For now, placeholder
        _LOGGER.info("Turning pump ON")

        if self.coordinator.device and self.coordinator.device.is_connected:
            # Example command - adjust based on actual protocol
            # command = bytes.fromhex("...")
            # await self.coordinator.device.send_command(command)
            pass

        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        # Send turn off command to pump
        _LOGGER.info("Turning pump OFF")

        if self.coordinator.device and self.coordinator.device.is_connected:
            # Example command - adjust based on actual protocol
            # command = bytes.fromhex("...")
            # await self.coordinator.device.send_command(command)
            pass

        self._is_on = False
        self.async_write_ha_state()
