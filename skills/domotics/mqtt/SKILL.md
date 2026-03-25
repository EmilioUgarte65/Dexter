---
name: mqtt
description: >
  Publish and subscribe to MQTT topics. Works with any MQTT broker (Mosquitto, EMQX, HiveMQ).
  Supports both plaintext (1883) and TLS (8883) connections.
  Trigger: "mqtt", "publicar mqtt", "subscribe mqtt", "broker", "topic", "mosquitto",
  "enviar mensaje mqtt", "escuchar mqtt", "publish", "subscribe".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# MQTT

Publish and subscribe to MQTT topics. Uses `paho-mqtt` if available, falls back to `mosquitto_pub`/`mosquitto_sub` CLI.

## Setup

```bash
export MQTT_HOST="192.168.1.10"    # broker IP or hostname
export MQTT_PORT="1883"            # 1883 (plain) or 8883 (TLS)
export MQTT_USER="myuser"          # optional
export MQTT_PASS="mypassword"      # optional
export MQTT_TLS="false"            # set "true" for port 8883
```

## Install paho-mqtt (recommended)

```bash
pip3 install paho-mqtt
```

## Usage

```bash
# Publish a message
python3 skills/domotics/mqtt/scripts/mqtt.py publish home/living_room/light "ON"
python3 skills/domotics/mqtt/scripts/mqtt.py publish home/thermostat/setpoint "22.5"

# Publish JSON payload
python3 skills/domotics/mqtt/scripts/mqtt.py publish zigbee2mqtt/light/set '{"state":"ON","brightness":200}'

# Subscribe to a topic (listens until Ctrl+C)
python3 skills/domotics/mqtt/scripts/mqtt.py subscribe home/#

# Subscribe and capture N messages then exit
python3 skills/domotics/mqtt/scripts/mqtt.py subscribe home/sensors/# --count 5

# Send Home Assistant MQTT discovery
python3 skills/domotics/mqtt/scripts/mqtt.py publish homeassistant/light/mylight/config \
  '{"name":"My Light","command_topic":"home/mylight/set","state_topic":"home/mylight/state"}'
```

## Common Topics

| Topic pattern | Use case |
|--------------|---------|
| `home/#` | All home messages |
| `zigbee2mqtt/{device}` | Zigbee device state |
| `zigbee2mqtt/{device}/set` | Control Zigbee device |
| `homeassistant/#` | HA MQTT discovery |
| `shellies/#` | Shelly device state |

## Notes

- Wildcard `#` = all subtopics, `+` = single level wildcard
- QoS 0 = fire and forget, QoS 1 = at least once, QoS 2 = exactly once
- For TLS: set MQTT_PORT=8883 and MQTT_TLS=true
