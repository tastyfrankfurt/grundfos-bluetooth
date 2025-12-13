#!/usr/bin/env python3
"""
Parse btsnoop_hci.log to extract Bluetooth LE GATT characteristics and communication patterns
"""
import struct
import sys
from collections import defaultdict

class BtsnoopParser:
    def __init__(self, filename):
        self.filename = filename
        self.packets = []
        self.services = defaultdict(list)
        self.characteristics = {}
        self.device_address = None

    def parse(self):
        with open(self.filename, 'rb') as f:
            # Read btsnoop header
            identification = f.read(8)
            if identification != b'btsnoop\x00':
                raise ValueError("Not a valid btsnoop file")

            version = struct.unpack('>I', f.read(4))[0]
            datalink = struct.unpack('>I', f.read(4))[0]

            print(f"Btsnoop version: {version}, Datalink type: {datalink}")
            print("=" * 80)

            # Parse packets
            packet_num = 0
            while True:
                # Read packet record header (btsnoop v1: 4+4+4+4+8 = 24 bytes)
                header = f.read(24)
                if len(header) < 24:
                    break

                orig_len, incl_len, flags, drops, timestamp_high = struct.unpack('>IIIII', header[:20])
                timestamp_low = struct.unpack('>I', header[20:24])[0]
                timestamp = (timestamp_high << 32) | timestamp_low

                # Read packet data
                packet_data = f.read(incl_len)
                if len(packet_data) < incl_len:
                    break

                packet_num += 1
                self.analyze_packet(packet_num, packet_data, flags)

        self.print_summary()

    def analyze_packet(self, num, data, flags):
        """Analyze HCI packet"""
        if len(data) < 1:
            return

        # HCI packet type
        packet_type = data[0]

        # 0x01 = HCI Command, 0x02 = ACL Data, 0x04 = HCI Event
        if packet_type == 0x04 and len(data) > 2:  # HCI Event
            event_code = data[1]
            param_len = data[2]

            # LE Meta Event (0x3E) contains GATT data
            if event_code == 0x3E and len(data) > 3:
                subevent = data[3]
                if subevent == 0x02:  # LE Advertising Report
                    self.parse_advertising(data[4:])

        elif packet_type == 0x02:  # ACL Data
            if len(data) > 8:
                # Parse ATT protocol data
                self.parse_att_data(num, data, flags)

    def parse_advertising(self, data):
        """Parse LE advertising data to find device address"""
        if len(data) < 10:
            return
        num_reports = data[0]
        if num_reports > 0 and len(data) > 7:
            addr_type = data[1]
            address = data[2:8]
            addr_str = ':'.join([f'{b:02X}' for b in reversed(address)])
            if self.device_address is None:
                self.device_address = addr_str
                print(f"Found device address: {addr_str}")

    def parse_att_data(self, num, data, flags):
        """Parse ATT protocol data"""
        if len(data) < 9:
            return

        # Skip to ATT payload (after HCI ACL header and L2CAP header)
        # HCI: 1 byte type + 2 handle + 2 length = 5
        # L2CAP: 2 length + 2 channel = 4
        offset = 9

        if len(data) <= offset:
            return

        att_opcode = data[offset]
        att_data = data[offset+1:]

        direction = "SENT" if (flags & 0x01) else "RECV"

        # ATT opcodes we care about
        if att_opcode == 0x10:  # Read By Type Request
            if len(att_data) >= 4:
                start_handle = struct.unpack('<H', att_data[0:2])[0]
                end_handle = struct.unpack('<H', att_data[2:4])[0]
                uuid = att_data[4:]
                uuid_str = self.format_uuid(uuid)
                print(f"[{num}] {direction} Read By Type Request: handles {start_handle:04x}-{end_handle:04x}, UUID: {uuid_str}")

        elif att_opcode == 0x11:  # Read By Type Response
            if len(att_data) >= 1:
                length = att_data[0]
                print(f"[{num}] {direction} Read By Type Response:")
                offset_data = 1
                while offset_data + length <= len(att_data):
                    item = att_data[offset_data:offset_data+length]
                    if len(item) >= 2:
                        handle = struct.unpack('<H', item[0:2])[0]
                        value = item[2:]
                        print(f"    Handle {handle:04x}: {value.hex()}")
                        self.characteristics[handle] = value
                    offset_data += length

        elif att_opcode == 0x08:  # Read By Group Type Request (discover services)
            if len(att_data) >= 4:
                start_handle = struct.unpack('<H', att_data[0:2])[0]
                end_handle = struct.unpack('<H', att_data[2:4])[0]
                uuid = att_data[4:]
                uuid_str = self.format_uuid(uuid)
                print(f"[{num}] {direction} Read By Group Type (Services): {start_handle:04x}-{end_handle:04x}, UUID: {uuid_str}")

        elif att_opcode == 0x09:  # Read By Group Type Response
            if len(att_data) >= 1:
                length = att_data[0]
                print(f"[{num}] {direction} Read By Group Type Response (Services):")
                offset_data = 1
                while offset_data + length <= len(att_data):
                    item = att_data[offset_data:offset_data+length]
                    if len(item) >= 4:
                        start_handle = struct.unpack('<H', item[0:2])[0]
                        end_handle = struct.unpack('<H', item[2:4])[0]
                        uuid = item[4:]
                        uuid_str = self.format_uuid(uuid)
                        print(f"    Service {start_handle:04x}-{end_handle:04x}: {uuid_str}")
                        self.services[uuid_str].append((start_handle, end_handle))
                    offset_data += length

        elif att_opcode == 0x0A:  # Find Information Request
            if len(att_data) >= 4:
                start_handle = struct.unpack('<H', att_data[0:2])[0]
                end_handle = struct.unpack('<H', att_data[2:4])[0]
                print(f"[{num}] {direction} Find Information Request: {start_handle:04x}-{end_handle:04x}")

        elif att_opcode == 0x0B:  # Find Information Response
            if len(att_data) >= 1:
                format_type = att_data[0]
                uuid_len = 2 if format_type == 1 else 16
                print(f"[{num}] {direction} Find Information Response:")
                offset_data = 1
                while offset_data + 2 + uuid_len <= len(att_data):
                    handle = struct.unpack('<H', att_data[offset_data:offset_data+2])[0]
                    uuid = att_data[offset_data+2:offset_data+2+uuid_len]
                    uuid_str = self.format_uuid(uuid)
                    print(f"    Handle {handle:04x}: {uuid_str}")
                    offset_data += 2 + uuid_len

        elif att_opcode == 0x12:  # Write Request
            if len(att_data) >= 2:
                handle = struct.unpack('<H', att_data[0:2])[0]
                value = att_data[2:]
                print(f"[{num}] {direction} Write Request to handle {handle:04x}: {value.hex()} ({self.try_decode(value)})")

        elif att_opcode == 0x52:  # Write Command
            if len(att_data) >= 2:
                handle = struct.unpack('<H', att_data[0:2])[0]
                value = att_data[2:]
                print(f"[{num}] {direction} Write Command to handle {handle:04x}: {value.hex()} ({self.try_decode(value)})")

        elif att_opcode == 0x13:  # Write Response
            print(f"[{num}] {direction} Write Response")

        elif att_opcode == 0x1B:  # Handle Value Notification
            if len(att_data) >= 2:
                handle = struct.unpack('<H', att_data[0:2])[0]
                value = att_data[2:]
                print(f"[{num}] {direction} Notification from handle {handle:04x}: {value.hex()} ({self.try_decode(value)})")

        elif att_opcode == 0x1D:  # Handle Value Indication
            if len(att_data) >= 2:
                handle = struct.unpack('<H', att_data[0:2])[0]
                value = att_data[2:]
                print(f"[{num}] {direction} Indication from handle {handle:04x}: {value.hex()} ({self.try_decode(value)})")

    def format_uuid(self, uuid_bytes):
        """Format UUID bytes into standard string"""
        if len(uuid_bytes) == 2:
            return f"{struct.unpack('<H', uuid_bytes)[0]:04x}"
        elif len(uuid_bytes) == 16:
            # Convert to standard UUID format
            uuid_hex = uuid_bytes.hex()
            return f"{uuid_hex[0:8]}-{uuid_hex[8:12]}-{uuid_hex[12:16]}-{uuid_hex[16:20]}-{uuid_hex[20:32]}"
        else:
            return uuid_bytes.hex()

    def try_decode(self, data):
        """Try to decode data as ASCII string"""
        try:
            decoded = data.decode('ascii')
            if all(c.isprintable() or c.isspace() for c in decoded):
                return f'"{decoded}"'
        except:
            pass
        return ""

    def print_summary(self):
        """Print summary of discovered services and characteristics"""
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        if self.device_address:
            print(f"\nDevice Address: {self.device_address}")

        if self.services:
            print(f"\nDiscovered Services ({len(self.services)}):")
            for uuid, handles in sorted(self.services.items()):
                print(f"  {uuid}:")
                for start, end in handles:
                    print(f"    Handles: {start:04x} - {end:04x}")

        if self.characteristics:
            print(f"\nCharacteristic Values ({len(self.characteristics)}):")
            for handle, value in sorted(self.characteristics.items()):
                print(f"  Handle {handle:04x}: {value.hex()}")

if __name__ == '__main__':
    parser = BtsnoopParser('btsnoop_hci.log')
    parser.parse()
