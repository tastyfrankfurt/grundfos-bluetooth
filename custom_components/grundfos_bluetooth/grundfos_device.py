"""Grundfos Bluetooth device client."""
from __future__ import annotations

import asyncio
import logging
import struct
from typing import Any, Callable

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

_LOGGER = logging.getLogger(__name__)


class GrundfosDevice:
    """Represents a Grundfos Bluetooth device."""

    def __init__(self, ble_device: BLEDevice) -> None:
        """Initialize the device."""
        self.ble_device = ble_device
        self.client: BleakClient | None = None
        self._notification_callbacks: list[Callable[[bytes], None]] = []
        self._data: dict[str, Any] = {}
        self._lock = asyncio.Lock()

        # Grundfos custom service UUIDs (reversed from btsnoop)
        self.service_uuid_1 = "9d41001835d6f4adad60e7bd8dc491c0"
        self.service_uuid_2 = "9d41001935d6f4adad60e7bd8dc491c0"

        # Main communication characteristics (may be separate for notify/write)
        self.notify_char_uuid = None  # Characteristic for notifications
        self.write_char_uuid = None  # Characteristic for writing commands

    async def connect(self) -> bool:
        """Connect to the device."""
        try:
            _LOGGER.debug("Connecting to %s", self.ble_device.address)
            self.client = await establish_connection(
                BleakClient,
                self.ble_device,
                self.ble_device.address,
                disconnected_callback=self._disconnected_callback,
            )

            # Discover characteristics
            await self._discover_characteristics()

            # Start listening for notifications
            if self.notify_char_uuid:
                await self.client.start_notify(
                    self.notify_char_uuid, self._notification_handler
                )
                _LOGGER.info("Started notifications on %s", self.notify_char_uuid)
            else:
                _LOGGER.warning("No notify characteristic found - notifications disabled")

            return True
        except (BleakError, asyncio.TimeoutError) as ex:
            _LOGGER.error("Failed to connect to device: %s", ex)
            return False

    def _disconnected_callback(self, client: BleakClient) -> None:
        """Handle disconnection."""
        _LOGGER.warning("Device %s disconnected", self.ble_device.address)
        self.client = None

    async def _discover_characteristics(self) -> None:
        """Discover device characteristics."""
        if not self.client or not self.client.is_connected:
            _LOGGER.error("Cannot discover characteristics - client not connected")
            return

        _LOGGER.info("Discovering characteristics for device %s", self.ble_device.address)

        notify_candidates = []
        write_candidates = []
        combined_candidates = []

        # Scan all services and characteristics
        for service in self.client.services:
            _LOGGER.info("Service: %s (UUID: %s)", service.description, service.uuid)

            for char in service.characteristics:
                props_str = ", ".join(char.properties)
                _LOGGER.info(
                    "  Characteristic: %s (UUID: %s) - Properties: [%s]",
                    char.description,
                    char.uuid,
                    props_str,
                )

                # Check for combined notify+write characteristic (ideal)
                if "notify" in char.properties and "write" in char.properties:
                    combined_candidates.append(char)
                    _LOGGER.info("    → Found COMBINED notify+write characteristic")

                # Track notify-capable characteristics
                if "notify" in char.properties:
                    notify_candidates.append(char)
                    _LOGGER.debug("    → Can receive notifications")

                # Track write-capable characteristics (write or write-without-response)
                if "write" in char.properties or "write-without-response" in char.properties:
                    write_candidates.append(char)
                    _LOGGER.debug("    → Can write commands")

        # Prioritize combined characteristic, then separate characteristics
        if combined_candidates:
            # Use the same characteristic for both notify and write
            self.notify_char_uuid = combined_candidates[0].uuid
            self.write_char_uuid = combined_candidates[0].uuid
            _LOGGER.info(
                "Using combined characteristic for notify+write: %s",
                combined_candidates[0].uuid,
            )
        else:
            # Use separate characteristics
            if notify_candidates:
                self.notify_char_uuid = notify_candidates[0].uuid
                _LOGGER.info("Using notify characteristic: %s", self.notify_char_uuid)
            else:
                _LOGGER.warning("No notify characteristic found!")

            if write_candidates:
                self.write_char_uuid = write_candidates[0].uuid
                _LOGGER.info("Using write characteristic: %s", self.write_char_uuid)
            else:
                _LOGGER.warning("No write characteristic found!")

        # Summary
        if self.notify_char_uuid and self.write_char_uuid:
            _LOGGER.info("Characteristic discovery successful")
        else:
            _LOGGER.error(
                "Characteristic discovery incomplete - notify: %s, write: %s",
                self.notify_char_uuid,
                self.write_char_uuid,
            )

    def _notification_handler(self, sender: int, data: bytes) -> None:
        """Handle notifications from the device."""
        _LOGGER.debug("Notification from %s: %s", sender, data.hex())

        # Parse notification data (based on btsnoop analysis)
        # Format appears to be: [header][command][payload][checksum]
        if len(data) < 4:
            return

        try:
            # Example parsing - adjust based on actual protocol
            header = data[0]
            length = data[1]
            command_type = data[2:4]

            if header == 0x24:  # Response header from btsnoop
                self._parse_response(data)

            # Notify callbacks
            for callback in self._notification_callbacks:
                callback(data)

        except Exception as ex:
            _LOGGER.error("Error parsing notification: %s", ex)

    def _parse_response(self, data: bytes) -> None:
        """Parse device response data."""
        # Based on btsnoop analysis, responses contain various device info
        # Format: 24 [len] f8 e7 [cmd] [payload] [checksum]

        if len(data) < 6:
            return

        try:
            length = data[1]
            # cmd_high = data[4]
            # cmd_low = data[5]
            payload = data[6:-2]  # Exclude checksum at end

            # Try to decode ASCII strings (device info, model, serial, etc.)
            try:
                decoded = payload.decode("ascii", errors="ignore")
                if decoded and any(c.isprintable() for c in decoded):
                    _LOGGER.debug("Decoded response: %s", decoded)

                    # Store device info
                    if "SCALA" in decoded:
                        self._data["model"] = decoded.strip()
                    elif decoded.startswith("V") and "." in decoded:
                        self._data["firmware"] = decoded.strip()
                    elif decoded.isdigit() and len(decoded) >= 8:
                        self._data["serial"] = decoded.strip()

            except UnicodeDecodeError:
                pass

            # Parse numeric data
            # Based on btsnoop, there are many sensor readings in the responses
            if len(payload) >= 4:
                # Example: parse 32-bit integers
                pass  # Add specific parsing based on pump data format

        except Exception as ex:
            _LOGGER.error("Error parsing response: %s", ex)

    async def send_command(self, command: bytes) -> None:
        """Send a command to the device."""
        # Check client connection
        if not self.client:
            raise RuntimeError("BLE client not initialized")

        if not self.client.is_connected:
            raise RuntimeError("Device not connected to BLE")

        # Check if write characteristic was discovered
        if not self.write_char_uuid:
            raise RuntimeError(
                "Write characteristic not found - characteristic discovery may have failed"
            )

        async with self._lock:
            try:
                _LOGGER.debug("Sending command to %s: %s", self.write_char_uuid, command.hex())
                await self.client.write_gatt_char(
                    self.write_char_uuid, command, response=False
                )
                _LOGGER.debug("Command sent successfully")
            except BleakError as ex:
                _LOGGER.error("Failed to send command via BLE: %s", ex)
                # Mark as disconnected
                self.client = None
                raise RuntimeError(f"BLE write failed: {ex}") from ex

    async def read_device_info(self) -> dict[str, Any]:
        """Read device information (model, serial, firmware)."""
        _LOGGER.debug("Reading device info from %s", self.ble_device.address)

        try:
            # Based on btsnoop, device info commands start with 2705e7f807...
            # Command pattern: 27 05 e7 f8 07 01 [param] [checksum]

            commands = [
                bytes.fromhex("2705e7f80701015238"),  # Read command (from btsnoop)
                bytes.fromhex("2705e7f80701085238"),  # Serial number
                bytes.fromhex("2705e7f80701095238"),  # Another ID
                bytes.fromhex("2705e7f80701325408"),  # Firmware 1
                bytes.fromhex("2705e7f807013ad500"),  # Firmware 2
            ]

            _LOGGER.debug("Sending %d device info commands", len(commands))
            for idx, cmd in enumerate(commands, 1):
                await self.send_command(cmd)
                await asyncio.sleep(0.2)  # Wait for response

            # Give time for notifications to arrive
            await asyncio.sleep(1)

            _LOGGER.info("Device info read complete. Data: %s", self._data)
            return self._data
        except Exception as ex:
            _LOGGER.error("Failed to read device info: %s", ex, exc_info=True)
            raise RuntimeError(f"Failed to read device info: {ex}") from ex

    async def read_pump_status(self) -> dict[str, Any]:
        """Read pump status and sensor data."""
        _LOGGER.debug("Reading pump status from %s", self.ble_device.address)

        try:
            # Based on btsnoop analysis, status commands use pattern:
            # 2707e7f80a03[param][checksum]

            status_commands = [
                bytes.fromhex("2707e7f80a035e00044cb9"),  # Status command from btsnoop
                bytes.fromhex("2707e7f80a035b00a412a3"),  # Another status
            ]

            _LOGGER.debug("Sending %d pump status commands", len(status_commands))
            for cmd in status_commands:
                await self.send_command(cmd)
                await asyncio.sleep(0.2)

            await asyncio.sleep(1)
            _LOGGER.debug("Pump status read complete")
            return self._data
        except Exception as ex:
            _LOGGER.error("Failed to read pump status: %s", ex, exc_info=True)
            raise RuntimeError(f"Failed to read pump status: {ex}") from ex

    def register_notification_callback(self, callback: Callable[[bytes], None]) -> None:
        """Register a callback for notifications."""
        self._notification_callbacks.append(callback)

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self.client and self.client.is_connected:
            try:
                # Stop notifications if they were started
                if self.notify_char_uuid:
                    try:
                        await self.client.stop_notify(self.notify_char_uuid)
                        _LOGGER.debug("Stopped notifications on %s", self.notify_char_uuid)
                    except Exception as ex:
                        _LOGGER.warning("Error stopping notifications: %s", ex)

                await self.client.disconnect()
                _LOGGER.info("Disconnected from device %s", self.ble_device.address)
            except BleakError as ex:
                _LOGGER.error("Error disconnecting from device: %s", ex)

    @property
    def is_connected(self) -> bool:
        """Return if device is connected."""
        return self.client is not None and self.client.is_connected

    @property
    def address(self) -> str:
        """Return device address."""
        return self.ble_device.address

    @property
    def name(self) -> str:
        """Return device name."""
        return self.ble_device.name or "Unknown"

    def get_data(self) -> dict[str, Any]:
        """Get current device data."""
        return self._data.copy()
