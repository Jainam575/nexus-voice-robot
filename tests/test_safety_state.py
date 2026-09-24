"""
Expanded tests for SafetyController — fault state, emergency stop,
collision integration, and controlled recovery (Review #1, #4, #5, #6).
"""
import time
import threading
import pytest
from unittest.mock import MagicMock, patch
from nexus.safety import SafetyController, MotorWatchdog, STATE_STOPPED, STATE_MOVING, STATE_FAULT


class TestFaultState:
    """Review #4 — watchdog/worker failure must atomically reset safety state."""

    def test_emergency_stop_sets_fault(self):
        sc = SafetyController()
        gen = sc.request_movement()
        assert sc.get_state() == STATE_MOVING
        sc.emergency_stop(reason="watchdog")
        assert sc.get_state() == STATE_FAULT
        assert sc.is_fault() is True

    def test_fault_blocks_movement(self):
        sc = SafetyController()
        sc.emergency_stop(reason="crash")
        assert sc.request_movement() is None
        assert sc.is_fault() is True

    def test_clear_fault_allows_movement(self):
        """Controlled recovery: FAULT → STOPPED → movement allowed."""
        sc = SafetyController()
        sc.emergency_stop(reason="test")
        assert sc.is_fault()
        sc.clear_fault()
        assert not sc.is_fault()
        gen = sc.request_movement()
        assert gen is not None

    def test_emergency_stop_invalidates_generation(self):
        sc = SafetyController()
        gen = sc.request_movement()
        sc.emergency_stop(reason="watchdog")
        assert sc.is_generation_valid(gen) is False

    def test_fault_reason_recorded(self):
        sc = SafetyController()
        sc.emergency_stop(reason="worker_crash")
        assert sc.get_fault_reason() == "worker_crash"

    def test_is_stopped_in_fault(self):
        """FAULT state is also considered 'stopped' — no movement."""
        sc = SafetyController()
        sc.emergency_stop()
        assert sc.is_stopped() is True


class TestCollisionSensor:
    """Review #6 — collision sensor can veto movement and trigger STOP."""

    def test_collision_blocks_movement(self):
        sc = SafetyController()
        mock_sensor = MagicMock()
        mock_sensor.is_collision_imminent.return_value = True
        sc.set_collision_sensor(mock_sensor)
        assert sc.request_movement() is None

    def test_no_collision_allows_movement(self):
        sc = SafetyController()
        mock_sensor = MagicMock()
        mock_sensor.is_collision_imminent.return_value = False
        sc.set_collision_sensor(mock_sensor)
        assert sc.request_movement() is not None

    def test_check_collision_triggers_stop(self):
        sc = SafetyController()
        gen = sc.request_movement()
        mock_sensor = MagicMock()
        mock_sensor.is_collision_imminent.return_value = True
        mock_sensor.get_distance.return_value = (True, 0.15)
        sc.set_collision_sensor(mock_sensor)
        result = sc.check_collision()
        assert result is True
        assert sc.is_stopped() is True
        assert sc.is_generation_valid(gen) is False

    def test_no_collision_during_movement(self):
        sc = SafetyController()
        gen = sc.request_movement()
        mock_sensor = MagicMock()
        mock_sensor.is_collision_imminent.return_value = False
        sc.set_collision_sensor(mock_sensor)
        assert sc.check_collision() is False
        assert sc.is_generation_valid(gen) is True


class TestWatchdogEStopEvent:
    """Review #1 — watchdog triggers an event, not direct GPIO."""

    def test_watchdog_callback_is_called(self):
        called = []
        wd = MotorWatchdog(timeout=0.3, emergency_stop_callback=lambda: called.append(True))
        wd._last_heartbeat = time.time() - 1.0
        wd.start()
        time.sleep(0.6)
        wd.stop()
        wd.join(timeout=1)
        assert len(called) >= 1

    def test_watchdog_callback_does_not_touch_gpio(self):
        """The callback is an event request, not a GPIO call."""
        sc = SafetyController()
        wd = MotorWatchdog(timeout=0.3, emergency_stop_callback=lambda: sc.emergency_stop("watchdog"))
        wd._last_heartbeat = time.time() - 1.0
        wd.start()
        time.sleep(0.6)
        wd.stop()
        wd.join(timeout=1)
        assert sc.is_fault() is True

    def test_watchdog_join_completes(self):
        """Review #23 — watchdog thread can be joined."""
        wd = MotorWatchdog(timeout=10, emergency_stop_callback=lambda: None)
        wd.start()
        wd.stop()
        wd.join(timeout=2)
        assert not wd._thread.is_alive()
