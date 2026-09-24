"""
Final founder-demo validation — the two required fixes.

FIX 1 — Movement parser: conversation mentioning a direction must NEVER
         move the robot; explicit verb-led commands still work.
FIX 2 — Motor GPIO ownership: only the Motor Worker touches motor GPIO,
         including the final stop + PWM teardown during shutdown.

The adversarial and positive test strings are taken verbatim from the
founder-demo requirements document.
"""
import threading
import time

import pytest

from nexus.command_parser import parse_movement_command, is_safety_stop
from nexus.motor import MotorController, MotorCommand


# ================================================================ FIX 1
class TestParserConversationSafety:
    """Adversarial cases from the requirements doc — NO MOVEMENT."""

    ADVERSARIAL = [
        "You are right.",
        "The answer is right.",
        "What is right?",
        "Right now, tell me a joke.",
        "I need the right answer.",
        "Left or right?",
        "That's right, this is impressive.",
        # additional variants of the same class
        "What's right?",
        "Right now...",
        "Which way is left",
        "the way forward is clear",
        "we are moving ahead with the plan",
        "he took a left turn at the junction",
        "let's go back to what you said",
    ]

    @pytest.mark.parametrize("text", ADVERSARIAL)
    def test_conversation_never_moves_robot(self, text):
        recognized, action, _ = parse_movement_command(text)
        assert recognized is False, f"must NOT be a movement command: {text!r}"
        assert action is None

    def test_bare_direction_words_rejected(self):
        for word in ("forward", "ahead", "left", "right", "back", "backward"):
            recognized, _, _ = parse_movement_command(word)
            assert recognized is False, f"bare {word!r} must not move the robot"

    def test_polite_question_form_rejected(self):
        """Indirect/question forms are conversation, not explicit intent."""
        assert parse_movement_command("can you turn right?")[0] is False
        assert parse_movement_command("could you move forward")[0] is False


class TestParserExplicitCommands:
    """Positive cases from the requirements doc — movement MUST work."""

    POSITIVE = [
        ("turn right", "right"),
        ("go right", "right"),
        ("move forward", "forward"),
        ("go forward", "forward"),
        ("turn left", "left"),
        ("move backward", "back"),
        ("reverse", "back"),
        ("please turn right", "right"),
        ("please move forward", "forward"),
        ("go back", "back"),
        ("spin", "spin"),
        ("turn around", "spin"),
        ("go straight", "forward"),
        ("move ahead", "forward"),
        ("nexus, move forward", "forward"),
        ("move forward for 2 seconds", "forward"),
    ]

    @pytest.mark.parametrize("text,expected", POSITIVE)
    def test_explicit_command_moves_robot(self, text, expected):
        recognized, action, _ = parse_movement_command(text)
        assert recognized is True, f"must be a movement command: {text!r}"
        assert action == expected

    def test_safety_stop_unchanged(self):
        """Safety-stop words keep their (higher) priority path."""
        assert is_safety_stop("stop") is True
        assert is_safety_stop("halt") is True
        assert is_safety_stop("don't stop me now") is False

    def test_negation_still_rejected(self):
        assert parse_movement_command("don't turn right")[0] is False
        assert parse_movement_command("never go forward")[0] is False


# ================================================================ FIX 2
class TestMotorGpioOwnership:
    """Only the Motor Worker touches motor GPIO — including shutdown."""

    def _instrumented_controller(self):
        """Build a controller whose GPIO-touching methods record which
        thread invoked them."""
        mc = MotorController()
        calls = []

        main_thread = threading.current_thread().ident

        def record(name):
            def _fn(*a, **kw):
                calls.append((name, threading.current_thread().ident))
            return _fn

        mc._raw_stop = record("raw_stop")
        mc._teardown_gpio = record("teardown_gpio")
        return mc, calls, main_thread

    def test_cleanup_gpio_happens_on_worker_thread_only(self):
        mc, calls, main_thread = self._instrumented_controller()
        mc.start()
        mc.cleanup()

        names = [c[0] for c in calls]
        assert "raw_stop" in names, "worker must perform the final physical stop"
        assert "teardown_gpio" in names, "worker must perform the PWM teardown"
        for name, thread_id in calls:
            assert thread_id != main_thread, \
                f"{name} was called from the MAIN thread — GPIO ownership violation (FIX 2)"
        assert not mc._worker_thread.is_alive()

    def test_cleanup_acknowledges_and_exits_promptly(self):
        mc = MotorController()
        mc.start()
        t0 = time.time()
        mc.cleanup()
        assert time.time() - t0 < 5, "cleanup must not hang"
        assert not mc._worker_thread.is_alive(), "worker must exit after shutdown"
        assert not mc._running

    def test_cleanup_interrupts_active_movement(self):
        """Movement -> shutdown: worker must stop + ack, no GPIO from main."""
        mc, calls, main_thread = self._instrumented_controller()
        mc.start()

        result_box = {}

        def mover():
            result_box["res"] = mc.execute_move(
                "forward", duration=3.0, source="test", wait=True, timeout=8)

        t = threading.Thread(target=mover, daemon=True)
        t.start()
        time.sleep(0.4)          # let the (simulated) movement get going
        mc.cleanup()             # shutdown while moving
        t.join(timeout=5)

        assert result_box.get("res", {}).get("status") == "interrupted"
        for name, thread_id in calls:
            assert thread_id != main_thread, f"{name} ran on the MAIN thread"
        assert not mc._worker_thread.is_alive()

    def test_cleanup_idempotent(self):
        mc = MotorController()
        mc.start()
        mc.cleanup()
        mc.cleanup()  # second call must be a safe no-op

    def test_restart_after_cleanup(self):
        """start() after cleanup() must bring the worker back (verified in
        simulated mode)."""
        mc = MotorController()
        mc.start()
        mc.cleanup()
        mc.start()
        try:
            res = mc.execute_move("forward", duration=0.1, source="restart_test",
                                  wait=True, timeout=5)
            assert res["status"] == "completed"
        finally:
            mc.cleanup()

    def test_worker_shutdown_command_shape(self):
        """The shutdown command goes through the queue as a queued command
        with a done_event (ack), like every other motor command."""
        mc = MotorController()
        mc.start()
        ack = threading.Event()
        mc._cmd_queue.put(MotorCommand(action="shutdown", duration=0,
                                       priority="stop", source="test",
                                       done_event=ack))
        assert ack.wait(timeout=3), "worker must acknowledge the shutdown command"
        mc._worker_thread.join(timeout=2)
        assert not mc._worker_thread.is_alive()
