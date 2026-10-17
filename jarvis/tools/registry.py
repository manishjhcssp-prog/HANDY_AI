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
from .vision_tools import analyze_screen, get_active_window_title
from jarvis.memory.memory_manager import get_memory_manager

logger = logging.getLogger("JARVIS.Tools.Registry")


def remember_user_fact(key: str, value: str, category: str = "general") -> str:
    """Stores a fact or preference in long-term memory."""
    return get_memory_manager().remember_fact(key, value, category)


def recall_user_memory(query: str = "") -> str:
    """Recalls stored facts or searches notes."""
    mm = get_memory_manager()
    if not query:
        facts = mm.get_all_facts()
        if not facts:
            return "No persistent facts or preferences are currently stored in memory, sir."
        res = ["Here is what I have committed to long-term memory, sir:"]
        for k, v in facts.items():
            res.append(f"• {k.title()}: {v}")
        return "\n".join(res)
    matches = mm.search_memory(query)
    if not matches:
        return f"No memories found matching '{query}', sir."
    res = [f"Memory search results for '{query}', sir:"]
    for m in matches:
        if m.get("type") == "fact":
            res.append(f"• Fact: {m['key']} = {m['value']}")
        else:
            res.append(f"• Note: {m['title']} - {m['content']}")
    return "\n".join(res)


def forget_user_fact(key: str) -> str:
    """Removes a fact from long-term memory."""
    success = get_memory_manager().forget_fact(key)
    if success:
        return f"Fact '{key}' has been removed from long-term memory, sir."
    return f"I could not locate '{key}' in long-term memory, sir."


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
    "analyze_screen": analyze_screen,
    "get_active_window": get_active_window_title,
    "remember_user_fact": remember_user_fact,
    "recall_user_memory": recall_user_memory,
    "forget_user_fact": forget_user_fact,
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
    {
        "type": "function",
        "function": {
            "name": "analyze_screen",
            "description": "Capture the user's workstation screen and inspect, summarize, or debug visible windows, code, or errors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Specific question or request about the screen content (default: 'Analyze what is on my screen')"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_window",
            "description": "Get the title and application name of the currently active/focused foreground window.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_user_fact",
            "description": "Store a permanent fact, user preference, project detail, or personal instruction into long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Unique key or topic (e.g. 'user_name', 'favorite_ide', 'project_name')"},
                    "value": {"type": "string", "description": "The exact fact or preference to remember"},
                    "category": {"type": "string", "description": "Category (e.g. 'preference', 'project', 'personal', 'general')"}
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_user_memory",
            "description": "Recall remembered user facts, preferences, project details, and persistent notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Optional keyword to search memory, or leave empty to list all remembered facts"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_user_fact",
            "description": "Remove a fact or preference from long-term memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The key of the fact to remove"}
                },
                "required": ["key"],
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
