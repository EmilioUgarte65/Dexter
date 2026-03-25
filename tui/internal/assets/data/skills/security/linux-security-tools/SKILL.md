---
name: linux-security-tools
description: >
  Guide for using Linux security and network discovery tools. Reference-only — documents nmap, arp-scan, netstat, ss, lynis, and more.
  Trigger: "nmap", "arp-scan", "escanear red", "descubrir dispositivos", "network scan", "security scan", "puertos abiertos", "open ports", "lynis".
license: Apache-2.0
metadata:
  author: dexter
  version: "1.0"
  source: dexter
allowed-tools: Bash
---

# Linux Security Tools

Reference guide for network and system security tools. For IoT/domotics device discovery, use the `domotics/device-discovery` skill instead.

> **IMPORTANT**: Only scan networks you own or have explicit authorization to test. Unauthorized scanning is illegal in most jurisdictions.

## Installation

```bash
# Debian/Ubuntu
sudo apt install nmap arp-scan netstat-nat lynis nikto

# Arch
sudo pacman -S nmap arp-scan lynis

# macOS (Homebrew)
brew install nmap arp-scan lynis
```

## Network Discovery

### nmap — Port Scanner

```bash
# Discover hosts on local network
nmap -sn 192.168.1.0/24

# Scan specific host (common ports)
nmap -sV 192.168.1.100

# Scan top 1000 ports with OS detection
nmap -A 192.168.1.100

# Scan specific ports
nmap -p 22,80,443,8123,1883 192.168.1.0/24

# Fast scan of local network (IoT discovery)
nmap -T4 -F 192.168.1.0/24
```

### arp-scan — Layer 2 Discovery

```bash
# Scan local network (requires root or cap_net_raw)
sudo arp-scan --localnet

# Scan specific subnet
sudo arp-scan 192.168.1.0/24

# Identify manufacturer by MAC
sudo arp-scan --localnet | grep -i "philips\|espressif\|raspberry\|tuya"
```

### Common IoT Ports

| Port | Protocol | Device |
|------|----------|--------|
| 1883 | MQTT | Broker (unencrypted) |
| 8883 | MQTT/TLS | Broker (encrypted) |
| 8123 | HTTP | Home Assistant |
| 8080 | HTTP | Zigbee2MQTT |
| 80/443 | HTTP/HTTPS | Philips Hue Bridge |
| 5683 | CoAP | IoT devices |
| 9100 | raw | Printers |

## Port & Connection Analysis

```bash
# Show all listening ports
ss -tlnp

# Show established connections
ss -tnp state established

# Check what's using a specific port
ss -tlnp | grep :8123

# Legacy: netstat
netstat -tlnp
```

## System Hardening Audit

### Lynis — System Auditor

```bash
# Run full system audit (requires root for full results)
sudo lynis audit system

# Quick audit (no root)
lynis audit system --quick

# Check specific category
lynis audit system --tests-from-group firewall
```

### Key areas Lynis checks:
- Authentication (SSH, PAM, sudo)
- File permissions
- Firewall (iptables/ufw/nftables)
- Kernel hardening (sysctl)
- Installed software vulnerabilities
- User account security

## Firewall

```bash
# Check UFW status
sudo ufw status verbose

# Allow specific port
sudo ufw allow 8123/tcp

# Block external access to MQTT (keep local only)
sudo ufw deny in on eth0 to any port 1883
sudo ufw allow in on lo to any port 1883

# Check iptables rules
sudo iptables -L -n -v
```

## SSH Hardening Quick Reference

```bash
# Disable root login + enforce key auth
sudo sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart sshd

# Check who's logged in
who
w
last | head -20
```

## Notes

- Always use `--dry-run` or preview flags before making changes
- For production Ubuntu server: run `lynis audit system` monthly
- MQTT on port 1883 is unencrypted — restrict to localhost or use TLS (8883)
- Home Assistant should NOT be exposed to internet without VPN or Cloudflare Tunnel
