"""
JARVIS AI - Windows OS Controller (Tier 3)
Handles volume, media keys, application launching, and desktop window controls.
"""

import os
import sys
import subprocess
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("JARVIS.Tools.OSControl")

# Virtual Key Codes for Windows
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3
KEYEVENTF_KEYUP = 0x0002


def _send_virtual_key(vk_code: int):
    """Sends a virtual key event to Windows user32."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
            ctypes.windll.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception as e:
            logger.error(f"Failed to send VK code {vk_code}: {e}")
            return False
    return False


def volume_up(steps: int = 5) -> str:
    """Increases master volume by given steps."""
    for _ in range(max(1, min(steps, 25))):
        _send_virtual_key(VK_VOLUME_UP)
    return f"Master volume increased by {steps * 2}%"


def volume_down(steps: int = 5) -> str:
    """Decreases master volume by given steps."""
    for _ in range(max(1, min(steps, 25))):
        _send_virtual_key(VK_VOLUME_DOWN)
    return f"Master volume decreased by {steps * 2}%"


def volume_mute_toggle() -> str:
    """Toggles master audio mute state."""
    _send_virtual_key(VK_VOLUME_MUTE)
    return "Audio mute toggled"


def media_play_pause() -> str:
    """Sends play/pause media command to active media player."""
    _send_virtual_key(VK_MEDIA_PLAY_PAUSE)
    return "Media play/pause triggered"


def media_next() -> str:
    """Skips to next track in active media player."""
    _send_virtual_key(VK_MEDIA_NEXT)
    return "Skipped to next track"


def media_previous() -> str:
    """Goes to previous track in active media player."""
    _send_virtual_key(VK_MEDIA_PREV)
    return "Returned to previous track"


def launch_application(app_name: str) -> str:
    """
    Launches a Windows application by name or common alias.
    Examples: 'chrome', 'notepad', 'calculator', 'explorer', 'code', 'cmd', 'powershell', 'spotify'.
    """
    clean = app_name.strip().lower()
    known_apps = {
        "chrome": "start chrome",
        "google chrome": "start chrome",
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "code": "code",
        "vs code": "code",
        "vscode": "code",
        "terminal": "wt.exe",
        "cmd": "start cmd",
        "task manager": "taskmgr.exe",
        "taskmgr": "taskmgr.exe",
        "spotify": "start spotify:",
    }

    cmd = known_apps.get(clean, f"start {clean}")
    try:
        subprocess.Popen(cmd, shell=True)
        return f"Opening {app_name}, sir."
    except Exception as e:
        return f"Unable to open {app_name}: {str(e)}"


def open_url(url: str) -> str:
    """Opens a website URL in the user's default browser."""
    clean = url.strip()
    if not clean.startswith(("http://", "https://")):
        clean = "https://" + clean
    try:
        import webbrowser
        webbrowser.open(clean)
        return f"Opening {clean} in your default browser, sir."
    except Exception as e:
        return f"Failed to open URL: {e}"


def lock_workstation() -> str:
    """Locks the Windows computer workstation securely."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "Workstation locked securely, sir."
        except Exception as e:
            return f"Failed to lock workstation: {e}"
    return "Workstation lock is only supported on Windows OS."
