---
name: philips-hue
description: >
  Control Philips Hue lights via the local bridge REST API.
  Turn lights on/off, change color, brightness, color temperature, and scenes.
  No cloud account required — purely local API.
  Trigger: "philips hue", "hue", "luces hue", "bombillas", "lights", "encender luz",
  "apagar luz", "color de luz", "brillo", "escena hue", "hue bridge".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Philips Hue

Controls Hue lights via the local bridge API (v2). No internet required.

## Setup

```bash
export HUE_BRIDGE_IP="192.168.1.10"    # Hue bridge IP (find with device-discovery)
export HUE_API_KEY="your-api-key"       # Create with: python3 hue.py register
```

### Get API Key

```bash
# 1. Press the physical button on your Hue bridge
# 2. Run within 30 seconds:
python3 skills/domotics/philips-hue/scripts/hue.py register
# → Prints your HUE_API_KEY
```

## Usage

```bash
# List all lights
python3 skills/domotics/philips-hue/scripts/hue.py lights

# Turn on/off
python3 skills/domotics/philips-hue/scripts/hue.py on 1
python3 skills/domotics/philips-hue/scripts/hue.py off 1
python3 skills/domotics/philips-hue/scripts/hue.py on all

# Set brightness (0-254)
python3 skills/domotics/philips-hue/scripts/hue.py brightness 1 128

# Set color temperature (Kelvin: 2000K warm → 6500K cool)
python3 skills/domotics/philips-hue/scripts/hue.py colortemp 1 4000

# Set RGB color
python3 skills/domotics/philips-hue/scripts/hue.py color 1 255 128 0

# Set a scene in a room
python3 skills/domotics/philips-hue/scripts/hue.py scenes
python3 skills/domotics/philips-hue/scripts/hue.py scene "Living room" "Relax"

# List rooms/groups
python3 skills/domotics/philips-hue/scripts/hue.py groups
```

## Color Reference

| Scene | Color temp (K) | Mood |
|-------|---------------|------|
| Candle | 2000 | Very warm |
| Warm white | 2700 | Cozy |
| Neutral | 4000 | Work |
| Cool white | 6000 | Alert |
| Daylight | 6500 | Maximum |

## Notes

- Light IDs are integers (get them from `lights` command)
- Bridge API: `http://{bridge_ip}/api/{key}/lights`
- For colored bulbs only: `color` command requires Hue Color or Ambiance bulb
- `all` is a special target that controls all lights
