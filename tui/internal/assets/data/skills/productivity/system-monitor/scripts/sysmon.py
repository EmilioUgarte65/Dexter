#!/usr/bin/env python3
"""
Dexter — System Monitor.
Uses psutil if available, falls back to /proc on Linux.

Usage:
  sysmon.py status
  sysmon.py cpu [--interval N]
  sysmon.py memory
  sysmon.py disk [path]
  sysmon.py network [--interface eth0]
  sysmon.py processes [--top N] [--sort cpu|mem]
"""

import sys
import os
import argparse
import time
from typing import Optional

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"

# ─── psutil detection ─────────────────────────────────────────────────────────

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


# ─── Fallback /proc helpers (Linux only) ──────────────────────────────────────

def _proc_cpu_percent(interval: float = 1.0) -> float:
    """Read CPU usage from /proc/stat with sampling interval."""
    def _read_stat():
        with open("/proc/stat") as f:
            line = f.readline()
        vals = list(map(int, line.split()[1:]))
        idle = vals[3]
        total = sum(vals)
        return idle, total

    idle1, total1 = _read_stat()
    time.sleep(interval)
    idle2, total2 = _read_stat()
    delta_idle  = idle2 - idle1
    delta_total = total2 - total1
    if delta_total == 0:
        return 0.0
    return round((1 - delta_idle / delta_total) * 100, 1)


def _proc_memory() -> dict:
    with open("/proc/meminfo") as f:
        data = {}
        for line in f:
            key, val = line.split(":")
            data[key.strip()] = int(val.split()[0]) * 1024  # kB → bytes
    total     = data.get("MemTotal", 0)
    available = data.get("MemAvailable", 0)
    used      = total - available
    return {"total": total, "available": available, "used": used, "percent": round(used / total * 100, 1) if total else 0}


def _proc_disk(path: str = "/") -> dict:
    stat = os.statvfs(path)
    total  = stat.f_blocks * stat.f_frsize
    free   = stat.f_bfree  * stat.f_frsize
    used   = total - free
    return {"total": total, "used": used, "free": free, "percent": round(used / total * 100, 1) if total else 0}


