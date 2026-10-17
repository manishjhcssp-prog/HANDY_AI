"""
JARVIS AI - Cognitive Brain & Conversational Agent Loop
Maintains conversational history, manages persona system prompts,
and interfaces directly with the Intelligent Multi-Provider Router.
"""

import logging
from typing import Dict, List, Optional, Any, AsyncIterator
import re
from .router import LLMRouter, LLMResponse
from .prompts import get_system_prompt
from config.settings import Settings, settings as default_settings
from jarvis.tools.registry import execute_tool, TOOLS_SCHEMA

logger = logging.getLogger("JARVIS.Agent")


class JarvisAgent:
    """
    Core conversational agent implementing the JARVIS persona,
    sliding window memory, OS tool calling, and multi-provider failover routing.
    """

    def __init__(
        self,
        router: Optional[LLMRouter] = None,
        custom_settings: Optional[Settings] = None,
        max_history_turns: int = 20,
    ):
        self.settings = custom_settings or default_settings
        self.router = router or LLMRouter(custom_settings=self.settings)
        self.max_history_turns = max_history_turns
        self.history: List[Dict[str, str]] = []
        self.reset()

    def reset(self) -> None:
        """Resets conversational history back to initial system prompt."""
        self.history = [
            {"role": "system", "content": get_system_prompt()}
        ]

    def get_history(self) -> List[Dict[str, str]]:
        return list(self.history)

    def _trim_history_if_needed(self) -> None:
        """Keeps system prompt intact while trimming older dialogue turns."""
        system_msg = self.history[0]
        dialogue = self.history[1:]
        max_messages = self.max_history_turns * 2
        if len(dialogue) > max_messages:
            dialogue = dialogue[-max_messages:]
            self.history = [system_msg] + dialogue

    async def _handle_direct_os_command(self, user_input: str) -> Optional[str]:
        """
        Fast-path handler for direct workstation commands (< 50ms latency).
        """
        lower = user_input.lower().strip()

        # Volume controls
        if any(w in lower for w in ["volume up", "increase volume", "raise volume", "louder"]):
            await execute_tool("volume_up", {"steps": 5})
            return "Right away, sir. Increasing master volume."

        if any(w in lower for w in ["volume down", "decrease volume", "lower volume", "softer"]):
            await execute_tool("volume_down", {"steps": 5})
            return "Of course, sir. Decreasing master volume."

        if lower in ["mute", "unmute", "mute sound", "mute volume", "toggle mute"]:
            await execute_tool("volume_mute_toggle")
            return "Audio mute toggled, sir."

        # Media controls
        if any(w in lower for w in ["play music", "pause music", "pause", "resume", "play/pause"]):
            await execute_tool("media_play_pause")
            return "Media playback toggled, sir."

        if any(w in lower for w in ["next song", "next track", "skip song"]):
            await execute_tool("media_next")
            return "Skipping to the next track, sir."

        if any(w in lower for w in ["previous song", "previous track"]):
            await execute_tool("media_previous")
            return "Returning to the previous track, sir."

        # Application launcher
        app_match = re.search(r"\b(open|launch|start)\s+(chrome|notepad|calculator|calc|spotify|explorer|code|cmd|terminal)\b", lower)
        if app_match:
            app_name = app_match.group(2)
            await execute_tool("launch_application", {"app_name": app_name})
            return f"Opening {app_name.title()} for you now, sir."

        # System health / hardware telemetry
        if any(w in lower for w in ["system status", "hardware status", "cpu usage", "ram usage", "battery status", "system stats", "workstation health"]):
            info = await execute_tool("get_system_summary")
            if isinstance(info, dict):
                cpu = info.get("cpu_percent")
                ram = info.get("ram_percent")
                disk = info.get("disk_percent")
                batt = info.get("battery", {}).get("percent")
                plugged = "plugged in" if info.get("battery", {}).get("power_plugged") else "on battery"
                return (
                    f"Workstation telemetry report, sir:\n"
                    f"• CPU Load: {cpu}%\n"
                    f"• Memory Usage: {ram}% ({info.get('ram_used_gb')} GB / {info.get('ram_total_gb')} GB)\n"
                    f"• Primary Disk: {disk}% used ({info.get('disk_free_gb')} GB free)\n"
                    f"• Battery: {batt}% ({plugged})"
                )

        # Web search
        search_match = re.search(r"\b(?:search\s+(?:the\s+)?web\s+for|search\s+for|look\s+up|google)\s+(.+)$", lower)
        if search_match:
            query = search_match.group(1).strip()
            results = await execute_tool("search_duckduckgo", {"query": query})
            if results and not str(results).lower().startswith("i was unable"):
                return f"Here is what I found on the web regarding '{query}', sir:\n{results}"
            return results or f"I could not locate any relevant web results for '{query}', sir."

        # Weather lookup
        weather_match = re.search(r"\b(?:weather\s+in|weather\s+for|forecast\s+for)\s+([a-zA-Z\s]+)$", lower)
        if weather_match:
            city = weather_match.group(1).strip()
            weather = await execute_tool("get_weather", {"city": city})
            return f"{weather}"

        # Workstation lock
        if any(w in lower for w in ["lock pc", "lock computer", "lock screen", "lock workstation"]):
            await execute_tool("lock_workstation")
            return "Locking workstation now, sir."

        return None

    async def chat(
        self,
        user_input: str,
        preferred_provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> LLMResponse:
        """
        Executes a conversational turn with JARVIS.
        First checks direct OS command fast-path, then falls back to LLM router.
        """
        direct_reply = await self._handle_direct_os_command(user_input)
        if direct_reply:
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": direct_reply})
            return LLMResponse(
                content=direct_reply,
                model="local-tool",
                provider="os_controller",
                key_masked="local",
            )

        self.history.append({"role": "user", "content": user_input})
        self._trim_history_if_needed()

        response = await self.router.generate(
            messages=self.history,
            preferred_provider=preferred_provider,
            model=model,
            tools=TOOLS_SCHEMA,
        )

        self.history.append({"role": "assistant", "content": response.content})
        return response

    async def stream_chat(
        self,
        user_input: str,
        preferred_provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        Streams response tokens chunk-by-chunk for low-latency feedback.
        Direct OS commands execute and yield immediately.
        """
        direct_reply = await self._handle_direct_os_command(user_input)
        if direct_reply:
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": direct_reply})
            yield direct_reply
            return

        self.history.append({"role": "user", "content": user_input})
        self._trim_history_if_needed()

        full_content = []
        async for chunk in self.router.stream(
            messages=self.history,
            preferred_provider=preferred_provider,
            model=model,
        ):
            full_content.append(chunk)
            yield chunk

        self.history.append({"role": "assistant", "content": "".join(full_content)})

    def get_status(self) -> Dict[str, Any]:
        """Returns diagnostic telemetry for the agent and provider pools."""
        return self.router.get_telemetry()
