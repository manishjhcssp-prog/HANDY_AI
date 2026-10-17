"""
JARVIS AI - Speech-to-Text (STT) Engine (Tier 1)
Dual-Engine Speech Recognition:
  1. Ultra-fast Cloud Whisper (Groq whisper-large-v3-turbo, < 400ms, ₹0 cost)
  2. 100% Offline Local faster-whisper (CTranslate2 base.en)
"""

import io
import wave
import logging
from typing import Optional, Union
import numpy as np
import httpx
from config.settings import settings

logger = logging.getLogger("JARVIS.Audio.STT")


class STTEngine:
    """
    Speech-to-Text engine combining ultra-low-latency Groq Whisper Cloud
    with local faster-whisper offline fallback.
    """

    def __init__(
        self,
        local_model_size: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        prefer_cloud: bool = True,
    ):
        self.local_model_size = local_model_size
        self.device = device
        self.compute_type = compute_type
        self.prefer_cloud = prefer_cloud
        self._local_model = None

    def _get_local_model(self):
        """Lazy load local faster-whisper model on first offline invocation."""
        if self._local_model is None:
            logger.info(f"Loading local faster-whisper model '{self.local_model_size}'...")
            try:
                from faster_whisper import WhisperModel
                self._local_model = WhisperModel(
                    self.local_model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
                logger.info("Local faster-whisper model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load local faster-whisper: {e}")
                raise
        return self._local_model

    def _audio_to_wav_bytes(self, audio_data: np.ndarray, sample_rate: int = 16000) -> bytes:
        """Converts a float32 NumPy audio array to a standard 16-bit PCM WAV in memory."""
        # Normalize and scale to int16
        clipped = np.clip(audio_data, -1.0, 1.0)
        pcm_data = (clipped * 32767).astype(np.int16)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(pcm_data.tobytes())
        buf.seek(0)
        return buf.read()

    def _transcribe_groq_cloud(self, wav_bytes: bytes) -> Optional[str]:
        """Transcribes audio using Groq Whisper Large-v3-Turbo API (< 400ms)."""
        groq_keys = settings.api_keys.get("groq", [])
        if not groq_keys:
            return None

        key = groq_keys[0]
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        headers = {"Authorization": f"Bearer {key}"}
        files = {"file": ("audio.wav", wav_bytes, "audio/wav")}
        data = {
            "model": "whisper-large-v3-turbo",
            "language": "en",
            "temperature": "0.0",
        }

        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.post(url, headers=headers, files=files, data=data)
                if resp.status_code == 200:
                    text = resp.json().get("text", "").strip()
                    logger.info(f"Groq Cloud Whisper transcribed: '{text}'")
                    return text
                else:
                    logger.warning(f"Groq Whisper returned status {resp.status_code}: {resp.text}")
                    return None
        except Exception as e:
            logger.warning(f"Groq Whisper Cloud failed: {e}")
            return None

    def _transcribe_local(self, audio_input: Union[str, np.ndarray]) -> str:
        """Transcribes audio using local faster-whisper engine."""
        try:
            model = self._get_local_model()
            segments, info = model.transcribe(
                audio_input,
                beam_size=3,
                language="en",
                condition_on_previous_text=False,
            )
            transcription = " ".join(seg.text.strip() for seg in segments)
            logger.info(f"Local faster-whisper transcribed: '{transcription.strip()}'")
            return transcription.strip()
        except Exception as e:
            logger.error(f"Local STT error: {e}")
            return ""

    def transcribe(self, audio_input: Union[str, np.ndarray]) -> str:
        """
        Transcribes audio. If Groq API key is configured, uses ultra-fast
        Groq Whisper Large-v3-Turbo first, then falls back to local faster-whisper.
        """
        # If input is a numpy array
        if isinstance(audio_input, np.ndarray):
            if len(audio_input) == 0:
                return ""

            if self.prefer_cloud:
                wav_bytes = self._audio_to_wav_bytes(audio_input)
                cloud_text = self._transcribe_groq_cloud(wav_bytes)
                if cloud_text is not None:
                    # Ignore common silent hallucination artifacts (like single punctuation or ellipses)
                    if cloud_text.strip() not in (".", "..", "...", "!", "?", "you", "Thank you."):
                        return cloud_text

            # Fallback to local faster-whisper
            return self._transcribe_local(audio_input)

        # If input is a file path
        if isinstance(audio_input, str):
            if self.prefer_cloud:
                try:
                    with open(audio_input, "rb") as f:
                        cloud_text = self._transcribe_groq_cloud(f.read())
                    if cloud_text is not None:
                        return cloud_text
                except Exception:
                    pass

            return self._transcribe_local(audio_input)

        return ""
