"""
Nexus Robot — Face Recognition (Review P1 #12, #13, #14)

- camera_manager injection: enroll_face always uses the supplied manager
  when one is provided (Review #12).
- Privacy controls (Review #13): delete face, delete all faces,
  disable-face-storage option, configurable retention, restrictive
  filesystem permissions, no biometric logging.
- Missing face-data directory handled safely (Review #14).
- Names are sanitized to safe filesystem characters.
"""
import os
import re
import time
import json
import logging
import shutil
from pathlib import Path

from .face_display import face
from .config import (KNOWN_FACES_DIR, FACE_RECOGNIZER_FILE,
                      FACE_CONFIDENCE_THRESHOLD, FACE_ENROLL_SAMPLES, FACE_MIN_SIZE,
                      FACE_STORAGE_ENABLED, FACE_DATA_RETENTION,
                      FACE_FILE_PERMISSIONS, FACE_DIR_PERMISSIONS)

logger = logging.getLogger("Nexus.FaceRecog")

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
        logger.info("Loaded face recognizer from %s", os.path.basename(FACE_RECOGNIZER_FILE))
    except Exception as e:
        logger.warning("Could not load face recognizer: %s", type(e).__name__)


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
        logger.error("Face detection error: %s", e, exc_info=True)
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
            logger.info("Loaded %d samples for '%s'", count, name)
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
        logger.info("Face recognizer trained with %d people", len(label_map))
        return True
    except Exception as e:
        logger.error("Face recognizer training error: %s", e, exc_info=True)
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
        logger.info("Face enrollment refused — face storage disabled by configuration")
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
        from .camera import camera_manager
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
            logger.info("Enroll frame %d/%d: %dx%d brightness=%.0f faces=%d",
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
                logger.warning("Could not save face image: %s", type(e).__name__)

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
        logger.error("Face deletion error: %s", type(e).__name__)
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
        logger.error("Delete all faces error: %s", type(e).__name__)
        return "I couldn't delete all face data."
