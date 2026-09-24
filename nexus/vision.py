"""
Nexus Robot — Vision System (Review P1 #9, #10, #11; P2 #26)

TFLite object detection with:
- Strict output tensor validation (Review #10) — detection is DISABLED
  rather than guessing when the model signature is unsupported.
- Correct quantized input handling (Review #9) — reads the tensor's
  scale/zero_point quantization metadata and supports float32, uint8,
  and int8 models.
- Vision context TTL so stale observations aren't used (Review #11).
- Atomic vision-log writes (Review #26) — tmp + fsync + rename.

Scene description via Sarvam vision API.
"""
import base64
import json
import os
import queue
import threading
import time
import logging

from .config import (MODEL_FILE, LABELS_FILE, DETECTION_THRESHOLD,
                     VISION_CAPTURE_PATH, SARVAM_KEY, SARVAM_VISION_MODEL,
                     VISION_MEMORY_DIR, VISION_MEMORY_FILE, MAX_VISION_MEMORY,
                     VISION_CONTEXT_TTL, VISION_CACHE_AGE,
                     NEXUS_VISION_API_KEY, NEXUS_VISION_BASE_URL,
                     NEXUS_VISION_MODEL, NEXUS_REPLY_LANGUAGE)
from .latency import measure

logger = logging.getLogger("Nexus.Vision")

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
            logger.info("Vision context expired (TTL=%ds)", VISION_CONTEXT_TTL)
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
        logger.error("TFLite output identification FAILED — detection disabled. "
                     "boxes=%s classes=%s scores=%s",
                     boxes_idx, classes_idx, scores_idx)
        return None

    # All N values must match (Review #10)
    if not (boxes_n == classes_n == scores_n):
        logger.error("TFLite tensor N mismatch: boxes=%s classes=%s scores=%s "
                     "— detection disabled", boxes_n, classes_n, scores_n)
        return None

    result = {"boxes": boxes_idx, "classes": classes_idx, "scores": scores_idx}
    logger.info("TFLite outputs validated: %s (N=%s)", result, boxes_n)
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
        logger.warning("Quantized dtype %s without scale metadata — "
                       "assuming raw [0,255] input", dtype)
        return input_data.astype(dtype)

    # Unsupported tensor configuration — reject safely (Review #9)
    logger.error("Unsupported input tensor dtype: %s (scale=%s, zero_point=%s) "
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
            logger.warning("Vision unavailable — missing deps (tflite/numpy/cv2)")
            return False

        if not os.path.exists(MODEL_FILE):
            logger.warning("Model file %s not found — detection unavailable", MODEL_FILE)
            return False

        try:
            self.interpreter = tflite.Interpreter(model_path=MODEL_FILE)
            self.interpreter.allocate_tensors()
            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()

            # Validate input tensor (Review #9)
            dtype = self.input_details[0]['dtype']
            if dtype not in (np.float32, np.uint8, np.int8):
                logger.error("Unsupported input dtype %s — detection DISABLED", dtype)
                self.interpreter = None
                return False

            # Validate outputs — disable detection if identification fails
            # (Review #10)
            self.output_map = identify_tflite_outputs(self.output_details)
            if self.output_map is None:
                self.interpreter = None
                logger.error("TFLite tensor validation failed — detection DISABLED")
                return False
        except Exception as e:
            logger.error("TFLite init error: %s", e, exc_info=True)
            return False

        # Load labels
        try:
            with open(LABELS_FILE, "r") as f:
                self.labels = [line.strip() for line in f.readlines()]
            if not self.labels:
                logger.warning("Labels file is empty — detection DISABLED")
                self.interpreter = None
                return False
        except Exception as e:
            logger.warning("Could not load labels: %s — detection DISABLED", e)
            self.interpreter = None
            return False

        self.available = True
        logger.info("Vision system online (input dtype=%s)",
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
                logger.error("Input preparation failed — detection disabled")
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
                logger.error("Output tensor length mismatch — skipping detection")
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
            logger.error("Object detection error: %s", e, exc_info=True)
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
            logger.error("Scene description error: %s", e, exc_info=True)
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
        logger.error("Atomic write failed for %s: %s", path, e)
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
        logger.error("Could not save vision memory: %s", e)


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
            logger.error("Background vision-memory save failed: %s", e)


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
            from .camera import camera_manager
            self._camera = camera_manager
        if self._vision is None:
            self._vision = vision_system
        if not getattr(self._vision, "available", False):
            logger.info("Vision worker not started — local detection unavailable")
            return False
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="vision-worker")
        self._thread.start()
        logger.info("Vision worker started (continuous local detection)")
        return True

    def stop(self, timeout=2.0):
        """Stop the worker. Idempotent; safe from shutdown handlers."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("Vision worker did not stop within %.1fs", timeout)
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
                logger.error("Vision worker error: %s", e)
                time.sleep(1.0)


# Singleton
vision_worker = VisionWorker()
