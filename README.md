# Grundfos Bluetooth Integration for Home Assistant

This custom component allows you to integrate Grundfos water pumps (like the SCALA series) with Home Assistant via Bluetooth Low Energy (BLE).

## Features

- Monitor pump status and device information
- Read pump model, serial number, and firmware version
- Control pump operations (work in progress)
- Native Home Assistant integration with config flow

## Installation

### HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Install "Grundfos Bluetooth" through HACS
3. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/grundfos_bluetooth` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "Grundfos Bluetooth"
4. Select your pump from the discovered devices or enter the Bluetooth address manually

## Supported Devices

This integration has been tested with:
- Grundfos SCALA1 3-45 pumps

Other Grundfos pumps with Bluetooth may work but have not been tested.

## Protocol Reverse Engineering

This integration was built by reverse-engineering the Bluetooth protocol using btsnoop HCI logs. The protocol uses custom Grundfos service UUIDs:

- Service 1: `9d41001835d6f4adad60e7bd8dc491c0`
- Service 2: `9d41001935d6f4adad60e7bd8dc491c0`

Commands are sent via write operations on characteristic handle `0x0016`, and responses are received through notifications.

### Command Format

Commands follow this general structure:
- Header: `0x27`
- Length: 1 byte
- Command type: varies
- Payload: varies
- Checksum: CRC16 (last 2 bytes)

### Response Format

Responses follow this structure:
- Header: `0x24`
- Length: 1 byte
- Response markers: `0xf8 0xe7`
- Data: varies
- Checksum: CRC16 (last 2 bytes)

## Development

### Analyzing Bluetooth Captures

A btsnoop parser script is included (`parse_btsnoop.py`) to help reverse-engineer the protocol:

```bash
python3 parse_btsnoop.py
```

This will parse `btsnoop_hci.log` and display:
- Discovered BLE services and characteristics
- Command/response sequences
- Decoded device information

### Adding New Features

To add support for new pump features:

1. Capture a btsnoop log while using the official Grundfos app
2. Run the parser to identify new commands
3. Add command definitions to `grundfos_device.py`
4. Create corresponding sensors/switches in the appropriate platform files

## Known Limitations

- Pump control commands need further reverse engineering
- Some sensor readings are not yet decoded
- Requires Bluetooth adapter on Home Assistant host

## Troubleshooting

### Device not discovered

- Ensure the pump is powered on and within Bluetooth range
- Check that your Home Assistant host has a working Bluetooth adapter
- Try entering the Bluetooth MAC address manually

### Connection issues

- The pump may only allow one Bluetooth connection at a time
- Close the official Grundfos app if it's running
- Restart the Home Assistant Bluetooth integration

### Enable debug logging

Add to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.grundfos_bluetooth: debug
```

## Contributing

Contributions are welcome! If you have a different Grundfos pump model and can provide btsnoop logs, please open an issue or pull request.

## License

This project is provided as-is for educational and personal use. Grundfos is a trademark of Grundfos Holding A/S.

## Credits

Protocol reverse-engineered from btsnoop HCI captures of the official Grundfos app.
