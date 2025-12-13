"""Sensor platform for Grundfos Bluetooth."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPressure, UnitOfTemperature
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
    """Set up Grundfos sensors."""
    coordinator: GrundfosDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Define sensors based on typical pump data
    sensors = [
        GrundfosStatusSensor(coordinator, entry),
        GrundfosModelSensor(coordinator, entry),
        GrundfosSerialSensor(coordinator, entry),
        GrundfosFirmwareSensor(coordinator, entry),
    ]

    async_add_entities(sensors)


class GrundfosBaseSensor(CoordinatorEntity[GrundfosDataUpdateCoordinator], SensorEntity):
    """Base class for Grundfos sensors."""

    def __init__(
        self,
        coordinator: GrundfosDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._sensor_type = sensor_type

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get("name", "Grundfos Pump"),
            manufacturer="Grundfos",
            model=coordinator.data.get("model", "Unknown") if coordinator.data else "Unknown",
            sw_version=coordinator.data.get("firmware") if coordinator.data else None,
        )


class GrundfosStatusSensor(GrundfosBaseSensor):
    """Sensor for pump status."""

    def __init__(
        self,
        coordinator: GrundfosDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "status", "Pump Status")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        # Parse status from data
        return "Connected" if self.coordinator.device and self.coordinator.device.is_connected else "Disconnected"


class GrundfosModelSensor(GrundfosBaseSensor):
    """Sensor for pump model."""

    def __init__(
        self,
        coordinator: GrundfosDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "model", "Pump Model")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get("model")


class GrundfosSerialSensor(GrundfosBaseSensor):
    """Sensor for pump serial number."""

    def __init__(
        self,
        coordinator: GrundfosDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "serial", "Pump Serial Number")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get("serial")


class GrundfosFirmwareSensor(GrundfosBaseSensor):
    """Sensor for firmware version."""

    def __init__(
        self,
        coordinator: GrundfosDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "firmware", "Firmware Version")

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self.coordinator.data.get("firmware")
