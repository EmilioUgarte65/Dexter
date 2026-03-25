---
name: home-assistant
description: >
  Control and query Home Assistant via REST API. Turn on/off devices, read sensors,
  list entities, call services, and trigger automations — all without opening the UI.
  Trigger: "home assistant", "encender", "apagar", "luces", "temperatura", "sensor",
  "automatización", "turn on", "turn off", "HA", "smart home", "domótica".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Home Assistant

Controls your Home Assistant instance via the REST API. No HA SDK required — pure HTTP.

## Setup

```bash
export HASS_URL="http://192.168.1.10:8123"   # or https://your-ha.duckdns.org
export HASS_TOKEN="eyJ0eXAiOi..."             # Long-Lived Access Token from HA profile
```

Get your token: HA → Profile → Long-Lived Access Tokens → Create Token

## Usage

```bash
# List all entities
python3 skills/domotics/home-assistant/scripts/ha.py list

# Get state of an entity
python3 skills/domotics/home-assistant/scripts/ha.py state light.living_room

# Turn on/off
python3 skills/domotics/home-assistant/scripts/ha.py turn_on light.living_room
python3 skills/domotics/home-assistant/scripts/ha.py turn_off light.living_room

# Turn on with attributes (brightness, color temp)
python3 skills/domotics/home-assistant/scripts/ha.py turn_on light.living_room --brightness 180 --color_temp 4000

# Call any HA service
python3 skills/domotics/home-assistant/scripts/ha.py call light turn_on '{"entity_id":"light.kitchen","brightness":255}'

# Filter entities by domain
python3 skills/domotics/home-assistant/scripts/ha.py list --domain light
python3 skills/domotics/home-assistant/scripts/ha.py list --domain sensor
python3 skills/domotics/home-assistant/scripts/ha.py list --domain switch

# Get all sensor readings
python3 skills/domotics/home-assistant/scripts/ha.py sensors
```

## Automation Examples

```bash
# Morning routine: turn on lights at 50% warm white
python3 ha.py turn_on light.bedroom --brightness 128 --color_temp 3000

# Check if someone is home
python3 ha.py state person.john | grep state

# Trigger an automation
python3 ha.py call automation trigger '{"entity_id":"automation.morning_routine"}'
```

## Notes

- `HASS_URL` — no trailing slash
- `HASS_TOKEN` — Long-Lived Access Token (not OAuth)
- Entity IDs follow the pattern: `domain.name` (e.g., `light.kitchen`, `sensor.temp`)
- For HTTPS with self-signed certs, set `HASS_VERIFY_SSL=false`
