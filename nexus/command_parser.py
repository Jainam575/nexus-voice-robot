"""
Nexus Robot — Strict Command Parser (Bug #2, #4, #28, #29; Founder-demo FIX 1)

Intent-based parser, NOT substring matching. Physical movement requires
EXPLICIT MOVEMENT INTENT:

  1. Safety STOP (stop, halt, freeze, emergency stop, don't move)
  2. Negation check (don't, never, do not) → reject
  3. Navigation (go to, find, navigate to, move toward) → return navigation
  4. Direct movement — the utterance must BEGIN with a movement verb/command
     word (move / go / turn / spin / reverse / stop...) after an optional
     politeness or wake prefix ("please", "hey nexus", "nexus"), and must
     contain a recognized direction phrase.

A bare direction word ("right", "left", "forward", "ahead", "back",
"backward") inside a normal sentence is conversation — it can NEVER move
the robot (Founder-demo FIX 1). "You are right.", "Left or right?",
"Right now, tell me a joke." all fall through to AI conversation.
"reverse" and "spin" are treated as explicit commands (they are verbs),
but only at the start of an utterance.
"""
import re
import logging

logger = logging.getLogger("Nexus.Parser")

# Safety stop words — always highest priority
SAFETY_STOP_WORDS = ["stop", "halt", "freeze", "emergency stop"]
SAFETY_STOP_PHRASES = ["don't move", "do not move", "dont move"]

# Negation words
NEGATION_WORDS = ["don't", "do not", "dont", "never", "no "]

# Navigation indicators — checked BEFORE movement
NAVIGATION_PATTERNS = [
    re.compile(r"\bgo\s+to\b", re.I),
    re.compile(r"\bmove\s+to\b", re.I),
    re.compile(r"\bnavigate\s+to\b", re.I),
    re.compile(r"\bfind\b", re.I),
    re.compile(r"\bgo\s+toward", re.I),
    re.compile(r"\bmove\s+toward", re.I),
    re.compile(r"\bgo\s+towards", re.I),
    re.compile(r"\bmove\s+towards", re.I),
    re.compile(r"\bwhere\s+is\b", re.I),
]

# Movement phrases — EXPLICIT INTENT ONLY (Founder-demo FIX 1).
# Every entry begins with a movement verb or is itself an unambiguous
# command word. Bare direction words ("left", "right", "forward", "ahead",
# "back", "backward", "backwards") are deliberately ABSENT: they appear in
# normal conversation and must never move the robot on their own.
_MOVEMENT_PHRASES = [
    ("stop",     ["stop", "halt", "brake", "freeze"]),
    ("forward",  ["move forward", "go forward", "move ahead", "go ahead",
                   "go straight", "move straight"]),
    ("back",     ["move backward", "go backward", "move back", "go back",
                   "reverse"]),
    ("left",     ["turn left", "go left", "move left"]),
    ("right",    ["turn right", "go right", "move right"]),
    ("spin",     ["turn around", "spin around", "turn round", "spin"]),
]

# An utterance must START with one of these (after an optional politeness /
# wake prefix) for any movement phrase to be considered (Founder-demo FIX 1).
_MOVEMENT_STARTERS = {"move", "go", "turn", "spin", "reverse",
                      "stop", "halt", "brake", "freeze"}
_WAKE_PREFIXES = {"please", "hey", "nexus", "ok", "okay"}

# Conversational phrases that should NOT trigger movement.
# These contain movement words but are clearly conversational.
_CONVERSATION_REJECTIONS = [
    re.compile(r"\byou'?re\s+(right|left)\b", re.I),
    re.compile(r"\bthat'?s\s+(right|left)\b", re.I),
    re.compile(r"\bwhat'?s\s+(right|left)\b", re.I),
    re.compile(r"\bi\s+(was|am|am)\s+(walking|going|moving|turning)\b", re.I),
    re.compile(r"\bexplain\b.*\b(forward|backward|left|right|spin)\b", re.I),
    re.compile(r"\bwhat\b.*\b(forward|backward|left|right|spin)\s+means\b", re.I),
    re.compile(r"\bhe\s+(was|is)\s+(going|walking|turning)\s+(forward|back|left|right)\b", re.I),
    re.compile(r"\bshe\s+(was|is)\s+(going|walking|turning)\s+(forward|back|left|right)\b", re.I),
    re.compile(r"\bthat\s+was\s+(?:a\s+)?(?:left|right)\s+turn\b", re.I),
    re.compile(r"\ba\s+(?:left|right)\s+turn\b", re.I),
]


def _has_negation(text):
    """Check if text contains negation that prevents movement (Bug #4)."""
    t = text.lower().strip()
    for neg in NEGATION_WORDS:
        if neg in t:
            return True
    return False


def is_safety_stop(text):
    """Check if this is a safety STOP command (Bug #10). Highest priority."""
    if not text:
        return False
    t = text.lower().strip()
    for phrase in SAFETY_STOP_PHRASES:
        if phrase in t:
            return True
    # Whole-word match for stop words
    for word in SAFETY_STOP_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", t):
            # But reject if negated: "don't stop" shouldn't stop
            if _has_negation(t):
                return False
            return True
    return False


