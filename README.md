# Grundfos Bluetooth Integration for Home Assistant

![GitHub release (latest by date)](https://img.shields.io/github/v/release/tastyfrankfurt/grundfos-bluetooth)
![GitHub](https://img.shields.io/github/license/tastyfrankfurt/grundfos-bluetooth)

This custom component allows you to integrate Grundfos water pumps (only tested with SCALA series) with Home Assistant via Bluetooth Low Energy (BLE).

## Features

- Monitor pump status and device information
- Read pump model, serial number, and firmware version
- Control pump operations (work in progress)
- Native Home Assistant integration with config flow

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tastyfrankfurt&repository=grundfos-bluetooth)

1. Ensure that [HACS](https://hacs.xyz/) is installed.
2. Go to HACS > Integrations.
3. Click on the three dots in the top right corner and select "Custom repositories".
4. Add the repository URL: `https://github.com/tastyfrankfurt/grundfos-bluetooth` and select "Integration".
5. Find "Grundfos Bluetooth" in the list and click "Install".
6. Restart Home Assistant after installation.

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
- Grundfos SCALA1 1 pump

Other Grundfos pumps with Bluetooth may work but have not been tested.

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

Contributions are welcome! If you have a different Grundfos pump model, please open an issue or pull request.

## License

This project is licensed under the MIT License - see below for details.

```
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Grundfos is a trademark of Grundfos Holding A/S.

## Credits

Protocol reverse-engineered from btsnoop HCI captures of the official Grundfos app.
