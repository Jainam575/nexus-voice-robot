"""Tests for the safety controller and motor generation system."""
import time
import threading
import pytest
from nexus.safety import SafetyController, MotorWatchdog


class TestSafetyController:
    def test_initial_state_stopped(self):
        sc = SafetyController()
        assert sc.is_stopped() is True

    def test_request_movement_when_stopped(self):
        sc = SafetyController()
        gen = sc.request_movement()
        assert gen is not None
        assert sc.is_stopped() is False

    def test_request_movement_while_moving_denied(self):
        sc = SafetyController()
        gen1 = sc.request_movement()
        gen2 = sc.request_movement()  # should be denied
        assert gen1 is not None
        assert gen2 is None

    def test_stop_invalidates_generation(self):
        sc = SafetyController()
        gen = sc.request_movement()
        assert sc.is_generation_valid(gen) is True
        sc.request_stop()
        assert sc.is_generation_valid(gen) is False

    def test_stop_always_wins(self):
        """STOP must invalidate any in-flight movement (Bug #1)."""
        sc = SafetyController()
        gen = sc.request_movement()
        sc.request_stop(reason="test")
        # Old generation invalid
        assert sc.is_generation_valid(gen) is False
        # New movement after stop gets new generation
        new_gen = sc.request_movement()
        assert new_gen is not None
        assert new_gen != gen
        # The new generation is valid, old is not
        assert sc.is_generation_valid(new_gen) is True
        assert sc.is_generation_valid(gen) is False

    def test_rapid_stop_movement_sequence(self):
        """Multiple STOP + movement cycles — generation always increases."""
        sc = SafetyController()
        gens = []
        for _ in range(5):
            gen = sc.request_movement()
            sc.request_stop()
            sc.mark_complete(sc.get_generation())
            gens.append(gen)
        # All generations unique
        assert len(set(gens)) == len(gens)

    def test_stop_during_movement(self):
        """Simulate: movement starts → STOP → movement checks generation → abort."""
        sc = SafetyController()
        gen = sc.request_movement()
        # Movement is running, checks its generation periodically
        assert sc.is_generation_valid(gen)
        # STOP arrives
        sc.request_stop()
        # Movement's next check should fail
        assert not sc.is_generation_valid(gen)


class TestMotorWatchdog:
    def test_watchdog_fires_on_no_heartbeat(self):
        """Watchdog must fire emergency stop if no heartbeat."""
        fired = []
        wd = MotorWatchdog(timeout=0.3, emergency_stop_callback=lambda: fired.append(True))
        # Simulate no heartbeat
        wd._last_heartbeat = time.time() - 1.0
        wd.start()
        time.sleep(0.6)
        wd.stop()
        assert len(fired) >= 1, "Watchdog should have fired"

    def test_watchdog_does_not_fire_with_heartbeats(self):
        """Watchdog should NOT fire if heartbeats are regular."""
        fired = []
        wd = MotorWatchdog(timeout=0.5, emergency_stop_callback=lambda: fired.append(True))
        wd.start()
        # Send heartbeats for 1 second
        for _ in range(10):
            wd.heartbeat()
            time.sleep(0.1)
        wd.stop()
        assert len(fired) == 0, "Watchdog should NOT have fired"

    def test_watchdog_heartbeat_resets(self):
        """Heartbeat should reset the timer."""
        fired = []
        wd = MotorWatchdog(timeout=0.5, emergency_stop_callback=lambda: fired.append(True))
        wd._last_heartbeat = time.time() - 0.4  # almost timed out
        wd.heartbeat()  # reset
        wd.start()
        time.sleep(0.3)  # less than timeout
        wd.stop()
        assert len(fired) == 0
