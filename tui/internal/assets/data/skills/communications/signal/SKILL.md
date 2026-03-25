---
name: signal
description: >
  Send messages and media via Signal CLI. List linked devices.
  Requires signal-cli installed and a registered number.
  Trigger: "signal", "send signal", "mensaje signal", "signal message".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# Signal

Interacts with Signal via [signal-cli](https://github.com/AsamK/signal-cli) to send text messages, media attachments, and inspect linked devices.

## Setup

1. Install signal-cli — see https://github.com/AsamK/signal-cli/releases
2. Register or link your number:
   ```bash
   signal-cli -u +1234567890 register
   signal-cli -u +1234567890 verify 123456
   ```
3. Export your number and an optional allowlist:

```bash
export SIGNAL_NUMBER="+1234567890"                        # your registered sender number
export SIGNAL_ALLOWLIST="+0987654321,+1122334455"         # comma-separated; omit to allow any
```

## Usage

```bash
# Send a text message
python3 skills/communications/signal/scripts/send.py send "+0987654321" "Hello from Dexter!"

# Send a media attachment (image, video, document)
python3 skills/communications/signal/scripts/send.py send-media "+0987654321" /path/to/photo.jpg

# Send media with an optional caption
python3 skills/communications/signal/scripts/send.py send-media "+0987654321" /path/to/doc.pdf --caption "Q3 Report"

# List linked devices
python3 skills/communications/signal/scripts/send.py status
```

## Notes

- `SIGNAL_NUMBER` — required. The number registered with signal-cli (E.164 format, e.g. `+1234567890`).
- `SIGNAL_ALLOWLIST` — optional. Comma-separated E.164 numbers. If set, the script refuses to send to any number not in the list and prints a security warning.
- `signal-cli` must be on `$PATH` or at `/usr/local/bin/signal-cli`.
- signal-cli runs in foreground mode (`--output=json`); no daemon required.
- Attachments are passed via `--attachment`. Multiple attachments are not supported in a single call here; run the command multiple times.
