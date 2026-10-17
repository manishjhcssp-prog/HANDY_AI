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
    Launches a Windows desktop application or web platform by name, URL, or common alias.
    Supports desktop apps (Chrome, Notepad, Calc, VS Code, Steam, Spotify, Terminal, etc.)
    and web streaming/productivity services (Crunchyroll, YouTube, Netflix, Discord, GitHub, etc.).
    """
    import re
    import shutil

    clean = app_name.strip().lower()

    # Strip common leading verbs or noise prefixes
    for prefix in ["the ", "open ", "launch ", "start ", "app ", "website ", "site "]:
        if clean.startswith(prefix):
            clean = clean[len(prefix):].strip()

    # Direct URL or domain check
    if clean.startswith(("http://", "https://")) or re.match(r"^[a-zA-Z0-9-]+\.(com|org|net|io|in|tv|co|ai|app|me|edu|gov)(/.*)?$", clean):
        open_url(clean)
        return f"Opening {app_name} for you now, sir."

    # Known web apps, streaming platforms, and productivity services
    known_web_services = {
        "crunchyroll": "https://www.crunchyroll.com",
        "youtube": "https://www.youtube.com",
        "netflix": "https://www.netflix.com",
        "prime video": "https://www.primevideo.com",
        "primevideo": "https://www.primevideo.com",
        "amazon prime": "https://www.primevideo.com",
        "disney+": "https://www.hotstar.com",
        "disney plus": "https://www.hotstar.com",
        "hotstar": "https://www.hotstar.com",
        "hulu": "https://www.hulu.com",
        "twitch": "https://www.twitch.tv",
        "anime": "https://www.crunchyroll.com",
        "discord": "https://discord.com/app",
        "whatsapp": "https://web.whatsapp.com",
        "whatsapp web": "https://web.whatsapp.com",
        "telegram": "https://web.telegram.org",
        "telegram web": "https://web.telegram.org",
        "github": "https://github.com",
        "reddit": "https://www.reddit.com",
        "twitter": "https://x.com",
        "x": "https://x.com",
        "instagram": "https://www.instagram.com",
        "facebook": "https://www.facebook.com",
        "linkedin": "https://www.linkedin.com",
        "gmail": "https://mail.google.com",
        "google mail": "https://mail.google.com",
        "google drive": "https://drive.google.com",
        "drive": "https://drive.google.com",
        "google docs": "https://docs.google.com",
        "google sheets": "https://sheets.google.com",
        "google maps": "https://maps.google.com",
        "maps": "https://maps.google.com",
        "google": "https://www.google.com",
        "chatgpt": "https://chatgpt.com",
        "claude": "https://claude.ai",
        "gemini": "https://gemini.google.com",
        "stackoverflow": "https://stackoverflow.com",
        "stack overflow": "https://stackoverflow.com",
        "pinterest": "https://www.pinterest.com",
        "wikipedia": "https://www.wikipedia.org",
        "notion": "https://www.notion.so",
        "figma": "https://www.figma.com",
        "canva": "https://www.canva.com",
        "spotify web": "https://open.spotify.com",
    }

    if clean in known_web_services:
        url = known_web_services[clean]
        open_url(url)
        return f"Opening {clean.title()} for you now, sir."

    # Known desktop applications
    known_apps = {
        "chrome": "start chrome",
        "google chrome": "start chrome",
        "edge": "start msedge",
        "msedge": "start msedge",
        "microsoft edge": "start msedge",
        "firefox": "start firefox",
        "brave": "start brave",
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
        "paint": "mspaint.exe",
        "mspaint": "mspaint.exe",
        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "files": "explorer.exe",
        "my computer": "explorer.exe",
        "code": "code",
        "vs code": "code",
        "vscode": "code",
        "visual studio code": "code",
        "terminal": "wt.exe",
        "windows terminal": "wt.exe",
        "cmd": "start cmd",
        "command prompt": "start cmd",
        "powershell": "start powershell",
        "task manager": "taskmgr.exe",
        "taskmgr": "taskmgr.exe",
        "settings": "start ms-settings:",
        "windows settings": "start ms-settings:",
        "control panel": "control.exe",
        "spotify": "start spotify:",
        "steam": "start steam://",
        "vlc": "start vlc",
        "word": "start winword",
        "ms word": "start winword",
        "microsoft word": "start winword",
        "excel": "start excel",
        "ms excel": "start excel",
        "microsoft excel": "start excel",
        "powerpoint": "start powerpnt",
        "ppt": "start powerpnt",
        "ms powerpoint": "start powerpnt",
    }

    if clean in known_apps:
        cmd = known_apps[clean]
        try:
            subprocess.Popen(cmd, shell=True)
            return f"Opening {clean.title()} for you now, sir."
        except Exception as e:
            return f"Unable to open {clean}: {str(e)}"

    # Check if executable exists in system PATH or is local file
    if shutil.which(clean) or shutil.which(f"{clean}.exe"):
        try:
            subprocess.Popen(f"start {clean}", shell=True)
            return f"Opening {clean.title()} for you now, sir."
        except Exception as e:
            return f"Unable to open {clean}: {str(e)}"

    if os.path.exists(clean):
        try:
            if sys.platform == "win32":
                os.startfile(clean)
            else:
                subprocess.Popen(["xdg-open", clean])
            return f"Opening {clean} for you now, sir."
        except Exception as e:
            return f"Unable to open {clean}: {str(e)}"

    # Default fallback for arbitrary user targets: open as web domain
    fallback_url = f"https://www.{clean}.com"
    open_url(fallback_url)
    return f"Opening {clean.title()} for you now, sir."


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
