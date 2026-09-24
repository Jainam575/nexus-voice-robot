#!/usr/bin/env python3
"""
Nexus Robot v3.0.0 — ALL-IN-ONE single-file build.

This file is the complete Nexus package (originally nexus/*.py, 23 modules
plus the run_nexus.py entry point) combined into ONE standalone Python
file with no features removed:

    config, logging_config, latency, safety, collision, motor,
    command_parser, audio, tts, stt, camera, mood, memory, vision,
    navigation, face_display, face_recognition, games, weather, news,
    shutdown, safety_listener, main

Behaviour notes (identical to the original package):
- Data folders live NEXT TO this script: known_faces/, vision_memory/ and
  nexus_memory.json are created/loaded from this file's own directory.
- The model files (ssd_mobilenet_v1_coco.tflite / detect.tflite,
  coco_labels.txt) and the wake-word file (hey-Nexus_...ppn) are looked up
  in the current working directory, exactly as before.
- Optional hardware/libraries (RPi.GPIO, cv2, numpy, pygame, tflite,
  pvporcupine, openai, webrtcvad, audioop) are all still optional and
  guarded — the file imports and runs on any machine, full features light
  up on the robot.
- Each subsystem keeps its original log name (Nexus.Audio, Nexus.Motor, ...).

Run it exactly like run_nexus.py:

    python3 nexus_all_in_one.py
"""

__version__ = "3.0.0"



# ==========================================================================
# ======== MODULE: nexus/config.py ===============================
# ==========================================================================
# """
# Nexus Robot — Centralized Configuration
# All configuration in one place. No hard-coded device strings elsewhere.
# """
import os

# ==================== AUDIO (Bug #5, #6, #23) ====================
MIC_DEVICE = os.getenv("MIC_DEVICE", "plughw:2,0")
TTS_DEVICE = os.getenv("TTS_DEVICE", "hw:1,0")
SAMPLE_RATE = 16000
CHANNELS = 1
AUDIO_FORMAT = "S16_LE"
AUDIO_FILE = os.getenv("NEXUS_AUDIO_FILE", "/tmp/robot_audio.wav")

# Recording
RECORD_SECONDS_MAX = 8
SILENCE_THRESHOLD = 3
RMS_SILENCE_THRESHOLD = 300
VAD_MODE = 2
FRAME_DURATION_MS = 30

# ==================== API KEYS (Bug #3 — offline-safe) ====================
SARVAM_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_STT_MODEL = os.getenv("SARVAM_STT_MODEL", "saaras:v3")
STT_LANGUAGE_CODE = os.getenv("STT_LANGUAGE_CODE", "en-IN")
TTS_LANGUAGE_CODE = os.getenv("TTS_LANGUAGE_CODE", "en-IN")
SARVAM_CHAT_MODEL = os.getenv("SARVAM_CHAT_MODEL", "sarvam-105b-conversations")
SARVAM_VISION_MODEL = os.getenv("SARVAM_VISION_MODEL", "gemma4")

# TTS
NEXUS_VOICE = os.getenv("NEXUS_VOICE", "shubh")

# ==================== ALTERNATE VISION PROVIDER (2026-09) ====================
# Any OpenAI-compatible vision endpoint works (Groq recommended — fast and
# has a free tier). Set these to bypass the Sarvam gemma4 /v2 beta gate:
#   NEXUS_VISION_API_KEY   API key for the provider
#   NEXUS_VISION_BASE_URL  e.g. https://api.groq.com/openai/v1
#   NEXUS_VISION_MODEL     e.g. qwen/qwen3.6-27b (must accept image input)
# When unset (or key/base_url empty), the robot falls back to Sarvam gemma4.
NEXUS_VISION_API_KEY = os.getenv("NEXUS_VISION_API_KEY", "")
NEXUS_VISION_BASE_URL = os.getenv("NEXUS_VISION_BASE_URL", "")
NEXUS_VISION_MODEL = os.getenv("NEXUS_VISION_MODEL", "qwen/qwen3.6-27b")

# ==================== REPLY LANGUAGE (2026-09) ====================
# e.g. NEXUS_REPLY_LANGUAGE=Gujarati -> the chat LLM writes every reply in
# that language (TTS auto-detects the script and picks the matching voice).
# Empty (default) = the LLM mirrors whatever language the user speaks.
NEXUS_REPLY_LANGUAGE = os.getenv("NEXUS_REPLY_LANGUAGE", "")

# ==================== VISION ====================
MODEL_FILE = "ssd_mobilenet_v1_coco.tflite" if os.path.exists("ssd_mobilenet_v1_coco.tflite") else "detect.tflite"
LABELS_FILE = "coco_labels.txt"
DETECTION_THRESHOLD = 0.5
VISION_CAPTURE_PATH = os.getenv("NEXUS_VISION_CAPTURE_PATH", "/tmp/nexus_vision.jpg")

# ==================== FACE DISPLAY ====================
FACE_WIDTH = int(os.environ.get("FACE_WIDTH", 480))
FACE_HEIGHT = int(os.environ.get("FACE_HEIGHT", 320))
FACE_FULLSCREEN = os.environ.get("FACE_FULLSCREEN", "1") != "0"

# ==================== FACE RECOGNITION ====================
# LBPH "distance" — LOWER means a better match. 80 (2026-09, up from 70)
# gives a friendlier acceptance band now that crops are size-normalized.
FACE_CONFIDENCE_THRESHOLD = float(os.getenv("FACE_CONFIDENCE_THRESHOLD", "80"))
FACE_ENROLL_SAMPLES = int(os.getenv("FACE_ENROLL_SAMPLES", "12"))
FACE_MIN_SIZE = 60
KNOWN_FACES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "known_faces")
FACE_RECOGNIZER_FILE = os.path.join(KNOWN_FACES_DIR, "lbph_trainer.yml")

# ==================== NAVIGATION ====================
NAV_BBOX_CLOSE_THRESHOLD = float(os.getenv("NAV_BBOX_CLOSE_THRESHOLD", "0.25"))
NAV_MAX_STEPS = 10

# ==================== GUARD MODE ====================
GUARD_INTERVAL = 3
GUARD_MOTION_THRESHOLD = 25
GUARD_PIXEL_RATIO = 0.02
GUARD_MAX_DURATION = 600

# ==================== BEHAVIOR ====================
IDLE_SLEEP_THRESHOLD = int(os.getenv("NEXUS_SLEEP_THRESHOLD", "180"))
MAX_HISTORY_MESSAGES = 20
MAX_REMEMBERED_FACTS = 50
VISION_CONTEXT_TTL = 30  # seconds before vision context expires (Bug #12)
# Max age (seconds) of cached VisionWorker frame+detections that a fast
# vision answer may use; older caches fall back to a fresh capture (perf req. 9)
VISION_CACHE_AGE = float(os.getenv("NEXUS_VISION_CACHE_AGE", "2.0"))

# ==================== MOTOR ====================
# All pins are environment-overridable so wiring changes never need a
# rebuild: NEXUS_MOTOR_A_EN / _IN1 / _IN2, NEXUS_MOTOR_B_EN / _IN3 / _IN4.
# 2026-09-16: MOTOR_B_IN4 moved from GPIO 26 (physical pin 37) to GPIO 23
# (physical pin 16) — pin 37 proved dead on the user's Pi (motor probe test).
def _motor_pin(env_name, default):
    return int(os.getenv(env_name, str(default)))

MOTOR_A_EN = _motor_pin("NEXUS_MOTOR_A_EN", 5)
MOTOR_A_IN1 = _motor_pin("NEXUS_MOTOR_A_IN1", 6)
MOTOR_A_IN2 = _motor_pin("NEXUS_MOTOR_A_IN2", 12)
MOTOR_B_EN = _motor_pin("NEXUS_MOTOR_B_EN", 13)
MOTOR_B_IN3 = _motor_pin("NEXUS_MOTOR_B_IN3", 16)
MOTOR_B_IN4 = _motor_pin("NEXUS_MOTOR_B_IN4", 23)

# If turn left/right come out physically reversed (channel A/B wired to the
# opposite sides of the robot), run with NEXUS_MOTOR_SWAP_AB=1 — no rewiring
# needed, this swaps the two channels' pins in software.
if os.getenv("NEXUS_MOTOR_SWAP_AB", "0") == "1":
    MOTOR_A_EN, MOTOR_B_EN = MOTOR_B_EN, MOTOR_A_EN
    MOTOR_A_IN1, MOTOR_B_IN3 = MOTOR_B_IN3, MOTOR_A_IN1
    MOTOR_A_IN2, MOTOR_B_IN4 = MOTOR_B_IN4, MOTOR_A_IN2

DEFAULT_SPEED = 80

# Motor self-test (Bug #21 — disabled by default)
MOTOR_SELF_TEST = os.getenv("NEXUS_MOTOR_SELF_TEST", "0") == "1"

# Motor watchdog (Bug #5)
MOTOR_WATCHDOG_TIMEOUT = float(os.getenv("MOTOR_WATCHDOG_TIMEOUT", "5.0"))

# ==================== COLLISION SAFETY (P0 #6) ====================
COLLISION_SENSOR_ENABLED = os.getenv("NEXUS_COLLISION_SENSOR", "0") == "1"
COLLISION_SENSOR_TYPE = os.getenv("COLLISION_SENSOR_TYPE", "none")  # tof, ultrasonic, lidar, bumper, none
COLLISION_DISTANCE_THRESHOLD = float(os.getenv("COLLISION_DISTANCE_THRESHOLD", "0.3"))  # meters
COLLISION_GPIO_TRIG = int(os.getenv("COLLISION_GPIO_TRIG", "20"))
COLLISION_GPIO_ECHO = int(os.getenv("COLLISION_GPIO_ECHO", "21"))

# ==================== FACE PRIVACY (P1 #13) ====================
FACE_STORAGE_ENABLED = os.getenv("NEXUS_FACE_STORAGE", "1") == "1"
FACE_DATA_RETENTION = int(os.getenv("FACE_DATA_RETENTION", "0"))  # 0 = unlimited, N = max samples per person
FACE_FILE_PERMISSIONS = 0o600
FACE_DIR_PERMISSIONS = 0o700

# ==================== MOTOR COMMAND TIMEOUT (P1 #16) ====================
MOTOR_COMMAND_TIMEOUT = float(os.getenv("MOTOR_COMMAND_TIMEOUT", "10.0"))

# ==================== DEMO MODE (P2 #30) ====================
DEMO_MODE_CONFIRMATION = os.getenv("NEXUS_DEMO_CONFIRMATION", "1") == "1"

# ==================== CIRCUIT BREAKER (Bug #27) ====================
CB_FAILURE_THRESHOLD = 3
CB_RECOVERY_TIMEOUT = 60  # seconds before retrying after circuit opens

# ==================== PATHS ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "nexus_memory.json")
VISION_MEMORY_DIR = os.path.join(BASE_DIR, "vision_memory")
VISION_MEMORY_FILE = os.path.join(VISION_MEMORY_DIR, "vision_log.json")
MAX_VISION_MEMORY = 20

# ==================== WEATHER / NEWS ====================
WEATHER_LOCATION = os.getenv("WEATHER_LOCATION", "")
NEWS_TOPIC = os.getenv("NEWS_TOPIC", "")

# Mood colors shared across modules
MOOD_COLORS = {
    "neutral":  (60, 200, 255),
    "happy":    (90, 230, 140),
    "sleepy":   (100, 130, 200),
    "annoyed":  (230, 100, 90),
    "excited":  (255, 200, 50),
    "curious":  (170, 120, 255),
}

FACE_VALID_STATES = {"idle", "listening", "thinking", "talking", "happy", "sad",
                      "moving", "asleep", "playing", "navigating", "guarding"}

NEXUS_PERSONALITY = "Nexus is energetic, creative, and always ready to help with excitement and enthusiasm."

# Wake word
KEYWORD_PATH = "hey-Nexus_en_raspberry-pi_v3_0_0.ppn"


# ==========================================================================
# ======== MODULE: nexus/logging_config.py =======================
# ==========================================================================
# """Nexus Robot — Structured logging configuration (Bug #25)."""
import logging
import sys


def setup_logging(level=logging.INFO):
    """Configure structured logging with levels for all subsystems."""
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=level,
        format=fmt,
        stream=sys.stdout,
        force=True,
    )
    # Reduce noise from libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    return logging.getLogger("Nexus")


logger_logging_config = setup_logging()


# ==========================================================================
# ======== MODULE: nexus/latency.py ==============================
# ==========================================================================
# """
# Nexus Robot — Latency Instrumentation (vision-performance pass, requirement 6)
#
# Lightweight, thread-safe latency recorder built on time.perf_counter().
# Every pipeline component records its own metric so the actual bottleneck
# can be identified instead of guessed:
#
    # mic_recording        — audio_manager.record_to_wav()
    # stt                  — Sarvam speech-to-text call
    # camera_capture       — CameraManager.capture()
    # tflite_preprocess    — input tensor preparation (resize + quantize)
    # tflite_inference     — interpreter.set_tensor + invoke + get_tensor
    # cloud_vision         — Sarvam scene-description call (incl. encode)
    # ai_chat              — ask_ai() streaming (cloud chat)
    # tts                  — speak() fetch + playback
    # e2e_total            — end-to-end per handled voice command
    # e2e_vision_fast      — simple vision question, local-only route
    # e2e_vision_cloud     — deep vision question, cloud route
#
# A rolling summary is logged every E2E_LOG_EVERY end-to-end measurements.
#
# IMPORTANT: numbers logged on the dev machine are NOT Raspberry Pi
# performance — validate on the target hardware before quoting them.
# """
import logging
import threading
import time
from collections import deque
from contextlib import contextmanager

logger_latency = logging.getLogger("Nexus.Latency")

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
        logger_latency.info("=== LATENCY SUMMARY (rolling, %d samples per metric) ===",
                    self._max_samples)
        for name in sorted(stats):
            s = stats[name]
            logger_latency.info("  %-18s n=%-3d last=%-7.3fs avg=%-7.3fs max=%-7.3fs",
                        name, s["count"], s["last_s"], s["avg_s"], s["max_s"])
        logger_latency.info("  NOTE: %s", PI_VALIDATION_NOTE)

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


# ==========================================================================
# ======== MODULE: nexus/safety.py ===============================
# ==========================================================================
# """
# Nexus Robot — Safety Controller & Motor Watchdog (Review P0 #1, #4, #5, #6)
#
# Architecture:
    # AI / Voice / Vision
           # ↓
     # Intent Parser
           # ↓
    # SafetyController  ← always has final authority
           # ↓                ← CollisionSensor (physical layer)
      # Motor Queue
           # ↓
     # Motor Worker (single thread owns GPIO)
           # ↓
        # GPIO
           # ↑
    # MotorWatchdog (independent — triggers emergency-stop EVENT,
                   # never touches GPIO directly per Review #1)
#
# The SafetyController uses a command-generation system: every movement gets a
# generation ID. STOP invalidates the current generation, so any in-flight
# movement that checks its generation will abort.
#
# States: STOPPED → MOVING → STOPPED (normal)
        # STOPPED → MOVING → FAULT (worker failure / watchdog)
        # FAULT requires explicit clear_fault() before movement resumes (Review #4)
# """
import threading
import time
import logging

logger_safety = logging.getLogger("Nexus.Safety")

# Safety states
STATE_STOPPED = "stopped"
STATE_MOVING = "moving"
STATE_FAULT = "fault"


class SafetyController:
    """
    Single authority over whether movement is allowed.
    - STOP has unconditional priority (Review #5).
    - Uses a generation counter: each movement gets a generation ID.
      STOP bumps the generation, invalidating all prior movements.
    - FAULT state after watchdog/worker failure — requires controlled
      recovery (Review #4).
    - CollisionSensor integration (Review #6).
    """

    def __init__(self):
        self._generation = 0
        self._lock = threading.Lock()
        self._state = STATE_STOPPED
        self._stop_time = time.time()
        self._fault_reason = None
        self._collision_sensor = None  # injected by MotorController

    def set_collision_sensor(self, sensor):
        """Inject the physical collision-sensor (Review #6)."""
        self._collision_sensor = sensor

    def get_generation(self):
        with self._lock:
            return self._generation

    def get_state(self):
        with self._lock:
            return self._state

    # ------------------------------------------------------------------
    # STOP — highest priority (Review #5)
    # ------------------------------------------------------------------
    def request_stop(self, reason="manual"):
        """STOP — highest priority. Invalidates all in-flight movements.

        A FAULT is NOT cleared by a plain STOP (Review #4) — a STOP only bumps
        the generation so in-flight movement aborts, and marks STOPPED when the
        system was MOVING. Controlled recovery from FAULT still requires
        clear_fault(). This prevents a spoken "stop" from silently resetting a
        watchdog/collision fault and allowing motion again.
        """
        with self._lock:
            self._generation += 1
            if self._state != STATE_FAULT:
                self._state = STATE_STOPPED
            self._stop_time = time.time()
            logger_safety.warning("STOP issued (reason=%s, generation=%d, state=%s)",
                           reason, self._generation, self._state)

    # ------------------------------------------------------------------
    # EMERGENCY STOP — watchdog / critical failure (Review #1, #4)
    # ------------------------------------------------------------------
    def emergency_stop(self, reason="watchdog"):
        """
        Atomically (Review #4):
        1. Invalidate the active command generation.
        2. Set state = FAULT.
        3. Mark stopped.
        4. Record the fault.

        Does NOT touch GPIO — that is the Motor Worker's job via the queue
        (Review #1). The watchdog calls this to *request* an e-stop; the
        Motor Worker performs the actual GPIO cutoff.
        """
        with self._lock:
            self._generation += 1
            self._state = STATE_FAULT
            self._fault_reason = reason
            self._stop_time = time.time()
            logger_safety.critical("EMERGENCY STOP (reason=%s, generation=%d, state=FAULT)",
                            reason, self._generation)

    def clear_fault(self):
        """Controlled recovery: transition FAULT → STOPPED (Review #4)."""
        with self._lock:
            if self._state == STATE_FAULT:
                self._state = STATE_STOPPED
                self._fault_reason = None
                logger_safety.info("Fault cleared — robot ready for controlled recovery")

    def get_fault_reason(self):
        with self._lock:
            return self._fault_reason

    # ------------------------------------------------------------------
    # Movement approval (with collision check — Review #6)
    # ------------------------------------------------------------------
    def request_movement(self):
        """
        Request permission to start a new movement.
        Returns the generation ID, or None if denied.

        Denied when:
        - A movement is already in progress.
        - State is FAULT (requires clear_fault first).
        - Collision sensor detects an imminent obstacle (Review #6).
        """
        # Collision check before acquiring the movement lock
        if self._collision_sensor is not None and self._collision_sensor.is_collision_imminent():
            logger_safety.warning("Movement DENIED — collision imminent (Review #6)")
            return None

        with self._lock:
            if self._state == STATE_FAULT:
                logger_safety.warning("Movement DENIED — system in FAULT state (reason=%s)", self._fault_reason)
                return None
            if self._state == STATE_MOVING:
                return None
            self._state = STATE_MOVING
            gen = self._generation
            logger_safety.info("Movement approved (generation=%d)", gen)
            return gen

    def is_generation_valid(self, gen):
        with self._lock:
            return gen == self._generation

    def is_stopped(self):
        with self._lock:
            return self._state in (STATE_STOPPED, STATE_FAULT)

    def is_fault(self):
        with self._lock:
            return self._state == STATE_FAULT

    def mark_complete(self, gen):
        """Mark a movement as completed (only if generation still valid)."""
        with self._lock:
            if gen == self._generation and self._state == STATE_MOVING:
                self._state = STATE_STOPPED

    def check_collision(self):
        """
        Runtime collision check during movement (Review #6).
        If collision is imminent, issue STOP.
        Returns True if collision was detected and movement interrupted.
        """
        if self._collision_sensor is None:
            return False
        if self._collision_sensor.is_collision_imminent():
            collision, distance = self._collision_sensor.get_distance()
            logger_safety.warning("Collision detected during movement (distance=%s) — STOP",
                           distance)
            self.request_stop(reason="collision-sensor")
            return True
        return False


class MotorWatchdog:
    """
    Independent watchdog (Review #1).

    If the motor worker hasn't sent a heartbeat within MOTOR_WATCHDOG_TIMEOUT
    seconds, the watchdog fires. Instead of directly touching GPIO (Review #1),
    it calls the emergency_stop callback, which:
    - Calls SafetyController.emergency_stop() to atomically reset state.
    - Enqueues a STOP command for the Motor Worker (which owns GPIO).

    If the worker is truly dead (thread hang), the STOP command won't be
    processed. A physical hardware motor-enable cutoff is the only fully
    reliable failsafe — the review recommends installing one independently.
    """

    def __init__(self, timeout, emergency_stop_callback):
        self._timeout = timeout
        self._emergency_stop = emergency_stop_callback
        self._last_heartbeat = time.time()
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def heartbeat(self):
        with self._lock:
            self._last_heartbeat = time.time()

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch, daemon=True)
        self._thread.start()
        logger_safety.info("Motor watchdog started (timeout=%.1fs)", self._timeout)

    def stop(self):
        self._running = False

    def join(self, timeout=2):
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _watch(self):
        check_interval = min(0.5, self._timeout / 4)
        while self._running:
            with self._lock:
                elapsed = time.time() - self._last_heartbeat
            if elapsed > self._timeout:
                logger_safety.critical(
                    "MOTOR WATCHDOG FIRED — no heartbeat for %.1fs. "
                    "Triggering emergency-stop EVENT (not direct GPIO).",
                    elapsed)
                try:
                    self._emergency_stop()
                except Exception as e:
                    logger_safety.error("Watchdog emergency-stop callback failed: %s", e)
                # Reset heartbeat to avoid repeated triggers
                with self._lock:
                    self._last_heartbeat = time.time()
            time.sleep(check_interval)


# ==========================================================================
# ======== MODULE: nexus/collision.py ============================
# ==========================================================================
# """
# Nexus Robot — Collision Safety Layer (P0 Review #6)
#
# Camera object detection is NOT collision detection. Vision can miss:
# - stairs, holes/drop-offs, transparent objects, thin objects,
# - objects below the camera, low obstacles, objects outside FOV,
# - rapidly approaching objects.
#
# This module provides a physical distance-sensing layer that the
# SafetyController uses to veto/override movement. Supported sensor types:
# - ultrasonic (HC-SR04 style, GPIO trig/echo)
# - tof (Time-of-Flight, I2C — stubbed unless hardware present)
# - lidar (serial — stubbed unless hardware present)
# - bumper (GPIO switch — always safe-on-trigger)
# - none (disabled — robot must be operated with extra caution)
#
# Architecture:
#
    # Camera Vision
         # ↓
    # Navigation
         # ↓
    # Safety Controller  ← CollisionSensor (this module)
         # ↓
       # Motor
#
# NOTE: For maximum safety, a hardware motor-enable cutoff / physical
# emergency-stop circuit independent of software should also be installed.
# """
import threading
import time
import logging


logger_collision = logging.getLogger("Nexus.Collision")

# Optional GPIO — not available on non-Pi systems
_GPIO = None
try:
    import RPi.GPIO as _GPIO
    _GPIO.setwarnings(False)
except Exception:
    _GPIO = None


class CollisionSensor:
    """
    Physical collision-detection layer.

    The sensor is polled by the SafetyController before/while approving
    movement. If an obstacle is closer than COLLISION_DISTANCE_THRESHOLD,
    movement is vetoed and active movement is interrupted.
    """

    def __init__(self, sensor_type=COLLISION_SENSOR_TYPE,
                 threshold=COLLISION_DISTANCE_THRESHOLD,
                 enabled=COLLISION_SENSOR_ENABLED):
        self.sensor_type = sensor_type
        self.threshold = threshold
        self.enabled = enabled and sensor_type in ("tof", "ultrasonic", "lidar", "bumper")
        self._lock = threading.Lock()
        self._last_reading = None       # meters, or True for bumper hit
        self._last_reading_time = 0.0
        self._reading_ttl = 0.2         # readings older than this are re-taken
        # A single transient ultrasonic misread (common on a loaded Pi) must not
        # brick all movement (H5). Require this many consecutive failures before
        # treating a sensor outage as a fail-safe collision.
        self._consecutive_failures = 0
        self._failure_threshold = 3
        self._reuse_window = 1.0        # reuse a recent good reading on a transient miss
        self._distance_func = self._make_distance_func()

    # ------------------------------------------------------------------
    def _make_distance_func(self):
        """Return the hardware-specific distance function, or None."""
        if not self.enabled:
            return None
        if self.sensor_type == "ultrasonic" and _GPIO is not None:
            _GPIO.setup(COLLISION_GPIO_TRIG, _GPIO.OUT)
            _GPIO.setup(COLLISION_GPIO_ECHO, _GPIO.IN)
            _GPIO.output(COLLISION_GPIO_TRIG, False)
            time.sleep(0.1)
            return self._read_ultrasonic
        if self.sensor_type == "bumper" and _GPIO is not None:
            return self._read_bumper
        # tof / lidar require external libraries/hardware — log clearly
        if self.sensor_type in ("tof", "lidar"):
            logger_collision.warning(
                "Collision sensor type '%s' configured but hardware driver "
                "not available — collision layer INACTIVE", self.sensor_type)
        return None

    def _read_ultrasonic(self):
        """HC-SR04 single reading in meters. Returns None on timeout."""
        try:
            _GPIO.output(COLLISION_GPIO_TRIG, True)
            time.sleep(0.00001)
            _GPIO.output(COLLISION_GPIO_TRIG, False)

            start = time.time()
            while _GPIO.input(COLLISION_GPIO_ECHO) == 0:
                if time.time() - start > 0.02:
                    return None
            pulse_start = time.time()
            while _GPIO.input(COLLISION_GPIO_ECHO) == 1:
                if time.time() - pulse_start > 0.02:
                    return None
            pulse_duration = time.time() - pulse_start
            return round(pulse_duration * 17150 / 100.0, 3)  # cm→m /100 after *17150
        except Exception as e:
            logger_collision.error("Ultrasonic read error: %s", e)
            return None

    def _read_bumper(self):
        """Bumper switch: True = pressed (collision). Returns None on error so
        the failure path (fail-safe) applies (L5)."""
        try:
            return _GPIO.input(COLLISION_GPIO_ECHO) == 1
        except Exception as e:
            logger_collision.error("Bumper read error: %s", e)
            return None

    # ------------------------------------------------------------------
    def get_distance(self):
        """
        Return (collision: bool, distance_or_None).
        Bumper sensors report (True, None) when pressed.
        """
        if not self.enabled or self._distance_func is None:
            # No physical sensor — collision layer cannot confirm safety.
            # Report "no collision" but callers must treat vision-only
            # operation as reduced-safety.
            return False, None

        with self._lock:
            now = time.time()
            if (now - self._last_reading_time) < self._reading_ttl \
                    and self._last_reading is not None:
                return self._evaluate(self._last_reading)

            reading = self._distance_func()
            if reading is None:
                # Sensor failure. A single transient miss is common (HC-SR04 on a
                # busy Pi) — do NOT immediately deny all movement (H5). Reuse the
                # last good reading if it is recent; only after N consecutive
                # failures do we treat the outage as a fail-safe collision.
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._failure_threshold:
                    logger_collision.warning("Collision sensor failed %d times in a row — fail-safe collision",
                                   self._consecutive_failures)
                    return True, None
                if self._last_reading is not None and (now - self._last_reading_time) < self._reuse_window:
                    return self._evaluate(self._last_reading)
                return False, None
            self._consecutive_failures = 0
            self._last_reading = reading
            self._last_reading_time = now
            return self._evaluate(reading)

    def _evaluate(self, reading):
        if self.sensor_type == "bumper":
            return bool(reading), None
        return reading < self.threshold, reading

    def is_collision_imminent(self):
        """True if an obstacle is closer than the safety threshold."""
        collision, _ = self.get_distance()
        return collision

    @property
    def active(self):
        """True if a real physical sensor is operational."""
        return self.enabled and self._distance_func is not None


