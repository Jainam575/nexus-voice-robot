"""
Nexus Robot — Motor Controller (Review P0 #1, #2, #3, #4, #5, #6; P2 #23, #24, #33)

Single owner of all GPIO motor operations:
- A dedicated motor worker thread (the ONLY thread that touches GPIO)
- A command queue: all components submit commands, never touch GPIO
- STOP is a high-priority command that jumps the queue (Review #5)
- Command generation system: STOP invalidates all prior generations
- Interruptible movement: checks generation + collision every 0.1s
- Motor watchdog: triggers an emergency-stop EVENT routed through the
  SafetyController → Motor Queue → Motor Worker (never touches GPIO
  directly — Review #1)
- Blocking/awaitable motor API: execute_move(..., wait=True) blocks until
  the command finishes / is interrupted / fails / times out (Review #2)
- Self-test goes through the same Motor Worker queue (Review #3)
- Structured safety logging for every movement (Review #33)

IMPORTANT: the watchdog e-stop path only works if the worker thread is
alive. For guaranteed safety a physical motor-enable cutoff / hardware
e-stop circuit independent of software is required (Review #1/#6).
"""
import threading
import queue
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

from .config import (MOTOR_A_EN, MOTOR_A_IN1, MOTOR_A_IN2,
                     MOTOR_B_EN, MOTOR_B_IN3, MOTOR_B_IN4,
                     DEFAULT_SPEED, MOTOR_WATCHDOG_TIMEOUT,
                     MOTOR_SELF_TEST, MOTOR_COMMAND_TIMEOUT)
from .safety import SafetyController, MotorWatchdog, STATE_FAULT
from .collision import collision_sensor

logger = logging.getLogger("Nexus.Motor")

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
    logger.info("GPIO initialized with PWM")
except Exception as e:
    _IS_PI = False
    logger.warning("GPIO not available: %s", e)


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
                logger.error("GPIO re-initialization failed: %s", e)
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        self._watchdog.start()
        logger.info("Motor controller started (worker + watchdog)")

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
            logger.warning("Movement denied — safety state=%s (source=%s)",
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
        from .command_parser import parse_movement_command
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
                    logger.info("Movement interrupted (gen=%d, elapsed=%.1fs)",
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
            logger.error("Motor execution error: %s", e, exc_info=True)
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
            logger.error("GPIO teardown error: %s", e)
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
                logger.error("Raw stop failed: %s", e, exc_info=True)

    # ------------------------------------------------------------------
    # Structured safety logging (Review #33)
    # ------------------------------------------------------------------
    def _log_movement(self, cmd, action, result, reason, duration=None):
        """
        Structured safety log for every physical movement (Review #33).
        Never logs credentials or biometric data.
        """
        logger.info(
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
            logger.info("Motor self-test skipped (set NEXUS_MOTOR_SELF_TEST=1 to enable)")
            return
        if not _IS_PI:
            logger.info("Motor self-test skipped — not on Pi")
            return
        logger.info("Motor self-test — short pulses at low speed (queued)")
        for direction in ("forward", "back"):
            result = self.execute_move(
                direction, duration=0.15, speed=30,
                source="self_test", wait=True, timeout=5.0,
            )
            if result.get("status") not in ("completed", "simulated"):
                logger.warning("Self-test %s: %s", direction, result)
                return
        logger.info("Motor self-test complete")

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
                logger.error("Could not enqueue shutdown command: %s", e)
            if ack.wait(timeout=3.0):
                logger.info("Motor Worker acknowledged the shutdown STOP (FIX 2)")
            else:
                logger.error("Motor Worker did not acknowledge the shutdown STOP — "
                             "GPIO left untouched by this thread")
        self._running = False
        if worker is not None:
            worker.join(timeout=2)

    @property
    def is_pi(self):
        return _IS_PI


# Singleton instance — the ONLY motor controller
motor = MotorController()
