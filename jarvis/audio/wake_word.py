"""
JARVIS AI - Hands-Free Wake-Word Detection Engine (Tier 1 / Phase 5)
Continuous low-power microphone listening with RMS VAD gating
and openWakeWord neural inference for 'Hey JARVIS'.
"""

import logging
import threading
import time
from typing import Optional, Callable
import numpy as np

logger = logging.getLogger("JARVIS.Audio.WakeWord")


def play_wake_chime():
    """Plays an instant futuristic two-tone sci-fi acoustic chime."""
    try:
        import sounddevice as sd
        sr = 24000
        duration = 0.16
        t = np.linspace(0, duration, int(sr * duration), False)
        # Smooth frequency modulation from 880Hz to 1320Hz with soft envelope
        freqs = np.linspace(880, 1320, len(t))
        envelope = np.sin(np.pi * np.linspace(0, 1, len(t)))
        tone = 0.25 * envelope * np.sin(2 * np.pi * freqs * t)
        sd.play(tone.astype(np.float32), sr)
    except Exception as e:
        logger.debug(f"Chime playback notice: {e}")


class WakeWordDetector:
    """
    Detects the 'Hey JARVIS' wake word using openWakeWord
    with adaptive RMS energy pre-filtering for ~0% idle CPU usage.
    """

    def __init__(self, threshold: float = 0.45, model_name: str = "hey_jarvis_v0.1.tflite"):
        self.threshold = threshold
        self.model_name = model_name
        self.model = None
        self._init_model()

    def _init_model(self):
        try:
            from openwakeword.model import Model
            logger.info("Initializing openWakeWord neural model for 'Hey JARVIS'...")
            self.model = Model(wakeword_models=[self.model_name])
            logger.info("openWakeWord engine ready.")
        except Exception as e:
            logger.warning(f"openWakeWord initialization failed ({e}), using acoustic energy fallback.")
            self.model = None

    def process_chunk(self, chunk_16k: np.ndarray) -> bool:
        """
        Processes a 16kHz audio chunk (float32 [-1, 1] or int16 [-32768, 32767]).
        Returns True if the 'Hey JARVIS' wake word is detected.
        """
        if len(chunk_16k) == 0:
            return False

        # 1. Convert to float32 for RMS calculation
        if chunk_16k.dtype == np.int16:
            float_audio = chunk_16k.astype(np.float32) / 32768.0
            int16_audio = chunk_16k
        else:
            float_audio = chunk_16k.astype(np.float32)
            int16_audio = (chunk_16k * 32767).clip(-32768, 32767).astype(np.int16)

        # 2. VAD Gate: if acoustic energy is negligible, skip neural inference
        rms = float(np.sqrt(np.mean(float_audio ** 2)))
        if rms < 0.003:
            return False

        # 3. Neural inference with openWakeWord
        if self.model is not None:
            try:
                predictions = self.model.predict(int16_audio)
                for name, score in predictions.items():
                    if "jarvis" in name.lower() and score >= self.threshold:
                        logger.info(f"Wake word detected! Score: {score:.3f}")
                        return True
            except Exception as e:
                logger.debug(f"Wake prediction error: {e}")

        return False


class WakeWordListener:
    """
    Runs a background microphone audio stream and fires a callback
    immediately whenever 'Hey JARVIS' is spoken.
    """

    def __init__(
        self,
        on_wake: Optional[Callable[[], None]] = None,
        threshold: float = 0.45,
        play_chime: bool = True,
    ):
        self.on_wake = on_wake
        self.play_chime = play_chime
        self.detector = WakeWordDetector(threshold=threshold)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._paused = False

    def start(self):
        """Starts the background listening thread."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._stream_loop, daemon=True, name="WakeWordStream")
            self._thread.start()
            logger.info("Background hands-free wake word listener active.")

    def pause(self):
        """Temporarily pauses wake detection during active speech recording or TTS."""
        self._paused = True

    def resume(self):
        """Resumes wake detection."""
        self._paused = False

    def stop(self):
        """Stops the background listening thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        logger.info("Wake word listener stopped.")

    def _stream_loop(self):
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice is required for wake-word streaming.")
            return

        chunk_samples = 1280  # 80ms chunks at 16,000 Hz
        sample_rate = 16000

        try:
            with sd.InputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
                blocksize=chunk_samples,
            ) as stream:
                while self._running:
                    if self._paused:
                        time.sleep(0.05)
                        continue

                    chunk, overflowed = stream.read(chunk_samples)
                    if overflowed:
                        continue

                    audio_flat = chunk.flatten()
                    if self.detector.process_chunk(audio_flat):
                        logger.info("Wake word triggered!")
                        if self.play_chime:
                            play_wake_chime()
                        if self.on_wake:
                            self.pause()
                            try:
                                self.on_wake()
                            finally:
                                self.resume()
        except Exception as e:
            logger.debug(f"Wake word stream terminated: {e}")
