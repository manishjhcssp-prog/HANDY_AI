"""
JARVIS AI - System Hardware Telemetry & Health Monitoring (Tier 3)
Tracks CPU, RAM, Disk, Battery, and Process metrics for telemetry display and voice reporting.
"""

import os
import platform
import logging
from typing import Dict, Any, List
import psutil

logger = logging.getLogger("JARVIS.Tools.SysInfo")


def get_system_summary() -> Dict[str, Any]:
    """Returns an overall snapshot of workstation health and hardware usage."""
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\" if os.name == "nt" else "/")
    battery = psutil.sensors_battery()

    battery_info = {
        "percent": battery.percent if battery else None,
        "power_plugged": battery.power_plugged if battery else None,
    }

    return {
        "os": f"{platform.system()} {platform.release()}",
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "cpu_count": psutil.cpu_count(logical=True),
        "ram_percent": vm.percent,
        "ram_used_gb": round(vm.used / (1024 ** 3), 2),
        "ram_total_gb": round(vm.total / (1024 ** 3), 2),
        "disk_percent": disk.percent,
        "disk_free_gb": round(disk.free / (1024 ** 3), 2),
        "battery": battery_info,
    }


def get_top_processes(limit: int = 5, sort_by: str = "memory_percent") -> List[Dict[str, Any]]:
    """Returns top active processes by CPU or memory usage."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = p.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": info.get("cpu_percent") or 0.0,
                "memory_percent": round(info.get("memory_percent") or 0.0, 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    procs.sort(key=lambda x: x.get(sort_by, 0), reverse=True)
    return procs[:limit]
