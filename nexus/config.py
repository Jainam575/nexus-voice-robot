"""
Nexus Robot — Centralized Configuration
All configuration in one place. No hard-coded device strings elsewhere.
"""
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
KNOWN_FACES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "known_faces")
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
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
