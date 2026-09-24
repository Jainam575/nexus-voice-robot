"""
Expanded tests for collision sensor, audio coordination, and
camera manager (Review #6, #7, #8).
"""
import time
import threading
import pytest
from unittest.mock import MagicMock, patch
from nexus.collision import CollisionSensor
from nexus.audio import AudioManager


class TestCollisionSensor:
    """Review #6 — physical collision-safety layer."""

    def test_disabled_sensor_reports_no_collision(self):
        sensor = CollisionSensor(sensor_type="none", enabled=False)
        collision, distance = sensor.get_distance()
        assert collision is False
        assert sensor.active is False

    def test_ultrasonic_stub_inactive_without_gpio(self):
        """On non-Pi systems, ultrasonic driver is inactive."""
        sensor = CollisionSensor(sensor_type="ultrasonic", enabled=True)
        # Without GPIO hardware, the sensor is not active
        assert sensor.active is False

    def test_bumper_inactive_without_gpio(self):
        sensor = CollisionSensor(sensor_type="bumper", enabled=True)
        assert sensor.active is False

    def test_unknown_type_disabled(self):
        sensor = CollisionSensor(sensor_type="magic", enabled=True)
        assert sensor.active is False

    def test_is_collision_imminent_false_when_inactive(self):
        sensor = CollisionSensor(sensor_type="none", enabled=False)
        assert sensor.is_collision_imminent() is False


class TestAudioManagerSpeakingState:
    """Review #7 — speaking-state coordination."""

    def test_set_and_check_speaking(self):
        am = AudioManager()
        assert am.is_speaking() is False
        am.set_speaking(True)
        assert am.is_speaking() is True
        am.set_speaking(False)
        assert am.is_speaking() is False

    def test_speaking_state_thread_safe(self):
        am = AudioManager()
        errors = []

        def flip():
            for _ in range(100):
                am.set_speaking(True)
                am.set_speaking(False)

        threads = [threading.Thread(target=flip) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert am.is_speaking() is False


class TestAudioManagerPlaybackOwnership:
    """Review #8 — AudioManager owns playback process state with one lock."""

    def test_stop_playback_without_active_process(self):
        """stop_playback is safe when nothing is playing."""
        am = AudioManager()
        am.stop_playback()  # must not raise

    def test_fallback_tts_nonexistent(self):
        """fallback_tts returns False when espeak is unavailable."""
        am = AudioManager()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert am.fallback_tts("hello") is False


class TestTTSSpeakingStateRestored:
    """Review #7 — TTS restores the speaking state even on error."""

    def test_speaking_state_restored_on_error(self):
        """When TTS fails, the speaking state must still be reset."""
        from nexus import tts as tts_module
        am = AudioManager()

        with patch.object(tts_module, "SARVAM_KEY", "fake-key"), \
             patch.object(tts_module, "audio_manager", am), \
             patch.object(tts_module.requests, "post",
                          side_effect=Exception("network down")), \
             patch.object(am, "fallback_tts", return_value=False):
            tts_module.speak("test sentence", face_callback=None)

        assert am.is_speaking() is False, \
            "speaking state must be restored after TTS error"

    def test_speaking_state_restored_on_success(self):
        """When TTS completes, the speaking state must be reset."""
        from nexus import tts as tts_module
        am = AudioManager()
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.iter_content.return_value = iter([b"fakeaudio"])
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()

        with patch.object(tts_module, "SARVAM_KEY", "fake-key"), \
             patch.object(tts_module, "audio_manager", am), \
             patch.object(tts_module.requests, "post", return_value=mock_response), \
             patch.object(am, "start_playback", return_value=mock_proc), \
             patch.object(am, "finish_playback"):
            tts_module.speak("test sentence", face_callback=None)

        assert am.is_speaking() is False