def _fmt_bytes(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _color_pct(pct: float) -> str:
    if pct >= 90:
        return RED
    if pct >= 70:
        return YELLOW
    return GREEN


# ─── Commands ─────────────────────────────────────────────────────────────────

def cmd_cpu(interval: int = 1):
    if HAS_PSUTIL:
        pct = psutil.cpu_percent(interval=interval)
        count_l = psutil.cpu_count(logical=True)
        count_p = psutil.cpu_count(logical=False)
        freq    = psutil.cpu_freq()
        print(f"\nCPU Usage:   {_color_pct(pct)}{pct:.1f}%{RESET}")
        print(f"Cores:       {count_p} physical, {count_l} logical")
        if freq:
            print(f"Frequency:   {freq.current:.0f} MHz (max: {freq.max:.0f} MHz)")
        # Per-core
        per_core = psutil.cpu_percent(percpu=True)
        print(f"\nPer-core:")
        for i, c in enumerate(per_core):
            bar = "█" * int(c / 5)
            print(f"  core {i}: {_color_pct(c)}{c:5.1f}%{RESET}  {bar}")
    else:
        pct = _proc_cpu_percent(interval)
        print(f"\nCPU Usage: {_color_pct(pct)}{pct:.1f}%{RESET}")
        try:
            with open("/proc/cpuinfo") as f:
                cores = sum(1 for l in f if l.startswith("processor"))
            print(f"Cores:     {cores} logical")
        except Exception:
            pass


def cmd_memory():
    if HAS_PSUTIL:
        vm  = psutil.virtual_memory()
        sw  = psutil.swap_memory()
        pct = vm.percent
        print(f"\nMemory")
        print(f"  Total:     {_fmt_bytes(vm.total)}")
        print(f"  Used:      {_color_pct(pct)}{_fmt_bytes(vm.used)} ({pct:.1f}%){RESET}")
        print(f"  Available: {_fmt_bytes(vm.available)}")
        print(f"  Cached:    {_fmt_bytes(getattr(vm, 'cached', 0))}")
        print(f"\nSwap")
        print(f"  Total:     {_fmt_bytes(sw.total)}")
        print(f"  Used:      {_color_pct(sw.percent)}{_fmt_bytes(sw.used)} ({sw.percent:.1f}%){RESET}")
        print(f"  Free:      {_fmt_bytes(sw.free)}")
    else:
        m = _proc_memory()
        print(f"\nMemory")
        print(f"  Total:     {_fmt_bytes(m['total'])}")
        print(f"  Used:      {_color_pct(m['percent'])}{_fmt_bytes(m['used'])} ({m['percent']:.1f}%){RESET}")
        print(f"  Available: {_fmt_bytes(m['available'])}")


def cmd_disk(path: str = "/"):
    if HAS_PSUTIL:
        partitions = psutil.disk_partitions()
        if path != "/":
            # Single path query
            usage = psutil.disk_usage(path)
            pct = usage.percent
            print(f"\nDisk: {path}")
            print(f"  Total: {_fmt_bytes(usage.total)}")
            print(f"  Used:  {_color_pct(pct)}{_fmt_bytes(usage.used)} ({pct:.1f}%){RESET}")
            print(f"  Free:  {_fmt_bytes(usage.free)}")
        else:
            print(f"\n  {'MOUNT':<25} {'TOTAL':>10} {'USED':>10} {'FREE':>10} {'USE%':>6}  FS")
            print("  " + "-" * 70)
            for p in partitions:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    pct   = usage.percent
                    print(f"  {p.mountpoint:<25} {_fmt_bytes(usage.total):>10} "
                          f"{_color_pct(pct)}{_fmt_bytes(usage.used):>10}{RESET} "
                          f"{_fmt_bytes(usage.free):>10} {_color_pct(pct)}{pct:>5.1f}%{RESET}  {p.fstype}")
                except PermissionError:
                    pass
    else:
        d = _proc_disk(path)
        pct = d["percent"]
        print(f"\nDisk: {path}")
        print(f"  Total: {_fmt_bytes(d['total'])}")
        print(f"  Used:  {_color_pct(pct)}{_fmt_bytes(d['used'])} ({pct:.1f}%){RESET}")
        print(f"  Free:  {_fmt_bytes(d['free'])}")


def cmd_network(interface: Optional[str] = None):
    if HAS_PSUTIL:
        stats = psutil.net_io_counters(pernic=True)
        if interface:
            if interface not in stats:
                print(f"{RED}Interface not found: {interface}{RESET}", file=sys.stderr)
                print(f"Available: {', '.join(stats.keys())}", file=sys.stderr)
                sys.exit(1)
            stats = {interface: stats[interface]}

        print(f"\n  {'INTERFACE':<15} {'BYTES SENT':>14} {'BYTES RECV':>14} {'PKT SENT':>10} {'PKT RECV':>10}")
        print("  " + "-" * 70)
        for iface, s in stats.items():
            print(f"  {iface:<15} {_fmt_bytes(s.bytes_sent):>14} {_fmt_bytes(s.bytes_recv):>14} {s.packets_sent:>10,} {s.packets_recv:>10,}")
    else:
        # /proc/net/dev fallback
        try:
            with open("/proc/net/dev") as f:
                lines = f.readlines()[2:]  # skip header
            print(f"\n  {'INTERFACE':<15} {'BYTES RECV':>14} {'BYTES SENT':>14}")
            print("  " + "-" * 50)
            for line in lines:
                parts = line.split()
                if not parts:
                    continue
                iface    = parts[0].rstrip(":")
                recv_b   = int(parts[1])
                sent_b   = int(parts[9])
                if interface and iface != interface:
                    continue
                print(f"  {iface:<15} {_fmt_bytes(recv_b):>14} {_fmt_bytes(sent_b):>14}")
        except FileNotFoundError:
            print(f"{RED}/proc/net/dev not found — install psutil for cross-platform support.{RESET}", file=sys.stderr)
            sys.exit(1)


def cmd_processes(top: int = 10, sort_by: str = "cpu"):
    if HAS_PSUTIL:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
        procs.sort(key=lambda x: x.get(key, 0) or 0, reverse=True)
        procs = procs[:top]

        print(f"\n  {'PID':<8} {'NAME':<30} {'CPU%':>6} {'MEM%':>6} STATUS")
        print("  " + "-" * 65)
        for p in procs:
            pid   = p.get("pid", "?")
            name  = (p.get("name") or "?")[:28]
            cpu   = p.get("cpu_percent") or 0.0
            mem   = p.get("memory_percent") or 0.0
            stat  = p.get("status", "?")
            print(f"  {pid:<8} {name:<30} {_color_pct(cpu)}{cpu:>5.1f}%{RESET} {_color_pct(mem)}{mem:>5.1f}%{RESET} {stat}")
    else:
        # /proc fallback: read /proc/[pid]/stat
        print(f"\n  {'PID':<8} {'NAME':<30} {'STATE':<10}")
        print("  " + "-" * 50)
        count = 0
        proc_dirs = sorted(
            [d for d in os.listdir("/proc") if d.isdigit()],
            key=lambda x: int(x),
        )
        for pid in proc_dirs:
            if count >= top:
                break
            try:
                with open(f"/proc/{pid}/comm") as f:
                    name = f.read().strip()
                with open(f"/proc/{pid}/status") as f:
                    status_lines = f.read()
                state = "?"
                for line in status_lines.splitlines():
                    if line.startswith("State:"):
                        state = line.split(":", 1)[1].strip()
                        break
                print(f"  {pid:<8} {name:<30} {state}")
                count += 1
            except (FileNotFoundError, PermissionError):
                pass


def cmd_status():
    print("\n── System Status ──────────────────────────────────\n")
    cmd_cpu(interval=1)
    print()
    cmd_memory()
    print()
    cmd_disk("/")
    print()
    if HAS_PSUTIL:
        # Boot time
        import datetime
        boot = datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime = time.time() - psutil.boot_time()
        hours, rem = divmod(int(uptime), 3600)
        mins  = rem // 60
        print(f"\nUptime: {hours}h {mins}m  (booted {boot.strftime('%Y-%m-%d %H:%M')})")
    if not HAS_PSUTIL:
        print(f"\n{YELLOW}Tip: install psutil for richer stats: pip install psutil{RESET}")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Dexter System Monitor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    subparsers.add_parser("status", help="Overall system snapshot")

    # cpu
    p_cpu = subparsers.add_parser("cpu", help="CPU usage")
    p_cpu.add_argument("--interval", type=int, default=1, help="Sampling interval in seconds (default: 1)")

    # memory
    subparsers.add_parser("memory", help="Memory usage")

    # disk
    p_disk = subparsers.add_parser("disk", help="Disk usage")
    p_disk.add_argument("path", nargs="?", default="/", help="Path to check (default: /)")

    # network
    p_net = subparsers.add_parser("network", help="Network I/O stats")
    p_net.add_argument("--interface", help="Filter by interface name (e.g. eth0, wlan0)")

    # processes
    p_procs = subparsers.add_parser("processes", help="List running processes")
    p_procs.add_argument("--top", type=int, default=10, help="Number of processes to show (default: 10)")
    p_procs.add_argument("--sort", default="cpu", choices=["cpu", "mem"], help="Sort by cpu or mem (default: cpu)")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "cpu":
        cmd_cpu(interval=args.interval)
    elif args.command == "memory":
        cmd_memory()
    elif args.command == "disk":
        cmd_disk(path=args.path)
    elif args.command == "network":
        cmd_network(interface=getattr(args, "interface", None))
    elif args.command == "processes":
        cmd_processes(top=args.top, sort_by=args.sort)


if __name__ == "__main__":
    main()