# Singleton
collision_sensor = CollisionSensor()


# ==========================================================================
# ======== MODULE: nexus/motor.py ================================
# ==========================================================================
# """
# Nexus Robot — Motor Controller (Review P0 #1, #2, #3, #4, #5, #6; P2 #23, #24, #33)
#
# Single owner of all GPIO motor operations:
# - A dedicated motor worker thread (the ONLY thread that touches GPIO)
# - A command queue: all components submit commands, never touch GPIO
# - STOP is a high-priority command that jumps the queue (Review #5)
# - Command generation system: STOP invalidates all prior generations
# - Interruptible movement: checks generation + collision every 0.1s
# - Motor watchdog: triggers an emergency-stop EVENT routed through the
  # SafetyController → Motor Queue → Motor Worker (never touches GPIO
  # directly — Review #1)
# - Blocking/awaitable motor API: execute_move(..., wait=True) blocks until
  # the command finishes / is interrupted / fails / times out (Review #2)
# - Self-test goes through the same Motor Worker queue (Review #3)
# - Structured safety logging for every movement (Review #33)
#
# IMPORTANT: the watchdog e-stop path only works if the worker thread is
# alive. For guaranteed safety a physical motor-enable cutoff / hardware
# e-stop circuit independent of software is required (Review #1/#6).
# """
import threading
import queue
import time
import logging
from dataclasses import dataclass, field
from typing import Optional


logger_motor = logging.getLogger("Nexus.Motor")

# GPIO is optional — not available on non-Pi systems
_GPIO = None
_IS_PI = False
_pwm_a = None
_pwm_b = None


def _setup_gpio():
    """Configure motor pins + PWM. Called at import and on restart after cleanup (M6)."""
    global _pwm_a, _pwm_b
    for pin in (MOTOR_A_IN1, MOTOR_A_IN2, MOTOR_A_EN, MOTOR_B_IN3, MOTOR_B_IN4, MOTOR_B_EN):
        _GPIO.setup(pin, _GPIO.OUT)
    _pwm_a = _GPIO.PWM(MOTOR_A_EN, 1000)
    _pwm_b = _GPIO.PWM(MOTOR_B_EN, 1000)
    _pwm_a.start(0)
    _pwm_b.start(0)


try:
    import RPi.GPIO as _GPIO
    _GPIO.setwarnings(False)
    _GPIO.setmode(_GPIO.BCM)
    _setup_gpio()
    _IS_PI = True
    logger_motor.info("GPIO initialized with PWM")
except Exception as e:
    _IS_PI = False
    logger_motor.warning("GPIO not available: %s", e)


@dataclass
class MotorCommand:
    """A command for the motor worker."""
    action: str              # "forward", "back", "left", "right", "spin", "stop"
    duration: float = 1.0
    speed: int = DEFAULT_SPEED
    generation: int = 0      # safety generation ID
    priority: str = "normal" # "normal" or "stop"
    source: str = ""         # who issued this (for logging)
    done_event: Optional[threading.Event] = field(default=None, repr=False)
    result: dict = field(default_factory=dict, repr=False)  # execution result


class MotorController:
    """
    Single motor-control interface. All movement goes through here.
    No other component should touch motor GPIO pins.

    Uses a dedicated worker thread + command queue so that:
    - STOP can jump the queue (Review #5)
    - Only one thread accesses GPIO (Review #1)
    - Movement is interruptible (by STOP, watchdog, collision)
    - The watchdog triggers an e-stop EVENT, not GPIO (Review #1)
    - Callers can wait for completion (Review #2)
    """

    def __init__(self):
        self.safety = SafetyController()
        self.safety.set_collision_sensor(collision_sensor)
        self._cmd_queue: queue.Queue = queue.Queue()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._current_generation = -1
        self._cleaned_up = False
        self._gpio_torn_down = False
        self._cleanup_lock = threading.Lock()

        # Watchdog — routes an e-stop EVENT, never touches GPIO (Review #1)
        self._watchdog = MotorWatchdog(
            timeout=MOTOR_WATCHDOG_TIMEOUT,
            emergency_stop_callback=self._handle_watchdog_trigger,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self):
        """Start the motor worker thread and watchdog."""
        if self._running:
            return
        with self._cleanup_lock:
            self._cleaned_up = False
        # If GPIO was torn down by a previous cleanup(), re-initialize it so a
        # restart actually works (M6).
        if _IS_PI and self._gpio_torn_down:
            try:
                _setup_gpio()
                self._gpio_torn_down = False
            except Exception as e:
                logger_motor.error("GPIO re-initialization failed: %s", e)
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        self._watchdog.start()
        logger_motor.info("Motor controller started (worker + watchdog)")

    def join(self, timeout=3):
        """Wait for the worker thread to exit (Review #23)."""
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=timeout)
        self._watchdog.join(timeout=2)

    # ------------------------------------------------------------------
    # STOP — highest priority (Review #5)
    # ------------------------------------------------------------------
    def stop(self, source="stop_command"):
        """
        STOP — jumps the queue, highest priority (Review #5).
        Returns a threading.Event that is set when the STOP is executed
        by the worker (usable for startup verification — Review #21).
        """
        self.safety.request_stop(reason=source)
        # Clear the queue of any pending non-stop commands
        while not self._cmd_queue.empty():
            try:
                old = self._cmd_queue.get_nowait()
                if old.done_event is not None:
                    old.result = {"status": "invalidated", "reason": "superseded_by_stop"}
                    old.done_event.set()
            except queue.Empty:
                break
        # Put a stop command at the front
        ack = threading.Event()
        self._cmd_queue.put(MotorCommand(
            action="stop", duration=0, generation=self.safety.get_generation(),
            priority="stop", source=source, done_event=ack,
        ))
        return ack

    # ------------------------------------------------------------------
    # Emergency stop — watchdog / fault path (Review #1, #4)
    # ------------------------------------------------------------------
    def _handle_watchdog_trigger(self):
        """
        Called by the watchdog. Does NOT touch GPIO directly (Review #1).

        Atomically (Review #4):
        1. SafetyController.emergency_stop() — invalidate generation,
           set FAULT state, mark stopped, record fault.
        2. Clear the motor queue.
        3. Enqueue a STOP for the Motor Worker (owner of GPIO).

        If the worker is alive, it will perform the GPIO cutoff. If the
        worker is dead, a hardware e-stop circuit is the last line of
        defense (see module docstring).
        """
        self.safety.emergency_stop(reason="watchdog")
        # Clear queued commands
        while not self._cmd_queue.empty():
            try:
                old = self._cmd_queue.get_nowait()
                if old.done_event is not None:
                    old.result = {"status": "invalidated", "reason": "emergency_stop"}
                    old.done_event.set()
            except queue.Empty:
                break
        # Enqueue the stop for the worker (the GPIO owner)
        self._cmd_queue.put(MotorCommand(
            action="stop", duration=0,
            generation=self.safety.get_generation(),
            priority="stop", source="emergency_stop",
        ))

    def emergency_stop(self, reason="manual_e_stop"):
        """Public e-stop API (same path as watchdog)."""
        self._handle_watchdog_trigger()

    def clear_fault(self):
        """Controlled recovery after a fault (Review #4)."""
        self.safety.clear_fault()

    # ------------------------------------------------------------------
    # Movement API (Review #2 — blocking/awaitable)
    # ------------------------------------------------------------------
    def execute_move(self, direction, duration=1.0, speed=DEFAULT_SPEED,
                     source="", wait=False,
                     timeout=MOTOR_COMMAND_TIMEOUT):
        """
        Submit a movement command through the Motor Worker queue.

        Parameters
        ----------
        wait : bool
            If True, blocks until the command finishes / is interrupted /
            fails / times out (Review #2). Returns the result dict.
        timeout : float
            Max seconds to wait when wait=True (Review #16).
            No navigation loop can leave a command running indefinitely.

        Returns
        -------
        If wait=False: bool (True if accepted, False if denied by safety).
        If wait=True:  dict with keys:
            status  — "accepted" | "denied" | "completed" | "interrupted" |
                      "failed" | "timeout" | "invalidated"
            reason  — detail (optional)
        """
        gen = self.safety.request_movement()
        if gen is None:
            logger_motor.warning("Movement denied — safety state=%s (source=%s)",
                           self.safety.get_state(), source)
            if wait:
                return {"status": "denied", "reason": "safety_denied"}
            return False

        duration = max(0.0, min(duration, timeout))
        done_event = threading.Event() if wait else None
        cmd = MotorCommand(
            action=direction, duration=duration, speed=speed,
            generation=gen, priority="normal", source=source,
            done_event=done_event,
        )
        self._cmd_queue.put(cmd)

        if not wait:
            return True

        # Blocking wait (Review #2) — wait for the worker to signal completion
        total_timeout = duration + timeout
        if not cmd.done_event.wait(timeout=total_timeout):
            # Timed out — attempt to interrupt the movement
            self.safety.request_stop(reason="command_timeout")
            return {"status": "timeout", "reason": f"no completion in {total_timeout}s"}
        return cmd.result or {"status": "failed", "reason": "unknown"}

    def execute_command(self, text, source=""):
        """Parse and execute a movement command from text. Returns (success, action)."""
        recognized, action, duration = parse_movement_command(text)
        if not recognized:
            return False, None
        accepted = self.execute_move(action, duration, source=source)
        return accepted, action

    # ------------------------------------------------------------------
    # Worker — the ONLY thread that touches GPIO (Review #1, #3)
    # ------------------------------------------------------------------
    def _worker_loop(self):
        while self._running:
            try:
                cmd = self._cmd_queue.get(timeout=0.5)
            except queue.Empty:
                self._watchdog.heartbeat()
                continue

            self._watchdog.heartbeat()

            # FIX 2 (founder-demo): the shutdown command asks the WORKER to
            # perform the final physical stop + PWM teardown. The worker is
            # the sole GPIO owner — the calling thread never touches GPIO.
            if cmd.action == "shutdown":
                self._raw_stop()
                self._teardown_gpio()
                cmd.result = {"status": "completed", "reason": "shutdown"}
                if cmd.done_event is not None:
                    cmd.done_event.set()
                self._log_movement(cmd, "shutdown", "completed", "worker_exit")
                break  # worker exits cleanly after the final stop

            if cmd.priority == "stop" or cmd.action == "stop":
                self._raw_stop()
                if self.safety.get_state() != STATE_FAULT:
                    self.safety.mark_complete(cmd.generation)
                cmd.result = {"status": "completed", "reason": "stop_executed"}
                if cmd.done_event is not None:
                    cmd.done_event.set()
                self._log_movement(cmd, "stop", "completed", "n/a")
                continue

            # Check if this command's generation is still valid
            if not self.safety.is_generation_valid(cmd.generation):
                cmd.result = {"status": "invalidated", "reason": "generation_invalid"}
                if cmd.done_event is not None:
                    cmd.done_event.set()
                self._log_movement(cmd, "skipped", "invalidated", "generation")
                continue

            self._current_generation = cmd.generation
            result = self._execute_interruptible(cmd)
            cmd.result = result
            if cmd.done_event is not None:
                cmd.done_event.set()

    def _execute_interruptible(self, cmd: MotorCommand):
        """
        Execute movement with interruptible sleep. Only ever called from
        the worker thread (including for self-test — Review #3).
        Checks generation + collision every 0.1s.
        """
        # Pre-movement collision check (Review #6)
        if self.safety.check_collision():
            self._log_movement(cmd, cmd.action, "denied", "collision_imminent")
            return {"status": "denied", "reason": "collision_imminent"}

        if not _IS_PI:
            # Simulated movement — uses the REAL duration so navigation
            # sequencing and interruption behave like hardware (Review #2).
            # The watchdog must be heartbeated here too (C5) so simulated
            # moves that last longer than the watchdog timeout are not
            # spuriously interrupted into FAULT.
            self._log_movement(cmd, cmd.action, "simulated", "ok")
            elapsed = 0.0
            while elapsed < cmd.duration:
                if not self.safety.is_generation_valid(cmd.generation):
                    return {"status": "interrupted", "reason": "stop"}
                self._watchdog.heartbeat()
                time.sleep(0.01)
                elapsed += 0.01
            self.safety.mark_complete(cmd.generation)
            return {"status": "completed", "reason": "ok"}

        # Set motor direction
        try:
            if cmd.action == "forward":
                _GPIO.output(MOTOR_A_IN1, 1); _GPIO.output(MOTOR_A_IN2, 0)
                _GPIO.output(MOTOR_B_IN3, 1); _GPIO.output(MOTOR_B_IN4, 0)
            elif cmd.action == "back":
                _GPIO.output(MOTOR_A_IN1, 0); _GPIO.output(MOTOR_A_IN2, 1)
                _GPIO.output(MOTOR_B_IN3, 0); _GPIO.output(MOTOR_B_IN4, 1)
            elif cmd.action == "left":
                _GPIO.output(MOTOR_A_IN1, 0); _GPIO.output(MOTOR_A_IN2, 1)
                _GPIO.output(MOTOR_B_IN3, 1); _GPIO.output(MOTOR_B_IN4, 0)
            elif cmd.action == "right":
                _GPIO.output(MOTOR_A_IN1, 1); _GPIO.output(MOTOR_A_IN2, 0)
                _GPIO.output(MOTOR_B_IN3, 0); _GPIO.output(MOTOR_B_IN4, 1)
            elif cmd.action == "spin":
                _GPIO.output(MOTOR_A_IN1, 1); _GPIO.output(MOTOR_A_IN2, 0)
                _GPIO.output(MOTOR_B_IN3, 0); _GPIO.output(MOTOR_B_IN4, 1)
            else:
                self._raw_stop()
                self.safety.mark_complete(cmd.generation)
                return {"status": "failed", "reason": "unknown_action"}

            _pwm_a.ChangeDutyCycle(cmd.speed)
            _pwm_b.ChangeDutyCycle(cmd.speed)

            # Interruptible sleep: check generation + collision every 0.1s
            elapsed = 0.0
            while elapsed < cmd.duration:
                if not self.safety.is_generation_valid(cmd.generation):
                    logger_motor.info("Movement interrupted (gen=%d, elapsed=%.1fs)",
                                cmd.generation, elapsed)
                    self._raw_stop()
                    self._log_movement(cmd, cmd.action, "interrupted", "stop", elapsed)
                    return {"status": "interrupted", "reason": "stop"}
                # Runtime collision check (Review #6)
                if self.safety.check_collision():
                    self._raw_stop()
                    self._log_movement(cmd, cmd.action, "interrupted", "collision", elapsed)
                    return {"status": "interrupted", "reason": "collision"}
                self._watchdog.heartbeat()
                time.sleep(0.1)
                elapsed += 0.1

            self._raw_stop()
            self.safety.mark_complete(cmd.generation)
            self._log_movement(cmd, cmd.action, "completed", "ok", elapsed)
            return {"status": "completed", "reason": "ok"}

        except Exception as e:
            logger_motor.error("Motor execution error: %s", e, exc_info=True)
            self._raw_stop()
            self.safety.mark_complete(cmd.generation)
            self._log_movement(cmd, cmd.action, "failed", str(e))
            return {"status": "failed", "reason": str(e)}

    def _teardown_gpio(self):
        """
        Stop PWM and zero the motor pins. WORKER-THREAD ONLY (FIX 2).

        Called by the Motor Worker when it processes the 'shutdown'
        command, so the final GPIO teardown happens on the same thread that
        owns GPIO — never from cleanup()/main.
        """
        global _pwm_a, _pwm_b
        try:
            if _IS_PI:
                _GPIO.output(MOTOR_A_IN1, 0)
                _GPIO.output(MOTOR_A_IN2, 0)
                _GPIO.output(MOTOR_B_IN3, 0)
                _GPIO.output(MOTOR_B_IN4, 0)
                if _pwm_a is not None:
                    _pwm_a.stop()
                    _pwm_a = None
                if _pwm_b is not None:
                    _pwm_b.stop()
                    _pwm_b = None
        except Exception as e:
            logger_motor.error("GPIO teardown error: %s", e)
        finally:
            self._gpio_torn_down = True

    def _raw_stop(self):
        """Stop motors immediately (GPIO level). Worker-thread only."""
        if _IS_PI:
            try:
                _GPIO.output(MOTOR_A_IN1, 0)
                _GPIO.output(MOTOR_A_IN2, 0)
                _GPIO.output(MOTOR_B_IN3, 0)
                _GPIO.output(MOTOR_B_IN4, 0)
                _pwm_a.ChangeDutyCycle(0)
                _pwm_b.ChangeDutyCycle(0)
            except Exception as e:
                logger_motor.error("Raw stop failed: %s", e, exc_info=True)

    # ------------------------------------------------------------------
    # Structured safety logging (Review #33)
    # ------------------------------------------------------------------
    def _log_movement(self, cmd, action, result, reason, duration=None):
        """
        Structured safety log for every physical movement (Review #33).
        Never logs credentials or biometric data.
        """
        logger_motor.info(
            "SAFETY_EVENT | timestamp=%s | source=%s | intent=%s | duration=%s | "
            "safety=%s | result=%s | interruption_reason=%s",
            time.strftime("%Y-%m-%dT%H:%M:%S"),
            cmd.source or "unknown",
            action,
            f"{duration:.1f}" if duration is not None else f"{cmd.duration:.1f}",
            self.safety.get_state(),
            result,
            reason,
        )

    # ------------------------------------------------------------------
    # Self-test — through the SAME Motor Worker path (Review #3)
    # ------------------------------------------------------------------
    def self_test(self):
        """
        Safe motor self-test — only when explicitly enabled.
        Uses the same SafetyController → Motor Queue → Motor Worker path
        (Review #3). STOP can interrupt it; the watchdog can stop it;
        all safety limits apply.
        """
        if not MOTOR_SELF_TEST:
            logger_motor.info("Motor self-test skipped (set NEXUS_MOTOR_SELF_TEST=1 to enable)")
            return
        if not _IS_PI:
            logger_motor.info("Motor self-test skipped — not on Pi")
            return
        logger_motor.info("Motor self-test — short pulses at low speed (queued)")
        for direction in ("forward", "back"):
            result = self.execute_move(
                direction, duration=0.15, speed=30,
                source="self_test", wait=True, timeout=5.0,
            )
            if result.get("status") not in ("completed", "simulated"):
                logger_motor.warning("Self-test %s: %s", direction, result)
                return
        logger_motor.info("Motor self-test complete")

    # ------------------------------------------------------------------
    # Shutdown — idempotent (Review #24), joins worker (Review #23)
    # ------------------------------------------------------------------
    def cleanup(self):
        """
        Shutdown — stop everything. Idempotent (Review #24).

        FIX 2 (founder-demo): the calling thread NEVER touches motor GPIO.
        The sequence is:

            cleanup() called (main/shutdown thread)
                ↓
            in-flight movement invalidated (safety generation bump)
                ↓
            'shutdown' command queued for the Motor Worker
                ↓
            Motor Worker performs the physical STOP + PWM teardown
                ↓
            Motor Worker acknowledges (done_event) and exits
                ↓
            main thread joins the worker

        If the worker is dead or does not acknowledge within 3 s, NO GPIO
        is touched from this thread — a hardware motor-enable cutoff
        remains the last line of defense (see module docstring).
        """
        with self._cleanup_lock:
            if self._cleaned_up:
                return
            self._cleaned_up = True

        self._watchdog.stop()
        worker = self._worker_thread
        if worker is not None and worker.is_alive() and self._running:
            # Invalidate any in-flight movement first, so the worker is free
            # to pick up the shutdown command within ~0.1 s.
            self.safety.request_stop(reason="cleanup")
            ack = threading.Event()
            try:
                self._cmd_queue.put(MotorCommand(
                    action="shutdown", duration=0,
                    generation=self.safety.get_generation(),
                    priority="stop", source="cleanup", done_event=ack,
                ))
            except Exception as e:
                logger_motor.error("Could not enqueue shutdown command: %s", e)
            if ack.wait(timeout=3.0):
                logger_motor.info("Motor Worker acknowledged the shutdown STOP (FIX 2)")
            else:
                logger_motor.error("Motor Worker did not acknowledge the shutdown STOP — "
                             "GPIO left untouched by this thread")
        self._running = False
        if worker is not None:
            worker.join(timeout=2)

    @property
    def is_pi(self):
        return _IS_PI


# Singleton instance — the ONLY motor controller
motor = MotorController()


# ==========================================================================
# ======== MODULE: nexus/command_parser.py =======================
# ==========================================================================
# """
# Nexus Robot — Strict Command Parser (Bug #2, #4, #28, #29; Founder-demo FIX 1)
#
# Intent-based parser, NOT substring matching. Physical movement requires
# EXPLICIT MOVEMENT INTENT:
#
  # 1. Safety STOP (stop, halt, freeze, emergency stop, don't move)
  # 2. Negation check (don't, never, do not) → reject
  # 3. Navigation (go to, find, navigate to, move toward) → return navigation
  # 4. Direct movement — the utterance must BEGIN with a movement verb/command
     # word (move / go / turn / spin / reverse / stop...) after an optional
     # politeness or wake prefix ("please", "hey nexus", "nexus"), and must
     # contain a recognized direction phrase.
#
# A bare direction word ("right", "left", "forward", "ahead", "back",
# "backward") inside a normal sentence is conversation — it can NEVER move
# the robot (Founder-demo FIX 1). "You are right.", "Left or right?",
# "Right now, tell me a joke." all fall through to AI conversation.
# "reverse" and "spin" are treated as explicit commands (they are verbs),
# but only at the start of an utterance.
# """
import re
import logging

logger_command_parser = logging.getLogger("Nexus.Parser")

# Safety stop words — always highest priority
SAFETY_STOP_WORDS = ["stop", "halt", "freeze", "emergency stop"]
SAFETY_STOP_PHRASES = ["don't move", "do not move", "dont move"]

# Negation words
NEGATION_WORDS = ["don't", "do not", "dont", "never", "no "]

# Navigation indicators — checked BEFORE movement
NAVIGATION_PATTERNS = [
    re.compile(r"\bgo\s+to\b", re.I),
    re.compile(r"\bmove\s+to\b", re.I),
    re.compile(r"\bnavigate\s+to\b", re.I),
    re.compile(r"\bfind\b", re.I),
    re.compile(r"\bgo\s+toward", re.I),
    re.compile(r"\bmove\s+toward", re.I),
    re.compile(r"\bgo\s+towards", re.I),
    re.compile(r"\bmove\s+towards", re.I),
    re.compile(r"\bwhere\s+is\b", re.I),
]

# Movement phrases — EXPLICIT INTENT ONLY (Founder-demo FIX 1).
# Every entry begins with a movement verb or is itself an unambiguous
# command word. Bare direction words ("left", "right", "forward", "ahead",
# "back", "backward", "backwards") are deliberately ABSENT: they appear in
# normal conversation and must never move the robot on their own.
_MOVEMENT_PHRASES = [
    ("stop",     ["stop", "halt", "brake", "freeze"]),
    ("forward",  ["move forward", "go forward", "move ahead", "go ahead",
                   "go straight", "move straight"]),
    ("back",     ["move backward", "go backward", "move back", "go back",
                   "reverse"]),
    ("left",     ["turn left", "go left", "move left"]),
    ("right",    ["turn right", "go right", "move right"]),
    ("spin",     ["turn around", "spin around", "turn round", "spin"]),
]

# An utterance must START with one of these (after an optional politeness /
# wake prefix) for any movement phrase to be considered (Founder-demo FIX 1).
_MOVEMENT_STARTERS = {"move", "go", "turn", "spin", "reverse",
                      "stop", "halt", "brake", "freeze"}
_WAKE_PREFIXES = {"please", "hey", "nexus", "ok", "okay"}

# Conversational phrases that should NOT trigger movement.
# These contain movement words but are clearly conversational.
_CONVERSATION_REJECTIONS = [
    re.compile(r"\byou'?re\s+(right|left)\b", re.I),
    re.compile(r"\bthat'?s\s+(right|left)\b", re.I),
    re.compile(r"\bwhat'?s\s+(right|left)\b", re.I),
    re.compile(r"\bi\s+(was|am|am)\s+(walking|going|moving|turning)\b", re.I),
    re.compile(r"\bexplain\b.*\b(forward|backward|left|right|spin)\b", re.I),
    re.compile(r"\bwhat\b.*\b(forward|backward|left|right|spin)\s+means\b", re.I),
    re.compile(r"\bhe\s+(was|is)\s+(going|walking|turning)\s+(forward|back|left|right)\b", re.I),
    re.compile(r"\bshe\s+(was|is)\s+(going|walking|turning)\s+(forward|back|left|right)\b", re.I),
    re.compile(r"\bthat\s+was\s+(?:a\s+)?(?:left|right)\s+turn\b", re.I),
    re.compile(r"\ba\s+(?:left|right)\s+turn\b", re.I),
]


def _has_negation(text):
    """Check if text contains negation that prevents movement (Bug #4)."""
    t = text.lower().strip()
    for neg in NEGATION_WORDS:
        if neg in t:
            return True
    return False


def is_safety_stop(text):
    """Check if this is a safety STOP command (Bug #10). Highest priority."""
    if not text:
        return False
    t = text.lower().strip()
    for phrase in SAFETY_STOP_PHRASES:
        if phrase in t:
            return True
    # Whole-word match for stop words
    for word in SAFETY_STOP_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", t):
            # But reject if negated: "don't stop" shouldn't stop
            if _has_negation(t):
                return False
            return True
    return False


def _is_navigation(text):
    """Check if this is a navigation command (Bug #2)."""
    t = text.lower().strip()
    return any(p.search(t) for p in NAVIGATION_PATTERNS)


def _extract_duration(text):
    """Extract duration: 'for 2 seconds', 'for 1.5', 'for three'."""
    t = text.lower()
    m = re.search(r"for\s+(\d+(?:\.\d+)?)", t)
    if m:
        return float(m.group(1))
    words_to_nums = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    m2 = re.search(r"for\s+(one|two|three|four|five)\b", t)
    if m2:
        return float(words_to_nums.get(m2.group(1), 1))
    return None


