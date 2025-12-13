"""Grundfos Bluetooth device client."""
from __future__ import annotations

import asyncio
import logging
import struct
from typing import Any, Callable

from bleak import BleakClient, BleakError
from bleak.backends.device import BLEDevice
from bleak_retry_connector import (
    BLEAK_RETRY_EXCEPTIONS as BLEAK_EXCEPTIONS,
    BleakClientWithServiceCache,
    establish_connection,
)

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
        self._response_queue: asyncio.Queue = asyncio.Queue()
        self._notification_count = 0

        # Grundfos custom service UUIDs (reversed from btsnoop)
        self.service_uuid_1 = "9d41001835d6f4adad60e7bd8dc491c0"
        self.service_uuid_2 = "9d41001935d6f4adad60e7bd8dc491c0"

        # Main communication characteristics (may be separate for notify/write)
        self.notify_char_uuid = None  # Characteristic UUID for notifications
        self.write_char_uuid = None  # Characteristic UUID for writing commands
        self._notify_char = None  # Actual characteristic object for notifications
        self._write_char = None  # Actual characteristic object for writing

    async def connect(self) -> bool:
        """Connect to the device."""
        try:
            _LOGGER.info("Attempting to connect to %s (name: %s)",
                        self.ble_device.address, self.ble_device.name)
            self.client = await establish_connection(
                BleakClientWithServiceCache,
                self.ble_device,
                self.ble_device.address,
                disconnected_callback=self._disconnected_callback,
                max_attempts=3,  # Reduce from default 10 to avoid slot exhaustion
                use_services_cache=False,  # Disable cache to avoid stale characteristic issues
                ble_device_callback=lambda: self.ble_device,
            )

            _LOGGER.info("Successfully established connection to %s", self.ble_device.address)

            # Services are automatically loaded by BleakClientWithServiceCache
            # and accessible via self.client.services property
            _LOGGER.debug("GATT services are available via client.services property")

            # Small delay to let services stabilize
            await asyncio.sleep(0.1)

            # Discover characteristics
            await self._discover_characteristics()

            # Start listening for notifications
            if self._notify_char:
                try:
                    # Verify the characteristic is still valid in current services
                    char_found = False
                    for service in self.client.services:
                        for char in service.characteristics:
                            if char.uuid == self._notify_char.uuid:
                                char_found = True
                                _LOGGER.debug(
                                    "Verified characteristic %s exists in service %s",
                                    char.uuid,
                                    service.uuid
                                )
                                break
                        if char_found:
                            break

                    if not char_found:
                        _LOGGER.error(
                            "Characteristic %s not found in current services! "
                            "Available characteristics: %s",
                            self._notify_char.uuid,
                            [char.uuid for s in self.client.services for char in s.characteristics]
                        )
                        raise BleakError(f"Characteristic {self._notify_char.uuid} not found in services")

                    _LOGGER.debug("Starting notifications on %s", self._notify_char.uuid)
                    # Use the characteristic object directly
                    await self.client.start_notify(
                        self._notify_char, self._notification_handler
                    )
                    _LOGGER.info("Started notifications on %s", self._notify_char.uuid)
                except BleakError as ex:
                    _LOGGER.error(
                        "Failed to start notifications on %s: %s",
                        self._notify_char.uuid if self._notify_char else "None",
                        ex
                    )
                    raise
            else:
                _LOGGER.warning("No notify characteristic found - notifications disabled")

            _LOGGER.info("Connection to %s fully established and ready", self.ble_device.address)
            return True
        except (BleakError, asyncio.TimeoutError) as ex:
            _LOGGER.error("Failed to connect to device %s: %s", self.ble_device.address, ex, exc_info=True)
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
            self._notify_char = combined_candidates[0]
            self._write_char = combined_candidates[0]
            self.notify_char_uuid = combined_candidates[0].uuid
            self.write_char_uuid = combined_candidates[0].uuid
            _LOGGER.info(
                "Using combined characteristic for notify+write: %s",
                combined_candidates[0].uuid,
            )
        else:
            # Use separate characteristics
            if notify_candidates:
                self._notify_char = notify_candidates[0]
                self.notify_char_uuid = notify_candidates[0].uuid
                _LOGGER.info("Using notify characteristic: %s", self.notify_char_uuid)
            else:
                _LOGGER.warning("No notify characteristic found!")

            if write_candidates:
                self._write_char = write_candidates[0]
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
        self._notification_count += 1
        _LOGGER.info(
            "📨 NOTIFICATION #%d from %s (%d bytes): %s",
            self._notification_count,
            sender,
            len(data),
            data.hex()
        )

        # Add to response queue for command responses
        try:
            self._response_queue.put_nowait(data)
        except asyncio.QueueFull:
            _LOGGER.warning("Response queue is full, dropping notification")

        # Parse notification data (based on btsnoop analysis)
        # Format appears to be: [header][command][payload][checksum]
        if len(data) < 4:
            _LOGGER.warning("Notification too short (%d bytes), skipping parse", len(data))
            return

        try:
            # Example parsing - adjust based on actual protocol
            header = data[0]
            length = data[1]
            command_type = data[2:4]

            _LOGGER.debug(
                "Notification details: header=0x%02x, length=%d, command_type=%s",
                header,
                length,
                command_type.hex()
            )

            if header == 0x24:  # Response header from btsnoop
                self._parse_response(data)
            else:
                _LOGGER.debug("Unknown header 0x%02x, attempting parse anyway", header)
                self._parse_response(data)

            # Notify callbacks
            for callback in self._notification_callbacks:
                callback(data)

        except Exception as ex:
            _LOGGER.error("Error parsing notification: %s", ex, exc_info=True)

    def _parse_response(self, data: bytes) -> None:
        """Parse device response data."""
        # Based on btsnoop analysis, responses contain various device info
        # Format: 24 [len] f8 e7 [cmd] [payload] [checksum]

        _LOGGER.debug("Parsing response of %d bytes: %s", len(data), data.hex())

        if len(data) < 6:
            _LOGGER.debug("Response too short for parsing (%d bytes)", len(data))
            return

        try:
            header = data[0]
            length = data[1]
            # cmd_high = data[4]
            # cmd_low = data[5]
            payload = data[6:-2] if len(data) > 8 else data[6:]  # Exclude checksum at end

            _LOGGER.debug(
                "Response structure: header=0x%02x, length=%d, payload=%d bytes: %s",
                header,
                length,
                len(payload),
                payload.hex() if payload else "(empty)"
            )

            # Try to decode ASCII strings (device info, model, serial, etc.)
            try:
                decoded = payload.decode("ascii", errors="ignore")
                if decoded and any(c.isprintable() for c in decoded):
                    _LOGGER.info("✅ Decoded ASCII response: '%s'", decoded)

                    # Store device info
                    if "SCALA" in decoded:
                        self._data["model"] = decoded.strip()
                        _LOGGER.info("Found model: %s", self._data["model"])
                    elif decoded.startswith("V") and "." in decoded:
                        self._data["firmware"] = decoded.strip()
                        _LOGGER.info("Found firmware: %s", self._data["firmware"])
                    elif decoded.isdigit() and len(decoded) >= 8:
                        self._data["serial"] = decoded.strip()
                        _LOGGER.info("Found serial: %s", self._data["serial"])
                else:
                    _LOGGER.debug("Payload is not printable ASCII")

            except UnicodeDecodeError:
                _LOGGER.debug("Payload is not ASCII text")

            # Parse numeric data
            # Based on btsnoop, there are many sensor readings in the responses
            if len(payload) >= 4:
                # Example: parse 32-bit integers
                _LOGGER.debug("Payload has %d bytes for numeric parsing", len(payload))
                # Add specific parsing based on pump data format

        except Exception as ex:
            _LOGGER.error("Error parsing response: %s", ex, exc_info=True)

    async def send_command(self, command: bytes, wait_for_response: bool = False, timeout: float = 2.0) -> bytes | None:
        """Send a command to the device.

        Args:
            command: The command bytes to send
            wait_for_response: If True, wait for and return a notification response
            timeout: How long to wait for a response in seconds

        Returns:
            The response bytes if wait_for_response=True, otherwise None
        """
        # Check client connection
        if not self.client:
            _LOGGER.error("Cannot send command: BLE client not initialized")
            raise RuntimeError("BLE client not initialized")

        if not self.client.is_connected:
            _LOGGER.error("Cannot send command: Device not connected to BLE")
            raise RuntimeError("Device not connected to BLE")

        # Check if write characteristic was discovered
        if not self._write_char:
            _LOGGER.error("Cannot send command: Write characteristic not found")
            raise RuntimeError(
                "Write characteristic not found - characteristic discovery may have failed"
            )

        async with self._lock:
            try:
                # Clear response queue before sending
                if wait_for_response:
                    while not self._response_queue.empty():
                        try:
                            self._response_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break

                _LOGGER.debug("📤 Sending command to %s: %s", self._write_char.uuid, command.hex())
                # Use the characteristic object directly
                await self.client.write_gatt_char(
                    self._write_char, command, response=False
                )
                _LOGGER.debug("✅ Command sent successfully")

                # Wait for response if requested
                if wait_for_response:
                    try:
                        _LOGGER.debug("⏳ Waiting up to %.1fs for response...", timeout)
                        response = await asyncio.wait_for(
                            self._response_queue.get(),
                            timeout=timeout
                        )
                        _LOGGER.debug("✅ Got response: %s", response.hex())
                        return response
                    except asyncio.TimeoutError:
                        _LOGGER.warning("⏱️ Timeout waiting for response to command %s", command.hex())
                        return None

                return None

            except BleakError as ex:
                _LOGGER.error("Failed to send command via BLE: %s", ex, exc_info=True)
                # Mark as disconnected
                self.client = None
                raise RuntimeError(f"BLE write failed: {ex}") from ex

    async def read_device_info(self) -> dict[str, Any]:
        """Read device information (model, serial, firmware)."""
        _LOGGER.info("📖 Reading device info from %s", self.ble_device.address)

        try:
            # Read standard Device Information Service characteristics
            # These are safe to read and won't cause disconnection
            device_info_chars = {
                "00002a29-0000-1000-8000-00805f9b34fb": "manufacturer",
                "00002a24-0000-1000-8000-00805f9b34fb": "model",
                "00002a26-0000-1000-8000-00805f9b34fb": "firmware",
                "00002a27-0000-1000-8000-00805f9b34fb": "hardware_version",
                "00002a28-0000-1000-8000-00805f9b34fb": "software_version",
            }

            _LOGGER.info("Reading standard Device Information Service characteristics")

            for char_uuid, data_key in device_info_chars.items():
                try:
                    # Find the characteristic in services
                    char_found = False
                    for service in self.client.services:
                        for char in service.characteristics:
                            if char.uuid == char_uuid:
                                char_found = True
                                _LOGGER.debug("Reading %s characteristic: %s", data_key, char_uuid)

                                # Read the characteristic value
                                value = await self.client.read_gatt_char(char)

                                # Decode as UTF-8 string (standard for device info characteristics)
                                decoded_value = value.decode("utf-8", errors="ignore").strip()

                                if decoded_value:
                                    self._data[data_key] = decoded_value
                                    _LOGGER.info("✅ Read %s: '%s'", data_key, decoded_value)
                                else:
                                    _LOGGER.debug("Empty value for %s", data_key)

                                break
                        if char_found:
                            break

                    if not char_found:
                        _LOGGER.debug("Characteristic %s not found (optional)", char_uuid)

                except Exception as ex:
                    _LOGGER.warning("Error reading %s: %s", data_key, ex)
                    # Continue with other characteristics even if one fails
                    continue

            _LOGGER.info("Device info read complete. Data: %s", self._data)
            return self._data

        except Exception as ex:
            _LOGGER.error("Failed to read device info: %s", ex, exc_info=True)
            raise RuntimeError(f"Failed to read device info: {ex}") from ex

    async def read_pump_status(self) -> dict[str, Any]:
        """Read pump status and sensor data."""
        _LOGGER.info("📊 Reading pump status from %s", self.ble_device.address)

        try:
            # For now, we rely on notifications from the device for status updates
            # Sending commands causes the device to disconnect, so we need to
            # figure out the correct protocol/handshake first
            _LOGGER.info(
                "Waiting for status updates via notifications. "
                "Current data: %s",
                self._data
            )

            # If the device sends periodic notifications, they will be captured
            # by the notification handler and stored in self._data
            # For now, just return what we have
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
                if self._notify_char:
                    try:
                        await self.client.stop_notify(self._notify_char)
                        _LOGGER.debug("Stopped notifications on %s", self._notify_char.uuid)
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
