#!/usr/bin/env python3
"""
Dexter — MQTT publish/subscribe client.
Uses paho-mqtt if available, falls back to mosquitto CLI tools.

Usage:
  mqtt.py publish <topic> <payload> [--qos 0|1|2] [--retain]
  mqtt.py subscribe <topic> [--count N] [--timeout N]
"""

import sys
import os
import json
import argparse
import subprocess
import shutil
from typing import Optional

# ─── Config from env ──────────────────────────────────────────────────────────

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USER = os.environ.get("MQTT_USER", "")
MQTT_PASS = os.environ.get("MQTT_PASS", "")
MQTT_TLS  = os.environ.get("MQTT_TLS", "false").lower() == "true"
MQTT_CLIENT_ID = os.environ.get("MQTT_CLIENT_ID", "dexter-mqtt")


def check_config():
    if not os.environ.get("MQTT_HOST"):
        print("Warning: MQTT_HOST not set, using 'localhost'", file=sys.stderr)


# ─── paho-mqtt backend ────────────────────────────────────────────────────────

def _paho_publish(topic: str, payload: str, qos: int = 0, retain: bool = False):
    import paho.mqtt.publish as publish

    auth = {"username": MQTT_USER, "password": MQTT_PASS} if MQTT_USER else None
    tls = {} if MQTT_TLS else None

    publish.single(
        topic,
        payload=payload,
        qos=qos,
        retain=retain,
        hostname=MQTT_HOST,
        port=MQTT_PORT,
        auth=auth,
        tls=tls,
        client_id=MQTT_CLIENT_ID,
    )
    print(f"  Published → {topic}: {payload[:80]}{'...' if len(payload) > 80 else ''}")


def _paho_subscribe(topic: str, count: Optional[int] = None, timeout: int = 30):
    import paho.mqtt.client as mqtt

    received = [0]

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(topic)
            print(f"  Subscribed to: {topic}")
            print(f"  Waiting for messages (Ctrl+C to stop)...\n")
        else:
            print(f"  Connection failed, rc={rc}", file=sys.stderr)

    def on_message(client, userdata, msg):
        payload = msg.payload.decode("utf-8", errors="replace")
        # Try pretty-print JSON
        try:
            parsed = json.loads(payload)
            payload_display = json.dumps(parsed, indent=2)
        except json.JSONDecodeError:
            payload_display = payload

        print(f"[{msg.topic}]")
        print(f"  {payload_display}")
        print()

        received[0] += 1
        if count and received[0] >= count:
            client.disconnect()

    client = mqtt.Client(client_id=MQTT_CLIENT_ID)

    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    if MQTT_TLS:
        client.tls_set()

    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    try:
        if count:
            client.loop_start()
            import time
            elapsed = 0
            while received[0] < count and elapsed < timeout:
                time.sleep(0.1)
                elapsed += 0.1
            client.loop_stop()
        else:
            client.loop_forever()
    except KeyboardInterrupt:
        print(f"\n  Stopped. Received {received[0]} message(s).")
        client.disconnect()


# ─── mosquitto CLI backend ─────────────────────────────────────────────────────

def _mosquitto_publish(topic: str, payload: str, qos: int = 0, retain: bool = False):
    cmd = ["mosquitto_pub", "-h", MQTT_HOST, "-p", str(MQTT_PORT),
           "-t", topic, "-m", payload, "-q", str(qos)]
    if retain:
        cmd.append("--retain")
    if MQTT_USER:
        cmd += ["-u", MQTT_USER, "-P", MQTT_PASS]
    if MQTT_TLS:
        cmd += ["--tls-version", "tlsv1.2"]

    subprocess.run(cmd, check=True)
    print(f"  Published → {topic}: {payload[:80]}{'...' if len(payload) > 80 else ''}")


def _mosquitto_subscribe(topic: str, count: Optional[int] = None, timeout: int = 30):
    cmd = ["mosquitto_sub", "-h", MQTT_HOST, "-p", str(MQTT_PORT), "-t", topic]
    if MQTT_USER:
        cmd += ["-u", MQTT_USER, "-P", MQTT_PASS]
    if MQTT_TLS:
        cmd += ["--tls-version", "tlsv1.2"]
    if count:
        cmd += ["-C", str(count)]

    print(f"  Subscribed to: {topic}")
    print(f"  Waiting for messages (Ctrl+C to stop)...\n")
    try:
        subprocess.run(cmd, check=True, timeout=timeout if count else None)
    except KeyboardInterrupt:
        print("\n  Stopped.")
    except subprocess.TimeoutExpired:
        print("\n  Timeout reached.")


# ─── Backend selection ────────────────────────────────────────────────────────

def _has_paho() -> bool:
    try:
        import paho.mqtt.client
        return True
    except ImportError:
        return False


def _has_mosquitto_pub() -> bool:
    return shutil.which("mosquitto_pub") is not None


def publish(topic: str, payload: str, qos: int = 0, retain: bool = False):
    if _has_paho():
        _paho_publish(topic, payload, qos, retain)
    elif _has_mosquitto_pub():
        print("  (using mosquitto_pub CLI — install paho-mqtt for better support)")
        _mosquitto_publish(topic, payload, qos, retain)
    else:
        print("Error: no MQTT backend available.", file=sys.stderr)
        print("Install: pip3 install paho-mqtt  OR  sudo apt install mosquitto-clients", file=sys.stderr)
        sys.exit(1)


def subscribe(topic: str, count: Optional[int] = None, timeout: int = 30):
    if _has_paho():
        _paho_subscribe(topic, count, timeout)
    elif shutil.which("mosquitto_sub"):
        print("  (using mosquitto_sub CLI — install paho-mqtt for better support)")
        _mosquitto_subscribe(topic, count, timeout)
    else:
        print("Error: no MQTT backend available.", file=sys.stderr)
        print("Install: pip3 install paho-mqtt  OR  sudo apt install mosquitto-clients", file=sys.stderr)
        sys.exit(1)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter MQTT Client")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pub = sub.add_parser("publish", help="Publish a message to a topic")
    p_pub.add_argument("topic")
    p_pub.add_argument("payload")
    p_pub.add_argument("--qos", type=int, choices=[0, 1, 2], default=0)
    p_pub.add_argument("--retain", action="store_true")

    p_sub = sub.add_parser("subscribe", help="Subscribe to a topic")
    p_sub.add_argument("topic")
    p_sub.add_argument("--count", type=int, help="Stop after N messages")
    p_sub.add_argument("--timeout", type=int, default=30, help="Timeout in seconds (with --count)")

    args = parser.parse_args()
    check_config()

    print(f"\n  MQTT broker: {MQTT_HOST}:{MQTT_PORT}{' (TLS)' if MQTT_TLS else ''}")

    if args.command == "publish":
        publish(args.topic, args.payload, qos=args.qos, retain=args.retain)
    elif args.command == "subscribe":
        subscribe(args.topic, count=getattr(args, "count", None),
                  timeout=getattr(args, "timeout", 30))


if __name__ == "__main__":
    main()
