"""Constants for the Grundfos Bluetooth integration."""

DOMAIN = "grundfos_bluetooth"

# BLE Service UUIDs (from btsnoop analysis)
GRUNDFOS_SERVICE_UUID_1 = "9d41001835d6f4adad60e7bd8dc491c0"  # Custom service 1
GRUNDFOS_SERVICE_UUID_2 = "9d41001935d6f4adad60e7bd8dc491c0"  # Custom service 2

# Characteristic handles (from btsnoop analysis)
# Handle 0x0016 is the main communication characteristic
GRUNDFOS_CHAR_HANDLE = 0x0016

# Configuration
CONF_ADDRESS = "address"
CONF_NAME = "name"
CONF_SCAN_INTERVAL = "scan_interval"

# Default values
DEFAULT_NAME = "Grundfos Pump"
DEFAULT_SCAN_INTERVAL = 60  # seconds

# Device info patterns (from btsnoop)
# Model: SCALA1 3-45 1x230V 50Hz
# Serial pattern: 99530420
# Firmware pattern: 99545258V01.00.02.000001
