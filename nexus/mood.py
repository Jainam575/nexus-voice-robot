"""
Nexus Robot — Mood System (Bug #16, #17)

Conservative mood detection — requires multiple signals, not single keywords.
Mood is SEPARATED from robot state (Bug #17): mood affects personality/voice,
but doesn't override face_state or robot operational state.

Mood never affects safety-critical behavior (Bug #16).
"""
import threading
import time
import re
import logging

logger = logging.getLogger("Nexus.Mood")

MOOD_DATA = {
    "neutral":  {"voice": None,   "temp": 0.4, "prompt": "friendly and helpful"},
    "happy":    {"voice": "shubh", "temp": 0.5, "prompt": "cheerful and warm"},
    "sleepy":   {"voice": "shubh", "temp": 0.3, "prompt": "slow and drowsy, speaking softly as if just waking up"},
    "annoyed":  {"voice": "shubh", "temp": 0.2, "prompt": "a bit grumpy and curt, but still helpful"},
    "excited":  {"voice": "shubh", "temp": 0.8, "prompt": "very enthusiastic and energetic"},
    "curious":  {"voice": "shubh", "temp": 0.6, "prompt": "curious and inquisitive, often asking follow-up questions"},
}

# Sets for conservative matching — require multiple hits for longer messages
POSITIVE_WORDS = {"great", "awesome", "amazing", "love", "good", "nice", "cool",
                  "fantastic", "wonderful", "excellent", "perfect", "thanks",
                  "happy", "fun", "brilliant", "wow", "incredible"}
NEGATIVE_WORDS = {"stupid", "dumb", "hate", "useless", "boring", "annoying",
                 "terrible", "awful", "worst", "broken"}
# Multi-word phrases checked separately (L2): per-word set matching could
# never hit these, so "thank you" / "shut up" were dead entries.
POSITIVE_PHRASES = {"thank you", "well done", "good job"}
NEGATIVE_PHRASES = {"shut up"}
EXCITED_TRIGGERS = {"joke", "game", "dance", "party", "celebrate", "surprise"}
QUESTION_INDICATORS = {"what", "why", "how", "when", "where", "who", "which", "explain", "tell me about"}


class Mood:
    """
    Tracks mood independently of robot operational state.
    Mood affects TTS voice/temperature and AI personality prompt.
    Mood NEVER affects safety, motor control, or command parsing.

    Thread safety (Review #28): ALL mutable mood state, including
    _last_interaction, is protected by the same lock.
    """

    def __init__(self):
        self._mood = "neutral"
        self._last_interaction = time.time()
        self._lock = threading.Lock()

    def set_mood(self, m):
        if m in MOOD_DATA:
            with self._lock:
                self._mood = m

    def get_mood(self):
        with self._lock:
            return self._mood

    def touch(self):
        # Same lock as other mutable mood state (Review #28)
        with self._lock:
            self._last_interaction = time.time()

    def _get_last_interaction(self):
        with self._lock:
            return self._last_interaction

    def analyze_user_text(self, text):
        """
        Conservative mood detection.
        Requires multiple keyword hits for longer messages.
        Short commands (<=3 words) don't trigger mood changes.
        Never affects safety-critical behavior.

        Negation handling (Review #29): "This is not great" / "I don't
        feel happy" / "That wasn't fun" are NOT classified as positive.
        """
        if not text:
            return
        t = text.lower()
        self.touch()

        cleaned = re.sub(r'[^\w\s]', '', t)
        words = cleaned.split()
        word_count = len(words)
        if word_count <= 3:
            return

        word_set = set(words)

        # Negation handling (Review #29): a positive word within a few
        # words after a negator is NOT positive — it flips to negative.
        # NOTE: punctuation is stripped above, so "don't" → "dont",
        # "wasn't" → "wasnt", etc.
        NEGATORS = {"not", "no", "never", "dont", "wasnt", "isnt", "arent",
                    "werent", "wont", "cant", "couldnt", "wouldnt", "nothing"}
        negated_positive = False
        negated_negative = False
        for i, w in enumerate(words):
            if w in NEGATORS or w == "don't":
                window = words[i + 1:i + 4]  # negation applies to next ~3 words
                if any(x in POSITIVE_WORDS or x in EXCITED_TRIGGERS for x in window):
                    negated_positive = True
                if any(x in NEGATIVE_WORDS for x in window):
                    negated_negative = True

        positive_hits = len(word_set & POSITIVE_WORDS)
        negative_hits = len(word_set & NEGATIVE_WORDS)
        excited_hits = len(word_set & EXCITED_TRIGGERS)
        question_hits = len(word_set & QUESTION_INDICATORS)

        # Multi-word phrase matching (L2)
        positive_hits += sum(1 for p in POSITIVE_PHRASES if p in cleaned)
        negative_hits += sum(1 for p in NEGATIVE_PHRASES if p in cleaned)

        # Apply negation scoring (Review #29)
        if negated_positive:
            # "not great" / "don't feel happy" → counts as negative signal
            negative_hits += 1
            positive_hits = max(0, positive_hits - 1)
            excited_hits = max(0, excited_hits - 1)
        if negated_negative:
            # "not bad" → mild positive
            positive_hits += 1
            negative_hits = max(0, negative_hits - 1)

        threshold = 2 if word_count > 12 else 1

        if negative_hits >= threshold:
            self.set_mood("annoyed")
        elif excited_hits >= threshold:
            self.set_mood("excited")
        elif positive_hits >= threshold:
            self.set_mood("happy")
        elif question_hits >= threshold and word_count <= 15:
            self.set_mood("curious")

    def check_idle(self, sleep_threshold=180):
        # _last_interaction read under the same lock (Review #28)
        with self._lock:
            current_mood = self._mood
            idle = time.time() - self._last_interaction > sleep_threshold
        if current_mood != "sleepy" and idle:
            self.set_mood("sleepy")
            return True
        return False

    @property
    def voice(self):
        with self._lock:
            return MOOD_DATA[self._mood]["voice"]

    @property
    def temperature(self):
        with self._lock:
            return MOOD_DATA[self._mood]["temp"]

    @property
    def personality_prompt(self):
        with self._lock:
            return MOOD_DATA[self._mood]["prompt"]


# Singleton
mood = Mood()
