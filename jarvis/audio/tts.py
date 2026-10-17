"""
JARVIS AI - Text-to-Speech (TTS) Engine (Tier 1)
Supports local, studio-quality neural speech synthesis via Kokoro TTS (82M)
with automatic zero-latency fallback to Windows native SAPI5.
"""

import sys
import os
import re
import asyncio
import logging
import warnings
from typing import Optional, AsyncIterator, Callable

# Disable Hugging Face symlink warnings on Windows
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)

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
            voice = None
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:
        logger.error(f"SAPI thread error: {e}")


class TTSEngine:
    """
    Kokoro neural and native SAPI TTS engine with sentence streaming and graceful fallbacks.
    Default voice: bm_george (British Butler persona).
    """

    def __init__(
        self,
        voice: str = "bm_george",
        speed: float = 1.05,
        lang_code: str = "b",
        prefer_native: bool = False,
    ):
        self.voice = voice
        self.speed = speed
        self.lang_code = lang_code
        self.prefer_native = prefer_native
        self._kokoro_pipeline = None
        self._sapi_voice = None
        self._init_sapi()

    def _init_sapi(self):
        """Initializes native Windows SAPI.SpVoice COM interface as fallback."""
        if sys.platform == "win32":
            try:
                import win32com.client
                self._sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
                self._sapi_voice.Rate = 1
                logger.info("Windows SAPI.SpVoice initialized as fallback.")
            except Exception as e:
                logger.warning(f"Could not initialize Windows SAPI.SpVoice: {e}")
                self._sapi_voice = None

    def _get_kokoro_pipeline(self):
        """Lazy-loads the Kokoro neural TTS pipeline on demand."""
        if self._kokoro_pipeline is None:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    from kokoro import KPipeline
                    logger.info("Initializing Kokoro Neural TTS pipeline (82M)...")
                    self._kokoro_pipeline = KPipeline(lang_code=self.lang_code, repo_id="hexgrad/Kokoro-82M")
                    logger.info("Kokoro Neural TTS pipeline ready.")
            except Exception as e:
                logger.warning(f"Could not initialize Kokoro TTS: {e}")
                self._kokoro_pipeline = None
        return self._kokoro_pipeline

    def _speak_kokoro_thread(self, text: str, voice: str, speed: float) -> bool:
        """Synthesizes and plays audio with Kokoro in worker thread."""
        try:
            pipeline = self._get_kokoro_pipeline()
            if not pipeline:
                return False
            import sounddevice
            generator = pipeline(text, voice=voice, speed=speed)
            for _, _, audio in generator:
                audio_np = audio.numpy()
                sounddevice.play(audio_np, 24000)
                sounddevice.wait()
            return True
        except Exception as e:
            logger.warning(f"Kokoro playback error ({e}), falling back to SAPI.")
            return False

    async def speak_text(self, text: str):
        """
        Synthesizes and speaks text using Kokoro Neural TTS,
        falling back seamlessly to Windows SAPI5 if unavailable.
        """
        clean_text = self._sanitize_text(text)
        if not clean_text:
            return

        if not self.prefer_native:
            success = await asyncio.to_thread(self._speak_kokoro_thread, clean_text, self.voice, self.speed)
            if success:
                return

        # SAPI Fallback
        await asyncio.to_thread(_speak_sapi_thread, clean_text, 1)

    def speak_sync(self, text: str):
        """Synchronous speak wrapper for worker threads or CLI shutdown."""
        clean_text = self._sanitize_text(text)
        if not clean_text:
            return
        if not self.prefer_native:
            if self._speak_kokoro_thread(clean_text, self.voice, self.speed):
                return
        _speak_sapi_thread(clean_text, 1)

    async def stream_and_speak(
        self,
        token_stream: AsyncIterator[str],
        on_token: Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Streams tokens chunk-by-chunk with zero text latency, while simultaneously
        queueing complete sentences for immediate, non-blocking Kokoro speech synthesis.
        """
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
