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

        # Main communication characteristic handle (0x0016 from btsnoop)
        self.main_char_uuid = None  # Will be discovered during connect

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
            if self.main_char_uuid:
                await self.client.start_notify(
                    self.main_char_uuid, self._notification_handler
                )
                _LOGGER.debug("Started notifications on %s", self.main_char_uuid)

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
            return

        # Find the main communication characteristic
        # Based on btsnoop, this is in one of the Grundfos services
        for service in self.client.services:
            _LOGGER.debug("Service: %s", service.uuid)
            for char in service.characteristics:
                _LOGGER.debug("  Characteristic: %s - %s", char.uuid, char.properties)

                # Look for notify + write characteristics (typical for bidirectional comms)
                if "notify" in char.properties and "write" in char.properties:
                    self.main_char_uuid = char.uuid
                    _LOGGER.info("Found main characteristic: %s", char.uuid)
                    break

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
        if not self.client or not self.client.is_connected or not self.main_char_uuid:
            raise RuntimeError("Device not connected")

        async with self._lock:
            try:
                _LOGGER.debug("Sending command: %s", command.hex())
                await self.client.write_gatt_char(
                    self.main_char_uuid, command, response=False
                )
            except BleakError as ex:
                _LOGGER.error("Failed to send command: %s", ex)
                raise

    async def read_device_info(self) -> dict[str, Any]:
        """Read device information (model, serial, firmware)."""
        # Based on btsnoop, device info commands start with 2705e7f807...
        # Command pattern: 27 05 e7 f8 07 01 [param] [checksum]

        commands = [
            bytes.fromhex("2705e7f80701015238"),  # Read command (from btsnoop)
            bytes.fromhex("2705e7f80701085238"),  # Serial number
            bytes.fromhex("2705e7f80701095238"),  # Another ID
            bytes.fromhex("2705e7f80701325408"),  # Firmware 1
            bytes.fromhex("2705e7f807013ad500"),  # Firmware 2
        ]

        for cmd in commands:
            await self.send_command(cmd)
            await asyncio.sleep(0.2)  # Wait for response

        # Give time for notifications to arrive
        await asyncio.sleep(1)

        return self._data

    async def read_pump_status(self) -> dict[str, Any]:
        """Read pump status and sensor data."""
        # Based on btsnoop analysis, status commands use pattern:
        # 2707e7f80a03[param][checksum]

        status_commands = [
            bytes.fromhex("2707e7f80a035e00044cb9"),  # Status command from btsnoop
            bytes.fromhex("2707e7f80a035b00a412a3"),  # Another status
        ]

        for cmd in status_commands:
            await self.send_command(cmd)
            await asyncio.sleep(0.2)

        await asyncio.sleep(1)
        return self._data

    def register_notification_callback(self, callback: Callable[[bytes], None]) -> None:
        """Register a callback for notifications."""
        self._notification_callbacks.append(callback)

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self.client and self.client.is_connected:
            try:
                if self.main_char_uuid:
                    await self.client.stop_notify(self.main_char_uuid)
                await self.client.disconnect()
                _LOGGER.debug("Disconnected from device")
            except BleakError as ex:
                _LOGGER.error("Error disconnecting: %s", ex)

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