def _is_conversational(text):
    """Check if this is a conversational sentence that happens to contain movement words (Bug #2)."""
    t = text.lower().strip()
    for pattern in _CONVERSATION_REJECTIONS:
        if pattern.search(t):
            return True
    # If the sentence is long and complex (>8 words) and doesn't start with
    # a movement verb, treat it as conversation
    words = t.split()
    if len(words) > 8:
        # Check if it starts with a movement verb
        first_word = words[0] if words else ""
        if first_word not in ("move", "go", "turn", "forward", "backward", "back",
                              "left", "right", "spin", "stop", "halt", "ahead",
                              "reverse", "backwards"):
            return True
    return False


def _has_explicit_movement_intent(text):
    """Founder-demo FIX 1: movement requires explicit intent.

    The utterance must begin with a movement verb / command word, ignoring
    an optional politeness or wake prefix ("please", "hey nexus",
    "nexus", "ok"). Direction words alone ("right", "forward", ...) are
    conversation and never qualify.
    """
    words = re.findall(r"[a-z']+", text.lower())
    for w in words:
        if w in _WAKE_PREFIXES:
            continue
        return w in _MOVEMENT_STARTERS
    return False


def parse_movement_command(text):
    """
    Strict movement parser (Bug #2, #28; Founder-demo FIX 1).
    Returns (recognized: bool, action: str or None, duration: float or None).

    1. Conversational rejection — "You're right" → not a command
    2. Negation check — "don't move forward" → not a command
    3. Navigation check — "go to chair" → not a movement (it's navigation)
    4. Explicit-intent check — the utterance must START with a movement
       verb/command ("move forward" → command; "the answer is right" →
       conversation)
    5. Phrase match — "move forward" → (True, "forward", 1.0)
    """
    if not text:
        return False, None, None

    t = text.lower().strip()

    # Too long = probably conversation
    if len(t.split()) > 12:
        return False, None, None

    # 0. Conversational rejection (Bug #2)
    if _is_conversational(t):
        return False, None, None

    # 1. Negation check (Bug #4)
    if _has_negation(t):
        logger_command_parser.info("Command rejected — negation detected: %s", text)
        return False, None, None

    # 2. Navigation check (Bug #2) — "go to chair" is NOT "go forward"
    if _is_navigation(t):
        return False, None, None

    # 3. Explicit movement intent (Founder-demo FIX 1) — a bare direction
    #    word inside a sentence is conversation, never a command.
    if not _has_explicit_movement_intent(t):
        logger_command_parser.info("Command rejected — no explicit movement intent: %s", text)
        return False, None, None

    # 4. Exact phrase matching — verb-led phrases only
    for action, phrases in _MOVEMENT_PHRASES:
        for phrase in phrases:
            if re.search(rf"\b{re.escape(phrase)}\b", t):
                dur = _extract_duration(t)
                if dur is None:
                    if action in ("left", "right"):
                        dur = 0.7
                    elif action in ("spin",):
                        dur = 2.0
                    elif action == "stop":
                        dur = 0.0
                    else:
                        dur = 1.0
                logger_command_parser.info("Movement parsed: text=%r action=%s duration=%.1f", text, action, dur)
                return True, action, dur

    return False, None, None


def parse_navigation_command(text):
    """
    Navigation parser (Bug #29).
    Returns (is_navigation: bool, target: str or None).
    """
    if not text:
        return False, None
    t = text.lower().strip()

    # "go to the chair" → target = "chair"
    m = re.search(r"(?:go|move|navigate)\s+(?:to|toward|towards)\s+(?:the\s+|a\s+|an\s+)?(.+)", t)
    if m:
        target = m.group(1).strip()
        target = re.sub(r"\s+(?:please|now|quickly)$", "", target)
        return True, target

    # "find the cup"
    m = re.search(r"find\s+(?:the\s+|a\s+|an\s+)?(.+)", t)
    if m:
        target = m.group(1).strip()
        target = re.sub(r"\s+(?:please|now|quickly)$", "", target)
        return True, target

    # "where is the chair"
    m = re.search(r"where\s+(?:is|are)\s+(?:the\s+|a\s+|an\s+)?(.+)", t)
    if m:
        target = m.group(1).strip()
        target = re.sub(r"\s+(?:please|now|quickly)$", "", target)
        return True, target

    return False, None


# ==========================================================================
# ======== MODULE: nexus/audio.py ================================
# ==========================================================================
# """
# Nexus Robot — Audio Manager (Review P0 #7, #8)
#
# Centralized coordinator for microphone recording AND TTS playback.
# The AudioManager is the single owner of:
# - the current playback process (Review #8 — one lock)
# - the speaking state (Review #7 — TTS sets/restores it via try/finally)
# - stop playback
# - fallback TTS
#
# No other component directly manipulates the playback process.
# When TTS is speaking, microphone recording is suppressed so the robot
# never hears its own voice.
# """
import subprocess
import threading
import time
import wave
import logging
import os

try:
    import audioop
except Exception:  # Python 3.13+ removed audioop
    audioop = None


logger_audio = logging.getLogger("Nexus.Audio")

# Optional VAD
try:
    import webrtcvad
    VAD_AVAILABLE = True
except Exception:
    webrtcvad = None
    VAD_AVAILABLE = False
    logger_audio.info("webrtcvad unavailable — using RMS threshold fallback")


