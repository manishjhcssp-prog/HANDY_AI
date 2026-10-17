"""
Tests for Audio Pipeline (TTS text cleaning, STT lazy load, Recorder config).
"""

import pytest
import numpy as np
from jarvis.audio.tts import TTSEngine
from jarvis.audio.stt import STTEngine
from jarvis.audio.recorder import AudioRecorder


def test_tts_text_sanitization():
    tts = TTSEngine(prefer_native=True)
    raw = "**Right away**, sir! Here is `code` and a [link](http://test.com) - # Title"
    cleaned = tts._sanitize_text(raw)
    assert "**" not in cleaned
    assert "`" not in cleaned
    assert "http://test.com" not in cleaned
    assert "Right away, sir! Here is code and a link Title" == cleaned


def test_stt_initialization():
    stt = STTEngine(local_model_size="base.en")
    assert stt.local_model_size == "base.en"
    assert stt._local_model is None
    # Test audio to WAV conversion
    audio = np.zeros(16000, dtype=np.float32)
    wav_bytes = stt._audio_to_wav_bytes(audio)
    assert len(wav_bytes) > 100


def test_recorder_initialization():
    rec = AudioRecorder(sample_rate=16000, silence_duration=1.5)
    assert rec.target_sample_rate == 16000
    assert rec.silence_duration == 1.5
    # Test 16k resampling logic
    orig = np.zeros(44100, dtype=np.float32)
    resampled = rec._resample_to_16k(orig, 44100)
    assert len(resampled) == 16000


@pytest.mark.asyncio
async def test_tts_stream_and_speak():
    tts = TTSEngine(prefer_native=True)
    async def mock_stream():
        for chunk in ["Greetings, ", "sir. ", "System online."]:
            yield chunk

    tokens_received = []
    full = await tts.stream_and_speak(mock_stream(), on_token=lambda t: tokens_received.append(t))
    assert full == "Greetings, sir. System online."
    assert tokens_received == ["Greetings, ", "sir. ", "System online."]
