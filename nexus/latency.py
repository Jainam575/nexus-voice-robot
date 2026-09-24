"""
Nexus Robot — Latency Instrumentation (vision-performance pass, requirement 6)

Lightweight, thread-safe latency recorder built on time.perf_counter().
Every pipeline component records its own metric so the actual bottleneck
can be identified instead of guessed:

    mic_recording        — audio_manager.record_to_wav()
    stt                  — Sarvam speech-to-text call
    camera_capture       — CameraManager.capture()
    tflite_preprocess    — input tensor preparation (resize + quantize)
    tflite_inference     — interpreter.set_tensor + invoke + get_tensor
    cloud_vision         — Sarvam scene-description call (incl. encode)
    ai_chat              — ask_ai() streaming (cloud chat)
    tts                  — speak() fetch + playback
    e2e_total            — end-to-end per handled voice command
    e2e_vision_fast      — simple vision question, local-only route
    e2e_vision_cloud     — deep vision question, cloud route

A rolling summary is logged every E2E_LOG_EVERY end-to-end measurements.

IMPORTANT: numbers logged on the dev machine are NOT Raspberry Pi
performance — validate on the target hardware before quoting them.
"""
import logging
import threading
import time
from collections import deque
from contextlib import contextmanager

logger = logging.getLogger("Nexus.Latency")

E2E_LOG_EVERY = 10
PI_VALIDATION_NOTE = ("Latency numbers above were measured on THIS machine — "
                      "they are not Raspberry Pi performance; validate on the "
                      "target hardware before quoting them.")


class LatencyRecorder:
    """Thread-safe rolling latency stats per metric name."""

    def __init__(self, max_samples=100):
        self._lock = threading.Lock()
        self._samples = {}            # name -> deque of seconds
        self._max_samples = max_samples
        self._e2e_count = 0

    def record(self, name, seconds):
        """Record one measurement (seconds) for a metric."""
        with self._lock:
            bucket = self._samples.get(name)
            if bucket is None:
                bucket = deque(maxlen=self._max_samples)
                self._samples[name] = bucket
            bucket.append(seconds)
            should_log = False
            if name == "e2e_total":
                self._e2e_count += 1
                should_log = self._e2e_count % E2E_LOG_EVERY == 0
        if should_log:
            self.log_summary()

    def last(self, name):
        with self._lock:
            bucket = self._samples.get(name)
            return bucket[-1] if bucket else None

    def summary(self):
        """dict name -> {count, last_s, avg_s, max_s}."""
        with self._lock:
            out = {}
            for name, bucket in self._samples.items():
                if not bucket:
                    continue
                vals = list(bucket)
                out[name] = {
                    "count": len(vals),
                    "last_s": round(vals[-1], 3),
                    "avg_s": round(sum(vals) / len(vals), 3),
                    "max_s": round(max(vals), 3),
                }
            return out

    def log_summary(self):
        """Log a compact one-line-per-metric summary."""
        stats = self.summary()
        if not stats:
            return
        logger.info("=== LATENCY SUMMARY (rolling, %d samples per metric) ===",
                    self._max_samples)
        for name in sorted(stats):
            s = stats[name]
            logger.info("  %-18s n=%-3d last=%-7.3fs avg=%-7.3fs max=%-7.3fs",
                        name, s["count"], s["last_s"], s["avg_s"], s["max_s"])
        logger.info("  NOTE: %s", PI_VALIDATION_NOTE)

    def reset(self):
        with self._lock:
            self._samples = {}
            self._e2e_count = 0


# Singleton
latency = LatencyRecorder()


@contextmanager
def measure(name):
    """Context manager that records elapsed wall time under a metric name.

    Example:
        with measure("stt"):
            text = call_api()
    """
    t0 = time.perf_counter()
    try:
        yield
    finally:
        latency.record(name, time.perf_counter() - t0)
