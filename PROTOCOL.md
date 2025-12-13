# Grundfos Bluetooth Protocol Documentation

This document describes the Bluetooth Low Energy protocol used by Grundfos SCALA water pumps, as reverse-engineered from btsnoop HCI captures.

## BLE Service UUIDs

- **Service 1**: `9d41001835d6f4adad60e7bd8dc491c0`
- **Service 2**: `9d41001935d6f4adad60e7bd8dc491c0`

## Communication Characteristic

- **Main Handle**: `0x0016`
- **Properties**: Write + Notify
- Used for bidirectional communication (commands and responses)

## Message Format

### Command Format (Host → Pump)

Commands typically follow this structure:

```
[Header] [Length] [Type] [Subtype] [Payload...] [CRC16]
```

**Common Headers:**
- `0x27` - Command header

**Examples from btsnoop:**

1. **Device Info Request**:
   ```
   27 05 e7 f8 07 01 01 52 38
   ├─ Header (0x27)
   ├─ Length (0x05)
   ├─ Command type (e7 f8)
   ├─ Subcommand (07 01)
   ├─ Parameter (01)
   └─ CRC16 (52 38)
   ```

2. **Status Request**:
   ```
   27 07 e7 f8 0a 03 5e 00 04 4c b9
   ├─ Header (0x27)
   ├─ Length (0x07)
   ├─ Command type (e7 f8)
   ├─ Subcommand (0a 03)
   ├─ Parameters (5e 00 04)
   └─ CRC16 (4c b9)
   ```

### Response Format (Pump → Host)

Responses come as notifications:

```
[Header] [Length] [Marker] [Payload...] [CRC16]
```

**Response Header:**
- `0x24` - Response header

**Response Markers:**
- `f8 e7` - Common response marker

**Examples:**

1. **Device Model Response**:
   ```
   24 1d f8 e7 07 19 53 43 41 4c 41 31 20 33 2d 34 35 20 31 78
   ├─ Header (0x24)
   ├─ Length (0x1d = 29 bytes)
   ├─ Marker (f8 e7)
   ├─ Subtype (07 19)
   ├─ ASCII: "SCALA1 3-45 1x"
   └─ (continues in next packet)
   ```
   Decoded: "SCALA1 3-45 1x230V 50Hz"

2. **Serial Number Response**:
   ```
   24 0d f8 e7 07 09 39 39 35 33 30 34 32 30 00 55 9e
   ├─ Header (0x24)
   ├─ Length (0x0d = 13 bytes)
   ├─ Marker (f8 e7)
   ├─ Subtype (07 09)
   ├─ ASCII: "99530420"
   └─ CRC16 (55 9e)
   ```

## Known Commands

### Device Information

| Command | Description | Example |
|---------|-------------|---------|
| `2705e7f80701015238` | Read model info | Returns "SCALA1..." |
| `2705e7f80701085238` | Read serial number | Returns "99530420" |
| `2705e7f80701095238` | Read device ID | Returns "00000815" |
| `2705e7f807010ae353` | Read model number | Returns "2405" |
| `2705e7f80701114009` | Read location | Returns "grendal" |
| `2705e7f80701325408` | Read firmware 1 | Returns "99545258V01..." |
| `2705e7f807013ad500` | Read firmware 2 | Returns "99545256V03..." |

### Status and Sensor Data

| Command | Description | Observed Data |
|---------|-------------|---------------|
| `2707e7f80a035e00044cb9` | Read status | Various status bytes |
| `2707e7f80a035b00a412a3` | Read sensor data | Multi-packet response |
| `2707e7f80a035d03e87c18` | Read detailed status | Large data packet |

### Control Commands

| Command | Description | Notes |
|---------|-------------|-------|
| `2708e7f802040094959667b8` | Unknown control | Response: ff390100 |
| `2708e7f802c4009495965400` | Unknown control | Response: 80808080 |

## Multi-Packet Responses

Long responses are split across multiple notification packets. Example:

```
Packet 1: 24 1c f8 e7 07 18 39 39 35 34 35 32 35 38 56 30 31 2e 30 30
Packet 2: 2e 30 32 2e 30 30 30 30 30 31 00 b7 92
```

Combined: "99545258V01.00.02.000001"

The packets share:
- Same subtype in first packet
- Continuation packets start directly with data (no header)
- Last packet contains CRC16

## CRC Calculation

The protocol uses CRC16 for message integrity. The exact polynomial needs to be determined through testing.

Observations:
- CRC is the last 2 bytes of each message
- Both commands and responses include CRC
- Byte order appears to be little-endian

## Data Types Observed

### Strings
- ASCII encoded
- Null-terminated (0x00)
- Examples: model, serial, firmware, location

### Numeric Values
- 32-bit integers (little-endian)
- 16-bit integers (little-endian)
- Timestamps (Unix epoch?)

### Status Flags
- Binary flags in response packets
- Exact meaning to be determined

## Timing

- Wait ~200ms between commands
- Wait ~1s for multi-part responses
- Notifications arrive asynchronously

## Connection

1. Scan for device by address or name
2. Connect to GATT server
3. Discover services and characteristics
4. Enable notifications on handle 0x0016
5. Send commands via Write (without response)
6. Receive data via notifications

## Notes for Developers

1. **Enable Notifications First**: Always enable notifications before sending commands
2. **Wait for Responses**: Some commands trigger multiple notification packets
3. **Parse Multi-Packet**: Handle responses that span multiple notification packets
4. **CRC Validation**: Implement CRC checking for message integrity
5. **Retry Logic**: Add retry for failed commands (Bluetooth can be unreliable)

## Unknown/TODO

- [ ] Exact CRC16 polynomial
- [ ] Complete command list
- [ ] Pump start/stop commands
- [ ] Speed control commands
- [ ] Pressure setpoint commands
- [ ] Alarm/error codes
- [ ] Sensor value parsing (pressure, flow, temperature)

## Capturing More Data

To extend this documentation:

1. **Enable Android Bluetooth HCI Snoop Log**:
   - Settings → Developer Options → Enable Bluetooth HCI snoop log

2. **Use Official App**: Perform actions in the Grundfos app

3. **Extract Log**:
   ```bash
   adb pull /data/misc/bluetooth/logs/btsnoop_hci.log
   ```

4. **Parse**:
   ```bash
   python3 parse_btsnoop.py
   ```

5. **Document**: Add findings to this file
