"""
Nexus Robot — Mini Games (Bug #18, #19, #20)

Fixes:
- Simon Says: no longer claims to detect movement — pure voice-response game (Bug #18)
- Guess the Number: proper compound number parser ("twenty five" → 25) (Bug #19)
- Trivia: normalized answer matching, no false positives from substrings (Bug #20)
"""
import random
import re
import logging

logger = logging.getLogger("Nexus.Games")

# Compound number parser (Bug #19)
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
         "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
          "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
          "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
          "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_SPECIAL = {"hundred": 100}


def parse_spoken_number(text, min_val=1, max_val=100):
    """
    Parse a spoken number from text (Review #20).
    Handles: "25", "twenty five", "ninety nine", "one hundred", etc.
    Returns int if in [min_val, max_val], else None.
    Rejects invalid numbers and values outside the game range.
    """
    t = text.lower().strip()

    # Reject negatives (game range is 1-100)
    if t.startswith("-") or "negative" in t.split()[:1]:
        return None

    # Direct digit
    m = re.search(r'\d+', t)
    if m:
        val = int(m.group())
        return val if min_val <= val <= max_val else None

    # Try compound: "twenty five" → 25, "one hundred twenty five" → 125
    words = t.replace("-", " ").split()
    result = 0
    found = False
    for word in words:
        if word in _TENS:
            result += _TENS[word]
            found = True
        elif word in _UNITS:
            result += _UNITS[word]
            found = True
        elif word in _SPECIAL:
            result *= _SPECIAL[word]
            found = True
    if found:
        return result if min_val <= result <= max_val else None

    # Single word number
    for word, val in {**_UNITS, **_TENS, **_SPECIAL}.items():
        if word == t:
            return val if min_val <= val <= max_val else None

    return None


def _wants_quit(text, include_stop=True):
    """True if the user asked to leave the game (H1). Word-based so "stopwatch"
    etc. don't match."""
    if not text:
        return False
    words = set(normalize_answer(text).split())
    quit_words = {"quit", "exit", "cancel", "enough", "done"}
    if include_stop:
        quit_words.add("stop")
    return bool(words & quit_words)


def normalize_answer(text):
    """Normalize answer for comparison."""
    t = text.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)  # remove punctuation
    t = re.sub(r'\s+', ' ', t)     # normalize whitespace
    return t.strip()


# RPS answer aliases — clear, unambiguous only (Review #18)
_RPS_ALIASES = {
    "rock": "rock",
    "rocks": "rock",
    "paper": "paper",
    "scissors": "scissors",
    "scissor": "scissors",
}


def _parse_rps_answer(text):
    """
    Strict RPS answer parsing (Review #18).
    Only accepts normalized answers: rock / paper / scissors
    (with clear aliases). Rejects unrelated sentences.
    Returns "rock"|"paper"|"scissors" or None.
    """
    norm = normalize_answer(text)
    if not norm:
        return None
    # Exact single-word match (or clear alias)
    if norm in _RPS_ALIASES:
        return _RPS_ALIASES[norm]
    # Allow "I choose rock" / "my choice is paper" style — the answer
    # must be the ONLY game word in the sentence
    words = norm.split()
    hits = {w for w in words if w in _RPS_ALIASES}
    filler = {"i", "choose", "my", "choice", "is", "pick", "go", "with", "the", "a"}
    if len(hits) == 1 and all(w in filler or w in _RPS_ALIASES for w in words):
        return _RPS_ALIASES[hits.pop()]
    return None


def trivia_check_answer(user_answer, valid_hints):
    """
    Check if user's answer matches any valid hint (Bug #20).
    Uses normalized exact-word matching, not arbitrary substring.
    """
    norm = normalize_answer(user_answer)
    norm_words = set(norm.split())
    for hint in valid_hints:
        hint_norm = normalize_answer(hint)
        hint_words = set(hint_norm.split())
        # Check if the hint is a subset of the user's answer words
        if hint_words and hint_words.issubset(norm_words):
            return True
        # Also check exact match
        if norm == hint_norm:
            return True
    return False


