"""
Nexus Robot — Collision Safety Layer (P0 Review #6)

Camera object detection is NOT collision detection. Vision can miss:
- stairs, holes/drop-offs, transparent objects, thin objects,
- objects below the camera, low obstacles, objects outside FOV,
- rapidly approaching objects.

This module provides a physical distance-sensing layer that the
SafetyController uses to veto/override movement. Supported sensor types:
- ultrasonic (HC-SR04 style, GPIO trig/echo)
- tof (Time-of-Flight, I2C — stubbed unless hardware present)
- lidar (serial — stubbed unless hardware present)
- bumper (GPIO switch — always safe-on-trigger)
- none (disabled — robot must be operated with extra caution)

Architecture:

    Camera Vision
         ↓
    Navigation
         ↓
    Safety Controller  ← CollisionSensor (this module)
         ↓
       Motor

NOTE: For maximum safety, a hardware motor-enable cutoff / physical
emergency-stop circuit independent of software should also be installed.
"""
import threading
import time
import logging

from .config import (COLLISION_SENSOR_ENABLED, COLLISION_SENSOR_TYPE,
                     COLLISION_DISTANCE_THRESHOLD,
                     COLLISION_GPIO_TRIG, COLLISION_GPIO_ECHO)

logger = logging.getLogger("Nexus.Collision")

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
            logger.warning(
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
            logger.error("Ultrasonic read error: %s", e)
            return None

    def _read_bumper(self):
        """Bumper switch: True = pressed (collision). Returns None on error so
        the failure path (fail-safe) applies (L5)."""
        try:
            return _GPIO.input(COLLISION_GPIO_ECHO) == 1
        except Exception as e:
            logger.error("Bumper read error: %s", e)
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
                    logger.warning("Collision sensor failed %d times in a row — fail-safe collision",
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