class AudioManager:
    """
    Coordinates mic + speaker, and OWNS all TTS playback process state
    (Review #8). When TTS is speaking, recording is suppressed to avoid
    the robot hearing its own voice (Review #7).
    """

    def __init__(self):
        # Speaking state (Review #7)
        self._speaking = False
        self._speaking_lock = threading.Lock()
        self._recording_lock = threading.Lock()

        # Centralized playback process state (Review #8) — ONE lock
        self._playback_lock = threading.Lock()
        self._playback_process = None

    # ------------------------------------------------------------------
    # Speaking state (Review #7)
    # ------------------------------------------------------------------
    def set_speaking(self, value: bool):
        """TTS calls this to indicate playback in progress."""
        with self._speaking_lock:
            self._speaking = value

    def is_speaking(self):
        with self._speaking_lock:
            return self._speaking

    # ------------------------------------------------------------------
    # Centralized playback management (Review #8)
    # ------------------------------------------------------------------
    def start_playback(self):
        """Launch aplay for TTS output. Returns the process. Only one
        playback at a time (guarded by _playback_lock)."""
        with self._playback_lock:
            # Kill any stale playback first
            self._terminate_playback_locked()
            proc = subprocess.Popen(
                ["aplay", "-D", os.environ.get("TTS_DEVICE", "hw:1,0"),
                 "-f", AUDIO_FORMAT, "-c", str(CHANNELS), "-r", str(SAMPLE_RATE)],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._playback_process = proc
            return proc

    def get_playback_process(self):
        with self._playback_lock:
            return self._playback_process

    def finish_playback(self, proc, block=True, timeout=30):
        """Close stdin and optionally wait for the process to finish.

        The lock is NOT held during wait() (H4) so stop_playback() can terminate
        the process immediately even while a blocking wait is in flight (e.g. on
        shutdown). Without this, a hung aplay would block shutdown forever.
        """
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
            if block:
                proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger_audio.warning("aplay did not finish in %ss — terminating", timeout)
            self._terminate_proc(proc)
        except Exception as e:
            logger_audio.warning("Playback finish error: %s", e)
        finally:
            with self._playback_lock:
                if self._playback_process is proc:
                    self._playback_process = None

    def stop_playback(self):
        """Stop current TTS playback by terminating the exact tracked process
        (no pkill — Review #8). Runs outside the lock (H4) so it can interrupt
        a blocking finish_playback()."""
        with self._playback_lock:
            proc = self._playback_process
            self._playback_process = None
        if proc is not None:
            self._terminate_proc(proc)

    @staticmethod
    def _terminate_proc(proc):
        try:
            proc.terminate()
            proc.wait(timeout=1)
        except Exception:
            try:
                proc.kill()
            except Exception as e:
                logger_audio.warning("Failed to kill aplay: %s", e)

    def _terminate_playback_locked(self):
        proc = self._playback_process
        self._playback_process = None
        if proc is not None:
            self._terminate_proc(proc)

    def fallback_tts(self, text):
        """Fallback TTS via espeak when the primary path fails."""
        try:
            subprocess.run(["espeak", text],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Microphone
    # ------------------------------------------------------------------
    def validate_microphone(self) -> tuple:
        """
        Real microphone validation. Returns (ok: bool, message: str).
        Takes the recording lock (L8) so it cannot spawn a second arecord
        alongside an active recording.
        """
        with self._recording_lock:
            return self._validate_microphone_internal()

    def _validate_microphone_internal(self) -> tuple:
        try:
            proc = subprocess.Popen(
                ["arecord", "-D", MIC_DEVICE, "-f", AUDIO_FORMAT,
                 "-r", str(SAMPLE_RATE), "-c", str(CHANNELS), "-t", "raw"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            time.sleep(0.3)
            data = proc.stdout.read(1600)
            proc.terminate()
            proc.wait(timeout=1)

            if len(data) < 800:
                return False, f"device '{MIC_DEVICE}' produced no audio data"
            return True, f"device '{MIC_DEVICE}' working"

        except FileNotFoundError:
            return False, "arecord not found — install alsa-utils"
        except subprocess.TimeoutExpired:
            return False, f"device '{MIC_DEVICE}' unavailable (timeout)"
        except Exception as e:
            return False, f"device '{MIC_DEVICE}' error: {e}"

    def record_to_wav(self, timeout_seconds=RECORD_SECONDS_MAX,
                      out_file=AUDIO_FILE) -> tuple:
        """
        Record from mic to WAV file. Returns (ok, error).
        Skips recording while TTS is speaking (self-hearing prevention).
        """
        # Don't record while we're speaking (Review #7)
        if self.is_speaking():
            time.sleep(0.3)
            if self.is_speaking():
                return False, "tts-speaking"

        with self._recording_lock:
            # Measured as 'mic_recording' (vision-performance pass, req. 6)
            with measure("mic_recording"):
                return self._record_internal(timeout_seconds, out_file)

    def _record_internal(self, timeout_seconds, out_file):
        frame_ms = FRAME_DURATION_MS
        frame_bytes = int(SAMPLE_RATE * (frame_ms / 1000.0) * 2)

        try:
            proc = subprocess.Popen(
                ["arecord", "-D", MIC_DEVICE, "-f", AUDIO_FORMAT,
                 "-r", str(SAMPLE_RATE), "-c", str(CHANNELS), "-t", "raw"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            return False, f"arecord-failed:{e}"

        vad = webrtcvad.Vad(VAD_MODE) if VAD_AVAILABLE else None
        frames = bytearray()
        start_time = time.time()
        saw_speech = False
        consecutive_silence = 0
        max_silence_after_speech = int(0.5 / (frame_ms / 1000.0)) + 1

        try:
            while time.time() - start_time <= timeout_seconds:
                chunk = proc.stdout.read(frame_bytes)
                if not chunk or len(chunk) < frame_bytes:
                    break
                frames.extend(chunk)

                is_speech = False
                if vad:
                    try:
                        is_speech = vad.is_speech(chunk, sample_rate=SAMPLE_RATE)
                    except Exception:
                        pass
                elif audioop is not None:
                    try:
                        is_speech = audioop.rms(chunk, 2) > RMS_SILENCE_THRESHOLD
                    except Exception:
                        pass

                if is_speech:
                    saw_speech = True
                    consecutive_silence = 0
                elif saw_speech:
                    consecutive_silence += 1

                if saw_speech and consecutive_silence >= max_silence_after_speech:
                    break
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        if not frames:
            return False, "no-audio"

        # Phantom-wake fix (2026-09): a muted/disconnected mic that still
        # enumerates as a device records pure zeros — that is NOT speech.
        # Never send speech-free audio to STT (it hallucinates words like
        # "hello" out of pure silence). Only enforced when a speech
        # detector (webrtcvad or audioop RMS) was actually available.
        if not saw_speech and (vad is not None or audioop is not None):
            return False, "silent"

        try:
            with wave.open(out_file, "wb") as outw:
                outw.setnchannels(CHANNELS)
                outw.setsampwidth(2)
                outw.setframerate(SAMPLE_RATE)
                outw.writeframes(bytes(frames))
        except Exception:
            return False, "write-failed"

        if os.path.getsize(out_file) < 2000 if os.path.exists(out_file) else True:
            return False, "silent"

        return True, None


# Singleton
audio_manager = AudioManager()


# ==========================================================================
# ======== MODULE: nexus/tts.py ==================================
# ==========================================================================
# """
# Nexus Robot — TTS Manager (Review P0 #7, #8)
#
# TTS coordinates with AudioManager so that:
# - The speaking state is always set and restored via try/finally (Review #7).
# - Playback process state is owned by AudioManager with ONE lock (Review #8).
# - No component directly manipulates the aplay process.
#
# The AudioManager.stop_playback() terminates the exact tracked process
# (no pkill).
# """
import threading
import time
import re
import unicodedata
import logging
import requests


logger_tts = logging.getLogger("Nexus.TTS")

# Lock so only one speak() call runs at a time (Review #8)
_tts_lock = threading.Lock()

UNWANTED = r"[\#\*\;\:\'\"\!\(\)\@\&\%\$\^\{\}\[\]\|\<\>\?/]"

# Script ranges → Sarvam language codes (H3). Text written in an Indian
# script is spoken with the matching bulbul voice instead of being stripped.
_SCRIPT_LANGUAGE_MAP = [
    ("\u0900-\u097F", "hi-IN"),   # Devanagari (Hindi, Marathi, ...)
    ("\u0980-\u09FF", "bn-IN"),   # Bengali
    ("\u0A00-\u0A7F", "pa-IN"),   # Gurmukhi (Punjabi)
    ("\u0A80-\u0AFF", "gu-IN"),   # Gujarati
    ("\u0B00-\u0B7F", "or-IN"),   # Odia
    ("\u0B80-\u0BFF", "ta-IN"),   # Tamil
    ("\u0C00-\u0C7F", "te-IN"),   # Telugu
    ("\u0C80-\u0CFF", "kn-IN"),   # Kannada
    ("\u0D00-\u0D7F", "ml-IN"),   # Malayalam
]


def detect_language_code(text):
    """Pick a TTS language code from the script of the text (H3)."""
    for rng, code in _SCRIPT_LANGUAGE_MAP:
        if re.search(f"[{rng}]", text):
            return code
    return TTS_LANGUAGE_CODE


def clean_text(text):
    """Clean text for speech WITHOUT stripping non-ASCII (H3).

    Previously this removed every non-ASCII character, so Hindi/Bengali/Tamil
    text was silently deleted before it ever reached the TTS API. Unicode
    letters are now preserved; only ASCII markup symbols are removed.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(UNWANTED, " ", text)
    return re.sub(r"\s+", " ", text).strip()


def stop_playback():
    """Stop current TTS playback via AudioManager (Review #8)."""
    audio_manager.stop_playback()


def speak(text, voice=None, block=True, safety_delay=0.15, temperature=0.4,
          face_callback=None):
    """
    Stream TTS from Sarvam and play via aplay.

    Owns the AudioManager speaking-state via try/finally (Review #7):
        set_speaking(True)
        → playback
        → set_speaking(False) [always, even on error]

    Playback process state is managed by AudioManager (Review #8).
    """
    voice = voice or NEXUS_VOICE
    text = clean_text(text)
    if not text:
        return

    if not SARVAM_KEY:
        logger_tts.warning("TTS skipped — no API key")
        return

    # Speak non-Latin text with the matching Indic voice (H3)
    language_code = detect_language_code(text)

    if face_callback:
        face_callback("talking")

    with _tts_lock:
        audio_manager.set_speaking(True)
        t_tts = time.perf_counter()
        try:
            _speak_internal(text, voice, block, temperature, face_callback,
                            language_code)
        except Exception as e:
            logger_tts.error("TTS error: %s", e, exc_info=True)
            # Fallback to espeak if available (Review #8)
            audio_manager.fallback_tts(text)
        finally:
            # Measured as 'tts' — fetch + playback (vision-performance pass)
            latency.record("tts", time.perf_counter() - t_tts)
            # ALWAYS restore speaking state (Review #7)
            audio_manager.set_speaking(False)
            time.sleep(safety_delay)
            if face_callback:
                face_callback("idle")


def _speak_internal(text, voice, block, temperature, face_callback,
                    language_code=TTS_LANGUAGE_CODE):
    """Stream from Sarvam and pipe to aplay via AudioManager."""
    proc = audio_manager.start_playback()
    if proc is None:
        return

    try:
        with requests.post(
            "https://api.sarvam.ai/text-to-speech/stream",
            json={
                "text": text,
                "language_code": language_code,
                "speaker": voice,
                "model": "bulbul:v3",
                "output_audio_codec": "linear16",
                "speech_sample_rate": SAMPLE_RATE,
                "temperature": temperature,
            },
            headers={"api-subscription-key": SARVAM_KEY,
                     "Content-Type": "application/json"},
            stream=True, timeout=40
        ) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=4096):
                if chunk and proc and proc.stdin:
                    try:
                        proc.stdin.write(chunk)
                        proc.stdin.flush()
                    except BrokenPipeError:
                        break

        audio_manager.finish_playback(proc, block=block)
    except requests.exceptions.ConnectionError:
        logger_tts.error("TTS: cannot reach Sarvam — network unavailable")
        audio_manager.stop_playback()
    except requests.exceptions.Timeout:
        logger_tts.error("TTS: Sarvam timeout")
        audio_manager.stop_playback()
    except Exception:
        audio_manager.stop_playback()
        raise


# ==========================================================================
# ======== MODULE: nexus/stt.py ==================================
# ==========================================================================
# """
# Nexus Robot — STT with Circuit Breaker (Bug #27, #31)
#
# If the STT API fails repeatedly, the circuit opens and further calls
# return immediately with an error instead of hammering the API.
# After CB_RECOVERY_TIMEOUT seconds, the circuit half-opens for a retry.
# """
import time
import logging
import requests
from enum import Enum


logger_stt = logging.getLogger("Nexus.STT")


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
                logger_stt.warning("Circuit breaker OPENED after %d failures", self._failures)


_stt_breaker = CircuitBreaker()


def transcribe(wav_path=AUDIO_FILE, model=SARVAM_STT_MODEL, timeout=15):
    """
    Send WAV to Sarvam STT. Returns (text, error).
    Returns (None, "circuit-open") immediately if circuit breaker is open.
    """
    if not SARVAM_KEY:
        return None, "no-api-key"

    if not _stt_breaker.allow():
        logger_stt.warning("STT circuit breaker open — skipping request")
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


# ==========================================================================
# ======== MODULE: nexus/camera.py ===============================
# ==========================================================================
# """
# Nexus Robot — Camera Manager (Bug #11)
#
# Thread-safe camera access. Only CameraManager touches Picamera2.
# All other components go through camera_manager.capture().
# """
import threading
import logging
import os

# Manual channel-order override for driver-specific RGB/BGR changes:
# set NEXUS_CAMERA_SWAP=1 if colors on the preview/cloud vision look swapped.
NEXUS_CAMERA_SWAP = os.environ.get("NEXUS_CAMERA_SWAP", "0") == "1"

try:
    import numpy as _np
except ImportError:  # pragma: no cover - numpy is required with cv2 anyway
    _np = None


logger_camera = logging.getLogger("Nexus.Camera")

# Optional dependencies
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    Picamera2 = None
    PICAMERA_AVAILABLE = False


class CameraManager:
    """
    Thread-safe camera access (Bug #11).
    Only this class touches Picamera2 — all other components use capture().
    """

    def __init__(self):
        self._cam = None
        self._lock = threading.Lock()
        self._available = False

    def start(self) -> bool:
        """Initialize camera (Bug #17).

        2026-09 color fix: picamera2's format names are BACKWARDS relative
        to the actual byte order (libcamera/DRM naming). Per the Picamera2
        manual: 'RGB888 - ordered [B, G, R]' and 'BGR888 - ordered [R, G, B]'.
        The old code requested BGR888, which delivered RGB-ordered bytes
        that OpenCV treated as BGR — every frame had red and blue swapped
        (skin looked blue, light blue looked yellow) on the face preview
        AND in the cloud-vision JPEGs. Requesting RGB888 gives true BGR.
        If colors are ever wrong on some future driver, set
        NEXUS_CAMERA_SWAP=1 to flip the channels back.
        """
        if not PICAMERA_AVAILABLE or not CV2_AVAILABLE:
            logger_camera.warning("Camera unavailable — missing dependencies (picamera2 / opencv)")
            return False

        try:
            with self._lock:
                self._cam = Picamera2()
                config = self._cam.create_still_configuration(main={"format": "RGB888"})
                self._cam.configure(config)
                self._cam.start()
                import time
                time.sleep(2)
            self._available = True
            logger_camera.info("Picamera2 initialized (RGB888 requested — true BGR byte order)")
            return True
        except Exception as e:
            logger_camera.error("Camera init failed: %s", e, exc_info=True)
            self._cam = None
            self._available = False
            return False

    def capture(self):
        """
        Capture a frame, normalized to BGR. Thread-safe.
        Returns None if camera unavailable.
        Measured as 'camera_capture' latency (vision-performance pass).
        """
        if not self._available or self._cam is None:
            return None
        try:
            with measure("camera_capture"):
                with self._lock:
                    frame = self._cam.capture_array()
            if frame is not None and len(frame.shape) == 3:
                if frame.shape[2] == 4:  # BGRA → BGR
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                if frame.shape[2] == 3 and NEXUS_CAMERA_SWAP and _np is not None:
                    # Manual override for driver-specific byte-order changes
                    frame = _np.ascontiguousarray(frame[:, :, ::-1])
            return frame
        except Exception as e:
            logger_camera.error("Camera capture failed: %s", e, exc_info=True)
            return None

    def health_check(self) -> bool:
        """Verify camera produces valid frames."""
        frame = self.capture()
        if frame is not None and frame.size > 0:
            return True
        return False

    @property
    def available(self):
        return self._available

    def stop(self):
        with self._lock:
            if self._cam is not None:
                try:
                    self._cam.stop()
                except Exception:
                    pass
                self._cam = None
            self._available = False


# Singleton
camera_manager = CameraManager()


# ==========================================================================
# ======== MODULE: nexus/mood.py =================================
# ==========================================================================
# """
# Nexus Robot — Mood System (Bug #16, #17)
#
# Conservative mood detection — requires multiple signals, not single keywords.
# Mood is SEPARATED from robot state (Bug #17): mood affects personality/voice,
# but doesn't override face_state or robot operational state.
#
# Mood never affects safety-critical behavior (Bug #16).
# """
import threading
import time
import re
import logging

logger_mood = logging.getLogger("Nexus.Mood")

MOOD_DATA = {
    "neutral":  {"voice": None,   "temp": 0.4, "prompt": "friendly and helpful"},
    "happy":    {"voice": "shubh", "temp": 0.5, "prompt": "cheerful and warm"},
    "sleepy":   {"voice": "shubh", "temp": 0.3, "prompt": "slow and drowsy, speaking softly as if just waking up"},
    "annoyed":  {"voice": "shubh", "temp": 0.2, "prompt": "a bit grumpy and curt, but still helpful"},
    "excited":  {"voice": "shubh", "temp": 0.8, "prompt": "very enthusiastic and energetic"},
    "curious":  {"voice": "shubh", "temp": 0.6, "prompt": "curious and inquisitive, often asking follow-up questions"},
}

# Sets for conservative matching — require multiple hits for longer messages
POSITIVE_WORDS = {"great", "awesome", "amazing", "love", "good", "nice", "cool",
                  "fantastic", "wonderful", "excellent", "perfect", "thanks",
                  "happy", "fun", "brilliant", "wow", "incredible"}
NEGATIVE_WORDS = {"stupid", "dumb", "hate", "useless", "boring", "annoying",
                 "terrible", "awful", "worst", "broken"}
# Multi-word phrases checked separately (L2): per-word set matching could
# never hit these, so "thank you" / "shut up" were dead entries.
POSITIVE_PHRASES = {"thank you", "well done", "good job"}
NEGATIVE_PHRASES = {"shut up"}
EXCITED_TRIGGERS = {"joke", "game", "dance", "party", "celebrate", "surprise"}
QUESTION_INDICATORS = {"what", "why", "how", "when", "where", "who", "which", "explain", "tell me about"}


class Mood:
    """
    Tracks mood independently of robot operational state.
    Mood affects TTS voice/temperature and AI personality prompt.
    Mood NEVER affects safety, motor control, or command parsing.

    Thread safety (Review #28): ALL mutable mood state, including
    _last_interaction, is protected by the same lock.
    """

    def __init__(self):
        self._mood = "neutral"
        self._last_interaction = time.time()
        self._lock = threading.Lock()

    def set_mood(self, m):
        if m in MOOD_DATA:
            with self._lock:
                self._mood = m

    def get_mood(self):
        with self._lock:
            return self._mood

    def touch(self):
        # Same lock as other mutable mood state (Review #28)
        with self._lock:
            self._last_interaction = time.time()

    def _get_last_interaction(self):
        with self._lock:
            return self._last_interaction

    def analyze_user_text(self, text):
        """
        Conservative mood detection.
        Requires multiple keyword hits for longer messages.
        Short commands (<=3 words) don't trigger mood changes.
        Never affects safety-critical behavior.

        Negation handling (Review #29): "This is not great" / "I don't
        feel happy" / "That wasn't fun" are NOT classified as positive.
        """
        if not text:
            return
        t = text.lower()
        self.touch()

        cleaned = re.sub(r'[^\w\s]', '', t)
        words = cleaned.split()
        word_count = len(words)
        if word_count <= 3:
            return

        word_set = set(words)

        # Negation handling (Review #29): a positive word within a few
        # words after a negator is NOT positive — it flips to negative.
        # NOTE: punctuation is stripped above, so "don't" → "dont",
        # "wasn't" → "wasnt", etc.
        NEGATORS = {"not", "no", "never", "dont", "wasnt", "isnt", "arent",
                    "werent", "wont", "cant", "couldnt", "wouldnt", "nothing"}
        negated_positive = False
        negated_negative = False
        for i, w in enumerate(words):
            if w in NEGATORS or w == "don't":
                window = words[i + 1:i + 4]  # negation applies to next ~3 words
                if any(x in POSITIVE_WORDS or x in EXCITED_TRIGGERS for x in window):
                    negated_positive = True
                if any(x in NEGATIVE_WORDS for x in window):
                    negated_negative = True

        positive_hits = len(word_set & POSITIVE_WORDS)
        negative_hits = len(word_set & NEGATIVE_WORDS)
        excited_hits = len(word_set & EXCITED_TRIGGERS)
        question_hits = len(word_set & QUESTION_INDICATORS)

        # Multi-word phrase matching (L2)
        positive_hits += sum(1 for p in POSITIVE_PHRASES if p in cleaned)
        negative_hits += sum(1 for p in NEGATIVE_PHRASES if p in cleaned)

        # Apply negation scoring (Review #29)
        if negated_positive:
            # "not great" / "don't feel happy" → counts as negative signal
            negative_hits += 1
            positive_hits = max(0, positive_hits - 1)
            excited_hits = max(0, excited_hits - 1)
        if negated_negative:
            # "not bad" → mild positive
            positive_hits += 1
            negative_hits = max(0, negative_hits - 1)

        threshold = 2 if word_count > 12 else 1

        if negative_hits >= threshold:
            self.set_mood("annoyed")
        elif excited_hits >= threshold:
            self.set_mood("excited")
        elif positive_hits >= threshold:
            self.set_mood("happy")
        elif question_hits >= threshold and word_count <= 15:
            self.set_mood("curious")

    def check_idle(self, sleep_threshold=180):
        # _last_interaction read under the same lock (Review #28)
        with self._lock:
            current_mood = self._mood
            idle = time.time() - self._last_interaction > sleep_threshold
        if current_mood != "sleepy" and idle:
            self.set_mood("sleepy")
            return True
        return False

    @property
    def voice(self):
        with self._lock:
            return MOOD_DATA[self._mood]["voice"]

    @property
    def temperature(self):
        with self._lock:
            return MOOD_DATA[self._mood]["temp"]

    @property
    def personality_prompt(self):
        with self._lock:
            return MOOD_DATA[self._mood]["prompt"]


# Singleton
mood = Mood()


# ==========================================================================
# ======== MODULE: nexus/memory.py ===============================
# ==========================================================================
# """
# Nexus Robot — Conversation Memory (Review P2 #25, #27)
#
# Auto-extracts non-sensitive facts from conversation.
# Excludes: allergies, medical, passwords, financial, address, biometric.
#
# Fixes:
# - Atomic writes: memory.tmp → flush/fsync → atomic rename (Review #25).
  # Power loss during write cannot corrupt the primary memory file.
# - Credentials/secrets are NEVER stored — even when the user explicitly
  # says "remember my password" (Review #27). Explicit memory permission
  # does not override security policy.
# """
import json
import os
import re
import threading
import logging


logger_memory = logging.getLogger("Nexus.Memory")

# Sensitive categories — NEVER auto-saved
SENSITIVE_PATTERNS = [
    re.compile(r"allerg", re.I),
    re.compile(r"password|passwd|pwd|pin\s+code|otp", re.I),
    re.compile(r"medical|diagnosis|medication|prescription|blood\s+pressure|diabetes", re.I),
    re.compile(r"\baddress\b", re.I),
    re.compile(r"\bbank\b|\baccount\b|\bcard\s+number\b|\bcvv\b|\bcredit\b|\bdebit\b", re.I),
    re.compile(r"\bssn\b|\baadhaar\b|\bpan\s+card\b|\bpassport\b", re.I),
    re.compile(r"\bphone\s+number\b|\bmobile\s+number\b", re.I),
    # Secrets / credentials — never stored, even on explicit request (Review #27)
    re.compile(r"\bapi\s+key\b|\bsecret\b|\bprivate\s+key\b|\bauth(?:entication)?\s+code\b", re.I),
    re.compile(r"\bcredential\b|\blogin\s+detail\b|\bpassphrase\b|\btoken\b", re.I),
]

# Auto-extraction patterns (sensitive categories excluded from this list)
_AUTO_MEMORY_PATTERNS = [
    re.compile(r"\bi\s+(?:like|love|enjoy|prefer|am into|am fond of|am a fan of)\s+(.+)", re.I),
    re.compile(r"\bi\s+play\s+(?:the\s+)?(.+)", re.I),
    re.compile(r"\bi\s+work\s+(?:at|as|in)\s+(.+)", re.I),
    re.compile(r"\bi\s+(?:study|am studying)\s+(.+)", re.I),
    re.compile(r"\bi\s+am\s+(?:a|an)\s+(.+?)(?:\.|,|$)", re.I),
    re.compile(r"\bmy\s+(name|favorite|favourite|pet|dog|cat|car)\s+is\s+(.+)", re.I),
    re.compile(r"\bi\s+have\s+a\s+(?:dog|cat|pet)\s+(?:named|called)?\s*(.+)", re.I),
    re.compile(r"\bi\s+hate\s+(.+)", re.I),
    # NOTE: "I live in" and "I'm allergic to" are EXCLUDED (Bug #20)
]


def _is_sensitive(text):
    return any(p.search(text) for p in SENSITIVE_PATTERNS)


class Memory:
    """Thread-safe conversation memory with privacy filter."""

    def __init__(self):
        self._data = {"facts": []}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            with open(MEMORY_FILE, "r") as f:
                self._data = json.load(f)
                if "facts" not in self._data:
                    self._data["facts"] = []
        except Exception:
            self._data = {"facts": []}

    def _save(self):
        """
        Atomic save (Review #25): memory.tmp → flush/fsync → rename.
        Power loss during write cannot corrupt the primary file.
        """
        tmp_file = MEMORY_FILE + ".tmp"
        try:
            with open(tmp_file, "w") as f:
                json.dump(self._data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, MEMORY_FILE)  # atomic rename
        except Exception as e:
            logger_memory.error("Could not save memory: %s", e)
            try:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            except Exception:
                pass

    def remember(self, fact):
        """
        Explicitly remember a fact (user said 'remember this').

        SECURITY POLICY (Review #27): credentials and secrets are NEVER
        stored — even if the user explicitly asks (e.g. "remember my
        password"). Explicit memory permission does not override
        security policy. Returns False and explains why.
        """
        fact = fact.strip().rstrip(".")
        if not fact:
            return False
        if _is_sensitive(fact):
            logger_memory.info("Explicit memory BLOCKED — sensitive/secret content "
                        "is never stored (security policy)")
            return False
        with self._lock:
            if fact.lower() not in [f.lower() for f in self._data["facts"]]:
                self._data["facts"].append(fact)
                self._data["facts"] = self._data["facts"][-MAX_REMEMBERED_FACTS:]
                self._save()
        return True

    def auto_extract(self, user_text, ai_reply=""):
        """
        Auto-extract non-sensitive facts from user messages (Bug #20).
        Sensitive information is never auto-saved.
        """
        if not user_text:
            return
        for pattern in _AUTO_MEMORY_PATTERNS:
            m = pattern.search(user_text)
            if m:
                fact = m.group(0).strip().rstrip(".")
                if _is_sensitive(fact):
                    logger_memory.info("Auto-memory blocked sensitive info: %s", fact)
                    return
                # Normalize
                fact = re.sub(r"^i\s+like\b", "User likes", fact, flags=re.I)
                fact = re.sub(r"^i\s+love\b", "User loves", fact, flags=re.I)
                fact = re.sub(r"^i\s+enjoy\b", "User enjoys", fact, flags=re.I)
                fact = re.sub(r"^i\s+play\b", "User plays", fact, flags=re.I)
                fact = re.sub(r"^i\s+work\b", "User works", fact, flags=re.I)
                fact = re.sub(r"^i\s+study\b", "User studies", fact, flags=re.I)
                fact = re.sub(r"^i\s+hate\b", "User hates", fact, flags=re.I)  # L3 grammar
                fact = re.sub(r"^i\s+am\b", "User is", fact, flags=re.I)
                fact = re.sub(r"^i\s+have\b", "User has", fact, flags=re.I)
                fact = re.sub(r"^i\b", "User", fact, flags=re.I)
                fact = re.sub(r"^my\b", "User's", fact, flags=re.I)
                if self.remember(fact):
                    logger_memory.info("Auto-remembered: %s", fact)

    def forget_all(self):
        with self._lock:
            self._data["facts"] = []
            self._save()

    def get_facts(self):
        with self._lock:
            return list(self._data["facts"])

    def context_string(self):
        with self._lock:
            if not self._data.get("facts"):
                return ""
            facts = "; ".join(self._data["facts"])
        return f" Known facts about the user, use them naturally when relevant (don't recite the list): {facts}"


# Singleton
memory = Memory()


# ==========================================================================
# ======== MODULE: nexus/vision.py ===============================
# ==========================================================================
# """
# Nexus Robot — Vision System (Review P1 #9, #10, #11; P2 #26)
#
# TFLite object detection with:
# - Strict output tensor validation (Review #10) — detection is DISABLED
  # rather than guessing when the model signature is unsupported.
# - Correct quantized input handling (Review #9) — reads the tensor's
  # scale/zero_point quantization metadata and supports float32, uint8,
  # and int8 models.
# - Vision context TTL so stale observations aren't used (Review #11).
# - Atomic vision-log writes (Review #26) — tmp + fsync + rename.
#
# Scene description via Sarvam vision API.
# """
import base64
import json
import os
import queue
import threading
import time
import logging


logger_vision = logging.getLogger("Nexus.Vision")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

try:
    import tflite_runtime.interpreter as tflite
    TFLITE_AVAILABLE = True
except ImportError:
    tflite = None
    TFLITE_AVAILABLE = False

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


class VisionContext:
    """Holds latest vision description with TTL expiration (Review #11)."""

    def __init__(self):
        self.description = None
        self.timestamp = None

    def set(self, description):
        self.description = description
        self.timestamp = time.time()

    def get_fresh(self):
        """Returns description if still fresh (within TTL), else None.
        Stale vision information is never presented as current (Review #11)."""
        if self.description is None or self.timestamp is None:
            return None
        if time.time() - self.timestamp > VISION_CONTEXT_TTL:
            logger_vision.info("Vision context expired (TTL=%ds)", VISION_CONTEXT_TTL)
            return None
        return self.description


vision_context = VisionContext()


# ----------------------------------------------------------------------
# Strict output tensor validation (Review #10)
# ----------------------------------------------------------------------
def identify_tflite_outputs(output_details):
    """
    Strictly identify boxes, classes, scores by tensor shape and name
    (Review #10).

    A supported detector signature must provide:
        boxes   = [1, N, 4]
        classes = [1, N]
        scores  = [1, N]
    with all N values matching.

    If the model does not match a supported signature, returns None —
    detection is DISABLED rather than guessed.
    """
    boxes_idx = classes_idx = scores_idx = None
    boxes_n = classes_n = scores_n = None

    for i, detail in enumerate(output_details):
        shape = list(detail.get('shape', []))
        name = detail.get('name', '').lower()

        # boxes: 3D tensor [1, N, 4]
        if len(shape) == 3 and shape[0] == 1 and shape[2] == 4:
            if boxes_idx is None:
                boxes_idx = i
                boxes_n = shape[1]
            continue

        # classes/scores: 2D tensors [1, N]
        if len(shape) == 2 and shape[0] == 1:
            n = shape[1]
            if 'score' in name and scores_idx is None:
                scores_idx = i
                scores_n = n
            elif 'class' in name and classes_idx is None:
                classes_idx = i
                classes_n = n

    # Strict fallback ONLY when names are absent: two 2D [1,N] tensors
    # whose N matches boxes N — assign in index order (classes, scores)
    # but only if both N values are equal, otherwise ambiguous → disable.
    if scores_idx is None or classes_idx is None:
        candidates = [i for i, d in enumerate(output_details)
                      if i != boxes_idx
                      and len(list(d.get('shape', []))) == 2
                      and list(d.get('shape', []))[0] == 1]
        if boxes_idx is not None and len(candidates) == 2:
            n1 = list(output_details[candidates[0]]['shape'])[1]
            n2 = list(output_details[candidates[1]]['shape'])[1]
            if n1 == n2 and boxes_n == n1:
                classes_idx, scores_idx = candidates[0], candidates[1]
                classes_n, scores_n = n1, n2

    # All three must be identified (Review #10)
    if None in (boxes_idx, classes_idx, scores_idx):
        logger_vision.error("TFLite output identification FAILED — detection disabled. "
                     "boxes=%s classes=%s scores=%s",
                     boxes_idx, classes_idx, scores_idx)
        return None

    # All N values must match (Review #10)
    if not (boxes_n == classes_n == scores_n):
        logger_vision.error("TFLite tensor N mismatch: boxes=%s classes=%s scores=%s "
                     "— detection disabled", boxes_n, classes_n, scores_n)
        return None

    result = {"boxes": boxes_idx, "classes": classes_idx, "scores": scores_idx}
    logger_vision.info("TFLite outputs validated: %s (N=%s)", result, boxes_n)
    return result


# ----------------------------------------------------------------------
# Quantized input handling (Review #9)
# ----------------------------------------------------------------------
def prepare_input(input_detail, frame):
    """
    Prepare the input tensor for the model, correctly handling
    quantization metadata (scale / zero_point) per Review #9.

    Supports:
    - float32 models (normalize to [0,1])
    - uint8 models (quantize: q = round(x/scale) + zero_point)
    - int8 models (quantize with clipping to int8 range)

    Returns the tensor data, or None if the tensor configuration is
    unsupported (detection should be disabled safely).
    """
    height, width = input_detail['shape'][1:3]
    img_resized = cv2.resize(frame, (width, height))
    input_data = np.expand_dims(img_resized, axis=0)

    dtype = input_detail['dtype']
    # Quantization metadata: (scale, zero_point) — both 0 means
    # the tensor is not quantized (or metadata missing).
    quant = input_detail.get('quantization', (0.0, 0))
    scale = quant[0] if len(quant) > 0 else 0.0
    zero_point = quant[1] if len(quant) > 1 else 0

    if dtype == np.float32:
        return (np.float32(input_data) / 255.0)

    if dtype in (np.uint8, np.int8) and scale > 0:
        # Quantize: q = round(x / scale) + zero_point
        # First normalize to the model's expected input range.
        # Standard TFLite detection models trained on [0,1] floats:
        normalized = np.float32(input_data) / 255.0
        quantized = np.round(normalized / scale).astype(np.int64) + int(zero_point)
        if dtype == np.uint8:
            quantized = np.clip(quantized, 0, 255).astype(np.uint8)
        else:
            quantized = np.clip(quantized, -128, 127).astype(np.int8)
        return quantized

    if dtype in (np.uint8, np.int8) and scale == 0:
        # No quantization metadata — legacy uint8 models often expect raw 0-255
        logger_vision.warning("Quantized dtype %s without scale metadata — "
                       "assuming raw [0,255] input", dtype)
        return input_data.astype(dtype)

    # Unsupported tensor configuration — reject safely (Review #9)
    logger_vision.error("Unsupported input tensor dtype: %s (scale=%s, zero_point=%s) "
                 "— detection disabled", dtype, scale, zero_point)
    return None


class VisionSystem:
    def __init__(self):
        self.labels = []
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.output_map = None
        self.available = False

    def start(self) -> bool:
        if not all([TFLITE_AVAILABLE, NUMPY_AVAILABLE, CV2_AVAILABLE]):
            logger_vision.warning("Vision unavailable — missing deps (tflite/numpy/cv2)")
            return False

        if not os.path.exists(MODEL_FILE):
            logger_vision.warning("Model file %s not found — detection unavailable", MODEL_FILE)
            return False

        try:
            self.interpreter = tflite.Interpreter(model_path=MODEL_FILE)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()

            # Validate input tensor (Review #9)
            dtype = self.input_details[0]['dtype']
            if dtype not in (np.float32, np.uint8, np.int8):
                logger_vision.error("Unsupported input dtype %s — detection DISABLED", dtype)
                self.interpreter = None
                return False

            # Validate outputs — disable detection if identification fails
            # (Review #10)
            self.output_map = identify_tflite_outputs(self.output_details)
            if self.output_map is None:
                self.interpreter = None
                logger_vision.error("TFLite tensor validation failed — detection DISABLED")
                return False
        except Exception as e:
            logger_vision.error("TFLite init error: %s", e, exc_info=True)
            return False

        # Load labels
        try:
            with open(LABELS_FILE, "r") as f:
                self.labels = [line.strip() for line in f.readlines()]
            if not self.labels:
                logger_vision.warning("Labels file is empty — detection DISABLED")
                self.interpreter = None
                return False
        except Exception as e:
            logger_vision.warning("Could not load labels: %s — detection DISABLED", e)
            self.interpreter = None
            return False

        self.available = True
        logger_vision.info("Vision system online (input dtype=%s)",
                    self.input_details[0]['dtype'])
        return True

    def detect_objects(self, frame, threshold=DETECTION_THRESHOLD):
        """Detect objects using validated tensor map + quantization-aware
        input handling (Review #9, #10)."""
        if not self.available or self.interpreter is None or frame is None:
            return []

        try:
            with measure("tflite_preprocess"):
                input_data = prepare_input(self.input_details[0], frame)
            if input_data is None:
                # Unsupported tensor configuration — disable safely (Review #9)
                self.available = False
                logger_vision.error("Input preparation failed — detection disabled")
                return []

            with measure("tflite_inference"):
                self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
                self.interpreter.invoke()

                bi = self.output_map["boxes"]
                ci = self.output_map["classes"]
                si = self.output_map["scores"]

                boxes = self.interpreter.get_tensor(self.output_details[bi]['index'])[0]
                class_ids = self.interpreter.get_tensor(self.output_details[ci]['index'])[0].astype(int)
                scores = self.interpreter.get_tensor(self.output_details[si]['index'])[0]

            # Strict length validation — all N values must match (Review #10)
            if not (len(boxes) == len(class_ids) == len(scores)):
                logger_vision.error("Output tensor length mismatch — skipping detection")
                return []

            # Dequantize outputs if needed (Review #9). Both scores AND boxes
            # must be dequantized for fully-integer quantized models (M3) —
            # previously only scores were, so navigation's normalized-coordinate
            # comparisons (0.25/0.35 thresholds) were meaningless with integer
            # box outputs.
            for key, idx in (("scores", si), ("boxes", bi)):
                detail = self.output_details[idx]
                quant = detail.get('quantization', (0.0, 0))
                if quant and quant[0] > 0 and detail['dtype'] in (np.uint8, np.int8):
                    if key == "scores":
                        scores = (scores.astype(np.float32) - quant[1]) * quant[0]
                    else:
                        boxes = (boxes.astype(np.float32) - quant[1]) * quant[0]

            detections = []
            for i in range(len(scores)):
                if scores[i] > threshold:
                    class_id = class_ids[i]
                    label = self.labels[class_id] if 0 <= class_id < len(self.labels) \
                        else f'Object{class_id}'
                    detections.append({
                        'label': label,
                        'confidence': float(scores[i]),
                        'box': boxes[i].tolist(),
                        'class_id': int(class_id)
                    })
            return detections
        except Exception as e:
            logger_vision.error("Object detection error: %s", e, exc_info=True)
            return []

    def describe_scene(self, frame):
        """Describe scene via a vision LLM.

        Primary: the alternate OpenAI-compatible provider configured via
        NEXUS_VISION_API_KEY / NEXUS_VISION_BASE_URL / NEXUS_VISION_MODEL
        (recommended: Groq — fast inference, free tier). Falls back to the
        Sarvam gemma4 endpoint when not configured. The frame is downscaled
        in memory before upload to keep the request fast on Pi hardware.
        """
        if frame is None:
            return "I cannot see right now."

        use_alt = bool(NEXUS_VISION_API_KEY and NEXUS_VISION_BASE_URL)
        if not use_alt and not SARVAM_KEY:
            return "Vision API unavailable — no API key."

        try:
            with measure("cloud_vision"):
                if OpenAI is None:
                    return "Vision API client unavailable."

                if use_alt:
                    client = self._alt_vision_client()
                    model = NEXUS_VISION_MODEL
                else:
                    client = OpenAI(api_key=SARVAM_KEY, base_url="https://api.sarvam.ai/v2")
                    model = SARVAM_VISION_MODEL

                img_b64 = self._encode_frame_b64(frame)

                prompt = ("Describe what you see in this image in 2-3 sentences. "
                          "Be concise.")
                reply_lang = (NEXUS_REPLY_LANGUAGE or "").strip()
                if reply_lang:
                    # Match the conversation language (e.g. Gujarati) so
                    # spoken vision answers stay consistent with chat.
                    prompt += f" Write your answer in {reply_lang}."

                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url",
                                 "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                            ]
                        }
                    ],
                    max_tokens=200
                )
                return response.choices[0].message.content
        except Exception as e:
            logger_vision.error("Scene description error: %s", e, exc_info=True)
            return "I had trouble analyzing the image."

    _alt_vision_client_obj = None

    def _alt_vision_client(self):
        """Create the alternate-provider client once and reuse it."""
        if self._alt_vision_client_obj is None:
            self._alt_vision_client_obj = OpenAI(
                api_key=NEXUS_VISION_API_KEY,
                base_url=NEXUS_VISION_BASE_URL,
                timeout=30.0, max_retries=1)
        return self._alt_vision_client_obj

    @staticmethod
    def _encode_frame_b64(frame, max_width=640):
        """JPEG-encode a frame in memory, downscaling for a fast upload.

        Keeps the debug capture on disk too (VISION_CAPTURE_PATH) so the
        last vision frame is still inspectable, but uploads the smaller
        image — a 640px JPEG at quality 80 is typically < 100 KB, so the
        request is quick even over Wi-Fi.
        """
        try:
            cv2.imwrite(VISION_CAPTURE_PATH, frame)
        except Exception:
            pass
        h, w = frame.shape[:2]
        if w > max_width:
            scale = max_width / float(w)
            small = cv2.resize(frame, (max_width, int(h * scale)))
        else:
            small = frame
        ok, buf = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not ok:
            raise RuntimeError("jpeg encode failed")
        return base64.b64encode(buf.tobytes()).decode("utf-8")


vision_system = VisionSystem()


# ----------------------------------------------------------------------
# Atomic JSON write helper (Review #25, #26)
# ----------------------------------------------------------------------
def atomic_write_json(path, data):
    """
    Atomically write JSON data: tmp file → flush/fsync → rename.
    Power loss during write cannot corrupt the primary file
    (Review #25, #26).
    """
    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)  # atomic rename
    except Exception as e:
        logger_vision.error("Atomic write failed for %s: %s", path, e)
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def save_vision_memory(frame, description):
    """Persist vision snapshot to disk. Log file updated atomically
    (Review #26)."""
    os.makedirs(VISION_MEMORY_DIR, exist_ok=True)
    try:
        ts = time.strftime("%Y%m%d-%H%M%S")
        image_path = os.path.join(VISION_MEMORY_DIR, f"snapshot_{ts}.jpg")
        cv2.imwrite(image_path, frame)

        log = []
        try:
            with open(VISION_MEMORY_FILE, "r") as f:
                log = json.load(f)
        except Exception:
            pass

        log.append({"timestamp": ts, "image_path": image_path,
                    "description": description})

        while len(log) > MAX_VISION_MEMORY:
            old = log.pop(0)
            try:
                if os.path.exists(old.get("image_path", "")):
                    os.remove(old["image_path"])
            except Exception:
                pass

        # Atomic write (Review #26)
        atomic_write_json(VISION_MEMORY_FILE, log)
    except Exception as e:
        logger_vision.error("Could not save vision memory: %s", e)


# ----------------------------------------------------------------------
# Background vision-memory persistence (vision-performance pass, req. 5)
# ----------------------------------------------------------------------
_vision_io_queue: "queue.Queue" = queue.Queue(maxsize=20)
_vision_io_thread = None
_vision_io_lock = threading.Lock()


def save_vision_memory_async(frame, description):
    """
    Enqueue a vision-memory save WITHOUT blocking the response (req. 5).

    The disk write (image + JSON log) happens on a background daemon
    thread, so a slow SD card can never increase conversational latency.
    The queue is bounded; if it is full the oldest pending save is dropped
    (vision memory is a rolling log of the last 20 snapshots anyway).
    """
    try:
        _vision_io_queue.put_nowait((frame, description))
    except queue.Full:
        try:
            _vision_io_queue.get_nowait()          # drop the oldest pending save
            _vision_io_queue.put_nowait((frame, description))
        except Exception:
            pass                                    # never block the caller
    _ensure_vision_io_worker()


def _ensure_vision_io_worker():
    global _vision_io_thread
    with _vision_io_lock:
        if _vision_io_thread is not None and _vision_io_thread.is_alive():
            return
        _vision_io_thread = threading.Thread(target=_vision_io_loop, daemon=True,
                                             name="vision-io")
        _vision_io_thread.start()


def _vision_io_loop():
    while True:
        item = _vision_io_queue.get()
        if item is None:
            break
        frame, description = item
        try:
            save_vision_memory(frame, description)
        except Exception as e:
            logger_vision.error("Background vision-memory save failed: %s", e)


# ----------------------------------------------------------------------
# Background VisionWorker (vision-performance pass, req. 2)
# ----------------------------------------------------------------------
class VisionWorker:
    """
    Continuously captures the latest frame and runs local TFLite object
    detection on a background thread (req. 2).

    Thread-safe state (one lock guards everything):
        frame        — latest captured frame (numpy array or None)
        detections   — latest local detections (list, possibly empty)
        timestamp    — time.time() of the last completed detection
        description  — optional latest cloud scene description

    The main conversation loop NEVER blocks waiting for a new frame when
    get_snapshot() returns fresh cached data; a stale/missing cache falls
    back to a synchronous fresh capture (req. 9). The worker touches only
    the camera and the TFLite interpreter — never motor/safety state
    (req. 8).
    """

    def __init__(self, camera=None, vision=None, on_frame=None,
                 poll_interval=0.1):
        self._camera = camera
        self._vision = vision
        self._on_frame = on_frame
        self._poll_interval = poll_interval
        self._lock = threading.Lock()
        self._state = {"frame": None, "detections": None,
                       "timestamp": 0.0, "description": None}
        self._running = False
        self._thread = None

    # ----------------------------------------------------------------
    # Lifecycle
    # ----------------------------------------------------------------
    def start(self, camera=None):
        """Start the worker. Returns True if running."""
        if self._running:
            return True
        if camera is not None:
            self._camera = camera
        if self._camera is None:
            pass  # relative import removed (global available)
            self._camera = camera_manager
        if self._vision is None:
            self._vision = vision_system
        if not getattr(self._vision, "available", False):
            logger_vision.info("Vision worker not started — local detection unavailable")
            return False
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="vision-worker")
        self._thread.start()
        logger_vision.info("Vision worker started (continuous local detection)")
        return True

    def stop(self, timeout=2.0):
        """Stop the worker. Idempotent; safe from shutdown handlers."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger_vision.warning("Vision worker did not stop within %.1fs", timeout)
            self._thread = None

    @property
    def is_running(self):
        return self._running

    # ----------------------------------------------------------------
    # Thread-safe state access (req. 8)
    # ----------------------------------------------------------------
    def get_snapshot(self, max_age=None):
        """
        Return a copy of the latest vision state if it is fresh enough,
        else None (stale data is clearly distinguishable from fresh —
        req. 9). Freshness defaults to VISION_CACHE_AGE (see config).
        """
        if max_age is None:
            max_age = VISION_CACHE_AGE
        with self._lock:
            if self._state["detections"] is None or self._state["timestamp"] <= 0:
                return None
            if time.time() - self._state["timestamp"] > max_age:
                return None
            return dict(self._state)

    def set_description(self, text):
        """Store the latest (cloud) scene description (req. 2)."""
        with self._lock:
            self._state["description"] = text

    def get_description(self):
        with self._lock:
            return self._state["description"]

    # ----------------------------------------------------------------
    # Worker loop
    # ----------------------------------------------------------------
    def _run(self):
        while self._running:
            try:
                if not getattr(self._camera, "available", False):
                    time.sleep(1.0)
                    continue
                frame = self._camera.capture()
                if frame is None:
                    time.sleep(0.5)
                    continue
                detections = self._vision.detect_objects(frame)
                with self._lock:
                    self._state["frame"] = frame
                    self._state["detections"] = detections
                    self._state["timestamp"] = time.time()
                # Keep the AI text context fresh (local detections only —
                # text, never images; TTL still enforced by VisionContext)
                labels = []
                for d in detections:
                    if d["label"] not in labels:
                        labels.append(d["label"])
                if labels:
                    vision_context.set(f"{', '.join(labels[:8])} "
                                        f"(local object detection)")
                if self._on_frame is not None:
                    try:
                        self._on_frame(frame)
                    except Exception:
                        pass
                time.sleep(self._poll_interval)
            except Exception as e:
                logger_vision.error("Vision worker error: %s", e)
                time.sleep(1.0)


# Singleton
vision_worker = VisionWorker()


# ==========================================================================
# ======== MODULE: nexus/navigation.py ===========================
# ==========================================================================
# """
# Nexus Robot — Navigation (Review P1 #15, #16)
#
# Uses bounding-box size as proximity indicator + obstacle check.
# Does NOT use blind fixed timers — re-detects after each step.
# Safety controller can interrupt at any point.
#
# Fixes:
# - Every movement checks the execute_move result (accepted/rejected) and
  # reacts accordingly (Review #15).
# - Every movement uses the blocking motor API with a timeout, so no
  # navigation loop can leave a command running indefinitely (Review #16).
# - Collision sensor is checked via SafetyController before/while moving
  # (Review #6).
#
# NOTE: This is APPROXIMATE navigation for a demo robot without depth
# sensors. True collision avoidance requires ToF/ultrasonic/LiDAR (Review #6).
# """
import logging


logger_navigation = logging.getLogger("Nexus.Navigation")


def _vlm_ask(frame, question):
    """Ask the configured cloud vision LLM a yes/no-ish question about a
    frame. Returns its short answer text, or None when unavailable/failing.
    Used as the perception fallback for navigation — the tiny offline COCO
    detector misses many everyday objects (bottles, remotes, cups)."""
    if frame is None:
        return None
    if not (NEXUS_VISION_API_KEY and NEXUS_VISION_BASE_URL):
        return None
    if OpenAI is None:
        return None
    try:
        img_b64 = vision_system._encode_frame_b64(frame)
        client = vision_system._alt_vision_client()
        resp = client.chat.completions.create(
            model=NEXUS_VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": question},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
            max_tokens=5)
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger_navigation.warning("VLM navigation question failed: %s", e)
        return None


def _vlm_locate_object(frame, target_object):
    """Cloud-VLM fallback for find_object_position(): ask where the target
    is in the frame (LEFT / CENTER / RIGHT / NO). Returns a synthetic
    position dict compatible with the navigation loop, or None."""
    ans = _vlm_ask(frame,
                   f"Is there a {target_object} visible in this image? "
                   "Answer with exactly one word: LEFT, CENTER, RIGHT, or NO.")
    if not ans:
        return None
    a = ans.upper()
    if "LEFT" in a:
        cx = 0.2
    elif "RIGHT" in a:
        cx = 0.8
    elif ("CENTER" in a) or ("MIDDLE" in a) or ("FRONT" in a):
        cx = 0.5
    else:
        return None
    logger_navigation.info("VLM located %s at %s (center_x=%.1f)",
                target_object, a.split()[0] if a.split() else a, cx)
    return {"found": True, "center_x": cx, "center_y": 0.5,
            "label": target_object, "box_width": 0.2, "confidence": 0.6}


def find_object_position(detections, target_object):
    """Find target object in detections. Returns dict with found/center/bbox_width."""
    target_lower = target_object.lower()
    for det in detections:
        if target_lower in det['label'].lower():
            box = det['box']
            box_width = box[3] - box[1]
            return {
                'found': True,
                'center_x': (box[1] + box[3]) / 2,
                'center_y': (box[0] + box[2]) / 2,
                'confidence': det['confidence'],
                'label': det['label'],
                'box_width': box_width,
            }
    return {'found': False}


def _check_obstacle_ahead(detections, target_label):
    """Check for obstacles in the center of frame."""
    for det in detections:
        if det['label'].lower() == target_label.lower():
            continue
        box = det['box']
        center_x = (box[1] + box[3]) / 2
        box_width = box[3] - box[1]
        if 0.3 < center_x < 0.7 and box_width > 0.15:
            return det['label']
    return None


def _do_move(direction, duration, source, timeout=MOTOR_COMMAND_TIMEOUT):
    """
    Execute a movement and check its result (Review #15).
    Uses the blocking API so navigation waits for completion before
    issuing the next command — this prevents commands being rejected
    because a prior movement is still active (Review #2).
    Every movement has a timeout (Review #16).
    """
    result = motor.execute_move(
        direction, duration=duration, source=source,
        wait=True, timeout=timeout,
    )
    status = result.get("status")
    if status == "denied":
        logger_navigation.warning("Navigation move denied: %s (%s)", direction, result.get("reason"))
        return False
    if status == "timeout":
        logger_navigation.warning("Navigation move timed out: %s", direction)
        return False
    if status == "interrupted":
        # Interrupted by STOP or collision — navigation should stop
        logger_navigation.info("Navigation move interrupted: %s (%s)", direction, result.get("reason"))
        return False
    return True


def navigate_to_object(target_object):
    """
    Navigate toward a target object using vision-guided steps.
    Stops when object bounding box is large enough (close).
    Checks for obstacles before each forward move.
    Safety controller can interrupt at any point.

    Every movement checks its result (Review #15) and has a timeout
    (Review #16). A voice safety-stop is heard via the SafetyListener (C2/C6).
    """

    logger_navigation.info("Navigation started: target=%s", target_object)
    speak(f"Looking for {target_object}.")

    safety_listener.start()
    try:
        return _navigate_loop(target_object, safety_listener)
    finally:
        safety_listener.finish()
        face.hide_camera()

def _navigate_loop(target_object, safety_listener):
    vlm_guided_steps = 0
    for step in range(NAV_MAX_STEPS):
        # Abort only on a FAULT or a stop explicitly requested by the safety
        # listener. NOTE: is_stopped() is True whenever the robot is at rest
        # between moves (STOPPED is the normal state), so it must NOT be used
        # as the abort condition — doing so made navigation bail out at step 0
        # without ever moving (C6).
        if motor.safety.is_fault() or safety_listener.stop_requested:
            return "Navigation stopped."

        frame = camera_manager.capture()
        if frame is None:
            return "I cannot see right now."

        # Show the camera preview on the robot's face while navigating
        # (2026-09 fix: the preview used to stay hidden, so it looked like
        # the camera never opened during "find the X").
        face.show_camera_frame(frame)

        detections = vision_system.detect_objects(frame)
        position = find_object_position(detections, target_object)

        if not position['found']:
            # Cloud-VLM fallback (2026-09): the offline COCO detector only
            # knows 80 classes and misses many everyday objects — ask the
            # configured vision LLM where the target is.
            vpos = _vlm_locate_object(frame, target_object)
            if vpos:
                position = vpos
                vlm_guided_steps += 1
                if vlm_guided_steps >= 2:
                    close = _vlm_ask(
                        frame,
                        f"Is the {target_object} close to the camera now, "
                        "filling a large part of the image? Answer YES or NO.")
                    if close and "YES" in close.upper():
                        speak(f"I've reached the {target_object}!")
                        return f"I reached the {target_object}!"

        if not position['found']:
            speak(f"I don't see {target_object}. Let me look around.")
            if not _do_move("right", 1.5, "nav_search"):
                return "I had to stop searching."
            frame = camera_manager.capture()
            position = find_object_position(vision_system.detect_objects(frame), target_object)
            if not position['found']:
                if not _do_move("left", 3.0, "nav_search"):
                    return "I had to stop searching."
                frame = camera_manager.capture()
                position = find_object_position(vision_system.detect_objects(frame), target_object)
                if not position['found']:
                    return f"I cannot find {target_object} nearby."

        label = position['label']
        center_x = position['center_x']
        box_width = position.get('box_width', 0)

        # Stop condition: object is large enough → close
        if box_width > NAV_BBOX_CLOSE_THRESHOLD:
            speak(f"I've reached the {label}!")
            return f"I reached the {label}!"

        # Obstacle check before forward
        obstacle = _check_obstacle_ahead(detections, label)
        if obstacle:
            speak(f"I see a {obstacle} in the way. Stopping for safety.")
            return f"Obstacle ({obstacle}) detected near the {label}. Stopped for safety."

        # Center the object
        if center_x < 0.35:
            if not _do_move("left", 0.5, "nav_center"):
                return "Navigation stopped."
        elif center_x > 0.65:
            if not _do_move("right", 0.5, "nav_center"):
                return "Navigation stopped."

        # Forward — short steps, re-check after each
        if 0.35 <= center_x <= 0.65:
            speak(f"Moving toward the {label}.")
            if not _do_move("forward", 1.0, "nav_forward"):
                return "Navigation stopped."

    return f"I got close to the {target_object} but couldn't reach it."


# ==========================================================================
# ======== MODULE: nexus/face_display.py =========================
# ==========================================================================
# """
# Nexus Robot — Face Display (pygame animated robot face)
#
# Rendered on the MAIN thread (SDL/pygame is unreliable from background threads).
# Mood and robot state are separated — this module just renders what it's told.
# """
import math
import random
import threading
import time
import logging


logger_face_display = logging.getLogger("Nexus.FaceDisplay")

try:
    import pygame
    PYGAME_AVAILABLE = True
except Exception:
    pygame = None
    PYGAME_AVAILABLE = False

FACE_BG = (8, 10, 18)

try:
    import os
    os.environ.setdefault("SDL_NOMOUSE", "1")
    if os.environ.get("FACE_FBDEV"):
        os.environ.setdefault("SDL_VIDEODRIVER", "fbcon")
        os.environ["SDL_FBDEV"] = os.environ["FACE_FBDEV"]
except Exception:
    pass


class FaceDisplay:
    """Animated robot face. State is set externally; rendering happens in tick()."""

    VALID_STATES = {"idle", "listening", "thinking", "talking", "happy", "sad",
                    "moving", "asleep", "playing", "navigating", "guarding"}

    def __init__(self):
        self.state = "idle"
        self._mood = "neutral"
        self._running = False
        self._lock = threading.Lock()
        self._screen = None
        self._clock = None
        self._blink_timer = time.time() + random.uniform(2, 5)
        self._blink_progress = 0.0
        self._blinking = False
        self._look_x = 0.0
        self._look_target = 0.0
        self._look_timer = time.time() + random.uniform(1.5, 3.5)
        self._move_look = 0.0
        self._move_until = 0.0
        self._talk_phase = 0.0
        self._camera_mode = False
        self._camera_frame = None
        self._sleep_z_phase = 0.0
        self._excite_bounce = 0.0

    def start(self):
        if not PYGAME_AVAILABLE:
            logger_face_display.warning("pygame not installed — face display disabled")
            return
        if self._screen is not None:
            return
        try:
            pygame.init()
            flags = pygame.FULLSCREEN if FACE_FULLSCREEN else 0
            self._screen = pygame.display.set_mode((FACE_WIDTH, FACE_HEIGHT), flags)
            pygame.mouse.set_visible(False)
            pygame.display.set_caption("Nexus Face")
        except Exception as e:
            logger_face_display.error("Face display init failed: %s", e)
            self._screen = None
            return
        self._clock = pygame.time.Clock()
        self._running = True
        logger_face_display.info("Face display started")

    def set_state(self, state):
        if state in self.VALID_STATES and self._screen is not None:
            with self._lock:
                self.state = state

    def set_mood(self, m):
        with self._lock:
            self._mood = m if m in MOOD_COLORS else "neutral"

    def nudge_look(self, direction, hold_seconds=0.9):
        if self._screen is None:
            return
        bias = {"left": -1.0, "right": 1.0, "forward": 0.0, "back": 0.0, "spin": 1.0, "stop": 0.0}.get(direction, 0.0)
        with self._lock:
            self._move_look = bias
            self._move_until = time.time() + hold_seconds
            self.state = "moving"

    def show_camera_frame(self, frame):
        if self._screen is None:
            return
        with self._lock:
            self._camera_mode = True
            self._camera_frame = frame

    def update_camera_frame(self, frame):
        if self._screen is None:
            return
        with self._lock:
            if self._camera_mode:
                self._camera_frame = frame

    def hide_camera(self):
        with self._lock:
            self._camera_mode = False
            self._camera_frame = None

    def stop(self):
        self._running = False
        if PYGAME_AVAILABLE:
            try:
                pygame.quit()
            except Exception:
                pass

    def request_stop(self):
        """Ask the render loop to stop without touching pygame — safe to call
        from a background thread (unlike stop())."""
        self._running = False

    _printed_error = False

    def tick(self):
        if self._screen is None or not self._running:
            return
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._running = False
        try:
            self._draw_frame()
        except Exception as e:
            if not self._printed_error:
                logger_face_display.error("Face render error: %s", e)
                self._printed_error = True
        self._clock.tick(30)

    def _draw_frame(self):
        now = time.time()
        with self._lock:
            move_active = now < self._move_until
            if self.state == "moving" and not move_active:
                self.state = "idle"
            state = self.state
            move_look = self._move_look
            camera_mode = self._camera_mode
            camera_frame = self._camera_frame
            current_mood = self._mood

        screen = self._screen
        screen.fill(FACE_BG)

        if camera_mode and camera_frame is not None:
            try:
                import cv2
                rgb = cv2.cvtColor(camera_frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[0], rgb.shape[1]
                surf = pygame.image.frombuffer(rgb.tobytes(), (w, h), "RGB")
                surf = pygame.transform.scale(surf, (FACE_WIDTH, FACE_HEIGHT))
                screen.blit(surf, (0, 0))
                pygame.draw.rect(screen, (60, 200, 255), screen.get_rect(), 4)
            except Exception as e:
                if not self._printed_error:
                    logger_face_display.error("Camera preview render error: %s", e)
                    self._printed_error = True
            pygame.display.flip()
            return

        cx, cy = FACE_WIDTH // 2, FACE_HEIGHT // 2
        eye_w, eye_h = int(FACE_WIDTH * 0.14), int(FACE_HEIGHT * 0.28)
        eye_gap = int(FACE_WIDTH * 0.22)
        eye_y = cy - int(FACE_HEIGHT * 0.08)

        if state == "sad":
            color = (230, 100, 90)
        elif state == "thinking":
            color = (230, 190, 60)
        elif state == "moving":
            color = (170, 120, 255)
        else:
            color = MOOD_COLORS.get(current_mood, (60, 200, 255))

        # Sleeping animation
        if state == "asleep":
            self._sleep_z_phase += 0.02
            for side in (-1, 1):
                ex = cx + side * eye_gap
                pygame.draw.line(screen, color, (ex - eye_w // 2, eye_y), (ex + eye_w // 2, eye_y), 5)
            try:
                font = pygame.font.Font(None, int(FACE_HEIGHT * 0.18))
                for i, z_char in enumerate(["z", "Z", "Z"]):
                    zy = eye_y - int(FACE_HEIGHT * 0.15) - i * int(FACE_HEIGHT * 0.1)
                    zx = cx + int(FACE_WIDTH * 0.12) + i * int(FACE_WIDTH * 0.06)
                    offset = math.sin(self._sleep_z_phase + i * 1.2) * 4
                    alpha = max(30, 200 - i * 60)
                    z_surf = font.render(z_char, True, color)
                    z_surf.set_alpha(alpha)
                    screen.blit(z_surf, (zx, zy + offset))
            except Exception:
                pass
            breath = (math.sin(self._sleep_z_phase * 0.7) * 0.5 + 0.5)
            mh = max(3, int(breath * FACE_HEIGHT * 0.04))
            rect = pygame.Rect(0, 0, int(FACE_WIDTH * 0.12), mh)
            rect.center = (cx, cy + int(FACE_HEIGHT * 0.22))
            pygame.draw.ellipse(screen, color, rect)
            pygame.display.flip()
            return

        # Look direction
        if state == "moving" and move_active:
            self._look_target = move_look
        elif now > self._look_timer:
            self._look_target = random.uniform(-1, 1)
            self._look_timer = now + random.uniform(1.5, 4.0)
        self._look_x += (self._look_target - self._look_x) * (0.25 if state == "moving" else 0.05)
        look_offset = int(self._look_x * FACE_WIDTH * 0.05)

        # Blinking
        if state != "moving" and current_mood != "excited":
            if not self._blinking and now > self._blink_timer:
                self._blinking = True
            if self._blinking:
                self._blink_progress += 0.25
                if self._blink_progress >= 1.0:
                    self._blink_progress = 0.0
                    self._blinking = False
                    self._blink_timer = now + random.uniform(2.5, 6.0)
        else:
            self._blinking = False
            self._blink_progress = 0.0
        blink_scale = abs(math.sin(self._blink_progress * math.pi)) if self._blinking else 0.0

        bounce_y = 0
        if current_mood == "excited" and state not in ("talking", "thinking", "asleep"):
            self._excite_bounce += 0.15
            bounce_y = int(math.sin(self._excite_bounce) * FACE_HEIGHT * 0.03)

        for side in (-1, 1):
            ex = cx + side * eye_gap + look_offset
            h = int(eye_h * (1 - 0.85 * blink_scale))
            if current_mood == "sleepy":
                h = int(h * 0.45)
            elif current_mood == "annoyed":
                h = int(h * 0.55)
            elif current_mood == "excited":
                h = int(h * 1.15)
            elif current_mood == "curious":
                h = int(h * (1.15 if side > 0 else 0.9))
            rect = pygame.Rect(0, 0, eye_w, max(h, 4))
            rect.center = (ex, eye_y + bounce_y)
            try:
                pygame.draw.rect(screen, color, rect, border_radius=eye_w // 3)
            except TypeError:
                pygame.draw.rect(screen, color, rect)
            if state == "happy" or current_mood == "happy":
                cover = pygame.Rect(0, 0, eye_w + 6, eye_h // 2)
                cover.midtop = (ex, eye_y + bounce_y)
                pygame.draw.ellipse(screen, FACE_BG, cover)

        mouth_y = cy + int(FACE_HEIGHT * 0.22)

        if state == "talking":
            self._talk_phase += 0.35
            open_amt = (math.sin(self._talk_phase) * 0.5 + 0.5) * random.uniform(0.6, 1.0)
            mh = max(4, int(open_amt * FACE_HEIGHT * 0.12))
            rect = pygame.Rect(0, 0, int(FACE_WIDTH * 0.28), mh)
            rect.center = (cx, mouth_y)
            pygame.draw.ellipse(screen, color, rect)
        elif state == "happy" or current_mood == "happy":
            rect = pygame.Rect(0, 0, int(FACE_WIDTH * 0.28), int(FACE_HEIGHT * 0.14))
            rect.center = (cx, mouth_y - int(FACE_HEIGHT * 0.02))
            pygame.draw.arc(screen, color, rect, math.pi * 1.15, math.pi * 1.85, 6)
        elif state == "sad":
            rect = pygame.Rect(0, 0, int(FACE_WIDTH * 0.28), int(FACE_HEIGHT * 0.14))
            rect.center = (cx, mouth_y + int(FACE_HEIGHT * 0.05))
            pygame.draw.arc(screen, color, rect, math.pi * 0.15, math.pi * 0.85, 6)
        elif state == "listening":
            pygame.draw.circle(screen, color, (cx, mouth_y), max(4, int(FACE_HEIGHT * 0.02)))
        elif state == "thinking":
            for i in range(3):
                phase = (now * 3 + i * 0.6) % (2 * math.pi)
                r = int(4 + 3 * (math.sin(phase) * 0.5 + 0.5))
                pygame.draw.circle(screen, color, (cx - 24 + i * 24, mouth_y), r)
        elif state == "moving":
            pygame.draw.circle(screen, color, (cx, mouth_y), max(5, int(FACE_HEIGHT * 0.03)))
        elif current_mood == "annoyed":
            pygame.draw.line(screen, color, (cx - int(FACE_WIDTH * 0.1), mouth_y), (cx + int(FACE_WIDTH * 0.1), mouth_y), 6)
        elif current_mood == "excited":
            rect = pygame.Rect(0, 0, int(FACE_WIDTH * 0.3), int(FACE_HEIGHT * 0.16))
            rect.center = (cx, mouth_y)
            pygame.draw.arc(screen, color, rect, math.pi * 1.1, math.pi * 1.9, 7)
        else:
            pygame.draw.line(screen, color, (cx - int(FACE_WIDTH * 0.14), mouth_y), (cx + int(FACE_WIDTH * 0.14), mouth_y), 4)

        pygame.display.flip()


# Singleton
face = FaceDisplay()


# ==========================================================================
# ======== MODULE: nexus/face_recognition.py =====================
# ==========================================================================
# """
# Nexus Robot — Face Recognition (Review P1 #12, #13, #14)
#
# - camera_manager injection: enroll_face always uses the supplied manager
  # when one is provided (Review #12).
# - Privacy controls (Review #13): delete face, delete all faces,
  # disable-face-storage option, configurable retention, restrictive
  # filesystem permissions, no biometric logging.
# - Missing face-data directory handled safely (Review #14).
# - Names are sanitized to safe filesystem characters.
# """
import os
import re
import time
import json
import logging
import shutil
from pathlib import Path


logger_face_recognition = logging.getLogger("Nexus.FaceRecog")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False

# Face detection cascades
_cascade_path = None
_face_cascade = None
_extra_cascades = []   # alt cascades tried when the default one misses
_face_recognizer = None

_CASCADE_FILENAMES = (
    "haarcascade_frontalface_default.xml",
    "haarcascade_frontalface_alt2.xml",      # often the most robust one
    "haarcascade_frontalface_alt.xml",
    "haarcascade_profileface.xml",          # side views while turning
)

def _find_cascade(filename=None):
    """Search the usual locations for a Haar cascade XML.

    2026-09 fix: on some installs (stripped/headless wheels, apt builds)
    cv2.data.haarcascades is missing — fall back to the script directory
    and the standard Debian/Raspberry Pi OS paths instead of dying."""
    if filename is None:
        filename = _CASCADE_FILENAMES[0]
    candidates = []
    try:
        candidates.append(os.path.join(cv2.data.haarcascades, filename))
    except Exception:
        pass
    try:
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       filename))
    except Exception:
        pass
    candidates += [
        f"/usr/share/opencv/haarcascades/{filename}",
        f"/usr/share/opencv4/haarcascades/{filename}",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


if CV2_AVAILABLE:
    for _fname in _CASCADE_FILENAMES:
        _p = _find_cascade(_fname)
        if not _p:
            continue
        _cls = cv2.CascadeClassifier(_p)
        if _cls.empty():
            continue
        if _face_cascade is None:
            _cascade_path = _p
            _face_cascade = _cls
        else:
            _extra_cascades.append(_cls)
    if _face_cascade is None:
        logging.getLogger("Nexus.FaceRec").warning(
            "Haar cascades not found in cv2.data, script dir, or /usr/share — "
            "install with: pip install opencv-contrib-python")

    try:
        _face_recognizer = cv2.face.LBPHFaceRecognizer_create()
    except Exception:
        _face_recognizer = None

FACE_RECOGNIZER_AVAILABLE = _face_recognizer is not None
FACE_CASCADE_AVAILABLE = _face_cascade is not None
_recognizer_loaded = False

# All face crops are resized to this before training/predicting — LBPH
# compares histograms pixel-for-pixel, so enrollment and recognition crops
# MUST have the same size for good match distances (2026-09).
_FACE_CROP_SIZE = (200, 200)


def _load_recognizer_from_disk():
    """Load a previously trained model so recognition survives a reboot (C3).

    Without this, every restart created an empty LBPH recognizer, so nobody
    was ever recognised after the process restarted — only within the session
    that enrolled them.
    """
    global _recognizer_loaded
    if _face_recognizer is None or not os.path.exists(FACE_RECOGNIZER_FILE):
        return
    try:
        _face_recognizer.read(FACE_RECOGNIZER_FILE)
        _recognizer_loaded = True
        logger_face_recognition.info("Loaded face recognizer from %s", os.path.basename(FACE_RECOGNIZER_FILE))
    except Exception as e:
        logger_face_recognition.warning("Could not load face recognizer: %s", type(e).__name__)


# Load any saved model at import time (C3)
_load_recognizer_from_disk()

# Name sanitization (Bug #15)
_SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_-]")


def sanitize_name(name):
    """Sanitize user-provided name for filesystem use (Bug #15)."""
    name = name.strip().lower().replace(" ", "_")
    name = _SAFE_NAME_RE.sub("", name)
    # Remove path separators just in case
    name = name.replace("/", "").replace("\\", "").replace("..", "")
    return name if name else "unknown"


def _detect_faces(frame):
    """Detect faces using Haar cascades. Returns list of (x, y, w, h).

    2026-09 robustness pass (Raspberry Pi, 32-bit, full-sensor frames):
    - downscale to <=800px wide before detection — Haar on an 8MP frame
      takes seconds per scan and often finds nothing usable;
    - try MULTIPLE cascades (default → alt2 → alt → profile) and multiple
      parameter sets before giving up — the default cascade alone misses
      far too many real faces in indoor light;
    - histogram-equalize the gray image (big help in dim rooms), with a
      final fallback attempt on the raw (unequalized) image;
    - coordinates are mapped back to the original frame size.
    """
    if _face_cascade is None or frame is None:
        return []
    try:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        scale = 1.0
        if w > 800:
            scale = 800.0 / w
            gray = cv2.resize(gray, (800, max(1, int(round(h * scale)))))
        try:
            eq = cv2.equalizeHist(gray)
        except cv2.error:
            eq = gray

        cascades = [_face_cascade] + list(_extra_cascades)
        # (image, scaleFactor, minNeighbors) attempts, first hit wins
        attempts = []
        for cls in cascades:
            attempts.append((cls, eq, 1.2, 4))
        for cls in cascades:
            attempts.append((cls, eq, 1.1, 3))
        attempts.append((cascades[0], gray, 1.1, 3))   # raw, no equalize

        for cls, img, sf, mn in attempts:
            faces = cls.detectMultiScale(
                img, scaleFactor=sf, minNeighbors=mn,
                minSize=(FACE_MIN_SIZE, FACE_MIN_SIZE))
            if faces is None or len(faces) == 0:
                continue
            faces = list(faces)
            if scale != 1.0:
                inv = 1.0 / scale
                faces = [(int(x * inv), int(y * inv), int(w * inv), int(h * inv))
                          for (x, y, w, h) in faces]
            return faces
        return []
    except Exception as e:
        logger_face_recognition.error("Face detection error: %s", e, exc_info=True)
        return []


def _reset_recognizer():
    """Drop all in-memory training when face data is deleted (C3).

    The previous version kept a stale trained recognizer in memory after
    delete_all_faces/delete_face, so removed people were still recognised
    until restart.
    """
    global _face_recognizer, _recognizer_loaded
    try:
        _face_recognizer = cv2.face.LBPHFaceRecognizer_create()
        _recognizer_loaded = False
    except Exception:
        _face_recognizer = None
        _recognizer_loaded = False


def _train_recognizer():
    """Train LBPH from all enrolled samples."""
    if _face_recognizer is None:
        return False
    # Missing directory = nothing to train (and nothing to remove)
    if not os.path.isdir(KNOWN_FACES_DIR):
        _reset_recognizer()
        return False
    samples = []
    labels = []
    label_map = {}
    label_id = 0

    for person_dir in sorted(Path(KNOWN_FACES_DIR).iterdir()):
        if not person_dir.is_dir():
            continue
        name = person_dir.name
        count = 0
        for img_path in person_dir.glob("*.jpg"):
            try:
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    # Normalize crop size (2026-09 — see _FACE_CROP_SIZE)
                    if img.shape[:2] != _FACE_CROP_SIZE:
                        img = cv2.resize(img, _FACE_CROP_SIZE)
                    samples.append(img)
                    labels.append(label_id)
                    count += 1
            except Exception:
                continue
        if count > 0:
            label_map[label_id] = name
            logger_face_recognition.info("Loaded %d samples for '%s'", count, name)
            label_id += 1

    if not samples:
        # No people left — remove stale model files and drop in-memory state so
        # deleted people are no longer recognised (C3).
        for p in (FACE_RECOGNIZER_FILE,
                  os.path.join(KNOWN_FACES_DIR, "label_map.json")):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except Exception:
                pass
        _reset_recognizer()
        return False

    try:
        _face_recognizer.train(samples, np.array(labels))
        os.makedirs(KNOWN_FACES_DIR, exist_ok=True)
        with open(os.path.join(KNOWN_FACES_DIR, "label_map.json"), "w") as f:
            json.dump(label_map, f)
        _face_recognizer.save(FACE_RECOGNIZER_FILE)
        logger_face_recognition.info("Face recognizer trained with %d people", len(label_map))
        return True
    except Exception as e:
        logger_face_recognition.error("Face recognizer training error: %s", e, exc_info=True)
        return False


def _load_label_map():
    try:
        with open(os.path.join(KNOWN_FACES_DIR, "label_map.json"), "r") as f:
            return {int(k): v for k, v in json.load(f).items()}
    except Exception:
        return {}


def _secure_dir(path):
    """Create directory with restrictive permissions (Review #13)."""
    os.makedirs(path, exist_ok=True)
    try:
        os.chmod(path, FACE_DIR_PERMISSIONS)
    except Exception:
        pass


def _secure_file(path):
    """Set restrictive permissions on a stored face file (Review #13)."""
    try:
        os.chmod(path, FACE_FILE_PERMISSIONS)
    except Exception:
        pass


def _apply_retention(person_dir, max_samples):
    """Keep only the most recent N samples per person (Review #13)."""
    try:
        files = sorted(Path(person_dir).glob("*.jpg"), key=os.path.getmtime)
        while len(files) > max_samples:
            old = files.pop(0)
            os.remove(str(old))
    except Exception:
        pass


def enroll_face(name, camera_manager=None, tts_callback=None, num_samples=FACE_ENROLL_SAMPLES):
    """
    Multi-sample enrollment. Requires EXACTLY ONE face visible.

    Uses the supplied camera_manager when one is provided (Review #12) —
    dependency injection is preserved for testing.

    Privacy (Review #13):
    - Storage can be disabled via NEXUS_FACE_STORAGE=0.
    - Per-person sample retention via FACE_DATA_RETENTION.
    - Files/directories get restrictive permissions.
    - No raw face images or biometric data are logged.
    """
    name = sanitize_name(name)
    if not name:
        return "I need a valid name."

    # Face storage disabled — policy check FIRST (Review #13)
    if not FACE_STORAGE_ENABLED:
        logger_face_recognition.info("Face enrollment refused — face storage disabled by configuration")
        return "Face storage is disabled on this robot, so I can't learn faces."

    if not FACE_CASCADE_AVAILABLE:
        return "I can't detect faces — cascade missing."

    # Always use the supplied manager when provided (Review #12)
    # 2026-09 fix: the parameter shadows the module-level `camera_manager`,
    # and the old fallback (a function-level relative import) is stripped in
    # the combined build — leaving cam = None and crashing the voice loop.
    # Fall back to the global singleton first, then to the package import.
    if camera_manager is None:
        camera_manager = globals().get("camera_manager")
    if camera_manager is None:
        pass  # relative import removed (global available)
    cam = camera_manager
    if cam is None or not getattr(cam, "available", False):
        return "My camera isn't working right now, so I can't learn faces."

    if tts_callback:
        tts_callback(f"Learning your face, {name.replace('_', ' ')}. "
                     "Look at the camera and slowly turn left, right, up and down.")

    person_dir = os.path.join(KNOWN_FACES_DIR, name)
    _secure_dir(person_dir)  # restrictive permissions (Review #13)

    captured = 0
    attempts = num_samples * 3   # 2026-09: extra tries for missed frames
    try:
        for i in range(attempts):
            if captured >= num_samples:
                break
            frame = cam.capture()
            if frame is None:
                time.sleep(0.5)
                continue

            # Show what the robot sees during enrollment (2026-09: the
            # preview used to stay hidden, so a dark/broken camera was
            # invisible to the user).
            try:
                face.show_camera_frame(frame)
            except Exception:
                pass

            faces = _detect_faces(frame)
            logger_face_recognition.info("Enroll frame %d/%d: %dx%d brightness=%.0f faces=%d",
                        i + 1, num_samples, frame.shape[1], frame.shape[0],
                        float(frame.mean()), len(faces))

            # Bug #14: exactly ONE face required
            if len(faces) == 0:
                if i % 3 == 0 and tts_callback:
                    tts_callback("I can't see your face. Move into the camera.")
                time.sleep(0.5)
                continue
            if len(faces) > 1:
                if i % 3 == 0 and tts_callback:
                    tts_callback("I see multiple faces. Please enroll alone.")
                time.sleep(0.5)
                continue

            # Exactly one face — enroll it
            (x, y, w, h) = faces[0]
            # Minimum face size check
            if w < FACE_MIN_SIZE or h < FACE_MIN_SIZE:
                if i % 4 == 0 and tts_callback:
                    tts_callback("Your face is too small. Move closer to the camera.")
                time.sleep(0.5)
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # Normalize the crop size — LBPH match quality depends heavily
            # on enrollment and recognition crops having the same size
            # (2026-09 fix: full-res frames made box sizes vary wildly).
            face_img = cv2.resize(gray[y:y+h, x:x+w], _FACE_CROP_SIZE)

            ts = time.strftime("%Y%m%d-%H%M%S")
            img_path = os.path.join(person_dir, f"{name}_{ts}_{i}.jpg")
            try:
                cv2.imwrite(img_path, face_img)
                _secure_file(img_path)  # restrictive permissions (Review #13)
                captured += 1
            except Exception as e:
                # Log the error only — never the face image or biometric content
                # (Review #13)
                logger_face_recognition.warning("Could not save face image: %s", type(e).__name__)

            if (i + 1) % 4 == 0 and tts_callback:
                tts_callback(f"Captured {captured} samples. Keep turning slowly.")
            time.sleep(0.4)
    finally:
        try:
            face.hide_camera()
        except Exception:
            pass

    if captured == 0:
        return "I couldn't capture any face samples. Please try again."

    if captured < 6 and tts_callback:
        tts_callback("I only got a few samples, so I may not always "
                      "recognize you. Say learn my face again in better "
                      "light to improve it.")

    # Apply retention limit — keep only the most recent N samples (Review #13)
    if FACE_DATA_RETENTION > 0:
        _apply_retention(person_dir, FACE_DATA_RETENTION)

    if _face_recognizer is not None:
        _train_recognizer()

    return f"Great, I've learned your face with {captured} samples, {name.replace('_', ' ')}!"


def recognize_faces(frame):
    """Recognize faces in frame. Returns list of (name, confidence)."""
    if _face_cascade is None or frame is None:
        return []

    faces = _detect_faces(frame)
    if len(faces) == 0:
        return []

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    label_map = _load_label_map()
    results = []

    for (x, y, w, h) in faces:
        # Normalize crop size (2026-09 — see _FACE_CROP_SIZE): must match
        # the enrollment crops or LBPH match distances blow up.
        face_img = cv2.resize(gray[y:y+h, x:x+w], _FACE_CROP_SIZE)
        name = None
        confidence = 999

        if _face_recognizer is not None:
            try:
                if os.path.exists(FACE_RECOGNIZER_FILE):
                    label_id, confidence = _face_recognizer.predict(face_img)
                    if confidence < FACE_CONFIDENCE_THRESHOLD and label_id in label_map:
                        name = label_map[label_id]
            except Exception:
                name = None

        results.append((name, confidence))

    return results


def delete_face(name):
    """Delete a specific person's face data (Review #13)."""
    name = sanitize_name(name)
    person_dir = os.path.join(KNOWN_FACES_DIR, name)
    if not os.path.exists(person_dir):
        return f"I don't have any face data for {name}."

    try:
        shutil.rmtree(person_dir)
        _train_recognizer()
        return f"Deleted all face data for {name}."
    except Exception as e:
        logger_face_recognition.error("Face deletion error: %s", type(e).__name__)
        return "I couldn't delete the face data."


def delete_all_faces():
    """
    Delete ALL face data (Review #13, #14).
    A missing directory is treated as "no face data exists" and returns
    success — deletion must not fail just because the directory doesn't
    exist (Review #14).
    """
    try:
        # Missing directory = no face data exists → success (Review #14)
        if not os.path.exists(KNOWN_FACES_DIR):
            return "All face data has been deleted."

        for person_dir in Path(KNOWN_FACES_DIR).iterdir():
            if person_dir.is_dir():
                shutil.rmtree(person_dir)
        if os.path.exists(FACE_RECOGNIZER_FILE):
            os.remove(FACE_RECOGNIZER_FILE)
        label_map_path = os.path.join(KNOWN_FACES_DIR, "label_map.json")
        if os.path.exists(label_map_path):
            os.remove(label_map_path)
        # Drop the in-memory recognizer so deleted people stop being recognised (C3)
        _reset_recognizer()
        return "All face data has been deleted."
    except Exception as e:
        logger_face_recognition.error("Delete all faces error: %s", type(e).__name__)
        return "I couldn't delete all face data."


# ==========================================================================
# ======== MODULE: nexus/games.py ================================
# ==========================================================================
# """
# Nexus Robot — Mini Games (Bug #18, #19, #20)
#
# Fixes:
# - Simon Says: no longer claims to detect movement — pure voice-response game (Bug #18)
# - Guess the Number: proper compound number parser ("twenty five" → 25) (Bug #19)
# - Trivia: normalized answer matching, no false positives from substrings (Bug #20)
# """
import random
import re
import logging

logger_games = logging.getLogger("Nexus.Games")

# Compound number parser (Bug #19)
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
          "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
          "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
          "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_SPECIAL = {"hundred": 100}


def parse_spoken_number(text, min_val=1, max_val=100):
    """
    Parse a spoken number from text (Review #20).
    Handles: "25", "twenty five", "ninety nine", "one hundred", etc.
    Returns int if in [min_val, max_val], else None.
    Rejects invalid numbers and values outside the game range.
    """
    t = text.lower().strip()

    # Reject negatives (game range is 1-100)
    if t.startswith("-") or "negative" in t.split()[:1]:
        return None

    # Direct digit
    m = re.search(r'\d+', t)
    if m:
        val = int(m.group())
        return val if min_val <= val <= max_val else None

    # Try compound: "twenty five" → 25, "one hundred twenty five" → 125
    words = t.replace("-", " ").split()
    result = 0
    found = False
    for word in words:
        if word in _TENS:
            result += _TENS[word]
            found = True
        elif word in _UNITS:
            result += _UNITS[word]
            found = True
        elif word in _SPECIAL:
            result *= _SPECIAL[word]
            found = True
    if found:
        return result if min_val <= result <= max_val else None

    # Single word number
    for word, val in {**_UNITS, **_TENS, **_SPECIAL}.items():
        if word == t:
            return val if min_val <= val <= max_val else None

    return None


def _wants_quit(text, include_stop=True):
    """True if the user asked to leave the game (H1). Word-based so "stopwatch"
    etc. don't match."""
    if not text:
        return False
    words = set(normalize_answer(text).split())
    quit_words = {"quit", "exit", "cancel", "enough", "done"}
    if include_stop:
        quit_words.add("stop")
    return bool(words & quit_words)


def normalize_answer(text):
    """Normalize answer for comparison."""
    t = text.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)  # remove punctuation
    t = re.sub(r'\s+', ' ', t)     # normalize whitespace
    return t.strip()


# RPS answer aliases — clear, unambiguous only (Review #18)
_RPS_ALIASES = {
    "rock": "rock",
    "rocks": "rock",
    "paper": "paper",
    "scissors": "scissors",
    "scissor": "scissors",
}


def _parse_rps_answer(text):
    """
    Strict RPS answer parsing (Review #18).
    Only accepts normalized answers: rock / paper / scissors
    (with clear aliases). Rejects unrelated sentences.
    Returns "rock"|"paper"|"scissors" or None.
    """
    norm = normalize_answer(text)
    if not norm:
        return None
    # Exact single-word match (or clear alias)
    if norm in _RPS_ALIASES:
        return _RPS_ALIASES[norm]
    # Allow "I choose rock" / "my choice is paper" style — the answer
    # must be the ONLY game word in the sentence
    words = norm.split()
    hits = {w for w in words if w in _RPS_ALIASES}
    filler = {"i", "choose", "my", "choice", "is", "pick", "go", "with", "the", "a"}
    if len(hits) == 1 and all(w in filler or w in _RPS_ALIASES for w in words):
        return _RPS_ALIASES[hits.pop()]
    return None


def trivia_check_answer(user_answer, valid_hints):
    """
    Check if user's answer matches any valid hint (Bug #20).
    Uses normalized exact-word matching, not arbitrary substring.
    """
    norm = normalize_answer(user_answer)
    norm_words = set(norm.split())
    for hint in valid_hints:
        hint_norm = normalize_answer(hint)
        hint_words = set(hint_norm.split())
        # Check if the hint is a subset of the user's answer words
        if hint_words and hint_words.issubset(norm_words):
            return True
        # Also check exact match
        if norm == hint_norm:
            return True
    return False


TRIVIA_QUESTIONS = [
    {"q": "What is the capital of India?", "a": "new delhi", "hints": ["delhi", "new delhi"]},
    {"q": "How many planets are in our solar system?", "a": "8", "hints": ["eight", "8"]},
    {"q": "What is the largest mammal on Earth?", "a": "blue whale", "hints": ["whale", "blue whale"]},
    {"q": "Who wrote the play Romeo and Juliet?", "a": "shakespeare", "hints": ["shakespeare", "william shakespeare"]},
    {"q": "What is the chemical symbol for water?", "a": "h2o", "hints": ["h2o"]},
    {"q": "What is the tallest mountain in the world?", "a": "mount everest", "hints": ["everest", "mount everest"]},
    {"q": "How many colors are in a rainbow?", "a": "7", "hints": ["seven", "7"]},
    {"q": "Which Indian scientist won the Nobel Prize for Physics in 1930?", "a": "c v raman", "hints": ["raman", "c v raman"]},
    {"q": "What is the national animal of India?", "a": "tiger", "hints": ["tiger"]},
    {"q": "Which planet is known as the Red Planet?", "a": "mars", "hints": ["mars"]},
]


class GameEngine:
    """Manages mini games. Takes callbacks for audio I/O."""

    def __init__(self, speak_callback, listen_callback, face_callback=None):
        self.speak = speak_callback
        self.listen = listen_callback
        self.set_face = face_callback or (lambda state: None)

    def play_rock_paper_scissors(self):
        self.set_face("playing")
        self.speak("Let's play rock paper scissors! Say rock, paper, or scissors on three. Ready?")
        self.speak("Rock, paper, scissors, shoot!")

        choice = self.listen(timeout=5)
        if not choice:
            self.speak("I didn't hear you. Maybe next time!")
            return

        if _wants_quit(choice):
            self.speak("Okay, we can play again later!")
            self.set_face("idle")
            return

        # Strict answer parsing (Review #18) — normalized exact match only
        user_choice = _parse_rps_answer(choice)
        if not user_choice:
            self.speak(f"I heard '{choice}', but I need rock, paper, or scissors.")
            return

        nexus_choice = random.choice(["rock", "paper", "scissors"])
        self.speak(f"I chose {nexus_choice}!")

        if user_choice == nexus_choice:
            self.speak("It's a tie! Great minds think alike.")
        elif (user_choice == "rock" and nexus_choice == "scissors") or \
             (user_choice == "paper" and nexus_choice == "rock") or \
             (user_choice == "scissors" and nexus_choice == "paper"):
            self.speak(f"You win! {user_choice} beats {nexus_choice}. Well done!")
        else:
            self.speak(f"I win! {nexus_choice} beats {user_choice}. Better luck next time!")
        self.set_face("idle")

    def play_guess_the_number(self):
        self.set_face("playing")
        target = random.randint(1, 100)
        attempts = 0
        max_attempts = 7

        self.speak("Let's play guess the number! I'm thinking of a number between 1 and 100. You have 7 tries.")

        while attempts < max_attempts:
            attempts += 1
            self.speak(f"Guess {attempts}. What's your number?")
            answer = self.listen(timeout=8)

            if not answer:
                # A missed/invalid guess consumes the attempt (H1): the old
                # version refunded attempts on silence, which made the game
                # run forever and blocked the main loop.
                self.speak("I didn't catch that. Moving on.")
                continue

            if _wants_quit(answer):
                self.speak(f"Okay! The number was {target}. We can play again later.")
                self.set_face("idle")
                return

            num = parse_spoken_number(answer)  # Bug #19: compound numbers
            if num is None:
                self.speak("I didn't hear a number. Moving on.")
                continue

            if num == target:
                self.speak(f"Yes! The number was {target}! You got it in {attempts} tries. Amazing!")
                self.set_face("idle")
                return
            elif num < target:
                self.speak(f"{num} is too low. Go higher!")
            else:
                self.speak(f"{num} is too high. Go lower!")

        self.speak(f"Out of guesses! The number was {target}. Better luck next time!")
        self.set_face("idle")

    def play_trivia(self):
        self.set_face("playing")
        self.speak("Welcome to Nexus Trivia! I'll ask you 3 questions.")
        score = 0
        questions = random.sample(TRIVIA_QUESTIONS, min(3, len(TRIVIA_QUESTIONS)))

        for i, q in enumerate(questions, 1):
            self.speak(f"Question {i}. {q['q']}")
            answer = self.listen(timeout=10)

            if not answer:
                self.speak(f"Time's up! The answer was {q['a']}.")
                continue

            if _wants_quit(answer):
                self.speak(f"Okay, ending the trivia. You scored {score} so far. Bye for now!")
                self.set_face("idle")
                return

            # Bug #20: normalized matching, not substring
            if trivia_check_answer(answer, q["hints"]):
                score += 1
                self.speak("Correct! Well done!")
            else:
                self.speak(f"Not quite! The answer was {q['a']}.")

        self.set_face("happy")
        if score == len(questions):
            self.speak(f"Perfect score! {score} out of {len(questions)}. You're a genius!")
        elif score > 0:
            self.speak(f"You scored {score} out of {len(questions)}. Not bad!")
        else:
            self.speak("Zero correct, but don't worry — practice makes perfect!")
        self.set_face("idle")

    def play_simon_says(self):
        """
        Simon Says — Voice Version (Review #19).
        Does NOT claim to detect physical movement. The game tests if the
        user follows the "Simon says" rule verbally. If you need actual
        movement verification, implement it using sensors/camera.
        """
        self.set_face("playing")
        self.speak("Let's play Simon Says — Voice Version! I'll give you commands. "
                   "Only follow them if I say 'Simon says'. "
                   "If I don't say 'Simon says', you should say 'I didn't move'. Ready?")

        rounds = 5
        score = 0
        commands = ["forward", "back", "left", "right", "spin", "stop"]
        spoken = {"forward": "forward", "back": "back", "left": "left",
                  "right": "right", "spin": "spin around", "stop": "stop"}

        for rnd in range(1, rounds + 1):
            say_simon = random.random() > 0.35
            cmd = random.choice(commands)

            if say_simon:
                self.speak(f"Simon says {spoken[cmd]}.")
                # User should respond with the action or confirm they did it.
                # Word-based matching (L6): "no" must not match "know".
                answer = self.listen(timeout=5)
                if answer and _wants_quit(answer, include_stop=False):
                    self.speak(f"Okay, ending Simon Says. You scored {score} so far!")
                    self.set_face("idle")
                    return
                if answer:
                    words = set(normalize_answer(answer).split())
                    if (cmd in words or "did" in words or "yes" in words
                            or "ok" in words or "okay" in words):
                        score += 1
            else:
                self.speak(f"{spoken[cmd]}.")
                # User should say "I didn't move" or similar
                answer = self.listen(timeout=5)
                if answer and _wants_quit(answer, include_stop=False):
                    self.speak(f"Okay, ending Simon Says. You scored {score} so far!")
                    self.set_face("idle")
                    return
                if answer:
                    words = set(normalize_answer(answer).split())
                    if words & {"didnt", "no", "not", "never"}:
                        score += 1

        self.speak(f"Great game! You scored {score} out of {rounds}. Well played!")
        self.set_face("idle")

    def dispatch(self, text):
        """
        Route to the correct game based on strict intent commands (Review #17).
        Normal conversation should NOT accidentally activate a game.
        """
        t = text.lower().strip()
        # Strict game commands — not arbitrary substring matching (Review #17)
        if re.search(r'\b(?:play|start|let\'s play)\s+rock\s+paper\s+scissors?\b', t) \
           or re.search(r'\b(?:play|start)\s+rock\s+paper\b', t):
            self.play_rock_paper_scissors()
        elif re.search(r'\b(?:play|start|let\'s play)\s+guess\s+(?:the\s+)?number\b', t):
            self.play_guess_the_number()
        elif re.search(r'\b(?:play|start|let\'s play)\s+trivia\b', t) \
           or re.search(r'\b(?:play|start)\s+(?:a\s+)?quiz\b', t):
            self.play_trivia()
        elif re.search(r'\b(?:play|start|let\'s play)\s+simon\s+says\b', t):
            self.play_simon_says()
        elif re.search(r'\b(?:play|start)\s+(?:a\s+)?game\b', t):
            # Generic “play a game” — ask which one
            self.speak("I know rock paper scissors, guess the number, trivia, and Simon says. Which one?")
        else:
            self.speak("I know rock paper scissors, guess the number, trivia, and Simon says. Which one?")


# ==========================================================================
# ======== MODULE: nexus/weather.py ==============================
# ==========================================================================
# """
# Nexus Robot — Weather (Open-Meteo, no API key needed).
#
# Primary source: Open-Meteo (https + geocoding, free, no key).
# wttr.in was the previous source but it periodically serves an expired
# TLS certificate which breaks HTTPS clients entirely (seen 2026-09-16),
# so it is no longer used.
#
# Location resolution:
  # 1. WEATHER_LOCATION env var (e.g. "Surat", "Mumbai") — geocoded via
     # Open-Meteo's geocoding API.
  # 2. If unset, the robot's public IP is geolocated (ipapi.co, then
     # ip-api.com) and that position is used.
# """
import logging
import requests


logger_weather = logging.getLogger("Nexus.Weather")

# WMO weather interpretation codes → short spoken description
_WMO = {
    0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy with frost",
    51: "lightly drizzling", 53: "drizzling", 55: "heavily drizzling",
    56: "freezing drizzle", 57: "freezing drizzle",
    61: "raining lightly", 63: "raining", 65: "raining heavily",
    66: "freezing rain", 67: "freezing rain",
    71: "snowing lightly", 73: "snowing", 75: "snowing heavily",
    77: "snowing",
    80: "having light showers", 81: "having showers", 82: "having heavy showers",
    85: "having snow showers", 86: "having snow showers",
    95: "thunderstorming", 96: "thunderstorming with hail",
    99: "thunderstorming with hail",
}


def _wmo_desc(code):
    try:
        return _WMO.get(int(code), "conditions unavailable")
    except (TypeError, ValueError):
        return "conditions unavailable"


def _locate():
    """Return (lat, lon, city) from WEATHER_LOCATION or IP geolocation."""
    loc = (WEATHER_LOCATION or "").strip()
    if loc:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": loc, "count": 1},
            timeout=6)
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            raise ValueError(f"unknown location: {loc}")
        g = results[0]
        return g["latitude"], g["longitude"], g.get("name", loc)

    # No configured location — approximate from the public IP
    for url in ("https://ipapi.co/json/", "http://ip-api.com/json/"):
        try:
            r = requests.get(url, timeout=5)
            r.raise_for_status()
            d = r.json()
            if "latitude" in d:  # ipapi.co shape
                return d["latitude"], d["longitude"], d.get("city", "")
            if "lat" in d:       # ip-api.com shape
                return d["lat"], d["lon"], d.get("city", "")
        except Exception:
            continue
    raise ValueError("could not determine location")


def get_weather():
    try:
        lat, lon, city = _locate()
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon,
                    "current": "temperature_2m,apparent_temperature,weather_code"},
            timeout=6)
        r.raise_for_status()
        cur = (r.json() or {}).get("current", {}) or {}
        temp = cur.get("temperature_2m", "?")
        feels = cur.get("apparent_temperature", temp)
        desc = _wmo_desc(cur.get("weather_code"))
        where = f" in {city}" if city else ""
        return (f"It's {desc} and {temp} degrees{where} right now, "
                f"feels like {feels}.")
    except requests.exceptions.Timeout:
        return "The weather service is taking too long to respond."
    except requests.exceptions.ConnectionError:
        return "I can't reach the weather service right now. Check your internet connection."
    except Exception as e:
        logger_weather.error("Weather fetch error: %s", e, exc_info=True)
        return ("Sorry, I couldn't get the weather right now. "
                "You can set the WEATHER_LOCATION environment variable "
                "to your city.")


