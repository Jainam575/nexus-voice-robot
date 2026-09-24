"""
Nexus Robot — Conversation Memory (Review P2 #25, #27)

Auto-extracts non-sensitive facts from conversation.
Excludes: allergies, medical, passwords, financial, address, biometric.

Fixes:
- Atomic writes: memory.tmp → flush/fsync → atomic rename (Review #25).
  Power loss during write cannot corrupt the primary memory file.
- Credentials/secrets are NEVER stored — even when the user explicitly
  says "remember my password" (Review #27). Explicit memory permission
  does not override security policy.
"""
import json
import os
import re
import threading
import logging

from .config import MEMORY_FILE, MAX_REMEMBERED_FACTS

logger = logging.getLogger("Nexus.Memory")

# Sensitive categories — NEVER auto-saved
SENSITIVE_PATTERNS = [
    re.compile(r"allerg", re.I),
    re.compile(r"password|passwd|pwd|pin\s+code|otp", re.I),
    re.compile(r"medical|diagnosis|medication|prescription|blood\s+pressure|diabetes", re.I),
    re.compile(r"\baddress\b", re.I),
    re.compile(r"\bbank\b|\baccount\b|\bcard\s+number\b|\bcvv\b|\bcredit\b|\bdebit\b", re.I),
    re.compile(r"\bssn\b|\baadhaar\b|\bpan\s+card\b|\bpassport\b", re.I),
    re.compile(r"\bphone\s+number\b|\bmobile\s+number\b", re.I),
    # Secrets / credentials — never stored, even on explicit request (Review #27)
    re.compile(r"\bapi\s+key\b|\bsecret\b|\bprivate\s+key\b|\bauth(?:entication)?\s+code\b", re.I),
    re.compile(r"\bcredential\b|\blogin\s+detail\b|\bpassphrase\b|\btoken\b", re.I),
]

# Auto-extraction patterns (sensitive categories excluded from this list)
_AUTO_MEMORY_PATTERNS = [
    re.compile(r"\bi\s+(?:like|love|enjoy|prefer|am into|am fond of|am a fan of)\s+(.+)", re.I),
    re.compile(r"\bi\s+play\s+(?:the\s+)?(.+)", re.I),
    re.compile(r"\bi\s+work\s+(?:at|as|in)\s+(.+)", re.I),
    re.compile(r"\bi\s+(?:study|am studying)\s+(.+)", re.I),
    re.compile(r"\bi\s+am\s+(?:a|an)\s+(.+?)(?:\.|,|$)", re.I),
    re.compile(r"\bmy\s+(name|favorite|favourite|pet|dog|cat|car)\s+is\s+(.+)", re.I),
    re.compile(r"\bi\s+have\s+a\s+(?:dog|cat|pet)\s+(?:named|called)?\s*(.+)", re.I),
    re.compile(r"\bi\s+hate\s+(.+)", re.I),
    # NOTE: "I live in" and "I'm allergic to" are EXCLUDED (Bug #20)
]


def _is_sensitive(text):
    return any(p.search(text) for p in SENSITIVE_PATTERNS)


class Memory:
    """Thread-safe conversation memory with privacy filter."""

    def __init__(self):
        self._data = {"facts": []}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            with open(MEMORY_FILE, "r") as f:
                self._data = json.load(f)
                if "facts" not in self._data:
                    self._data["facts"] = []
        except Exception:
            self._data = {"facts": []}

    def _save(self):
        """
        Atomic save (Review #25): memory.tmp → flush/fsync → rename.
        Power loss during write cannot corrupt the primary file.
        """
        tmp_file = MEMORY_FILE + ".tmp"
        try:
            with open(tmp_file, "w") as f:
                json.dump(self._data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_file, MEMORY_FILE)  # atomic rename
        except Exception as e:
            logger.error("Could not save memory: %s", e)
            try:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            except Exception:
                pass

    def remember(self, fact):
        """
        Explicitly remember a fact (user said 'remember this').

        SECURITY POLICY (Review #27): credentials and secrets are NEVER
        stored — even if the user explicitly asks (e.g. "remember my
        password"). Explicit memory permission does not override
        security policy. Returns False and explains why.
        """
        fact = fact.strip().rstrip(".")
        if not fact:
            return False
        if _is_sensitive(fact):
            logger.info("Explicit memory BLOCKED — sensitive/secret content "
                        "is never stored (security policy)")
            return False
        with self._lock:
            if fact.lower() not in [f.lower() for f in self._data["facts"]]:
                self._data["facts"].append(fact)
                self._data["facts"] = self._data["facts"][-MAX_REMEMBERED_FACTS:]
                self._save()
        return True

    def auto_extract(self, user_text, ai_reply=""):
        """
        Auto-extract non-sensitive facts from user messages (Bug #20).
        Sensitive information is never auto-saved.
        """
        if not user_text:
            return
        for pattern in _AUTO_MEMORY_PATTERNS:
            m = pattern.search(user_text)
            if m:
                fact = m.group(0).strip().rstrip(".")
                if _is_sensitive(fact):
                    logger.info("Auto-memory blocked sensitive info: %s", fact)
                    return
                # Normalize
                fact = re.sub(r"^i\s+like\b", "User likes", fact, flags=re.I)
                fact = re.sub(r"^i\s+love\b", "User loves", fact, flags=re.I)
                fact = re.sub(r"^i\s+enjoy\b", "User enjoys", fact, flags=re.I)
                fact = re.sub(r"^i\s+play\b", "User plays", fact, flags=re.I)
                fact = re.sub(r"^i\s+work\b", "User works", fact, flags=re.I)
                fact = re.sub(r"^i\s+study\b", "User studies", fact, flags=re.I)
                fact = re.sub(r"^i\s+hate\b", "User hates", fact, flags=re.I)  # L3 grammar
                fact = re.sub(r"^i\s+am\b", "User is", fact, flags=re.I)
                fact = re.sub(r"^i\s+have\b", "User has", fact, flags=re.I)
                fact = re.sub(r"^i\b", "User", fact, flags=re.I)
                fact = re.sub(r"^my\b", "User's", fact, flags=re.I)
                if self.remember(fact):
                    logger.info("Auto-remembered: %s", fact)

    def forget_all(self):
        with self._lock:
            self._data["facts"] = []
            self._save()

    def get_facts(self):
        with self._lock:
            return list(self._data["facts"])

    def context_string(self):
        with self._lock:
            if not self._data.get("facts"):
                return ""
            facts = "; ".join(self._data["facts"])
        return f" Known facts about the user, use them naturally when relevant (don't recite the list): {facts}"


# Singleton
memory = Memory()
