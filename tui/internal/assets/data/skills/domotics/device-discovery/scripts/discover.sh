#!/usr/bin/env bash
# Dexter — IoT Device Discovery
# Usage: discover.sh [subnet] [--full] [--force] [--no-arp-scan]
set -euo pipefail

FULL_SCAN=false
FORCE_NON_LOCAL=false
NO_ARP_SCAN=false
SUBNET=""

# ─── Colors ───────────────────────────────────────────────────────────────────
GREEN='\033[92m'; YELLOW='\033[93m'; CYAN='\033[94m'; RED='\033[91m'; BOLD='\033[1m'; RESET='\033[0m'
info()    { echo -e "${CYAN}[Dexter]${RESET} $*"; }
success() { echo -e "${GREEN}  ✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}  ⚠${RESET} $*"; }

# ─── Parse args ───────────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --full)         FULL_SCAN=true ;;
    --force)        FORCE_NON_LOCAL=true ;;
    --no-arp-scan)  NO_ARP_SCAN=true ;;
    --*)            echo "Unknown flag: $arg"; exit 1 ;;
    *)              SUBNET="$arg" ;;
  esac
done

# ─── Local subnet check ───────────────────────────────────────────────────────
is_local_subnet() {
  local subnet="$1"
  local ip="${subnet%%/*}"  # strip CIDR
  [[ "$ip" =~ ^192\.168\. ]] && return 0
  [[ "$ip" =~ ^10\. ]] && return 0
  [[ "$ip" =~ ^172\.(1[6-9]|2[0-9]|3[01])\. ]] && return 0
  return 1
}

# ─── Auto-detect local subnet ────────────────────────────────────────────────
detect_subnet() {
  local iface subnet

  # Try ip route first (Linux)
  if command -v ip &>/dev/null; then
    subnet=$(ip route | grep -E "^(192\.168|10\.|172\.(1[6-9]|2[0-9]|3[01]))\." | awk '{print $1}' | head -1)
    [[ -n "$subnet" ]] && echo "$subnet" && return
  fi

  # Try ifconfig (macOS / older Linux)
  if command -v ifconfig &>/dev/null; then
    local ip mask
    ip=$(ifconfig | grep "inet " | grep -v "127.0.0.1" | grep -E "(192\.168|10\.|172\.)" | awk '{print $2}' | head -1)
    if [[ -n "$ip" ]]; then
      # Assume /24 for simplicity
      echo "${ip%.*}.0/24" && return
    fi
  fi

  echo "192.168.1.0/24"  # fallback
}

# ─── Known IoT ports ──────────────────────────────────────────────────────────
declare -A IOT_PORTS=(
  [1883]="MQTT Broker (plaintext)"
  [8883]="MQTT Broker (TLS)"
  [8123]="Home Assistant"
  [8080]="Zigbee2MQTT / generic HTTP"
  [80]="HTTP (Philips Hue / generic)"
  [443]="HTTPS (Philips Hue / generic)"
  [4343]="Philips Hue HTTPS alt"
  [5683]="CoAP (IoT sensors)"
  [9001]="MQTT WebSocket"
)

# ─── Port check ───────────────────────────────────────────────────────────────
check_port() {
  local host="$1" port="$2"
  timeout 1 bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null && echo "open" || echo "closed"
}