def _is_navigation(text):
    """Check if this is a navigation command (Bug #2)."""
    t = text.lower().strip()
    return any(p.search(t) for p in NAVIGATION_PATTERNS)


def _extract_duration(text):
    """Extract duration: 'for 2 seconds', 'for 1.5', 'for three'."""
    t = text.lower()
    m = re.search(r"for\s+(\d+(?:\.\d+)?)", t)
    if m:
        return float(m.group(1))
    words_to_nums = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
    m2 = re.search(r"for\s+(one|two|three|four|five)\b", t)
    if m2:
        return float(words_to_nums.get(m2.group(1), 1))
    return None


def _is_conversational(text):
    """Check if this is a conversational sentence that happens to contain movement words (Bug #2)."""
    t = text.lower().strip()
    for pattern in _CONVERSATION_REJECTIONS:
        if pattern.search(t):
            return True
    # If the sentence is long and complex (>8 words) and doesn't start with
    # a movement verb, treat it as conversation
    words = t.split()
    if len(words) > 8:
        # Check if it starts with a movement verb
        first_word = words[0] if words else ""
        if first_word not in ("move", "go", "turn", "forward", "backward", "back",
                              "left", "right", "spin", "stop", "halt", "ahead",
                              "reverse", "backwards"):
            return True
    return False


def _has_explicit_movement_intent(text):
    """Founder-demo FIX 1: movement requires explicit intent.

    The utterance must begin with a movement verb / command word, ignoring
    an optional politeness or wake prefix ("please", "hey nexus",
    "nexus", "ok"). Direction words alone ("right", "forward", ...) are
    conversation and never qualify.
    """
    words = re.findall(r"[a-z']+", text.lower())
    for w in words:
        if w in _WAKE_PREFIXES:
            continue
        return w in _MOVEMENT_STARTERS
    return False


def parse_movement_command(text):
    """
    Strict movement parser (Bug #2, #28; Founder-demo FIX 1).
    Returns (recognized: bool, action: str or None, duration: float or None).

    1. Conversational rejection — "You're right" → not a command
    2. Negation check — "don't move forward" → not a command
    3. Navigation check — "go to chair" → not a movement (it's navigation)
    4. Explicit-intent check — the utterance must START with a movement
       verb/command ("move forward" → command; "the answer is right" →
       conversation)
    5. Phrase match — "move forward" → (True, "forward", 1.0)
    """
    if not text:
        return False, None, None

    t = text.lower().strip()

    # Too long = probably conversation
    if len(t.split()) > 12:
        return False, None, None

    # 0. Conversational rejection (Bug #2)
    if _is_conversational(t):
        return False, None, None

    # 1. Negation check (Bug #4)
    if _has_negation(t):
        logger.info("Command rejected — negation detected: %s", text)
        return False, None, None

    # 2. Navigation check (Bug #2) — "go to chair" is NOT "go forward"
    if _is_navigation(t):
        return False, None, None

    # 3. Explicit movement intent (Founder-demo FIX 1) — a bare direction
    #    word inside a sentence is conversation, never a command.
    if not _has_explicit_movement_intent(t):
        logger.info("Command rejected — no explicit movement intent: %s", text)
        return False, None, None

    # 4. Exact phrase matching — verb-led phrases only
    for action, phrases in _MOVEMENT_PHRASES:
        for phrase in phrases:
            if re.search(rf"\b{re.escape(phrase)}\b", t):
                dur = _extract_duration(t)
                if dur is None:
                    if action in ("left", "right"):
                        dur = 0.7
                    elif action in ("spin",):
                        dur = 2.0
                    elif action == "stop":
                        dur = 0.0
                    else:
                        dur = 1.0
                logger.info("Movement parsed: text=%r action=%s duration=%.1f", text, action, dur)
                return True, action, dur

    return False, None, None


def parse_navigation_command(text):
    """
    Navigation parser (Bug #29).
    Returns (is_navigation: bool, target: str or None).
    """
    if not text:
        return False, None
    t = text.lower().strip()

    # "go to the chair" → target = "chair"
    m = re.search(r"(?:go|move|navigate)\s+(?:to|toward|towards)\s+(?:the\s+|a\s+|an\s+)?(.+)", t)
    if m:
        target = m.group(1).strip()
        target = re.sub(r"\s+(?:please|now|quickly)$", "", target)
        return True, target

    # "find the cup"
    m = re.search(r"find\s+(?:the\s+|a\s+|an\s+)?(.+)", t)
    if m:
        target = m.group(1).strip()
        target = re.sub(r"\s+(?:please|now|quickly)$", "", target)
        return True, target

    # "where is the chair"
    m = re.search(r"where\s+(?:is|are)\s+(?:the\s+|a\s+|an\s+)?(.+)", t)
    if m:
        target = m.group(1).strip()
        target = re.sub(r"\s+(?:please|now|quickly)$", "", target)
        return True, target

    return False, None
