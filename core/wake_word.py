"""
Local wake-word detection for JARVIS ("Hey Jarvis").

Design goals:
  • ZERO cost when the feature is off — openwakeword is imported ONLY inside
    start()/install helpers, never at module load. If the user never enables
    wake word, none of this touches the app.
  • ZERO latency on the audio path — the microphone callback only ever does a
    cheap, non-blocking queue push (feed()); the actual model inference runs in
    this module's own background thread, so the real-time audio thread and the
    Gemini stream are never slowed.
  • Fully local & offline — audio fed here never leaves the machine; there is no
    network call except the one-time model download the user triggers from the UI.

openwakeword ships small ONNX models (a few MB each) and runs comfortably on a
CPU. The pretrained wake phrase used here is "Hey Jarvis".
"""

from __future__ import annotations

import importlib.util
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

# Pretrained openwakeword model that listens for "Hey Jarvis".
WAKE_MODEL = "hey_jarvis"

# Score in [0,1]; above this counts as a detection. Tunable per environment.
DEFAULT_THRESHOLD = 0.5

# Mic frames arrive at 16 kHz int16; this is just the detector's input rate.
SAMPLE_RATE = 16000


def is_installed() -> bool:
    """Check whether openwakeword is installed without importing it."""
    try:
        return importlib.util.find_spec("openwakeword") is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False
    except Exception:
        return False


def is_ready() -> bool:
    """
    True if openwakeword is installed AND its model files are present on disk.

    This is a cheap, deterministic file-existence check. It deliberately does
    NOT import openwakeword or construct a Model.

    Avoiding the package import here is important: this function can be called
    by the UI's background warm-up thread while the detector is importing
    openwakeword.model. Importing the package from both paths can cause a
    partially initialized module/circular-import error.

    Never raises.
    """
    try:
        # find_spec locates the package without executing its __init__.py.
        spec = importlib.util.find_spec("openwakeword")

        if spec is None or spec.origin is None:
            return False

        models_dir = (
            Path(spec.origin).resolve().parent
            / "resources"
            / "models"
        )

        if not models_dir.is_dir():
            return False

        has_wake = (
            any(models_dir.glob(f"{WAKE_MODEL}*.onnx"))
            or any(models_dir.glob(f"{WAKE_MODEL}*.tflite"))
        )

        has_mel = (
            any(models_dir.glob("melspectrogram*.onnx"))
            or any(models_dir.glob("melspectrogram*.tflite"))
        )

        has_emb = (
            any(models_dir.glob("embedding_model*.onnx"))
            or any(models_dir.glob("embedding_model*.tflite"))
        )

        return bool(has_wake and has_mel and has_emb)

    except Exception:
        return False


def install_and_download(
    logger: Callable[[str], None] = print,
    notify: Callable[[str], None] | None = None,
) -> tuple[bool, str]:
    """
    One-click setup for the UI button: pip-install openwakeword if missing,
    then download the wake model.

    Returns (ok, message). Never raises — every failure is reported through
    the returned message and the logger.
    """
    _tell = notify or (lambda _msg: None)

    try:
        if not is_installed():
            logger("Wake word: installing openwakeword (one-time)…")
            _tell("Wake word: installing openwakeword (one-time)…")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "openwakeword",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                output = (
                    result.stderr or result.stdout or ""
                ).strip().splitlines()

                detail = output[-1] if output else "Unknown pip error"
                return False, f"pip install failed: {detail[:160]}"

        # Download the pretrained melspectrogram, embedding and wake models.
        logger("Wake word: downloading models…")
        _tell("Wake word: downloading models…")

        try:
            import openwakeword.utils as _u

            try:
                _u.download_models([WAKE_MODEL])
            except TypeError:
                # Older openwakeword versions use a no-argument signature.
                _u.download_models()

        except Exception as e:
            return False, f"model download failed: {e}"

        if not is_ready():
            return False, "Installed, but the wake model files are missing."

        logger("Wake word: ready.")
        return True, "Wake word installed and ready."

    except Exception as e:
        return False, f"setup error: {e}"


class WakeWordDetector:
    """
    Runs the wake model in a dedicated thread.

    The mic thread calls feed() with raw int16 frames. Detections invoke
    on_detect() from the detector thread, so the callback must marshal to
    whatever event loop or UI it needs.
    """

    def __init__(
        self,
        on_detect: Callable[[], None],
        threshold: float = DEFAULT_THRESHOLD,
        logger: Callable[[str], None] = print,
        notify: Callable[[str], None] | None = None,
    ):
        self._on_detect = on_detect
        self._threshold = threshold
        self._logger = logger
        self._notify = notify or (lambda _msg: None)

        self._queue: queue.Queue = queue.Queue(maxsize=50)
        self._thread: threading.Thread | None = None

        self._running = False
        self._model = None
        self._ready = False

    def start(self) -> bool:
        """
        Load the model and spawn the inference thread.

        Returns True on success. Safe to call again — a no-op if already
        running. Never raises.
        """
        if self._running:
            return True

        try:
            # This is intentionally the only normal runtime location where
            # the OpenWakeWord model package is imported.
            from openwakeword.model import Model

            self._model = Model(
                wakeword_models=[WAKE_MODEL],
                inference_framework="onnx",
            )

        except Exception as e:
            self._logger(
                f"Wake word: could not load model — {e}"
            )
            self._notify(
                "Wake word unavailable — use the WAKE NOW button."
            )
            self._model = None
            self._ready = False
            return False

        self._running = True
        self._ready = True

        self._thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="WakeWordThread",
        )
        self._thread.start()

        self._logger("Wake word: listening for 'Hey Jarvis'.")
        return True

    def stop(self) -> None:
        """Stop the detector and release its model."""
        self._running = False

        # Unblock the inference thread if it is waiting on the queue.
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass

        self._model = None
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def feed(self, frame_int16) -> None:
        """
        Called from the mic callback.

        Must stay cheap and never block. The frame is copied and dropped if
        the queue is backed up.
        """
        if not self._running:
            return

        try:
            # frame_int16 is a NumPy int16 array, possibly 2-D mono.
            data = (
                frame_int16[:, 0].copy()
                if getattr(frame_int16, "ndim", 1) > 1
                else frame_int16.copy()
            )

            self._queue.put_nowait(data)

        except queue.Full:
            pass
        except Exception:
            pass

    def _loop(self) -> None:
        """Consume queued microphone frames and run wake-word inference."""
        import numpy as np

        while self._running:
            try:
                frame = self._queue.get()

                if frame is None or not self._running:
                    break

                scores = self._model.predict(
                    np.asarray(frame, dtype=np.int16)
                )

                score = 0.0

                if isinstance(scores, dict):
                    # Match the Jarvis model regardless of exact key suffix.
                    for key, value in scores.items():
                        if "jarvis" in key.lower():
                            score = max(score, float(value))

                    if score == 0.0 and scores:
                        score = max(
                            float(value)
                            for value in scores.values()
                        )

                if score >= self._threshold:
                    # Drain any backlog so we don't double-fire on the same
                    # utterance.
                    self._drain()

                    try:
                        self._on_detect()
                    except Exception as e:
                        self._logger(
                            f"Wake word: on_detect error — {e}"
                        )

            except Exception as e:
                self._logger(
                    f"Wake word: inference error — {e}"
                )

    def _drain(self) -> None:
        """Remove queued frames after a detection."""
        try:
            while True:
                self._queue.get_nowait()
        except Exception:
            pass