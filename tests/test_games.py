"""Tests for game components — number parser and trivia matching (Bug #19, #20)."""
import pytest
from nexus.games import parse_spoken_number, normalize_answer, trivia_check_answer


class TestSpokenNumberParser:
    """Compound number parser (Bug #19)."""

    def test_digit(self):
        assert parse_spoken_number("25") == 25

    def test_digit_in_sentence(self):
        assert parse_spoken_number("I guess 42") == 42

    def test_simple_word(self):
        assert parse_spoken_number("five") == 5

    def test_twenty_five(self):
        """'twenty five' should be 25, not 20 (Bug #19)."""
        assert parse_spoken_number("twenty five") == 25

    def test_thirty_five(self):
        assert parse_spoken_number("thirty five") == 35

    def test_forty_two(self):
        assert parse_spoken_number("forty two") == 42

    def test_ninety_nine(self):
        assert parse_spoken_number("ninety nine") == 99

    def test_one_hundred(self):
        assert parse_spoken_number("one hundred") == 100

    def test_seventy_three(self):
        assert parse_spoken_number("seventy three") == 73

    def test_sixty_eight(self):
        assert parse_spoken_number("sixty eight") == 68

    def test_fifteen(self):
        assert parse_spoken_number("fifteen") == 15

    def test_not_a_number(self):
        assert parse_spoken_number("hello world") is None

    def test_empty(self):
        assert parse_spoken_number("") is None


class TestTriviaMatching:
    """Normalized trivia answer matching (Bug #20)."""

    def test_exact_match(self):
        assert trivia_check_answer("delhi", ["delhi", "new delhi"]) is True

    def test_case_insensitive(self):
        assert trivia_check_answer("DELHI", ["delhi"]) is True

    def test_punctuation_removed(self):
        assert trivia_check_answer("It's Delhi!", ["delhi"]) is True

    def test_multi_word_match(self):
        assert trivia_check_answer("new delhi", ["new delhi"]) is True

    def test_no_false_positive(self):
        """Partial substring should NOT match (Bug #20)."""
        # "mars" should not match if the hint is "marsupial"
        assert trivia_check_answer("I don't know", ["mars"]) is False

    def test_word_subset_match(self):
        assert trivia_check_answer("it is mount everest", ["everest"]) is True

    def test_wrong_answer(self):
        assert trivia_check_answer("mumbai", ["delhi"]) is False

    def test_number_match(self):
        assert trivia_check_answer("there are eight", ["eight", "8"]) is True

    def test_normalize_answer(self):
        assert normalize_answer("  Hello,   World!  ") == "hello world"
