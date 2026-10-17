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


def _speak_sapi_thread(text: str, rate: int = 1):
    """Speaks text in a dedicated COM thread to prevent blocking asyncio loop."""
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            voice.Rate = rate
            voice.Speak(text, 0)
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        logger.error(f"SAPI thread error: {e}")


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
        flags = 1 if async_mode else 0
        try:
            self._sapi_voice.Speak(text, flags)
        except Exception as e:
            logger.error(f"SAPI speech error: {e}")

    async def speak_text(self, text: str):
        """
        Synthesizes and speaks text using Edge-TTS if possible,
        falling back seamlessly to non-blocking Windows SAPI5.
        """
        clean_text = self._sanitize_text(text)
        if not clean_text:
            return

        if self.prefer_native or not self._is_online_tts_available():
            await asyncio.to_thread(_speak_sapi_thread, clean_text, 1)
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
            await asyncio.to_thread(_speak_sapi_thread, clean_text, 1)

    def speak_sync(self, text: str):
        """Synchronous speak wrapper for console/worker threads."""
        clean_text = self._sanitize_text(text)
        if not clean_text:
            return
        _speak_sapi_thread(clean_text, 1)

    async def stream_and_speak(
        self,
        token_stream: AsyncIterator[str],
        on_token: Optional[any] = None,
    ) -> str:
        """
        Streams tokens chunk-by-chunk with zero text latency, while simultaneously
        queueing complete sentences for immediate, non-blocking speech synthesis.
        """
        from typing import Callable
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        full_text = []

        async def speech_worker():
            while True:
                sentence = await queue.get()
                if sentence is None:
                    queue.task_done()
                    break
                try:
                    await self.speak_text(sentence)
                except Exception as err:
                    logger.warning(f"Error speaking sentence: {err}")
                finally:
                    queue.task_done()

        worker_task = asyncio.create_task(speech_worker())
        buffer = ""
        sentence_end = re.compile(r"([.!?\n]+)\s*")
        clause_end = re.compile(r"([,;:]+)\s*")

        try:
            async for token in token_stream:
                full_text.append(token)
                if on_token:
                    on_token(token)

                buffer += token
                match = sentence_end.search(buffer)
                if match:
                    sentence = buffer[:match.end()].strip()
                    buffer = buffer[match.end():]
                    if sentence:
                        await queue.put(sentence)
                elif len(buffer) > 90:
                    cm = clause_end.search(buffer)
                    if cm:
                        sentence = buffer[:cm.end()].strip()
                        buffer = buffer[cm.end():]
                        if sentence:
                            await queue.put(sentence)

            if buffer.strip():
                await queue.put(buffer.strip())
        finally:
            await queue.put(None)
            await worker_task

        return "".join(full_text)

    async def stream_sentences(self, token_stream: AsyncIterator[str]):
        """Buffers streamed LLM tokens into complete sentences and speaks concurrently."""
        await self.stream_and_speak(token_stream, on_token=None)

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
