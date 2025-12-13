# Development Guide

This project uses `uv` for fast Python package management.

## Setup

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Or on macOS:
```bash
brew install uv
```

### 2. Create a virtual environment and install dependencies

```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"
```

### 3. Quick install (without virtual environment)

```bash
uv pip install bleak
```

## Analyzing Bluetooth Captures

The project includes a btsnoop parser for reverse-engineering the protocol:

```bash
python3 parse_btsnoop.py
```

This will parse `btsnoop_hci.log` in the current directory and show:
- Discovered services and characteristics
- Command/response sequences
- Decoded device information

## Testing the Integration

### 1. Copy to Home Assistant

```bash
# Copy the integration to your Home Assistant config directory
cp -r custom_components/grundfos_bluetooth ~/.homeassistant/custom_components/
```

### 2. Restart Home Assistant

```bash
# If using Home Assistant Core
hass --script check_config
systemctl restart home-assistant
```

### 3. Add the Integration

1. Go to Settings → Devices & Services
2. Click "+ Add Integration"
3. Search for "Grundfos Bluetooth"
4. Follow the setup flow

## Development Workflow

### Running Linters

```bash
# Format code with black
uv run black custom_components/

# Lint with ruff
uv run ruff check custom_components/

# Type checking with mypy
uv run mypy custom_components/
```

### Testing Protocol Commands

You can test individual commands by modifying and running the btsnoop parser:

```python
# Example: Test a specific command
import asyncio
from bleak import BleakClient

async def test_command():
    async with BleakClient("AA:BB:CC:DD:EE:FF") as client:
        # Write command
        await client.write_gatt_char(
            "characteristic-uuid",
            bytes.fromhex("2705e7f80701015238")
        )
        await asyncio.sleep(1)

asyncio.run(test_command())
```

## Project Structure

```
.
├── custom_components/
│   └── grundfos_bluetooth/
│       ├── __init__.py          # Integration setup
│       ├── manifest.json        # Integration metadata
│       ├── const.py             # Constants and UUIDs
│       ├── config_flow.py       # Config UI flow
│       ├── coordinator.py       # Data update coordinator
│       ├── grundfos_device.py   # BLE device client
│       ├── sensor.py            # Sensor entities
│       ├── switch.py            # Switch entities
│       └── strings.json         # Localization strings
├── parse_btsnoop.py             # Protocol analyzer
├── pyproject.toml               # Project configuration
├── README.md                    # User documentation
└── DEVELOPMENT.md               # This file
```

## Reverse Engineering New Features

1. **Capture Bluetooth traffic**:
   - Enable Bluetooth HCI snoop log on Android (Developer Options)
   - Use the official Grundfos app
   - Perform the action you want to reverse engineer
   - Pull the btsnoop log: `adb pull /data/misc/bluetooth/logs/btsnoop_hci.log`

2. **Analyze the capture**:
   ```bash
   python3 parse_btsnoop.py
   ```

3. **Identify patterns**:
   - Look for repeated command sequences
   - Note the characteristic handle being used
   - Extract hex data for commands

4. **Implement in code**:
   - Add command constants to `grundfos_device.py`
   - Create appropriate entity in sensor.py or switch.py
   - Test with your pump

## Debugging

Enable debug logging in Home Assistant `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.grundfos_bluetooth: debug
    bleak: debug
```

Then check logs:
```bash
tail -f ~/.homeassistant/home-assistant.log | grep grundfos
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with a real Grundfos pump if possible
5. Submit a pull request

## Resources

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Bleak Documentation](https://bleak.readthedocs.io/)
- [Bluetooth Core Specification](https://www.bluetooth.com/specifications/specs/)
