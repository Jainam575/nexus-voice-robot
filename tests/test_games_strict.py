"""
Expanded tests for game dispatch — strict intent matching, RPS parsing,
number range validation, Simon Says voice-only (Review #17, #18, #19, #20).
"""
import pytest
from unittest.mock import MagicMock
from nexus.games import parse_spoken_number, _parse_rps_answer, GameEngine


class TestStrictRPS:
    """Review #18 — strict RPS answer parsing."""

    def test_rock_exact(self):
        assert _parse_rps_answer("rock") == "rock"

    def test_paper_exact(self):
        assert _parse_rps_answer("paper") == "paper"

    def test_scissors_exact(self):
        assert _parse_rps_answer("scissors") == "scissors"

    def test_scissor_alias(self):
        assert _parse_rps_answer("scissor") == "scissors"

    def test_rocks_alias(self):
        assert _parse_rps_answer("rocks") == "rock"

    def test_i_choose_rock(self):
        assert _parse_rps_answer("I choose rock") == "rock"

    def test_my_choice_is_paper(self):
        assert _parse_rps_answer("my choice is paper") == "paper"

    def test_unrelated_rejected(self):
        assert _parse_rps_answer("I was talking about rock music") is None

    def test_two_answers_rejected(self):
        """Two game words in one answer = ambiguous → reject."""
        assert _parse_rps_answer("rock and paper") is None

    def test_empty_rejected(self):
        assert _parse_rps_answer("") is None

    def test_random_sentence_rejected(self):
        assert _parse_rps_answer("the weather is nice today") is None


class TestGameDispatch:
    """Review #17 — intent-based game dispatch, not substring."""

    def _make_engine(self, listen_responses=None):
        spoken = []
        responses = list(listen_responses or [])
        def listen(timeout=5):
            return responses.pop(0) if responses else None
        engine = GameEngine(
            speak_callback=lambda t: spoken.append(t),
            listen_callback=listen,
            face_callback=lambda s: None,
        )
        return engine, spoken

    def test_play_rps_dispatches(self):
        engine, spoken = self._make_engine(listen_responses=["rock"])
        engine.dispatch("play rock paper scissors")
        assert any("rock paper scissors" in s.lower() for s in spoken)

    def test_start_rps_dispatches(self):
        engine, spoken = self._make_engine(listen_responses=["paper"])
        engine.dispatch("start rock paper scissors")
        assert len(spoken) > 0

    def test_lets_play_number_dispatches(self):
        # Provide 7 responses (max_attempts) so the game completes
        engine, spoken = self._make_engine(listen_responses=["fifty"] * 7)
        engine.dispatch("let's play guess the number")
        assert any("guess" in s.lower() or "number" in s.lower() for s in spoken)

    def test_casual_conversation_no_dispatch(self):
        """Normal conversation should NOT activate a game."""
        engine, spoken = self._make_engine()
        engine.dispatch("I was talking about rock music")
        # Should ask which game, not start RPS
        assert any("which one" in s.lower() for s in spoken)

    def test_i_like_paper_no_dispatch(self):
        """'I like paper crafts' should NOT start RPS."""
        engine, spoken = self._make_engine()
        engine.dispatch("I like paper crafts")
        assert any("which one" in s.lower() for s in spoken)


class TestNumberRange:
    """Review #20 — spoken number parsing constrained to 1–100."""

    def test_valid_range(self):
        assert parse_spoken_number("fifty", 1, 100) == 50

    def test_out_of_range_rejected(self):
        assert parse_spoken_number("one hundred twenty five", 1, 100) is None

    def test_zero_rejected(self):
        assert parse_spoken_number("0", 1, 100) is None

    def test_negative_rejected(self):
        assert parse_spoken_number("-5", 1, 100) is None

    def test_custom_range(self):
        assert parse_spoken_number("25", 1, 50) == 25
        assert parse_spoken_number("75", 1, 50) is None

    def test_boundary_1(self):
        assert parse_spoken_number("1", 1, 100) == 1

    def test_boundary_100(self):
        assert parse_spoken_number("100", 1, 100) == 100

    def test_101_rejected(self):
        assert parse_spoken_number("101", 1, 100) is None

    def test_one_hundred_twenty_five(self):
        """Compound number > 100 is rejected in 1-100 range."""
        assert parse_spoken_number("one hundred twenty five", 1, 100) is None