# ==========================================================================
# ======== MODULE: nexus/news.py =================================
# ==========================================================================
# """Nexus Robot — News (Google News RSS, no API key needed)."""
import logging
import requests
import xml.etree.ElementTree as ET


logger_news = logging.getLogger("Nexus.News")


def get_news(topic=None, count=3):
    topic = (topic or NEWS_TOPIC or "").strip()
    if topic:
        url = f"https://news.google.com/rss/search?q={requests.utils.quote(topic)}&hl=en-IN&gl=IN&ceid=IN:en"
    else:
        url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
    try:
        r = requests.get(url, timeout=6)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:count]
        headlines = []
        for item in items:
            title = item.findtext("title") or ""
            headline = title.rsplit(" - ", 1)[0].strip()
            if headline:
                headlines.append(headline)
        if not headlines:
            return "I couldn't find any news right now."
        lead = f"Here's the latest on {topic}: " if topic else "Here's today's top news: "
        return lead + ". ".join(headlines) + "."
    except requests.exceptions.Timeout:
        return "The news service is taking too long to respond."
    except requests.exceptions.ConnectionError:
        return "I can't reach the news service right now. Check your internet connection."
    except Exception as e:
        logger_news.error("News fetch error: %s", e, exc_info=True)
        return "Sorry, I couldn't reach the news right now."


