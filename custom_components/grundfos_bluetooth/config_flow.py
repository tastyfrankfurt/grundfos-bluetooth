"""Config flow for Grundfos Bluetooth integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from bleak import BleakScanner

from homeassistant import config_entries
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SCAN_INTERVAL, DEFAULT_NAME, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GrundfosConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Grundfos Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]

            # Set unique ID to prevent duplicate entries
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                },
            )

        # Scan for Grundfos devices
        discovered = await self._async_scan_for_devices()

        if not discovered and not user_input:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): str,
                        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    }
                ),
                errors=errors,
            )

        # Show discovered devices
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {
                            addr: f"{info['name']} ({addr})"
                            for addr, info in discovered.items()
                        }
                    ),
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_bluetooth(
        self, discovery_info: dict[str, Any]
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        address = discovery_info.get("address")
        name = discovery_info.get("name", DEFAULT_NAME)

        if not address:
            return self.async_abort(reason="no_address")

        # Set unique ID to prevent duplicate entries
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()

        self.context["title_placeholders"] = {"name": name}

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        if user_input is not None:
            address = self.unique_id
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, DEFAULT_NAME),
                data={
                    CONF_ADDRESS: address,
                    CONF_NAME: user_input.get(CONF_NAME, DEFAULT_NAME),
                },
            )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {vol.Optional(CONF_NAME, default=DEFAULT_NAME): str}
            ),
        )

    async def _async_scan_for_devices(self) -> dict[str, Any]:
        """Scan for Grundfos BLE devices."""
        _LOGGER.debug("Scanning for Grundfos Bluetooth devices")

        try:
            # Scan for 10 seconds
            devices = await BleakScanner.discover(timeout=10.0)

            discovered = {}
            for device in devices:
                # Look for Grundfos devices
                # Based on btsnoop, we can identify by service UUIDs or name
                if device.name and any(
                    keyword in device.name.lower()
                    for keyword in ["grundfos", "scala", "pump"]
                ):
                    discovered[device.address] = {
                        "name": device.name,
                        "rssi": getattr(device, "rssi", None),
                    }
                    _LOGGER.debug("Found Grundfos device: %s (%s)", device.name, device.address)

            self._discovered_devices = discovered
            return discovered

        except Exception as ex:
            _LOGGER.error("Error scanning for devices: %s", ex)
            return {}


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Grundfos Bluetooth."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                }
            ),
        )
