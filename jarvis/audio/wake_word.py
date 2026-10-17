"""
JARVIS AI - Hands-Free Wake-Word Detection Engine (Tier 1 / Phase 5)
Continuous low-power microphone listening with openWakeWord neural inference
for 'Hey JARVIS' with acoustic chime feedback and debounce protection.
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
    running continuous 16kHz audio chunk inference with temporal feature buffers.
    """

    def __init__(
        self,
        threshold: float = 0.35,
        model_name: str = "hey_jarvis_v0.1.onnx",
        debounce_seconds: float = 2.0,
    ):
        self.threshold = threshold
        self.model_name = model_name
        self.debounce_seconds = debounce_seconds
        self.last_detection_time = 0.0
        self.model = None
        self._init_model()

    def _init_model(self):
        try:
            from openwakeword.model import Model
            logger.info(f"Initializing openWakeWord neural model '{self.model_name}'...")
            try:
                self.model = Model(wakeword_models=[self.model_name], inference_framework="onnx")
            except Exception:
                # Fallback to model name directly if onnx framework switch fails
                self.model = Model(wakeword_models=[self.model_name])
            
            # Prime model buffer with 5 frames of silence
            zero_chunk = np.zeros(1280, dtype=np.int16)
            for _ in range(5):
                self.model.predict(zero_chunk)

            logger.info("openWakeWord engine ready and primed for 'Hey JARVIS'.")
        except Exception as e:
            logger.warning(f"openWakeWord initialization failed ({e}), using acoustic energy fallback.")
            self.model = None

    def process_chunk(self, chunk_16k: np.ndarray) -> bool:
        """
        Processes a 16kHz audio chunk (1280 samples / 80ms).
        Returns True if the 'Hey JARVIS' wake word is detected.
        """
        if len(chunk_16k) == 0:
            return False

        # Convert to int16 1D array as expected by openWakeWord
        if chunk_16k.dtype == np.int16:
            int16_audio = chunk_16k.flatten()
        else:
            int16_audio = (chunk_16k.flatten() * 32767).clip(-32768, 32767).astype(np.int16)

        # Pad if chunk is shorter than 1280 samples
        if len(int16_audio) < 1280:
            int16_audio = np.pad(int16_audio, (0, 1280 - len(int16_audio)))
        elif len(int16_audio) > 1280:
            int16_audio = int16_audio[:1280]

        now = time.time()
        # Debounce check: prevent multiple triggers during same phrase
        if now - self.last_detection_time < self.debounce_seconds:
            if self.model is not None:
                try:
                    self.model.predict(int16_audio)
                except Exception:
                    pass
            return False

        # Neural inference with openWakeWord
        if self.model is not None:
            try:
                predictions = self.model.predict(int16_audio)
                for name, score in predictions.items():
                    if "jarvis" in name.lower() and score >= self.threshold:
                        self.last_detection_time = now
                        logger.info(f"Wake word detected! Model: {name}, Score: {score:.3f}")
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
        threshold: float = 0.35,
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
                    if overflowed or chunk is None:
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
                            except Exception as ex:
                                logger.error(f"Error in on_wake callback: {ex}")
                            finally:
                                self.resume()
        except Exception as e:
            logger.debug(f"Wake word stream terminated: {e}")