# ==========================================================================
# ======== MODULE: nexus/shutdown.py =============================
# ==========================================================================
# """
# Nexus Robot — Centralized Shutdown Manager (Bug #23)
#
# Idempotent shutdown that handles all cleanup:
# 1. STOP motors
# 2. Disable motor output
# 3. Stop camera
# 4. Stop recording (if active)
# 5. Stop TTS
# 6. Stop background threads
# 7. Close GPIO
# 8. Close UI
# 9. Flush logs
#
# Calling shutdown twice is safe (idempotent).
# """
import threading
import logging

logger_shutdown = logging.getLogger("Nexus.Shutdown")


class ShutdownManager:
    """Centralized, idempotent shutdown (Bug #23)."""

    def __init__(self):
        self._shutdown_done = False
        self._lock = threading.Lock()
        self._handlers = []

    def register_handler(self, name, handler):
        """Register a cleanup handler. Handlers run in REGISTRATION order
        (Round 2, M1): the first-registered handler runs first, matching the
        documented shutdown sequence. (Previously they ran in reverse, which
        put the motor GPIO teardown before the motor STOP and stopped TTS
        last.)"""
        self._handlers.append((name, handler))

    def shutdown(self, reason=""):
        """
        Execute full shutdown sequence. Idempotent — safe to call multiple times.
        """
        with self._lock:
            if self._shutdown_done:
                logger_shutdown.info("Shutdown already complete — skipping (idempotent)")
                return
            self._shutdown_done = True

        logger_shutdown.info("Shutdown initiated (reason=%s)", reason)

        # Execute handlers in registration order (M1)
        for name, handler in list(self._handlers):
            try:
                logger_shutdown.info("Shutdown step: %s", name)
                handler()
            except Exception as e:
                logger_shutdown.error("Shutdown handler '%s' failed: %s", name, e, exc_info=True)

        logger_shutdown.info("Shutdown complete")

    @property
    def is_shutdown(self):
        return self._shutdown_done


