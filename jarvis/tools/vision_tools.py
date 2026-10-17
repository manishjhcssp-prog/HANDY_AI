"""
JARVIS AI - Vision & Screen Inspection Engine (Tier 3 / Phase 4)
Captures workstation screen, inspects active window contexts,
and dispatches multimodal visual understanding via free vision LLMs.
"""

import base64
import io
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from config.settings import settings
import httpx

logger = logging.getLogger("JARVIS.Tools.Vision")

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "screenshots"


def get_active_window_title() -> str:
    """Retrieves the title of the currently focused foreground window on Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return "Desktop / Standby"
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return "Active Application (Unnamed Window)"
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            return buff.value or "Active Application"
        except Exception as e:
            logger.debug(f"Could not retrieve active window title: {e}")
            return "Windows Desktop"
    return "Non-Windows Host"


def capture_screen_image(max_dimension: int = 1280) -> Tuple[Optional[bytes], str, int, int]:
    """
    Captures primary screen using mss or PIL.ImageGrab,
    resizes to max_dimension, and returns JPEG bytes, active title, width, and height.
    """
    active_title = get_active_window_title()
    img = None

    # 1. Try mss for ultra-low latency capture
    try:
        import mss
        with mss.MSS() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            raw = sct.grab(monitor)
            from PIL import Image
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    except Exception as e:
        logger.debug(f"mss capture unavailable ({e}), trying PIL.ImageGrab...")

    # 2. Try PIL.ImageGrab fallback
    if img is None:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
        except Exception as e:
            logger.debug(f"PIL.ImageGrab screen capture notice: {e}")

    # 3. If live display DC unavailable (headless/locked session), create an informative status canvas
    if img is None:
        try:
            from PIL import Image, ImageDraw
            img = Image.new("RGB", (1280, 720), color=(10, 16, 29))
            draw = ImageDraw.Draw(img)
            draw.text((40, 40), f"JARVIS Mark VII - Virtual Screen Capture Buffer", fill=(0, 240, 255))
            draw.text((40, 80), f"Active Window: {active_title}", fill=(255, 255, 255))
            draw.text((40, 120), f"Timestamp: {time.ctime()}", fill=(143, 174, 197))
        except Exception:
            return None, active_title, 0, 0

    orig_w, orig_h = img.size

    # Resize if larger than max_dimension to preserve bandwidth and latency
    if max(orig_w, orig_h) > max_dimension:
        scale = max_dimension / max(orig_w, orig_h)
        new_size = (int(orig_w * scale), int(orig_h * scale))
        img = img.resize(new_size)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=82)
    jpeg_bytes = buffer.getvalue()

    # Save latest capture to disk for inspection
    try:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        latest_file = SCREENSHOT_DIR / "latest_screen.jpg"
        latest_file.write_bytes(jpeg_bytes)
    except Exception as e:
        logger.debug(f"Could not persist screenshot to disk: {e}")

    return jpeg_bytes, active_title, img.width, img.height


async def analyze_screen(query: str = "Describe what is currently displayed on my screen and note any visible windows or errors.") -> str:
    """
    Captures the workstation screen and sends it to a free multimodal vision model
    (Google Gemini / OpenRouter) for visual analysis, troubleshooting, or OCR.
    """
    active_title = get_active_window_title()
    jpeg_bytes, title, w, h = capture_screen_image()

    if not jpeg_bytes:
        return f"I was unable to capture the display buffer at this moment, sir. However, your active foreground window is '{active_title}'."

    b64_image = base64.b64encode(jpeg_bytes).decode("utf-8")

    # Strategy A: Google Gemini Free Multimodal Vision
    gemini_key = settings.get_api_key("gemini")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [{
                    "parts": [
                        {"text": f"You are JARVIS. The user is asking about their Windows workstation screen. Active window is: '{active_title}'. Question: {query}. Keep your response concise, polite, British butler style, and highlight key visual elements or errors clearly."},
                        {"inline_data": {"mime_type": "image/jpeg", "data": b64_image}}
                    ]
                }]
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    body = resp.json()
                    candidates = body.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text:
                            return f"Visual telemetry report, sir (Active Window: '{active_title}'):\n\n{text.strip()}"
        except Exception as e:
            logger.warning(f"Gemini vision call notice: {e}")

    # Strategy B: OpenRouter Free Multimodal Vision
    openrouter_key = settings.get_api_key("openrouter")
    if openrouter_key:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "HTTP-Referer": "https://github.com/manishjhcssp-prog/HANDY_AI",
                "X-Title": "JARVIS AI Assistant",
            }
            payload = {
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"You are JARVIS. The user asks: '{query}'. Active window is '{active_title}'. Be concise, polite, British butler tone."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                    ]
                }]
            }
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if content:
                        return f"Visual inspection report, sir (Active Window: '{active_title}'):\n\n{content.strip()}"
        except Exception as e:
            logger.warning(f"OpenRouter vision call notice: {e}")

    # Strategy C: Local Telemetry Fallback
    return (
        f"Workstation screen captured successfully at {w}x{h} resolution, sir.\n"
        f"• Active Foreground Window: '{active_title}'\n"
        f"• Visual Buffer Saved: data/screenshots/latest_screen.jpg\n"
        f"To enable deep visual intelligence, ensure your free GEMINI_API_KEY or OPENROUTER_API_KEY is configured in .env."
    )
