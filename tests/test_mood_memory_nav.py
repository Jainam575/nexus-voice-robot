"""
Expanded tests for mood negation handling, memory secrets policy,
and navigation movement checks (Review #15, #16, #27, #29).
"""
import time
import pytest
from unittest.mock import MagicMock, patch
from nexus.mood import Mood
from nexus.memory import Memory, _is_sensitive
from nexus import memory as memory_module
from nexus.navigation import find_object_position, _check_obstacle_ahead


class TestMoodNegation:
    """Review #29 — negation handling in mood context."""

    def test_not_great_is_not_positive(self):
        m = Mood()
        m.set_mood("neutral")
        m.analyze_user_text("this is not great at all honestly")
        assert m.get_mood() != "happy"

    def test_dont_feel_happy_is_not_positive(self):
        m = Mood()
        m.set_mood("neutral")
        m.analyze_user_text("I don't feel happy today my friend")
        assert m.get_mood() != "happy"

    def test_wasnt_fun_is_not_excited(self):
        m = Mood()
        m.set_mood("neutral")
        m.analyze_user_text("that wasn't fun and I didn't enjoy the game")
        assert m.get_mood() != "excited"
        assert m.get_mood() != "happy"

    def test_genuine_positive_still_works(self):
        m = Mood()
        m.set_mood("neutral")
        m.analyze_user_text("this is great, I love it so much")
        assert m.get_mood() == "happy"

    def test_not_bad_is_mildly_positive(self):
        m = Mood()
        m.set_mood("neutral")
        m.analyze_user_text("it wasn't terrible, actually not bad at all")
        assert m.get_mood() != "annoyed"


class TestMemorySecretsPolicy:
    """Review #27 — credentials/secrets are NEVER stored, even explicitly."""

    @pytest.fixture
    def test_memory(self, tmp_path):
        mem_file = tmp_path / "test_memory.json"
        old_file = memory_module.MEMORY_FILE
        memory_module.MEMORY_FILE = str(mem_file)
        m = Memory()
        yield m
        memory_module.MEMORY_FILE = old_file

    def test_remember_password_refused(self, test_memory):
        result = test_memory.remember("my password is hunter2")
        assert result is False
        assert test_memory.get_facts() == []

    def test_remember_api_key_refused(self, test_memory):
        result = test_memory.remember("my api key is sk-abc123")
        assert result is False
        assert test_memory.get_facts() == []

    def test_remember_private_key_refused(self, test_memory):
        result = test_memory.remember("my private key is XYZ")
        assert result is False

    def test_remember_banking_refused(self, test_memory):
        result = test_memory.remember("my bank account number is 1234567890")
        assert result is False

    def test_remember_auth_code_refused(self, test_memory):
        result = test_memory.remember("my authentication code is 1234")
        assert result is False

    def test_remember_token_refused(self, test_memory):
        result = test_memory.remember("my login token is abc")
        assert result is False

    def test_remember_normal_fact_works(self, test_memory):
        result = test_memory.remember("my favorite color is blue")
        assert result is True
        assert len(test_memory.get_facts()) == 1

    def test_is_sensitive_detects_secrets(self):
        assert _is_sensitive("api key") is True
        assert _is_sensitive("secret") is True
        assert _is_sensitive("private key") is True
        assert _is_sensitive("authentication code") is True
        assert _is_sensitive("credential") is True
        assert _is_sensitive("I like pizza") is False


class TestNavigationHelpers:
    """Navigation helper functions still work correctly."""

    def test_find_object(self):
        detections = [
            {"label": "person", "confidence": 0.9, "box": [0.1, 0.2, 0.5, 0.4]},
            {"label": "chair", "confidence": 0.8, "box": [0.3, 0.5, 0.7, 0.8]},
        ]
        pos = find_object_position(detections, "chair")
        assert pos["found"] is True
        assert pos["label"] == "chair"

    def test_find_object_not_found(self):
        detections = [{"label": "person", "confidence": 0.9, "box": [0.1, 0.2, 0.5, 0.4]}]
        pos = find_object_position(detections, "chair")
        assert pos["found"] is False

    def test_check_obstacle(self):
        detections = [
            {"label": "person", "confidence": 0.9, "box": [0.1, 0.2, 0.5, 0.4]},
            {"label": "chair", "confidence": 0.8, "box": [0.3, 0.45, 0.7, 0.7]},
        ]
        obstacle = _check_obstacle_ahead(detections, "person")
        assert obstacle == "chair"

    def test_no_obstacle_when_target_only(self):
        detections = [{"label": "person", "confidence": 0.9, "box": [0.1, 0.2, 0.5, 0.4]}]
        obstacle = _check_obstacle_ahead(detections, "person")
        assert obstacle is None