# Singleton
shutdown_manager = ShutdownManager()


# ==========================================================================
# ======== MODULE: nexus/safety_listener.py ======================
# ==========================================================================
# """
# Nexus Robot — Background Safety-Stop Listener (Round 2, C2)
#
# The main loop is single-threaded: while dance(), demo mode, navigation, or a
# voice movement is running, the robot never processes the microphone — so a
# spoken "STOP!" could not interrupt any of those activities. Only the watchdog,
# the collision sensor, or process shutdown could stop motion mid-activity.
#
# This module closes that gap. During any blocking activity that moves the robot,
# a small background thread records the microphone (only while the robot is NOT
# speaking, to avoid self-hearing) and transcribes it. If the transcript is a
# safety-stop phrase ("stop", "halt", "freeze", ... — the same strict
# is_safety_stop() parser the main loop uses), it:
#
  # 1. calls motor.stop() immediately (STOP jumps the motor queue and
     # invalidates the in-flight generation), and
  # 2. sets a stop-requested event the activity checks between every step so it
     # aborts promptly.
#
# Notes:
# - Network caveat: transcription uses the Sarvam STT API, so this listener needs
  # connectivity — exactly like every other voice feature. The watchdog and
  # collision sensor remain the network-independent safety layers.
# - Mic ownership: activities that use this listener must NOT record from the
  # main thread while it is active (they don't — they're blocked), and recording
  # is suppressed while TTS is speaking.
# - A stale listener thread (one still finishing a read after finish()) cannot
  # corrupt a later activity: each start() bumps an epoch, and a stale thread
  # never sets the newer epoch's event.
# """
import threading
import time
import logging


logger_safety_listener = logging.getLogger("Nexus.SafetyListener")


class SafetyListener:
    """Hears spoken safety-stops while the main loop is blocked."""

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self._active = False
        self._epoch = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    @property
    def stop_requested(self):
        """True once a safety-stop phrase has been heard this activity."""
        return self._stop_event.is_set()

    # ------------------------------------------------------------------
    def start(self):
        """Begin listening. Called at the start of a blocking activity."""
        with self._lock:
            self._epoch += 1
            epoch = self._epoch
            self._active = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, args=(epoch,), daemon=True, name="safety-listener")
        self._thread.start()
        logger_safety_listener.info("Safety listener active — say 'stop' to halt the robot")

    def finish(self, timeout=4.0):
        """Stop listening at the end of a blocking activity. Idempotent.

        stop_requested stays readable after finish() so the caller can still
        check why an activity ended.
        """
        self._active = False
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger_safety_listener.info("Safety listener still finishing a pending read; "
                            "stale results will be ignored")
            self._thread = None

    # ------------------------------------------------------------------
    def _run(self, epoch):
        while self._active and epoch == self._epoch:
            try:
                # Never record while the robot is speaking (self-hearing)
                if audio_manager.is_speaking():
                    time.sleep(0.3)
                    continue
                ok, _ = audio_manager.record_to_wav(timeout_seconds=2)
                if not ok:
                    time.sleep(0.2)
                    continue
                txt, _err = transcribe()
                if txt and is_safety_stop(txt.lower().strip()):
                    logger_safety_listener.warning("SAFETY STOP heard during activity: %r", txt)
                    # STOP the motors right away — jumps the motor queue and
                    # invalidates the in-flight movement generation.
                    motor.stop(source="voice_safety_listener")
                    if epoch == self._epoch:
                        self._stop_event.set()
                    return
            except Exception as e:
                logger_safety_listener.error("Safety listener error: %s", e)
                time.sleep(0.5)


# Singleton
safety_listener = SafetyListener()


# ==========================================================================
# ======== MODULE: nexus/main.py =================================
# ==========================================================================
# """
# Nexus Robot — Main Entry Point (Bug #3, #22, #23, #27)
#
# Safe startup order (Bug #22):
  # 1. Logging
  # 2. Configuration
  # 3. GPIO safety
  # 4. Verify emergency-stop path
  # 5. Motor controller (+ watchdog)
  # 6. Camera
  # 7. Microphone validation
  # 8. TTS (optional)
  # 9. Optional AI services (STT, chat, vision)
 # 10. Optional hardware tests
 # 11. READY
#
# Offline-safe (Bug #3): robot boots and runs local controls even without API key.
# AI services degrade gracefully — "AI services are offline, but local robot
# controls remain available."
# """
import os
import sys
import time
import re
import random
import threading
import struct
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("Nexus")

# Optional: Porcupine for wake word
try:
    from pvporcupine import create as porcupine_create
    PV_PORCUPINE_AVAILABLE = True
except Exception:
    porcupine_create = None
    PV_PORCUPINE_AVAILABLE = False

# Optional: OpenAI client for chat
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

IDENTITY_TRIGGERS = ["who are you", "your name", "what is your name",
                      "who created you", "who made you"]

VISION_QUERY_PHRASES = [
    "what do you see", "what can you see", "describe what", "tell me what you see",
    "look at", "show me what you see", "can you see",
    "what's happening", "what is happening", "what's going on", "what is going on",
    "what's around", "what is around", "what's in front", "what is in front",
    "what objects", "what is this person doing", "what's this person doing",
    "describe the scene", "describe my surroundings",
    # Gujarati (STT_LANGUAGE_CODE=gu-IN transcribes these in native script,
    # so English-only matching silently stopped routing vision questions)
    "શું જોઈ રહ્યા", "જોઈ રહ્યા છો", "શું દેખાય", "દેખાય છે",
    "સામે શું છે", "આજુબાજુ શું", "દ્રશ્ય વર્ણન", "શું છે ત્યાં", "ત્યાં શું છે",
]

# Deep-vision markers — these queries use the cloud scene description
# (vision-performance pass, req. 4). Everything else takes the fast local
# route (req. 3).
DETAILED_VISION_MARKERS = [
    "describe", "in detail", "detailed", "explain",
    "what's happening", "what is happening",
    "what's going on", "what is going on",
    "what is this person doing", "what's this person doing",
    "વિગત", "વર્ણન કરો",
]


def is_detailed_vision_query(text):
    """True for complex visual questions that need cloud/deep vision (req. 4)."""
    if not text:
        return False
    t = text.lower()
    return any(m in t for m in DETAILED_VISION_MARKERS)

# DANCE_ROUTINES and guard mode are defined below


def is_vision_query(text):
    if not text:
        return False
    t = text.lower()
    return any(p in t for p in VISION_QUERY_PHRASES)

def _vision_prefer_cloud():
    """
    Route ALL vision questions through a cloud vision model when any vision
    API key is present (user preference 2026-09: the offline SSD-MobileNet COCO
    detector only knows 80 classes and mislabels close-up faces as
    "handbag" / "Object31"). Costs ~2-4 s per answer.

    Uses the alternate provider (NEXUS_VISION_API_KEY — e.g. Groq) when
    configured, else Sarvam gemma4.

    NEXUS_VISION_MODE=fast  -> force the offline route
    NEXUS_VISION_MODE=cloud -> always use the cloud route
    auto (default)          -> cloud when a vision key is set, else offline
    """
    mode = os.getenv("NEXUS_VISION_MODE", "auto")
    if mode == "fast":
        return False
    if mode == "cloud":
        return True
    return bool(SARVAM_KEY or NEXUS_VISION_API_KEY)


def run_hardware_diagnostics():
    """Print hardware check table (Bug #24)."""
    print("\n=== NEXUS HARDWARE CHECK ===")
    # Real mic validation (Bug #8)
    mic_ok, mic_msg = audio_manager.validate_microphone()
    print(f"Microphone:  {'PASS' if mic_ok else 'FAIL'} — {mic_msg}")
    print(f"Speaker:     {TTS_DEVICE}")
    print(f"Camera:      {'OK' if camera_manager.available else 'FAIL'}")
    print(f"GPIO:        {'OK' if motor.is_pi else 'FAIL (not on Pi)'}")
    print(f"TFLite:      {'OK' if vision_system.available else 'FAIL'}")
    print(f"STT:         {'OK' if SARVAM_KEY else 'FAIL (no API key)'}")
    print(f"TTS:         {'OK' if SARVAM_KEY else 'FAIL (no API key)'}")
    print(f"Chat API:    {'OK' if SARVAM_KEY else 'FAIL (no API key)'}")
    print(f"Vision API:  {'OK' if (SARVAM_KEY or NEXUS_VISION_API_KEY) else 'FAIL (no API key)'}")
    print(f"Face Recog:  {'OK' if FACE_CASCADE_AVAILABLE else 'FAIL'}")
    print(f"Porcupine:   {'OK' if PV_PORCUPINE_AVAILABLE else 'FAIL (STT fallback)'}")
    print("============================\n")


DANCE_ROUTINES = [
    [("spin", 1.0, "Let's groove!"), ("forward", 0.5, ""), ("spin", 0.8, ""),
     ("back", 0.5, ""), ("left", 0.4, ""), ("right", 0.4, ""), ("spin", 1.2, "Yeah!")],
    [("right", 0.5, "Watch me dance!"), ("left", 0.5, ""), ("right", 0.5, ""),
     ("left", 0.5, ""), ("spin", 1.0, ""), ("forward", 0.6, ""),
     ("back", 0.6, ""), ("spin", 1.5, "Woo hoo!")],
    [("forward", 0.4, "Dance time!"), ("back", 0.4, ""), ("spin", 0.6, ""),
     ("back", 0.4, ""), ("forward", 0.4, ""), ("left", 0.3, ""), ("right", 0.3, ""),
     ("left", 0.3, ""), ("right", 0.3, ""), ("spin", 1.5, "That was fun!")],
]


def dance():
    """Dance routine — every move uses the BLOCKING motor API and the
    sequence aborts on a spoken safety-stop, a FAULT, or an interrupted move
    (Round 2: C1, C2, C6).

    The old version (a) submitted moves without wait=True so every move after
    the first was silently denied-and-dropped, and (b) aborted on
    is_stopped() — which is True whenever the robot is at rest — so the
    routine would also have ended after one move regardless.
    """

    mood.set_mood("excited")
    face.set_mood("excited")
    face.set_state("happy")
    routine = random.choice(DANCE_ROUTINES)
    safety_listener.start()
    try:
        for move, duration, sound in routine:
            if safety_listener.stop_requested or motor.safety.is_fault():
                break
            if sound:
                speak(sound)
            # Re-check after speaking (TTS blocks and the user may have spoken)
            if safety_listener.stop_requested or motor.safety.is_fault():
                break
            face.nudge_look(move)
            result = motor.execute_move(
                move, duration=duration, source="dance",
                wait=True, timeout=MOTOR_COMMAND_TIMEOUT,
            )
            if result.get("status") not in ("completed",):
                # interrupted / denied / timeout — abort the routine
                break
            time.sleep(0.1)
    finally:
        safety_listener.finish()
    motor.stop(source="dance_end")
    mood.set_mood("happy")
    face.set_mood("happy")
    face.set_state("idle")


def guard_mode():
    """Guard mode with separate camera/voice threads (Bug #6 — audio coordination)."""
    if not camera_manager.available:
        speak("I can't guard without my camera.")
        return

    mood.set_mood("curious")
    face.set_mood("curious")
    face.set_state("guarding")
    speak("Guard mode activated. I'll watch for movement and people. Say 'stop guard' to stop.")

    stop_flag = threading.Event()
    alert_lock = threading.Lock()
    last_alert = [0]

    try:
        import cv2
    except ImportError:
        cv2 = None


    def camera_monitor():
        prev_frame = camera_manager.capture()
        if prev_frame is None:
            return
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY) if cv2 else None
        start = time.time()

        while not stop_flag.is_set() and time.time() - start < GUARD_MAX_DURATION:
            # A safety stop or FAULT must also end guard mode (M4)
            if motor.safety.is_fault():
                stop_flag.set()
                break
            frame = camera_manager.capture()
            if frame is None:
                time.sleep(GUARD_INTERVAL)
                continue

            motion_detected = False
            person_detected = False

            if cv2 and prev_gray is not None:
                try:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.GaussianBlur(gray, (21, 21), 0)
                    diff = cv2.absdiff(prev_gray, gray)
                    _, thresh = cv2.threshold(diff, GUARD_MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)
                    thresh = cv2.dilate(thresh, None, iterations=2)
                    motion_pixels = cv2.countNonZero(thresh)
                    total_pixels = frame.shape[0] * frame.shape[1]
                    if motion_pixels / total_pixels > GUARD_PIXEL_RATIO:
                        motion_detected = True
                    prev_gray = gray
                except Exception as e:
                    logger.error("Motion detection error: %s", e)

            if vision_system.available:
                detections = vision_system.detect_objects(frame, threshold=0.55)
                if any(d["label"] == "person" for d in detections):
                    person_detected = True

            now = time.time()
            if (motion_detected or person_detected) and now - last_alert[0] > 5:
                with alert_lock:
                    last_alert[0] = now
                if person_detected:
                    # TTS coordinates speaking-state internally (Review #7)
                    speak("Alert! I detected a person!")
                else:
                    speak("I see movement! Something's happening.")

            time.sleep(GUARD_INTERVAL)

    def voice_monitor():
        while not stop_flag.is_set():
            # Don't record while TTS is speaking (Bug #6)
            if audio_manager.is_speaking():
                time.sleep(0.5)
                continue
            ok, _ = audio_manager.record_to_wav(timeout_seconds=2)
            if not ok:
                time.sleep(0.5)
                continue
            txt, err = transcribe()
            if not txt:
                continue
            t = txt.lower().strip()
            # A plain safety-stop ("stop!" / "halt") also ends guard mode (M4)
            if is_safety_stop(t):
                motor.stop(source="guard_safety_stop")
                stop_flag.set()
                return
            if "stop" in t and "guard" in t:
                stop_flag.set()
                return

    cam_thread = threading.Thread(target=camera_monitor, daemon=True)
    voice_thread = threading.Thread(target=voice_monitor, daemon=True)
    cam_thread.start()
    voice_thread.start()

    stop_flag.wait(timeout=GUARD_MAX_DURATION)
    stop_flag.set()
    cam_thread.join(timeout=3)
    voice_thread.join(timeout=3)

    mood.set_mood("happy")
    face.set_mood("happy")
    face.set_state("idle")
    speak("Guard mode deactivated. All clear!")


def _cleanup_porcupine():
    """Release Porcupine resources on shutdown (Review #32)."""
    global porcupine, porcupine_enabled
    if porcupine is not None:
        try:
            porcupine.delete()
            logger.info("Porcupine resources released (Review #32)")
        except Exception as e:
            logger.warning("Porcupine cleanup error: %s", e)
        finally:
            porcupine = None
            porcupine_enabled = False


def _log_offline_status(ai_available, camera_ok, vision_ok):
    """
    Clearly document offline vs network-required capabilities (Review #31).
    Do not describe the complete robot as fully offline.

    Local motor/safety controls:   OFFLINE (no network needed)
    Sarvam STT:                    NETWORK REQUIRED
    Sarvam TTS:                    NETWORK REQUIRED
    Porcupine wake word:           LOCAL (if installed/configured)
    """
    logger.info("=== CAPABILITY STATUS (Review #31) ===")
    logger.info("  Local motor/safety controls: OFFLINE (no network needed)")
    logger.info("  Sarvam STT:                  %s",
                "NETWORK REQUIRED" if ai_available else "UNAVAILABLE (no API key)")
    logger.info("  Sarvam TTS:                  %s",
                "NETWORK REQUIRED" if ai_available else "UNAVAILABLE (no API key)")
    logger.info("  Sarvam Chat:                  %s",
                "NETWORK REQUIRED" if ai_available else "UNAVAILABLE (no API key)")
    logger.info("  Porcupine wake word:          %s",
                "LOCAL (installed)" if porcupine_enabled else "UNAVAILABLE (STT fallback needs network)")
    logger.info("  Camera:                       %s", "OK" if camera_ok else "UNAVAILABLE")
    logger.info("  TFLite object detection:      %s", "OK" if vision_ok else "UNAVAILABLE")
    logger.info("===================================")


# ==================== WAKE WORD (Review #31, #32) ====================
porcupine = None
porcupine_enabled = False

if PV_PORCUPINE_AVAILABLE and os.path.exists(KEYWORD_PATH):
    try:
        porcupine = porcupine_create(keyword_paths=[KEYWORD_PATH])
        porcupine_enabled = True
    except Exception as e:
        logger.warning("Porcupine init failed: %s", e)


# NOTE: Porcupine is released on shutdown via _cleanup_porcupine() (Review #32)


