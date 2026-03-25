---
name: system-monitor
description: >
  Monitor system resources: CPU, memory, disk, network, and processes.
  Uses psutil when available, falls back to /proc on Linux.
  Trigger: "system status", "cpu usage", "memory", "disk space", "network", "processes", "top processes", "monitor".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
  audited: true
allowed-tools: Bash
---

# System Monitor

Reports system resource usage. Installs `psutil` for richer cross-platform data; falls back to `/proc` filesystem on Linux.

## Optional Setup

```bash
pip install psutil   # recommended for full cross-platform support
```

## Usage

```bash
# Overall system snapshot
python3 skills/productivity/system-monitor/scripts/sysmon.py status

# CPU usage (optionally with sampling interval)
python3 skills/productivity/system-monitor/scripts/sysmon.py cpu
python3 skills/productivity/system-monitor/scripts/sysmon.py cpu --interval 2

# Memory usage
python3 skills/productivity/system-monitor/scripts/sysmon.py memory

# Disk usage
python3 skills/productivity/system-monitor/scripts/sysmon.py disk
python3 skills/productivity/system-monitor/scripts/sysmon.py disk /home

# Network stats
python3 skills/productivity/system-monitor/scripts/sysmon.py network
python3 skills/productivity/system-monitor/scripts/sysmon.py network --interface eth0

# Running processes
python3 skills/productivity/system-monitor/scripts/sysmon.py processes
python3 skills/productivity/system-monitor/scripts/sysmon.py processes --top 20
python3 skills/productivity/system-monitor/scripts/sysmon.py processes --sort mem
```

## Notes

- Without psutil, only Linux `/proc` fallback is available (limited network/process info)
- `--sort` accepts `cpu` or `mem` (default: `cpu`)
- `--interval N` — sample CPU over N seconds for more accurate reading (default: 1)
