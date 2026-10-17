"""
JARVIS AI - Microphone Audio Recorder with Dynamic VAD (Tier 1)
Hardware-aware microphone recording with adaptive noise floor calibration
and automatic silence cutoff.
"""

import time
import logging
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger("JARVIS.Audio.Recorder")


class AudioRecorder:
    """
    Microphone stream recorder with dynamic noise floor calibration and adaptive VAD.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        silence_duration: float = 1.3,
        min_speech_duration: float = 0.5,
    ):
        self.target_sample_rate = sample_rate
        self.channels = channels
        self.silence_duration = silence_duration
        self.min_speech_duration = min_speech_duration

    def _resample_to_16k(self, audio: np.ndarray, orig_sr: int) -> np.ndarray:
        """Resamples audio from native device rate to 16,000 Hz using linear interpolation."""
        if orig_sr == self.target_sample_rate:
            return audio.astype(np.float32)
        target_len = int(len(audio) * self.target_sample_rate / orig_sr)
        indices = np.linspace(0, len(audio) - 1, target_len)
        return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)

    def _get_device_info(self) -> Tuple[int, int]:
        """Queries the default input device and returns (native_sample_rate, channels)."""
        import sounddevice as sd
        try:
            dev = sd.query_devices(kind="input")
            sr = int(dev.get("default_samplerate", 44100))
            ch = min(2, max(1, int(dev.get("max_input_channels", 1))))
            return sr, ch
        except Exception:
            return 16000, 1

    def record_until_silence(self, max_duration: float = 12.0) -> np.ndarray:
        """
        Records audio from the default microphone.
        Dynamically calculates the ambient noise floor in the first 200ms,
        detects speech onset, and stops after silence_duration seconds of quiet.
        """
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice is not installed.")
            return np.array([], dtype=np.float32)

        native_sr, native_ch = self._get_device_info()
        chunk_size = int(native_sr * 0.1)  # 100ms frames
        audio_buffer = []

        # State tracking
        ambient_energies = []
        speech_threshold = 0.005  # Initial baseline
        speech_started = False
        speech_start_time = None
        silence_start_time = None
        start_time = time.time()

        try:
            with sd.InputStream(
                samplerate=native_sr,
                channels=native_ch,
                dtype="float32",
                blocksize=chunk_size,
            ) as stream:
                while time.time() - start_time < max_duration:
                    data, _ = stream.read(chunk_size)
                    audio_buffer.append(data.copy())

                    # Convert to mono for energy calculation
                    mono_chunk = np.mean(data, axis=1) if data.ndim > 1 and data.shape[1] > 1 else data.flatten()
                    rms = float(np.sqrt(np.mean(mono_chunk ** 2)))

                    # Phase 1: Calibrate ambient noise floor for the first 200ms
                    elapsed = time.time() - start_time
                    if elapsed < 0.2:
                        ambient_energies.append(rms)
                        continue
                    elif elapsed < 0.25 and ambient_energies:
                        ambient_floor = float(np.mean(ambient_energies))
                        # Adaptive threshold: 2.5x ambient noise, but capped within [0.002, 0.025]
                        speech_threshold = max(0.002, min(ambient_floor * 2.5, 0.025))

                    # Phase 2: Detect speech vs silence
                    if rms > speech_threshold:
                        if not speech_started:
                            speech_started = True
                            speech_start_time = time.time()
                        silence_start_time = None
                    elif speech_started:
                        if silence_start_time is None:
                            silence_start_time = time.time()
                        elif time.time() - silence_start_time >= self.silence_duration:
                            # Verify minimum speech duration was satisfied
                            if speech_start_time and (time.time() - speech_start_time) >= self.min_speech_duration:
                                break

            if not audio_buffer:
                return np.array([], dtype=np.float32)

            # Concatenate all recorded frames
            full_audio = np.concatenate(audio_buffer, axis=0)

            # Convert to mono
            if full_audio.ndim > 1 and full_audio.shape[1] > 1:
                mono_audio = np.mean(full_audio, axis=1)
            else:
                mono_audio = full_audio.flatten()

            # Resample to 16 kHz
            resampled = self._resample_to_16k(mono_audio, native_sr)

            # Boost gain / normalize if audio is too quiet (< 0.5 peak)
            max_peak = float(np.max(np.abs(resampled)))
            if max_peak > 0.001:
                resampled = (resampled / max_peak) * 0.95

            return resampled

        except Exception as e:
            logger.warning(f"Microphone recording failed: {e}")
            return np.array([], dtype=np.float32)
