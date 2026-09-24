"""
Nexus Robot — Camera Manager (Bug #11)

Thread-safe camera access. Only CameraManager touches Picamera2.
All other components go through camera_manager.capture().
"""
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

from .latency import measure

logger = logging.getLogger("Nexus.Camera")

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
            logger.warning("Camera unavailable — missing dependencies (picamera2 / opencv)")
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
            logger.info("Picamera2 initialized (RGB888 requested — true BGR byte order)")
            return True
        except Exception as e:
            logger.error("Camera init failed: %s", e, exc_info=True)
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
            logger.error("Camera capture failed: %s", e, exc_info=True)
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