# ─── Pre-flight dependency check ──────────────────────────────────────────────
check_dependencies() {
  local missing=()

  if ! command -v nmap &>/dev/null; then
    missing+=("nmap")
  fi
  if ! command -v arp-scan &>/dev/null; then
    missing+=("arp-scan")
  fi

  if [[ ${#missing[@]} -gt 0 ]]; then
    warn "Missing required tools: ${missing[*]}"
    info "Install with:"
    info "  Ubuntu/Debian: sudo apt install ${missing[*]}"
    info "  macOS:         brew install ${missing[*]}"
    info "  Fedora/RHEL:   sudo dnf install ${missing[*]}"
    echo ""
    info "arp-scan requires root/sudo privileges to run."
    info "You can still run with --no-arp-scan to skip that phase."
  fi
}

# ─── Main ─────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}=== Dexter Device Discovery ===${RESET}"

# Pre-flight checks
check_dependencies

# Resolve subnet
if [[ -z "$SUBNET" ]]; then
  SUBNET=$(detect_subnet)
  info "Auto-detected subnet: $SUBNET"
else
  info "Using subnet: $SUBNET"
fi

# Safety check for non-local ranges
if ! is_local_subnet "$SUBNET"; then
  warn "WARNING: '$SUBNET' is NOT a local subnet."
  warn "Scanning external networks without authorization is illegal in most jurisdictions."
  if [[ "$FORCE_NON_LOCAL" != true ]]; then
    echo ""
    echo -e "${YELLOW}  To scan this range anyway, re-run with --force${RESET}"
    echo -e "${YELLOW}  Only do this if you own or have written authorization to test this network.${RESET}"
    exit 1
  fi
  warn "Proceeding with --force on non-local range. You confirmed authorization."
fi

echo ""
DISCOVERED=()
SERVICE_COUNT=0

# ─── Phase 1: ARP scan (fast, layer 2) ───────────────────────────────────────
if [[ "$NO_ARP_SCAN" == true ]]; then
  info "Skipping arp-scan phase (--no-arp-scan)"
elif command -v arp-scan &>/dev/null; then
  info "Running arp-scan (requires root for raw sockets)..."
  echo ""

  # Run with sudo if available, else try without
  if sudo -n arp-scan "$SUBNET" 2>/dev/null | grep -E "^[0-9]"; then
    ARP_OUTPUT=$(sudo arp-scan "$SUBNET" 2>/dev/null || true)
  else
    ARP_OUTPUT=$(arp-scan "$SUBNET" 2>/dev/null || echo "")
  fi

  if [[ -n "$ARP_OUTPUT" ]]; then
    while IFS= read -r line; do
      if [[ "$line" =~ ^([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)[[:space:]]+([0-9a-f:]+)[[:space:]]*(.*) ]]; then
        ip="${BASH_REMATCH[1]}"
        mac="${BASH_REMATCH[2]}"
        vendor="${BASH_REMATCH[3]}"
        printf "  %-18s %-20s %s\n" "$ip" "$mac" "$vendor"
        DISCOVERED+=("$ip")
      fi
    done <<< "$ARP_OUTPUT"
  else
    warn "arp-scan returned no results — try: sudo arp-scan $SUBNET"
  fi
else
  warn "arp-scan not found — install with: sudo apt install arp-scan"
fi

# ─── Phase 2: nmap host discovery (ICMP ping sweep) ─────────────────────────
if command -v nmap &>/dev/null; then
  echo ""
  info "Running nmap host discovery..."

  NMAP_FLAGS="-sn"
  [[ "$FULL_SCAN" == true ]] && NMAP_FLAGS="-sV -T4"

  NMAP_HOSTS=$(nmap $NMAP_FLAGS "$SUBNET" 2>/dev/null | grep "Nmap scan report" | awk '{print $NF}' | tr -d '()')

  while IFS= read -r ip; do
    [[ -z "$ip" ]] && continue
    # Add if not already from arp-scan
    if ! printf '%s\n' "${DISCOVERED[@]:-}" | grep -q "^$ip$"; then
      printf "  %-18s (via nmap)\n" "$ip"
      DISCOVERED+=("$ip")
    fi
  done <<< "$NMAP_HOSTS"
else
  warn "nmap not found — install with: sudo apt install nmap"
fi

# ─── Phase 3: IoT port scan on discovered hosts ───────────────────────────────
if [[ ${#DISCOVERED[@]} -gt 0 ]]; then
  echo ""
  info "Scanning IoT ports on ${#DISCOVERED[@]} host(s)..."
  echo ""

  declare -A FOUND_SERVICES

  for ip in "${DISCOVERED[@]}"; do
    host_services=()
    for port in "${!IOT_PORTS[@]}"; do
      if [[ $(check_port "$ip" "$port") == "open" ]]; then
        service="${IOT_PORTS[$port]}"
        host_services+=("$port:$service")
        FOUND_SERVICES["$ip:$port"]="$service"
        ((SERVICE_COUNT++))
      fi
    done

    if [[ ${#host_services[@]} -gt 0 ]]; then
      echo -e "  ${BOLD}$ip${RESET}"
      for svc in "${host_services[@]}"; do
        port="${svc%%:*}"
        name="${svc#*:}"
        success "  :$port  $name"
      done
    fi
  done
else
  warn "No hosts discovered. Try: sudo arp-scan $SUBNET"
fi

# ─── nmap IoT port scan (alternative if bash /dev/tcp is unavailable) ─────────
if [[ "$FULL_SCAN" == true ]] && command -v nmap &>/dev/null; then
  echo ""
  info "Full scan: running nmap IoT port scan..."
  IOT_PORT_LIST=$(IFS=,; echo "${!IOT_PORTS[*]}")
  nmap -p "$IOT_PORT_LIST" --open -T4 "$SUBNET" 2>/dev/null | \
    grep -E "^(Nmap scan|[0-9]+/tcp)" | \
    sed 's/Nmap scan report for /\n Host: /'
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}=== Summary ===${RESET}"
echo "  Subnet scanned: $SUBNET"
echo "  Hosts found:    ${#DISCOVERED[@]}"
echo "  IoT services:   $SERVICE_COUNT"
echo ""

if [[ $SERVICE_COUNT -gt 0 ]]; then
  echo "  Detected services:"
  for key in "${!FOUND_SERVICES[@]}"; do
    ip="${key%%:*}"
    port="${key#*:}"
    svc="${FOUND_SERVICES[$key]}"
    printf "    %-18s :%-6s %s\n" "$ip" "$port" "$svc"
  done
  echo ""
  echo "  Next steps:"
  [[ "${FOUND_SERVICES[*]:-}" == *"Home Assistant"* ]] && echo "  • Home Assistant: set HASS_URL + HASS_TOKEN, use domotics/home-assistant skill"
  [[ "${FOUND_SERVICES[*]:-}" == *"MQTT"* ]] && echo "  • MQTT: set MQTT_HOST, use domotics/mqtt skill"
  [[ "${FOUND_SERVICES[*]:-}" == *"Philips Hue"* ]] && echo "  • Philips Hue: set HUE_BRIDGE_IP + HUE_API_KEY, use domotics/philips-hue skill"
fi
