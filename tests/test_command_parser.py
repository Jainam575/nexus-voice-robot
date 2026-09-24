"""Tests for the command parser — the most safety-critical component."""
import pytest
from nexus.command_parser import (
    parse_movement_command,
    parse_navigation_command,
    is_safety_stop,
)


class TestSafetyStop:
    def test_stop(self):
        assert is_safety_stop("stop") is True

    def test_halt(self):
        assert is_safety_stop("halt") is True

    def test_emergency_stop(self):
        assert is_safety_stop("emergency stop") is True

    def test_dont_move(self):
        assert is_safety_stop("don't move") is True

    def test_do_not_move(self):
        assert is_safety_stop("do not move") is True

    def test_freeze(self):
        assert is_safety_stop("freeze") is True

    def test_conversation_not_stop(self):
        assert is_safety_stop("what time is it") is False

    def test_dont_stop_not_stop(self):
        """'don't stop' should NOT trigger stop (negation)."""
        assert is_safety_stop("don't stop me now") is False

    def test_empty(self):
        assert is_safety_stop("") is False
        assert is_safety_stop(None) is False


class TestDirectMovement:
    def test_bare_forward_rejected(self):
        """Founder-demo FIX 1: a bare direction word is conversation, never
        a movement command."""
        recognized, action, dur = parse_movement_command("forward")
        assert recognized is False
        assert action is None

    def test_bare_right_rejected(self):
        recognized, action, dur = parse_movement_command("right")
        assert recognized is False

    def test_bare_left_rejected(self):
        recognized, action, dur = parse_movement_command("left")
        assert recognized is False

    def test_move_forward(self):
        recognized, action, dur = parse_movement_command("move forward")
        assert recognized is True
        assert action == "forward"

    def test_go_forward(self):
        recognized, action, dur = parse_movement_command("go forward")
        assert recognized is True
        assert action == "forward"

    def test_move_ahead(self):
        recognized, action, dur = parse_movement_command("move ahead")
        assert recognized is True
        assert action == "forward"

    def test_turn_left(self):
        recognized, action, dur = parse_movement_command("turn left")
        assert recognized is True
        assert action == "left"

    def test_turn_right(self):
        recognized, action, dur = parse_movement_command("turn right")
        assert recognized is True
        assert action == "right"

    def test_go_backward(self):
        recognized, action, dur = parse_movement_command("go backward")
        assert recognized is True
        assert action == "back"

    def test_reverse(self):
        recognized, action, dur = parse_movement_command("reverse")
        assert recognized is True
        assert action == "back"

    def test_spin(self):
        recognized, action, dur = parse_movement_command("spin")
        assert recognized is True
        assert action == "spin"

    def test_turn_around(self):
        recognized, action, dur = parse_movement_command("turn around")
        assert recognized is True
        assert action == "spin"

    def test_stop(self):
        recognized, action, dur = parse_movement_command("stop")
        assert recognized is True
        assert action == "stop"

    def test_halt(self):
        recognized, action, dur = parse_movement_command("halt")
        assert recognized is True
        assert action == "stop"

    def test_duration_numeric(self):
        recognized, action, dur = parse_movement_command("move forward for 2.5 seconds")
        assert recognized is True
        assert action == "forward"
        assert dur == 2.5

    def test_duration_word(self):
        recognized, action, dur = parse_movement_command("move forward for three")
        assert recognized is True
        assert dur == 3.0


class TestConversationalRejection:
    """Movement words in conversational context must NOT trigger movement (Bug #2)."""

    def test_youre_right(self):
        recognized, _, _ = parse_movement_command("you're right")
        assert recognized is False

    def test_thats_right(self):
        recognized, _, _ = parse_movement_command("that's right")
        assert recognized is False

    def test_whats_right(self):
        recognized, _, _ = parse_movement_command("what's right")
        assert recognized is False

    def test_i_was_walking_forward(self):
        recognized, _, _ = parse_movement_command("I was walking forward")
        assert recognized is False

    def test_explain_forward(self):
        recognized, _, _ = parse_movement_command("can you explain what forward means")
        assert recognized is False

    def test_that_was_a_left_turn(self):
        recognized, _, _ = parse_movement_command("that was a left turn")
        assert recognized is False

    def test_long_conversation(self):
        recognized, _, _ = parse_movement_command(
            "I think we should go to the store and then maybe turn right at the corner"
        )
        assert recognized is False

    def test_he_was_going_forward(self):
        recognized, _, _ = parse_movement_command("he was going forward when it happened")
        assert recognized is False


class TestNegationRejection:
    """Negated commands must NEVER cause movement (Bug #4)."""

    def test_dont_move_forward(self):
        recognized, _, _ = parse_movement_command("don't move forward")
        assert recognized is False

    def test_dont_go_left(self):
        recognized, _, _ = parse_movement_command("don't go left")
        assert recognized is False

    def test_do_not_move(self):
        recognized, _, _ = parse_movement_command("do not move")
        assert recognized is False

    def test_never_turn(self):
        recognized, _, _ = parse_movement_command("never turn right")
        assert recognized is False


class TestNavigationParsing:
    def test_go_to_chair(self):
        is_nav, target = parse_navigation_command("go to the chair")
        assert is_nav is True
        assert "chair" in target

    def test_move_to_bottle(self):
        is_nav, target = parse_navigation_command("move to the bottle")
        assert is_nav is True
        assert "bottle" in target

    def test_find_cup(self):
        is_nav, target = parse_navigation_command("find the cup")
        assert is_nav is True
        assert "cup" in target

    def test_navigate_to_person(self):
        is_nav, target = parse_navigation_command("navigate to the person")
        assert is_nav is True
        assert "person" in target

    def test_go_toward_door(self):
        is_nav, target = parse_navigation_command("go toward the door")
        assert is_nav is True

    def test_where_is_chair(self):
        is_nav, target = parse_navigation_command("where is the chair")
        assert is_nav is True

    def test_not_navigation(self):
        is_nav, target = parse_navigation_command("move forward")
        assert is_nav is False


class TestMovementNotNavigation:
    """Movement commands should NOT be classified as navigation (Bug #2)."""

    def test_move_forward_not_nav(self):
        is_nav, _ = parse_navigation_command("move forward")
        assert is_nav is False

    def test_turn_left_not_nav(self):
        is_nav, _ = parse_navigation_command("turn left")
        assert is_nav is False
