"""
JARVIS AI - Tool Registry & Dispatcher (Tier 3)
Defines function schemas for LLM tool calling and executes system actions safely.
"""

import json
import inspect
import logging
from typing import Dict, Any, List, Callable, Optional

from .os_control import (
    volume_up,
    volume_down,
    volume_mute_toggle,
    media_play_pause,
    media_next,
    media_previous,
    launch_application,
    open_url,
    lock_workstation,
)
from .sys_info import get_system_summary, get_top_processes
from .web_tools import get_weather, search_duckduckgo

logger = logging.getLogger("JARVIS.Tools.Registry")


# Function mappings
TOOL_DISPATCH: Dict[str, Callable[..., Any]] = {
    "volume_up": volume_up,
    "volume_down": volume_down,
    "volume_mute_toggle": volume_mute_toggle,
    "media_play_pause": media_play_pause,
    "media_next": media_next,
    "media_previous": media_previous,
    "launch_application": launch_application,
    "open_url": open_url,
    "lock_workstation": lock_workstation,
    "get_system_summary": get_system_summary,
    "get_top_processes": get_top_processes,
    "get_weather": get_weather,
    "search_duckduckgo": search_duckduckgo,
}

# Standard OpenAI-compatible tool specifications
TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "volume_up",
            "description": "Increase master volume on the Windows workstation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {"type": "integer", "description": "Number of volume steps (default: 5)"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_down",
            "description": "Decrease master volume on the Windows workstation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {"type": "integer", "description": "Number of volume steps (default: 5)"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "volume_mute_toggle",
            "description": "Toggle audio mute or unmute on the Windows workstation.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_play_pause",
            "description": "Play or pause current media playback (Spotify, YouTube, browser).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_next",
            "description": "Skip to the next song or media track.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "media_previous",
            "description": "Return to the previous song or media track.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launch_application",
            "description": "Launch a Windows desktop application or web platform (e.g. 'crunchyroll', 'youtube', 'netflix', 'discord', 'chrome', 'calculator', 'notepad', 'code', 'spotify').",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Name or URL of the application/service to open (e.g. 'crunchyroll', 'youtube', 'chrome', 'calculator')"}
                },
                "required": ["app_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a specific website or URL in the default web browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Web URL to open"}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lock_workstation",
            "description": "Lock the Windows PC workstation.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_summary",
            "description": "Get real-time CPU, RAM, Disk, and Battery hardware metrics for the workstation.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_processes",
            "description": "Get the top running processes by memory or CPU usage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of processes to return (default: 5)"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather condition, temperature, and forecast for any city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name (e.g. 'London', 'Bengaluru', 'New York')"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_duckduckgo",
            "description": "Search the web for up-to-date facts, current events, or definitions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
]


async def execute_tool(tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
    """Executes a registered tool function safely with given arguments."""
    func = TOOL_DISPATCH.get(tool_name)
    if not func:
        return f"Tool '{tool_name}' is not recognized."

    args = arguments or {}
    try:
        if inspect.iscoroutinefunction(func):
            result = await func(**args)
        else:
            result = func(**args)
        return result
    except Exception as e:
        logger.error(f"Error executing tool '{tool_name}': {e}")
        return f"Error executing {tool_name}: {str(e)}"
