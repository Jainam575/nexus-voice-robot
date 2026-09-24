"""Tests for mood system — conservative detection (Bug #16)."""
import time
import pytest
from nexus.mood import Mood


class TestConservativeMood:
    def test_short_command_no_mood_change(self):
        """Short commands (<=3 words) should NOT trigger mood changes."""
        m = Mood()
        m.set_mood("neutral")
        m.analyze_user_text("turn left")
        assert m.get_mood() == "neutral"

    def test_positive_message(self):
        m = Mood()
        m.analyze_user_text("this is great, I love it")
        assert m.get_mood() == "happy"

    def test_negative_message(self):
        m = Mood()
        m.analyze_user_text("you are stupid and useless")
        assert m.get_mood() == "annoyed"

    def test_excited_trigger(self):
        m = Mood()
        m.analyze_user_text("let's play a game, this is fun")
        assert m.get_mood() == "excited"

    def test_question_curious(self):
        m = Mood()
        m.analyze_user_text("what is that thing over there")
        assert m.get_mood() == "curious"

    def test_long_message_needs_multiple_hits(self):
        """Long messages require 2+ keyword hits (Bug #16)."""
        m = Mood()
        m.set_mood("neutral")
        # 13+ words, only 1 negative keyword — should NOT change mood
        m.analyze_user_text("I was telling my friend about how my old robot was broken but then we fixed it together")
        assert m.get_mood() == "neutral", "Single 'broken' in long positive sentence should not trigger annoyed"

    def test_mood_never_affects_safety(self):
        """Mood system has no connection to safety/motor — verify by design."""
        m = Mood()
        m.analyze_user_text("you are terrible and awful and stupid")
        assert m.get_mood() == "annoyed"
        # Mood is just a state — it doesn't return motor commands
        # This test documents the design intent.
        assert m.get_mood() in ("neutral", "happy", "sleepy", "annoyed", "excited", "curious")


class TestIdleSleep:
    def test_idle_becomes_sleepy(self):
        m = Mood()
        # Simulate old interaction time
        m._last_interaction = time.time() - 999
        changed = m.check_idle(sleep_threshold=180)
        assert changed is True
        assert m.get_mood() == "sleepy"

    def test_recent_interaction_stays_awake(self):
        m = Mood()
        m.touch()
        changed = m.check_idle(sleep_threshold=180)
        assert changed is False
        assert m.get_mood() != "sleepy"
