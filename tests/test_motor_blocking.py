"""
Expanded tests for MotorController — blocking API, queued STOP,
self-test through queue, timeout (Review #2, #3, #5, #16).
"""
import time
import threading
import pytest
from unittest.mock import MagicMock, patch
from nexus.motor import MotorController, MotorCommand


class TestBlockingMove:
    """Review #2 — execute_move(wait=True) blocks until completion."""

    def test_blocking_move_completes(self):
        mc = MotorController()
        mc.start()
        try:
            result = mc.execute_move("forward", duration=0.05, source="test", wait=True, timeout=2.0)
            assert result["status"] == "completed"
        finally:
            mc.cleanup()

    def test_blocking_move_interrupted_by_stop(self):
        """STOP during a blocking move interrupts it."""
        mc = MotorController()
        mc.start()
        try:
            # Start a long move, then STOP after a short delay
            def stop_after_delay():
                time.sleep(0.1)
                mc.stop(source="test_interrupt")

            threading.Thread(target=stop_after_delay, daemon=True).start()
            result = mc.execute_move("forward", duration=2.0, source="test", wait=True, timeout=5.0)
            assert result["status"] in ("interrupted", "timeout")
        finally:
            mc.cleanup()

    def test_blocking_move_denied_by_collision(self):
        """Review #6 — collision sensor denies movement."""
        mc = MotorController()
        mock_sensor = MagicMock()
        mock_sensor.is_collision_imminent.return_value = True
        mc.safety.set_collision_sensor(mock_sensor)
        result = mc.execute_move("forward", duration=0.1, source="test", wait=True, timeout=2.0)
        assert result["status"] == "denied"

    def test_non_blocking_returns_bool(self):
        mc = MotorController()
        mc.start()
        try:
            result = mc.execute_move("forward", duration=0.05, source="test")
            assert isinstance(result, bool)
            assert result is True
            # Wait for it to complete
            time.sleep(0.2)
        finally:
            mc.cleanup()


class TestQueuedStop:
    """Review #5 — STOP jumps the queue."""

    def test_stop_returns_ack_event(self):
        """Review #21 — STOP returns an Event that's set when processed."""
        mc = MotorController()
        mc.start()
        try:
            ack = mc.stop(source="test")
            assert hasattr(ack, "wait")
            assert ack.wait(timeout=2.0) is True
        finally:
            mc.cleanup()

    def test_stop_clears_queued_commands(self):
        mc = MotorController()
        mc.start()
        try:
            # Queue a move, then stop
            mc.execute_move("forward", duration=1.0, source="test1")
            time.sleep(0.02)  # let it start
            mc.stop(source="test_stop")
            time.sleep(0.2)
            assert mc.safety.is_stopped()
        finally:
            mc.cleanup()


class TestSelfTestThroughQueue:
    """Review #3 — self-test goes through the Motor Worker queue."""

    def test_self_test_skipped_when_disabled(self):
        """Self-test is skipped by default (not enabled)."""
        mc = MotorController()
        mc.start()
        try:
            mc.self_test()  # should not raise, just skip
        finally:
            mc.cleanup()


class TestIdempotentCleanup:
    """Review #24 — cleanup is idempotent."""

    def test_double_cleanup_safe(self):
        mc = MotorController()
        mc.start()
        mc.cleanup()
        mc.cleanup()  # must not raise
        mc.cleanup()  # third time also safe

    def test_cleanup_stops_worker(self):
        mc = MotorController()
        mc.start()
        assert mc._worker_thread is not None
        assert mc._worker_thread.is_alive()
        mc.cleanup()
        assert not mc._worker_thread.is_alive()
