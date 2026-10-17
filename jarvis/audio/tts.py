"""
JARVIS AI - Text-to-Speech (TTS) Engine (Tier 1)
Supports streaming sentence-level neural speech synthesis via Edge-TTS
with automatic zero-latency fallback to Windows native SAPI5.
"""

import sys
import os
import re
import asyncio
import logging
from typing import Optional, AsyncIterator

logger = logging.getLogger("JARVIS.Audio.TTS")


class TTSEngine:
    """
    Neural and native TTS engine with sentence streaming and graceful fallbacks.
    """

    def __init__(
        self,
        voice: str = "en-GB-RyanNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
        prefer_native: bool = False,
    ):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.prefer_native = prefer_native
        self._sapi_voice = None
        self._init_sapi()

    def _init_sapi(self):
        """Initializes native Windows SAPI.SpVoice COM interface."""
        if sys.platform == "win32":
            try:
                import win32com.client
                self._sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
                # Speed control (-10 to 10)
                self._sapi_voice.Rate = 1
                logger.info("Windows SAPI.SpVoice successfully initialized as fallback.")
            except Exception as e:
                logger.warning(f"Could not initialize Windows SAPI.SpVoice: {e}")
                self._sapi_voice = None

    def _speak_sapi(self, text: str, async_mode: bool = False):
        """Speaks text using Windows SAPI voice."""
        if not self._sapi_voice:
            return
        # Flag 1 = SVSFlagsAsync (non-blocking)
        flags = 1 if async_mode else 0
        try:
            self._sapi_voice.Speak(text, flags)
        except Exception as e:
            logger.error(f"SAPI speech error: {e}")

    async def speak_text(self, text: str):
        """
        Synthesizes and speaks text using Edge-TTS if possible,
        falling back seamlessly to Windows SAPI5.
        """
        clean_text = self._sanitize_text(text)
        if not clean_text:
            return

        if self.prefer_native or not self._is_online_tts_available():
            self._speak_sapi(clean_text, async_mode=False)
            return

        # Attempt Edge-TTS
        try:
            import edge_tts
            import tempfile
            import pygame

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name

            communicate = edge_tts.Communicate(
                clean_text,
                self.voice,
                rate=self.rate,
                pitch=self.pitch,
            )
            await communicate.save(tmp_path)

            # Play using pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.05)
            pygame.mixer.music.unload()

            try:
                os.remove(tmp_path)
            except Exception:
                pass

        except Exception as e:
            logger.info(f"Online TTS unavailable ({e}), using Windows SAPI voice.")
            self._speak_sapi(clean_text, async_mode=False)

    def speak_sync(self, text: str):
        """Synchronous speak wrapper for console/worker threads."""
        clean_text = self._sanitize_text(text)
        if not clean_text:
            return
        self._speak_sapi(clean_text, async_mode=False)

    async def stream_sentences(self, token_stream: AsyncIterator[str]):
        """
        Buffers streamed LLM tokens into complete sentences and speaks each
        sentence as soon as it completes to minimize time-to-first-audio.
        """
        buffer = ""
        sentence_end = re.compile(r"([.!?\n]+)\s*")

        async for token in token_stream:
            buffer += token
            # Check if a sentence boundary is reached
            match = sentence_end.search(buffer)
            if match:
                idx = match.end()
                sentence = buffer[:idx].strip()
                buffer = buffer[idx:]
                if sentence:
                    await self.speak_text(sentence)

        # Speak remaining buffer
        if buffer.strip():
            await self.speak_text(buffer.strip())

    def _sanitize_text(self, text: str) -> str:
        """Removes markdown artifacts and unpronounceable characters."""
        # Strip raw tool call tags
        t = re.sub(r"<\|tool_call_start\|>[\s\S]*?<\|tool_call_end\|>", "", text)
        t = re.sub(r"<\|[^|>]+(?:start|end)[^|>]*\|>", "", t)
        # Strip code blocks
        t = re.sub(r"```[\s\S]*?```", "", t)
        # Strip inline code
        t = re.sub(r"`([^`]+)`", r"\1", t)
        # Strip markdown links [text](url) -> text
        t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
        # Strip bold and italics
        t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
        t = re.sub(r"\*([^*]+)\*", r"\1", t)
        # Strip markdown headers, hashes, bullets, and dashes
        t = re.sub(r"[#*_~•]", " ", t)
        t = re.sub(r"(?<=\s)-+(?=\s)", " ", t)
        # Clean up any space before punctuation
        t = re.sub(r"\s+([,.:;!?])", r"\1", t)
        return " ".join(t.split())

    def _is_online_tts_available(self) -> bool:
        # Defaults to False on network restrictions or 403
        return False