def _porcupine_streaming_wake():
    """Stream PCM directly to Porcupine (no WAV round-trip)."""
    logger.info("Sleeping — say 'Hey Nexus' (Porcupine streaming)")
    face.set_state("asleep")

    sample_rate = 16000
    frame_length = porcupine.frame_length
    frame_bytes = int(frame_length * 2)

    import subprocess
    try:
        proc = subprocess.Popen(
            ["arecord", "-D", MIC_DEVICE, "-f", "S16_LE", "-r", str(sample_rate), "-c", "1", "-t", "raw"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
    except Exception as e:
        logger.error("Wake word arecord error: %s", e)
        return

    try:
        consecutive_errors = 0
        while True:
            chunk = proc.stdout.read(frame_bytes)
            if not chunk:
                # EOF — arecord died. Bail out instead of spinning forever (L7).
                logger.error("Wake-word audio stream ended unexpectedly")
                break
            if len(chunk) < frame_bytes:
                time.sleep(0.01)
                continue
            pcm = struct.unpack('<' + 'h' * frame_length, chunk[:frame_bytes])
            try:
                if porcupine.process(pcm) >= 0:
                    proc.terminate()
                    proc.wait(timeout=1)
                    mood.set_mood("happy")
                    face.set_mood("happy")
                    face.set_state("happy")
                    speak("I'm awake!")
                    mood.touch()
                    return
                consecutive_errors = 0
            except Exception:
                consecutive_errors += 1
                if consecutive_errors > 50:
                    logger.error("Porcupine keeps failing — giving up on streaming wake word")
                    break
                continue
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=1)
        except Exception:
            try: proc.kill()
            except Exception: pass


# Wake-word spellings: saaras STT with STT_LANGUAGE_CODE=gu-IN writes
# "Nexus" phonetically in Gujarati script, and the exact cluster spelling
# varies between attempts — accept all the common variants.
_stt_outage_announced = False  # one-shot voice notice for STT circuit-breaker outages

_WAKE_GUJARATI = ["નેક્સસ", "નેક્ષસ", "નેકસસ", "નેક્સ", "નેક્ષ", "નેકસ", "નક્સસ"]

def _levenshtein(a, b, cap=3):
    """Small edit-distance helper (wake-word fuzziness only)."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1,          # deletion
                           cur[j - 1] + 1,       # insertion
                           prev[j - 1] + (ca != cb)))  # substitution
        prev = cur
    return prev[-1]


def _is_wake_word(txt):
    """True if the transcript mentions the robot's name (Latin or Gujarati).

    2026-09: fuzzy matching added — STT frequently renders "hey nexus" as
    "hey nex S", "hey nex", "nexus", "hey macus", "hey next", "lexus"…
    Any word within edit distance 2 of "nexus" now counts."""
    if not txt:
        return False
    low = txt.lower()
    if "nexus" in low:
        return True
    if any(v in txt for v in _WAKE_GUJARATI):
        return True
    for tok in re.findall(r"[a-z]+", low):
        if 3 <= len(tok) <= 7 and _levenshtein(tok, "nexus") <= 3:
            return True
    return False

def _stt_wake_fallback():
    """STT-based wake detection (Bug #11 — works without Porcupine)."""
    logger.info("Sleeping — say 'Hey Nexus' (STT fallback)")
    face.set_state("asleep")

    while True:
        ok, _ = audio_manager.record_to_wav(timeout_seconds=3)
        if not ok:
            time.sleep(0.5)
            continue
        txt, err = transcribe()
        if txt:
            # Show what the sleeping robot heard — makes wake misses
            # visible in the terminal instead of failing silently.
            logger.info("Wake loop heard: %r (stt_error=%s)", txt, err)
        if _is_wake_word(txt):
            mood.set_mood("happy")
            face.set_mood("happy")
            face.set_state("happy")
            speak("I'm awake!")
            mood.touch()
            return
        time.sleep(0.3)


def listen_for_wake_word():
    """Wake word detection — Porcupine streaming or STT fallback."""
    if porcupine_enabled and porcupine is not None:
        _porcupine_streaming_wake()
    else:
        _stt_wake_fallback()


# ==================== AI CHAT (Bug #7 — text-only history) ====================
# Chat circuit breaker + shared client (Round 2, M5)
_chat_breaker = CircuitBreaker()
_chat_client = None


def _get_chat_client():
    """Create the chat client once and reuse it (M5)."""
    global _chat_client
    if _chat_client is None:
        _chat_client = OpenAI(api_key=SARVAM_KEY, base_url="https://api.sarvam.ai/v1",
                               timeout=30.0, max_retries=1)
    return _chat_client


def build_system_prompt():
    mood_prompt = mood.personality_prompt
    base = (
        f"You are Nexus, a friendly voice assistant robot. {NEXUS_PERSONALITY} "
        f"Right now you are feeling {mood_prompt}. "
        "Always reply in ONE short, natural spoken sentence like a smart speaker "
        "(Alexa/Google Assistant style) unless the user clearly asks for detail or a story. "
        "IMPORTANT — you are only the CONVERSATION part of this robot. You cannot "
        "move the robot and you cannot see the camera; separate robot systems handle "
        "movement, the camera, news, weather and other actions automatically. Never "
        "claim that you are moving, have moved, or are looking at something. If the "
        "user asks you to move the robot, tell them to say a movement command such as "
        "'move forward for two seconds'. If they want you to look, tell them to ask "
        "'what do you see'. Any camera context provided to you is background "
        "information only — do not mention it or ask about the camera yourself. "
    )
    # Optional reply language (e.g. NEXUS_REPLY_LANGUAGE=Gujarati)
    lang = (NEXUS_REPLY_LANGUAGE or "").strip()
    if lang:
        base += f" Always write your replies in {lang}. "
    return base + memory.context_string()


def _trim_history(history):
    if len(history) > MAX_HISTORY_MESSAGES:
        system = [history[0]] if history and history[0].get("role") == "system" else []
        history = system + history[-(MAX_HISTORY_MESSAGES - 1):]
    return history


def ask_ai(text, history):
    """Streamed chat. Vision context injected as text, never images (Bug #7).

    Round 2 (M5): the chat call now goes through its own circuit breaker
    (previously only STT had one), reuses a single OpenAI client, and uses an
    explicit request timeout so a hung stream cannot block the main loop.
    """
    history = history or []

    user_content = text
    fresh_vision = vision_context.get_fresh()
    if fresh_vision:
        user_content = f"(Context: my camera recently saw: {fresh_vision}) {text}"

    history.append({"role": "user", "content": user_content})
    history = _trim_history(history)

    face.set_state("thinking")

    if not SARVAM_KEY or OpenAI is None:
        reply = "AI services are offline, but local robot controls remain available."
        speak(reply)
        history.append({"role": "assistant", "content": reply})
        return reply, history

    if not _chat_breaker.allow():
        reply = "I'm having trouble reaching my AI service right now. Local robot controls still work."
        speak(reply)
        history.append({"role": "assistant", "content": reply})
        return reply, history

    try:
        client = _get_chat_client()
        full_reply = ""
        buffer = ""

        t_ai = time.perf_counter()
        try:
            stream = client.chat.completions.create(
                model=SARVAM_CHAT_MODEL,
                messages=history,
                max_tokens=60,
                stream=True,
            )
            for chunk in stream:
                try:
                    delta = chunk.choices[0].delta.content or ""
                except Exception:
                    delta = ""
                if not delta:
                    continue
                buffer += delta
                full_reply += delta
                while True:
                    m = re.search(r'([.!?])(\s|$)', buffer)
                    if not m:
                        break
                    sentence = buffer[:m.end()].strip()
                    buffer = buffer[m.end():]
                    if sentence:
                        speak(sentence)
            if buffer.strip():
                speak(buffer.strip())
            _chat_breaker.record_success()
        finally:
            # Measured as 'ai_chat' (vision-performance pass, req. 6)
            latency.record("ai_chat", time.perf_counter() - t_ai)
    except Exception as e:
        logger.error("AI chat error: %s", e, exc_info=True)
        _chat_breaker.record_failure()
        full_reply = "Sorry, I hit a glitch."
        face.set_state("sad")
        speak(full_reply)

    history.append({"role": "assistant", "content": full_reply})
    history = _trim_history(history)
    memory.auto_extract(text, full_reply)
    return full_reply, history


# ==================== VISION QUERY HANDLING (performance pass) ====================
def _unique_labels(detections, limit=5):
    labels = []
    for d in detections:
        if d["label"] not in labels:
            labels.append(d["label"])
    return labels[:limit]

def _filter_face_false_positives(frame, detections):
    """
    Vision-accuracy pass: a close-up face is a classic SSD-MobileNet false
    positive — COCO has no "face" class, so a face filling the frame often
    fires "handbag" / "sports ball" / "traffic light" instead of "person".

    When the Haar cascade (the same one face recognition uses) finds a face:
      - drop any non-person detection whose centre lies inside a face region
        (that label is describing the face, not the scene), and
      - guarantee a "person" detection is present.

    Returns (detections, face_rects); returns the input unchanged when
    there is no camera frame, no cv2/cascade, or no face found.
    """
    if not FACE_CASCADE_AVAILABLE or frame is None or not detections:
        return detections, []
    try:
        faces = list(_detect_faces(frame))
        if not faces:
            return detections, []
        h, w = frame.shape[0], frame.shape[1]
        kept = []
        for d in detections:
            if d.get("label") == "person":
                kept.append(d)
                continue
            box = d.get("box") or []
            if len(box) != 4:
                kept.append(d)
                continue
            ymin, xmin, ymax, xmax = box  # tflite normalized [y,x,y,x]
            cx = ((xmin + xmax) / 2.0) * w
            cy = ((ymin + ymax) / 2.0) * h
            inside_face = any(x <= cx <= x + fw and y <= cy <= y + fh
                              for (x, y, fw, fh) in faces)
            if not inside_face:
                kept.append(d)
        if not any(d.get("label") == "person" for d in kept):
            kept.append({"label": "person", "confidence": 1.0,
                         "box": [0.0, 0.0, 1.0, 1.0], "class_id": 0})
        return kept, faces
    except Exception:
        logger.warning("Face-aware vision filter failed — using raw detections")
        return detections, []


def _handle_vision_query(txt, t_e2e=None):
    """
    Answer a vision question with the fast/deep routing required by the
    vision-performance pass:

    - Simple questions ("What do you see?", "What is in front of you?",
      "What objects are there?") use the fresh local VisionWorker cache and
      respond immediately — no cloud call (req. 3). Only if local vision
      cannot produce ANY detection do we fall back to cloud (req. 3's
      "unless local vision cannot provide a useful answer").
    - Complex questions ("Describe this scene in detail.", "What is this
      person doing?") use describe_scene(), running local detection and
      cloud vision CONCURRENTLY via a ThreadPoolExecutor when both are
      needed (req. 4).
    - Vision-memory persistence is enqueued in the background (req. 5).
    - The camera preview is shown without the old artificial 1 s sleep
      (req. 1); it stays up while the response is spoken.
    """
    e2e_t0 = time.perf_counter() if t_e2e is None else t_e2e
    detailed = is_detailed_vision_query(txt)

    # Fresh cached frame + detections, or a synchronous fallback capture
    # (req. 9: stale/missing cache never blocks the answer on stale data).
    snapshot = vision_worker.get_snapshot()
    frame = None
    detections = None
    if snapshot is not None:
        frame = snapshot["frame"]
        detections = snapshot["detections"]
    else:
        frame = camera_manager.capture()
        if frame is not None and not detailed:
            # Simple query with no cache: run the (fast, local) detection
            # first to decide the route — cloud is only used if it finds
            # nothing. For DETAILED queries, detection is deferred to the
            # pool below so it runs CONCURRENTLY with the cloud call (req. 4)
            # instead of sequentially.
            detections = vision_system.detect_objects(frame)

    if frame is None:
        face.set_state("sad")
        speak("I'm having trouble with my camera right now.")
        latency.record("e2e_vision", time.perf_counter() - e2e_t0)
        return

    face.show_camera_frame(frame)  # non-blocking preview — no artificial wait (req. 1)

    # ---------------- FAST LOCAL ROUTE (req. 3) ----------------
    # Skipped when cloud-first is requested (see _vision_prefer_cloud).
    cloud_first = _vision_prefer_cloud()
    if not detailed and detections and not cloud_first:
        detections, face_rects = _filter_face_false_positives(frame, detections)
        labels = _unique_labels(detections)
        # Face recognition: if a known person is in frame, answer with
        # their name instead of the generic "person" label.
        if face_rects:
            try:
                named = [n for n, _c in recognize_faces(frame) if n]
                if named:
                    named = list(dict.fromkeys(named))
                    labels = named + [l for l in labels if l != "person"]
            except Exception:
                pass
        listing = ", ".join(labels)
        summary = f"I can see {listing}."
        vision_context.set(summary)
        save_vision_memory_async(frame, f"Local detection: {listing}")
        speak(summary)
        face.hide_camera()
        latency.record("e2e_vision_fast", time.perf_counter() - e2e_t0)
        latency.record("e2e_vision", time.perf_counter() - e2e_t0)
        return

    # ---------------- DEEP / CLOUD ROUTE (req. 4) ----------------
    # Simple query with NO local detections also lands here: local vision
    # cannot provide a useful answer, so cloud is allowed (req. 3).
    speak("Let me look around.")

    with ThreadPoolExecutor(max_workers=2) as pool:
        cloud_future = pool.submit(vision_system.describe_scene, frame)
        local_future = None
        if detections is None:
            # No fresh cache — run local detection concurrently with the
            # cloud call instead of sequentially (req. 4/5 of the spec).
            local_future = pool.submit(vision_system.detect_objects, frame)
        try:
            description = cloud_future.result(timeout=45)
        except Exception as e:
            logger.error("Cloud vision failed: %s", e)
            description = None
        if local_future is not None:
            try:
                detections = local_future.result(timeout=10)
            except Exception:
                detections = []

    # Face-aware cleanup of the local labels (used only as the cloud-failure
    # fallback) + the name of any recognized person (user preference 2026-09:
    # the cloud VLM answer is spoken as-is; local COCO labels are NOT appended
    # — they are the source of close-up-face mislabels like "handbag").
    detections, _face_rects = _filter_face_false_positives(frame, detections or [])
    labels = _unique_labels(detections)
    named = []
    try:
        if FACE_CASCADE_AVAILABLE:
            named = list(dict.fromkeys(
                n for n, _c in recognize_faces(frame) if n))
    except Exception:
        named = []

    # Cloud failure fallback (tested): answer from local detections
    if not description or description.startswith("I had trouble"):
        if labels:
            description = f"I had trouble with the cloud, but I can see {', '.join(labels)}."
        else:
            description = description or "I couldn't analyze the scene."
    elif named:
        description = f"{description} And I recognize you, {', '.join(named)}!"

    vision_context.set(description)
    vision_worker.set_description(description)
    save_vision_memory_async(frame, description)
    speak(description)
    face.hide_camera()
    latency.record("e2e_vision_cloud", time.perf_counter() - e2e_t0)
    latency.record("e2e_vision", time.perf_counter() - e2e_t0)


# ==================== FACE CALLBACK ====================
def _face_callback(state):
    face.set_state(state)


# ==================== MAIN LOOP ====================
# ---- Startup greeting (spoken welcome; 2026-09) ----
# Spoken aloud at every boot. To change it later, either put new text in a
# file called greeting.txt next to the robot script, or set the env var
# NEXUS_STARTUP_GREETING (empty string disables the greeting entirely).
_DEFAULT_STARTUP_GREETING = """જય સ્વામિનારાયણ
હું છું નેક્સસ — એક અવાજ વડે ચાલતો, જાતે બનાવેલો એઆઈ રોબો.
આપ સૌનું હૃદયપૂર્વક સ્વાગત છે.
ચાલો, આજે નવું કંઈક શીખીએ અને જોઈએ."""


def _startup_greeting_text():
    """Greeting to speak at boot. Priority: NEXUS_STARTUP_GREETING env var,
    then greeting.txt next to the script, then the built-in default above.
    An explicitly empty env var skips the greeting entirely."""
    env = os.environ.get("NEXUS_STARTUP_GREETING")
    if env is not None:
        return env.strip()
    gpath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "greeting.txt")
    if os.path.exists(gpath):
        try:
            with open(gpath, encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            logger.warning("Could not read greeting.txt — using built-in greeting")
    return _DEFAULT_STARTUP_GREETING


def main():
    print("\n🤖 Nexus Vision Robot v3.0 🤖\n")

    # ---- Safe startup order (Review #22 — register shutdown handlers EARLY) ----
    # 1. Logging — already configured
    # 2. Config — already loaded
    # 3. GPIO safety — motor controller handles this
    # 4. Motor controller + watchdog (start worker FIRST so STOP can be verified)
    motor.start()
    logger.info("Motor controller + watchdog started")

    # 5. Register shutdown handlers IMMEDIATELY after hardware managers
    #    are created, so cleanup happens even if a later component fails
    #    (Review #22)
    shutdown_manager.register_handler("stop_tts", stop_playback)
    shutdown_manager.register_handler("stop_camera", camera_manager.stop)
    shutdown_manager.register_handler("vision_worker_stop", vision_worker.stop)
    shutdown_manager.register_handler("stop_motors", lambda: motor.stop(source="shutdown"))
    shutdown_manager.register_handler("motor_join", motor.join)
    shutdown_manager.register_handler("motor_cleanup", motor.cleanup)
    shutdown_manager.register_handler("porcupine_cleanup", _cleanup_porcupine)
    shutdown_manager.register_handler("face_stop", face.stop)

    # 6. Verify emergency-stop path — wait for STOP ack (Review #21)
    #    Queuing a STOP does not prove GPIO/PWM is safe; waiting for the
    #    worker to process it and verifying the safety state does.
    ack = motor.stop(source="startup_verification")
    if ack.wait(timeout=3.0):
        logger.info("Startup STOP acknowledged by Motor Worker (Review #21)")
    else:
        logger.warning("Startup STOP not acknowledged within 3s — proceeding with caution")
    if motor.safety.is_fault():
        logger.critical("Safety system in FAULT after startup STOP — clearing")
        motor.clear_fault()
    logger.info("Emergency-stop path verified")

    # 7. Camera
    camera_ok = camera_manager.start()

    # 8. Vision system (optional) + background VisionWorker
    #    (vision-performance pass, req. 2 — continuous local detection so
    #    simple vision questions are answered from a fresh cache)
    vision_ok = vision_system.start() if camera_ok else False
    if vision_ok:
        if vision_worker.start(camera=camera_manager):
            # Live camera preview while in camera mode (non-blocking)
            vision_worker._on_frame = face.update_camera_frame

    # 9. Microphone validation
    mic_ok, mic_msg = audio_manager.validate_microphone()
    if not mic_ok:
        logger.error("Microphone validation FAILED: %s", mic_msg)

    # 10. AI services (optional — offline-safe)
    ai_available = bool(SARVAM_KEY)
    if not ai_available:
        logger.warning("No SARVAM_API_KEY — AI services offline. Local controls remain available.")
    _log_offline_status(ai_available, camera_ok, vision_ok)

    # 11. Hardware diagnostics
    run_hardware_diagnostics()

    # 12. Motor self-test (only if explicitly enabled)
    motor.self_test()

    # READY
    mood.set_mood("happy")
    face.set_mood("happy")
    face.set_state("happy")

    # Startup greeting — Gujarati welcome (override via greeting.txt or
    # NEXUS_STARTUP_GREETING; empty env var skips it). Spoken before the intro.
    greeting = _startup_greeting_text()
    if greeting:
        for _para in [p.strip() for p in greeting.split("\n") if p.strip()]:
            speak(_para)

    intro = "Hello, I am Nexus, an AI robot created from scratch by Jainam Soni and his team. I am online and ready."
    if camera_ok:
        intro += " My vision system is active."
    if not ai_available:
        intro += " AI services are offline, but local robot controls remain available."
    speak(intro)
    mood.touch()

    # Game engine
    game_engine = GameEngine(
        speak_callback=lambda text: speak(text),
        listen_callback=_listen_for_game,
        face_callback=_face_callback,
    )

    history = [{"role": "system", "content": build_system_prompt()}]
    silence_count = 0

    while True:
        # Idle → sleep
        if mood.check_idle(sleep_threshold=IDLE_SLEEP_THRESHOLD):
            face.set_state("asleep")
            logger.info("Nexus is sleepy — entering sleep mode")

        print("Listening...")
        if mood.get_mood() == "sleepy":
            face.set_state("asleep")
        else:
            face.set_state("listening")

        ok, err = audio_manager.record_to_wav(timeout_seconds=RECORD_SECONDS_MAX)
        print("Recording complete:", ok, err)

        # End-to-end clock starts once the user's speech is captured
        # (vision-performance pass, req. 6 — 'total end-to-end response time')
        t_e2e = time.perf_counter()

        if not ok:
            # Sleep fix (2026-09): every failed recording is non-speech —
            # 'silent', 'no-audio' (mic muted/disconnected) and arecord
            # failures must ALL count toward sleep, otherwise a dead mic
            # keeps the robot awake forever. Only 'tts-speaking' is neutral
            # (the robot itself was talking).
            if err != "tts-speaking":
                silence_count += 1
            if silence_count >= SILENCE_THRESHOLD:
                face.set_state("asleep")
                listen_for_wake_word()
                silence_count = 0
                face.set_mood(mood.get_mood())
            continue

        silence_count = 0
        txt, stt_err = transcribe()

        if stt_err or not txt:
            if stt_err in ("connection-error", "timeout", "circuit-open"):
                logger.warning("STT error: %s — continuing to listen", stt_err)
            if stt_err == "circuit-open":
                # Tell the user out loud, once per outage, instead of going
                # silently deaf (2026-09 fix: the breaker used to open with
                # only a log line — the robot looked dead).
                global _stt_outage_announced
                if not _stt_outage_announced:
                    _stt_outage_announced = True
                    speak("Speech recognition is failing. Please check my "
                          "internet connection and API key. I will keep "
                          "retrying every minute.")
            else:
                _stt_outage_announced = False
            continue

        print("You:", txt)
        low = txt.lower().strip()

        # Update mood (never affects safety) (Bug #16)
        mood.analyze_user_text(txt)
        face.set_mood(mood.get_mood())

        # ---- PRIORITY 1: SAFETY STOP (Bug #10) ----
        if is_safety_stop(low):
            motor.stop()
            speak("Stopped.")
            continue

        if low in ["exit", "quit", "shutdown", "bye", "goodbye"]:
            face.set_state("sad")
            face.set_mood("annoyed")
            speak("Goodbye.")
            motor.stop()
            break

        # ---- PRIORITY 2: Sleep/wake ----
        if "go to sleep" in low or "sleep mode" in low:
            face.set_state("asleep")
            listen_for_wake_word()
            continue

        # ---- PRIORITY 3: Navigation (before movement) (Bug #2) ----
        is_nav, nav_target = parse_navigation_command(txt)
        if is_nav and vision_ok:
            face.set_state("navigating")
            speak(navigate_to_object(nav_target))
            face.set_state("idle")
            continue

        # ---- PRIORITY 4: Direct movement (explicit parser) (Bug #2, #4, #28) ----
        recognized, action, duration = parse_movement_command(txt)
        if recognized:
            if action == "stop":
                motor.stop()
                speak("Stopped.")
            else:
                pass  # relative import removed (global available)
                if duration and duration > MOTOR_COMMAND_TIMEOUT:
                    # Announce the clamp instead of silently shortening the move (H2)
                    speak(f"That's longer than my limit, so I'll move for "
                          f"{MOTOR_COMMAND_TIMEOUT:.0f} seconds.")
                    duration = MOTOR_COMMAND_TIMEOUT
                face.nudge_look(action)
                safety_listener.start()
                try:
                    result = motor.execute_move(
                        action, duration, source="voice",
                        wait=True, timeout=MOTOR_COMMAND_TIMEOUT,
                    )
                finally:
                    safety_listener.finish()
                status = result.get("status")
                if status == "completed":
                    speak("Done.")
                elif status == "interrupted":
                    speak("Stopped.")
                else:
                    speak("I couldn't complete that movement.")
            continue

        # ---- PRIORITY 5: Special commands ----
        # Demo mode — confirmation gate (Review #30)
        if "demo" in low:
            _run_demo_mode(vision_ok)
            continue

        if "guard mode" in low or "guard the" in low or "security mode" in low:
            guard_mode()
            continue

        if "dance" in low or "do a dance" in low:
            dance()
            continue

        # Face recognition
        if any(p in low for p in ["who am i", "recognize me", "do you know me",
                                   "who do you see", "recognize my face", "who is this"]):
            _greet_known_person()
            continue

        # Face enrollment
        if "remember my face" in low or "learn my face" in low or "save my face" in low:
            name_match = re.search(r"(?:remember|learn|save) my face(?:\s+as)?\s+(.+)", low)
            name = name_match.group(1).strip() if name_match else ""
            if name:
                result = enroll_face(name, tts_callback=lambda t: speak(t))
                mood.set_mood("happy")
                face.set_mood("happy")
                speak(result)
            else:
                speak("What name should I remember your face as?")
                ok2, _ = audio_manager.record_to_wav(timeout_seconds=5)
                name_txt = None
                if ok2:
                    name_txt, _ = transcribe()
                if name_txt:
                    result = enroll_face(name_txt, tts_callback=lambda t: speak(t))
                    speak(result)
            continue

        # Face privacy controls (Bug #13)
        if "delete my face" in low or "delete face" in low:
            # Extract name if provided
            name_match = re.search(r"delete\s+(?:my\s+face|face\s+(?:data\s+)?(?:for|of)\s+)(.+)", low)
            name = name_match.group(1).strip() if name_match else ""
            if not name:
                # Ask for the name instead of trying to delete a literal "my_face" (L4)
                speak("Which person's face data should I delete? Say the name.")
                ok2, _ = audio_manager.record_to_wav(timeout_seconds=5)
                name_txt = None
                if ok2:
                    name_txt, _ = transcribe()
                if name_txt:
                    speak(delete_face(name_txt))
                else:
                    speak("I didn't catch a name, so I didn't delete anything.")
            else:
                speak(delete_face(name))
            continue

        if "delete all faces" in low or "clear face memory" in low or "wipe faces" in low:
            speak(delete_all_faces())
            continue

        # Games — strict intent dispatch, not substring (Review #17)
        if any(w in low for w in ["play a game", "play game", "let's play",
                                   "play rock", "start rock",
                                   "start trivia", "start quiz",
                                   "start simon", "play simon",
                                   "start guess", "play guess"]):
            game_engine.dispatch(low)
            continue

        # Weather / News — checked BEFORE vision queries so phrases like
        # "show me the news" aren't hijacked by the camera (M2)
        if any(w in low for w in ["weather", "forecast", "is it raining", "how hot", "how cold", "temperature outside"]):
            face.set_state("thinking")
            speak(get_weather())
            continue

        if any(w in low for w in ["news", "headlines"]):
            face.set_state("thinking")
            m = re.search(r'news (?:about|on|regarding)\s+(.+)', low)
            topic = m.group(1).strip() if m else None
            speak(get_news(topic))
            continue

        # Vision queries — fast local route or deep cloud route
        # (vision-performance pass, reqs. 1/3/4)
        if vision_ok and is_vision_query(txt):
            _handle_vision_query(txt, t_e2e)
            latency.record("e2e_total", time.perf_counter() - t_e2e)
            continue

        # Memory
        if low.startswith("remember that") or low.startswith("remember this") or low.startswith("please remember"):
            fact = re.sub(r'^(please\s+)?remember(\s+that|\s+this)?\s*', '', txt, flags=re.IGNORECASE).strip()
            if fact and memory.remember(fact):
                history[0]["content"] = build_system_prompt()
                mood.set_mood("happy")
                face.set_mood("happy")
                speak("Got it, I'll remember that.")
            else:
                speak("What should I remember?")
            continue

        if "what do you remember about me" in low or "what do you know about me" in low:
            facts = memory.get_facts()
            if facts:
                mood.set_mood("happy")
                face.set_mood("happy")
                speak("Here's what I know: " + "; ".join(facts[-5:]))
            else:
                speak("I don't have anything saved about you yet.")
            continue

        if "forget everything" in low or "clear your memory" in low or "wipe your memory" in low:
            memory.forget_all()
            history[0]["content"] = build_system_prompt()
            speak("Okay, I've forgotten everything.")
            continue

        # Mood query
        if "how do you feel" in low or "what's your mood" in low or "what mood are you in" in low:
            current = mood.get_mood()
            mood_desc = {
                "happy": "feeling happy and great!",
                "sleepy": "feeling a bit sleepy...",
                "annoyed": "feeling a little annoyed, to be honest.",
                "excited": "feeling super excited right now!",
                "curious": "feeling curious about everything!",
                "neutral": "feeling good and ready to help.",
            }
            speak(f"I'm {mood_desc.get(current, 'doing fine')}")
            continue

        # Identity
        if any(q in low for q in IDENTITY_TRIGGERS):
            mood.set_mood("happy")
            face.set_mood("happy")
            face.set_state("happy")
            speak("I am Nexus, an AI robot created from scratch by Jainam Soni and his team.")
            continue

        # ---- PRIORITY 6: AI conversation ----
        history[0]["content"] = build_system_prompt()
        print("[AI Thinking...]")
        reply, history = ask_ai(txt, history)
        print("Robot:", reply)
        face.set_mood(mood.get_mood())
        latency.record("e2e_total", time.perf_counter() - t_e2e)


def _listen_for_game(timeout=10):
    """Helper for games: record + transcribe."""
    ok, _ = audio_manager.record_to_wav(timeout_seconds=timeout)
    if not ok:
        return None
    text, err = transcribe()
    if err or not text:
        return None
    return text.lower().strip()


def _greet_known_person():
    """Look through camera and greet recognized person."""
    if not FACE_CASCADE_AVAILABLE:
        speak("I can't recognize faces — my face detection module isn't available.")
        return
    frame = camera_manager.capture()
    if frame is None:
        speak("I can't see right now.")
        return
    face.show_camera_frame(frame)
    time.sleep(0.5)
    face.hide_camera()
    recognitions = recognize_faces(frame)
    if not recognitions:
        mood.set_mood("curious")
        face.set_mood("curious")
        speak("I see a face, but I don't think we've met. You can say 'remember my face as' and your name.")
        return
    known = [(name, conf) for name, conf in recognitions if name is not None]
    if known:
        mood.set_mood("happy")
        face.set_mood("happy")
        names = [name.replace("_", " ") for name, _ in known]
        if len(names) == 1:
            speak(f"Hey {names[0]}, nice to see you!")
        else:
            speak(f"Hey {' and '.join(names)}, great to see you both!")
    else:
        mood.set_mood("curious")
        face.set_mood("curious")
        speak("I see someone, but I don't recognize you.")


def _run_demo_mode(vision_available=False):
    """
    Demo mode with a confirmation gate (Review #30).
    Demo mode physically moves the robot — a casual sentence containing
    "demo" must NOT trigger movement. The user must explicitly confirm.
    """

    mood.set_mood("excited")
    face.set_mood("excited")
    face.set_state("happy")
    speak("The robot will move. Please stand clear. Say 'confirm' to start the demo.")

    if DEMO_MODE_CONFIRMATION:
        # Wait for explicit confirmation (Review #30). Accept only unambiguous
        # confirmations — a bare "start"/"okay" must NOT authorise physical
        # motion (L9).
        confirmed = False
        for _ in range(3):  # allow up to 3 attempts
            ok, _ = audio_manager.record_to_wav(timeout_seconds=5)
            if not ok:
                continue
            txt, _ = transcribe()
            if txt and any(w in txt.lower() for w in
                           ["confirm", "i confirm", "yes", "go ahead",
                            "start the demo", "start demo"]):
                confirmed = True
                break
            if txt and any(w in txt.lower() for w in
                           ["cancel", "no", "stop", "abort", "don't", "do not"]):
                speak("Demo cancelled.")
                face.set_state("idle")
                face.set_mood("neutral")
                mood.set_mood("neutral")
                return
        if not confirmed:
            speak("Demo cancelled — I didn't hear a confirmation.")
            face.set_state("idle")
            face.set_mood("neutral")
            mood.set_mood("neutral")
            return
        speak("Starting physical demo.")

    # Execute the demo — every move checks safety state (Review #5)
    _execute_demo(vision_available)


def _execute_demo(vision_available):
    """The actual demo sequence — every move uses the blocking motor API, and
    a spoken safety-stop or an interrupted move ends the demo immediately
    (Round 2: C1, C2, C6)."""

    speak("Hello everyone, I'm Nexus, an AI robot built by Jainam Soni and his team.")
    speak("I can hold a conversation, answer questions, and control myself using voice commands.")
    speak("Let me walk you through a few things I can do.")
    face.set_state("thinking")
    speak("I can check the live weather for you.")
    speak(get_weather())
    face.set_state("thinking")
    speak("I can also read out today's top news.")
    speak(get_news(count=1))
    mood.set_mood("happy")
    face.set_mood("happy")
    speak("And I have my own memory, so if you tell me something important, I'll remember it.")
    if vision_available:
        speak("I also have a camera, so I can see what's around me and recognize objects.")
    speak("Now, let me show you how I move. Please stand clear.")
    time.sleep(0.5)

    demo_moves = [
        ("forward", 1.2, "Moving forward."),
        ("back", 1.2, "And back."),
        ("left", 1.0, "Turning left."),
        ("right", 1.0, "Turning right."),
        ("spin", 1.8, "And just for fun, a full spin!"),
    ]
    stopped_for_safety = False
    safety_listener.start()
    try:
        for move, duration, announce in demo_moves:
            if safety_listener.stop_requested or motor.safety.is_fault():
                stopped_for_safety = True
                break
            speak(announce)
            if safety_listener.stop_requested or motor.safety.is_fault():
                stopped_for_safety = True
                break
            face.nudge_look(move)
            result = motor.execute_move(
                move, duration=duration, source="demo",
                wait=True, timeout=MOTOR_COMMAND_TIMEOUT,
            )
            if result.get("status") not in ("completed",):
                stopped_for_safety = True
                break
    finally:
        safety_listener.finish()
    motor.stop(source="demo_end")
    mood.set_mood("neutral")
    face.set_mood("neutral")
    if stopped_for_safety:
        speak("Demo stopped for safety.")
    else:
        face.set_state("happy")
        speak("That's me! Thank you for watching!")
    face.set_state("idle")


def _voice_worker():
    try:
        main()
    except Exception as e:
        logger.error("Voice loop crashed: %s", e, exc_info=True)
    finally:
        face.request_stop()


def entry_point():
    """Main entry point — handles startup, face display loop, and shutdown."""
    import signal

    # Handle SIGTERM/SIGINT for clean shutdown (Bug #23)
    def signal_handler(signum, frame):
        logger.info("Signal %s received — initiating shutdown", signum)
        shutdown_manager.shutdown(reason=f"signal-{signum}")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    face.start()
    worker = threading.Thread(target=_voice_worker, daemon=True)
    worker.start()

    try:
        while worker.is_alive() and (face._screen is None or face._running):
            face.tick()
            if face._screen is None:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        shutdown_manager.shutdown(reason="main_exit")


if __name__ == "__main__":
    entry_point()