TRIVIA_QUESTIONS = [
    {"q": "What is the capital of India?", "a": "new delhi", "hints": ["delhi", "new delhi"]},
    {"q": "How many planets are in our solar system?", "a": "8", "hints": ["eight", "8"]},
    {"q": "What is the largest mammal on Earth?", "a": "blue whale", "hints": ["whale", "blue whale"]},
    {"q": "Who wrote the play Romeo and Juliet?", "a": "shakespeare", "hints": ["shakespeare", "william shakespeare"]},
    {"q": "What is the chemical symbol for water?", "a": "h2o", "hints": ["h2o"]},
    {"q": "What is the tallest mountain in the world?", "a": "mount everest", "hints": ["everest", "mount everest"]},
    {"q": "How many colors are in a rainbow?", "a": "7", "hints": ["seven", "7"]},
    {"q": "Which Indian scientist won the Nobel Prize for Physics in 1930?", "a": "c v raman", "hints": ["raman", "c v raman"]},
    {"q": "What is the national animal of India?", "a": "tiger", "hints": ["tiger"]},
    {"q": "Which planet is known as the Red Planet?", "a": "mars", "hints": ["mars"]},
]


class GameEngine:
    """Manages mini games. Takes callbacks for audio I/O."""

    def __init__(self, speak_callback, listen_callback, face_callback=None):
        self.speak = speak_callback
        self.listen = listen_callback
        self.set_face = face_callback or (lambda state: None)

    def play_rock_paper_scissors(self):
        self.set_face("playing")
        self.speak("Let's play rock paper scissors! Say rock, paper, or scissors on three. Ready?")
        self.speak("Rock, paper, scissors, shoot!")

        choice = self.listen(timeout=5)
        if not choice:
            self.speak("I didn't hear you. Maybe next time!")
            return

        if _wants_quit(choice):
            self.speak("Okay, we can play again later!")
            self.set_face("idle")
            return

        # Strict answer parsing (Review #18) — normalized exact match only
        user_choice = _parse_rps_answer(choice)
        if not user_choice:
            self.speak(f"I heard '{choice}', but I need rock, paper, or scissors.")
            return

        nexus_choice = random.choice(["rock", "paper", "scissors"])
        self.speak(f"I chose {nexus_choice}!")

        if user_choice == nexus_choice:
            self.speak("It's a tie! Great minds think alike.")
        elif (user_choice == "rock" and nexus_choice == "scissors") or \
             (user_choice == "paper" and nexus_choice == "rock") or \
             (user_choice == "scissors" and nexus_choice == "paper"):
            self.speak(f"You win! {user_choice} beats {nexus_choice}. Well done!")
        else:
            self.speak(f"I win! {nexus_choice} beats {user_choice}. Better luck next time!")
        self.set_face("idle")

    def play_guess_the_number(self):
        self.set_face("playing")
        target = random.randint(1, 100)
        attempts = 0
        max_attempts = 7

        self.speak("Let's play guess the number! I'm thinking of a number between 1 and 100. You have 7 tries.")

        while attempts < max_attempts:
            attempts += 1
            self.speak(f"Guess {attempts}. What's your number?")
            answer = self.listen(timeout=8)

            if not answer:
                # A missed/invalid guess consumes the attempt (H1): the old
                # version refunded attempts on silence, which made the game
                # run forever and blocked the main loop.
                self.speak("I didn't catch that. Moving on.")
                continue

            if _wants_quit(answer):
                self.speak(f"Okay! The number was {target}. We can play again later.")
                self.set_face("idle")
                return

            num = parse_spoken_number(answer)  # Bug #19: compound numbers
            if num is None:
                self.speak("I didn't hear a number. Moving on.")
                continue

            if num == target:
                self.speak(f"Yes! The number was {target}! You got it in {attempts} tries. Amazing!")
                self.set_face("idle")
                return
            elif num < target:
                self.speak(f"{num} is too low. Go higher!")
            else:
                self.speak(f"{num} is too high. Go lower!")

        self.speak(f"Out of guesses! The number was {target}. Better luck next time!")
        self.set_face("idle")

    def play_trivia(self):
        self.set_face("playing")
        self.speak("Welcome to Nexus Trivia! I'll ask you 3 questions.")
        score = 0
        questions = random.sample(TRIVIA_QUESTIONS, min(3, len(TRIVIA_QUESTIONS)))

        for i, q in enumerate(questions, 1):
            self.speak(f"Question {i}. {q['q']}")
            answer = self.listen(timeout=10)

            if not answer:
                self.speak(f"Time's up! The answer was {q['a']}.")
                continue

            if _wants_quit(answer):
                self.speak(f"Okay, ending the trivia. You scored {score} so far. Bye for now!")
                self.set_face("idle")
                return

            # Bug #20: normalized matching, not substring
            if trivia_check_answer(answer, q["hints"]):
                score += 1
                self.speak("Correct! Well done!")
            else:
                self.speak(f"Not quite! The answer was {q['a']}.")

        self.set_face("happy")
        if score == len(questions):
            self.speak(f"Perfect score! {score} out of {len(questions)}. You're a genius!")
        elif score > 0:
            self.speak(f"You scored {score} out of {len(questions)}. Not bad!")
        else:
            self.speak("Zero correct, but don't worry — practice makes perfect!")
        self.set_face("idle")

    def play_simon_says(self):
        """
        Simon Says — Voice Version (Review #19).
        Does NOT claim to detect physical movement. The game tests if the
        user follows the "Simon says" rule verbally. If you need actual
        movement verification, implement it using sensors/camera.
        """
        self.set_face("playing")
        self.speak("Let's play Simon Says — Voice Version! I'll give you commands. "
                   "Only follow them if I say 'Simon says'. "
                   "If I don't say 'Simon says', you should say 'I didn't move'. Ready?")

        rounds = 5
        score = 0
        commands = ["forward", "back", "left", "right", "spin", "stop"]
        spoken = {"forward": "forward", "back": "back", "left": "left",
                  "right": "right", "spin": "spin around", "stop": "stop"}

        for rnd in range(1, rounds + 1):
            say_simon = random.random() > 0.35
            cmd = random.choice(commands)

            if say_simon:
                self.speak(f"Simon says {spoken[cmd]}.")
                # User should respond with the action or confirm they did it.
                # Word-based matching (L6): "no" must not match "know".
                answer = self.listen(timeout=5)
                if answer and _wants_quit(answer, include_stop=False):
                    self.speak(f"Okay, ending Simon Says. You scored {score} so far!")
                    self.set_face("idle")
                    return
                if answer:
                    words = set(normalize_answer(answer).split())
                    if (cmd in words or "did" in words or "yes" in words
                            or "ok" in words or "okay" in words):
                        score += 1
            else:
                self.speak(f"{spoken[cmd]}.")
                # User should say "I didn't move" or similar
                answer = self.listen(timeout=5)
                if answer and _wants_quit(answer, include_stop=False):
                    self.speak(f"Okay, ending Simon Says. You scored {score} so far!")
                    self.set_face("idle")
                    return
                if answer:
                    words = set(normalize_answer(answer).split())
                    if words & {"didnt", "no", "not", "never"}:
                        score += 1

        self.speak(f"Great game! You scored {score} out of {rounds}. Well played!")
        self.set_face("idle")

    def dispatch(self, text):
        """
        Route to the correct game based on strict intent commands (Review #17).
        Normal conversation should NOT accidentally activate a game.
        """
        t = text.lower().strip()
        # Strict game commands — not arbitrary substring matching (Review #17)
        if re.search(r'\b(?:play|start|let\'s play)\s+rock\s+paper\s+scissors?\b', t) \
           or re.search(r'\b(?:play|start)\s+rock\s+paper\b', t):
            self.play_rock_paper_scissors()
        elif re.search(r'\b(?:play|start|let\'s play)\s+guess\s+(?:the\s+)?number\b', t):
            self.play_guess_the_number()
        elif re.search(r'\b(?:play|start|let\'s play)\s+trivia\b', t) \
           or re.search(r'\b(?:play|start)\s+(?:a\s+)?quiz\b', t):
            self.play_trivia()
        elif re.search(r'\b(?:play|start|let\'s play)\s+simon\s+says\b', t):
            self.play_simon_says()
        elif re.search(r'\b(?:play|start)\s+(?:a\s+)?game\b', t):
            # Generic “play a game” — ask which one
            self.speak("I know rock paper scissors, guess the number, trivia, and Simon says. Which one?")
        else:
            self.speak("I know rock paper scissors, guess the number, trivia, and Simon says. Which one?")
