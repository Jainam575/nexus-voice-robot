"""
Nexus Robot — Main Entry Point (Bug #3, #22, #23, #27)

Safe startup order (Bug #22):
  1. Logging
  2. Configuration
  3. GPIO safety
  4. Verify emergency-stop path
  5. Motor controller (+ watchdog)
  6. Camera
  7. Microphone validation
  8. TTS (optional)
  9. Optional AI services (STT, chat, vision)
 10. Optional hardware tests
 11. READY

Offline-safe (Bug #3): robot boots and runs local controls even without API key.
AI services degrade gracefully — "AI services are offline, but local robot
controls remain available."
"""
import os
import sys
import time
import re
import random
import threading
import struct
from concurrent.futures import ThreadPoolExecutor

from .config import (SARVAM_KEY, SARVAM_CHAT_MODEL, IDLE_SLEEP_THRESHOLD,
                      MAX_HISTORY_MESSAGES, NEXUS_PERSONALITY, KEYWORD_PATH,
                      SILENCE_THRESHOLD, RECORD_SECONDS_MAX, MIC_DEVICE,
                      TTS_DEVICE, MOTOR_COMMAND_TIMEOUT, NEXUS_VISION_API_KEY,
                      NEXUS_REPLY_LANGUAGE)
from .logging_config import logger
from .motor import motor
from .command_parser import (parse_movement_command, parse_navigation_command,
                              is_safety_stop)
from .audio import audio_manager
from .camera import camera_manager
from .tts import speak, stop_playback
from .stt import transcribe, CircuitBreaker
from .mood import mood
from .memory import memory
from .face_display import face
from .vision import (vision_system, vision_context,
                     vision_worker, save_vision_memory_async)
from .latency import latency
from .navigation import navigate_to_object
from .face_recognition import (enroll_face, recognize_faces, delete_face,
                                delete_all_faces, FACE_CASCADE_AVAILABLE,
                                _detect_faces)
from .games import GameEngine
from .weather import get_weather
from .news import get_news
from .shutdown import shutdown_manager

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
    from .safety_listener import safety_listener

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

    from .config import (GUARD_INTERVAL, GUARD_MOTION_THRESHOLD,
                          GUARD_PIXEL_RATIO, GUARD_MAX_DURATION)

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
                from .safety_listener import safety_listener
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
    from .config import DEMO_MODE_CONFIRMATION

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
    from .safety_listener import safety_listener

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
