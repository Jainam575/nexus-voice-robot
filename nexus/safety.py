"""
Nexus Robot — Safety Controller & Motor Watchdog (Review P0 #1, #4, #5, #6)

Architecture:
    AI / Voice / Vision
           ↓
     Intent Parser
           ↓
    SafetyController  ← always has final authority
           ↓                ← CollisionSensor (physical layer)
      Motor Queue
           ↓
     Motor Worker (single thread owns GPIO)
           ↓
        GPIO
           ↑
    MotorWatchdog (independent — triggers emergency-stop EVENT,
                   never touches GPIO directly per Review #1)

The SafetyController uses a command-generation system: every movement gets a
generation ID. STOP invalidates the current generation, so any in-flight
movement that checks its generation will abort.

States: STOPPED → MOVING → STOPPED (normal)
        STOPPED → MOVING → FAULT (worker failure / watchdog)
        FAULT requires explicit clear_fault() before movement resumes (Review #4)
"""
import threading
import time
import logging

logger = logging.getLogger("Nexus.Safety")

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
            logger.warning("STOP issued (reason=%s, generation=%d, state=%s)",
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
            logger.critical("EMERGENCY STOP (reason=%s, generation=%d, state=FAULT)",
                            reason, self._generation)

    def clear_fault(self):
        """Controlled recovery: transition FAULT → STOPPED (Review #4)."""
        with self._lock:
            if self._state == STATE_FAULT:
                self._state = STATE_STOPPED
                self._fault_reason = None
                logger.info("Fault cleared — robot ready for controlled recovery")

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
            logger.warning("Movement DENIED — collision imminent (Review #6)")
            return None

        with self._lock:
            if self._state == STATE_FAULT:
                logger.warning("Movement DENIED — system in FAULT state (reason=%s)", self._fault_reason)
                return None
            if self._state == STATE_MOVING:
                return None
            self._state = STATE_MOVING
            gen = self._generation
            logger.info("Movement approved (generation=%d)", gen)
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
            logger.warning("Collision detected during movement (distance=%s) — STOP",
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
        logger.info("Motor watchdog started (timeout=%.1fs)", self._timeout)

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
                logger.critical(
                    "MOTOR WATCHDOG FIRED — no heartbeat for %.1fs. "
                    "Triggering emergency-stop EVENT (not direct GPIO).",
                    elapsed)
                try:
                    self._emergency_stop()
                except Exception as e:
                    logger.error("Watchdog emergency-stop callback failed: %s", e)
                # Reset heartbeat to avoid repeated triggers
                with self._lock:
                    self._last_heartbeat = time.time()
            time.sleep(check_interval)
