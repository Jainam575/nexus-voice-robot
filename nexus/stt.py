"""
Nexus Robot — STT with Circuit Breaker (Bug #27, #31)

If the STT API fails repeatedly, the circuit opens and further calls
return immediately with an error instead of hammering the API.
After CB_RECOVERY_TIMEOUT seconds, the circuit half-opens for a retry.
"""
import time
import logging
import requests
from enum import Enum

from .config import (SARVAM_KEY, SARVAM_STT_MODEL, STT_LANGUAGE_CODE,
                      CB_FAILURE_THRESHOLD, CB_RECOVERY_TIMEOUT, AUDIO_FILE)
from .latency import latency

logger = logging.getLogger("Nexus.STT")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Simple circuit breaker for network services (Bug #27)."""

    def __init__(self, failure_threshold=CB_FAILURE_THRESHOLD,
                 recovery_timeout=CB_RECOVERY_TIMEOUT):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failures = 0
        self._state = CircuitState.CLOSED
        self._last_failure_time = 0
        self._lock = __import__("threading").Lock()

    @property
    def state(self):
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time > self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
            return self._state

    def allow(self):
        """Check if a request is allowed."""
        return self.state != CircuitState.OPEN

    def record_success(self):
        with self._lock:
            self._failures = 0
            self._state = CircuitState.CLOSED

    def record_failure(self):
        with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()
            if self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning("Circuit breaker OPENED after %d failures", self._failures)


_stt_breaker = CircuitBreaker()


def transcribe(wav_path=AUDIO_FILE, model=SARVAM_STT_MODEL, timeout=15):
    """
    Send WAV to Sarvam STT. Returns (text, error).
    Returns (None, "circuit-open") immediately if circuit breaker is open.
    """
    if not SARVAM_KEY:
        return None, "no-api-key"

    if not _stt_breaker.allow():
        logger.warning("STT circuit breaker open — skipping request")
        return None, "circuit-open"

    t0 = time.perf_counter()
    try:
        with open(wav_path, "rb") as f:
            resp = requests.post(
                "https://api.sarvam.ai/speech-to-text",
                headers={"api-subscription-key": SARVAM_KEY},
                files={"file": ("audio.wav", f, "audio/wav")},
                data={"model": model, "mode": "transcribe",
                      "language_code": STT_LANGUAGE_CODE},
                timeout=timeout,
            )
        if resp.status_code != 200:
            _stt_breaker.record_failure()
            return None, f"HTTP {resp.status_code}"

        text = resp.json().get("transcript", "")
        if text.strip():
            _stt_breaker.record_success()
            return text, None
        return None, "empty-transcript"
    except requests.exceptions.Timeout:
        _stt_breaker.record_failure()
        return None, "timeout"
    except requests.exceptions.ConnectionError:
        _stt_breaker.record_failure()
        return None, "connection-error"
    except Exception as e:
        _stt_breaker.record_failure()
        return None, str(e)
    finally:
        # Measured even on failure — the user waits either way (req. 6)
        latency.record("stt", time.perf_counter() - t0)
