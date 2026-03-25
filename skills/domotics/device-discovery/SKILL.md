---
name: device-discovery
description: >
  Discover IoT devices on the local network using nmap and arp-scan.
  Identifies Home Assistant, MQTT brokers, Philips Hue bridges, Zigbee2MQTT,
  and other smart home devices by IP, MAC, and open ports.
  Trigger: "qué dispositivos tengo", "descubrir dispositivos", "escanear red", "device discovery",
  "what devices are on my network", "find iot devices", "network scan", "IoT scan".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Device Discovery

Scans the local network to find IoT devices and identify their services.

## Requirements

```bash
# Ubuntu/Debian
sudo apt install nmap arp-scan

# macOS
brew install nmap arp-scan

# Arch
sudo pacman -S nmap arp-scan
```

## Usage

```bash
# Auto-detect local subnet and scan
bash skills/domotics/device-discovery/scripts/discover.sh

# Scan a specific subnet
bash skills/domotics/device-discovery/scripts/discover.sh 192.168.1.0/24

# Full scan (slower, more detailed)
bash skills/domotics/device-discovery/scripts/discover.sh --full
```

## Example Output

```
=== Dexter Device Discovery ===
Subnet: 192.168.1.0/24

Scanning with arp-scan...
192.168.1.1    dc:a6:32:xx:xx:xx   Raspberry Pi Foundation
192.168.1.10   00:17:88:xx:xx:xx   Philips Lighting BV
192.168.1.20   b8:27:eb:xx:xx:xx   Raspberry Pi Foundation
192.168.1.30   cc:50:e3:xx:xx:xx   Espressif Inc (ESP32/Tuya)

Scanning IoT ports...
192.168.1.1  :8123  ✓  Home Assistant
192.168.1.1  :1883  ✓  MQTT Broker
192.168.1.10 :80    ✓  Philips Hue Bridge
192.168.1.20 :8080  ✓  Zigbee2MQTT

=== Summary ===
Found 4 devices, 4 IoT services identified.
```

## Known IoT Ports

| Port | Service | Device |
|------|---------|--------|
| 1883 | MQTT | Broker (unencrypted) |
| 8883 | MQTT/TLS | Broker (encrypted) |
| 8123 | HTTP | Home Assistant |
| 8080 | HTTP | Zigbee2MQTT |
| 80/443 | HTTP/HTTPS | Philips Hue Bridge |
| 5683 | CoAP | IoT sensors |
| 4343 | HTTPS | Philips Hue alt |

## Safety

- Only scans local subnets (192.168.x.x, 10.x.x.x, 172.16-31.x.x) by default
- Non-local ranges require explicit `--force` flag and user confirmation
- Does NOT send any data externally — purely local network scan
