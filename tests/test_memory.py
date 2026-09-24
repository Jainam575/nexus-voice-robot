"""Tests for memory privacy filtering (Bug #20)."""
import pytest
import os
import json
import tempfile

# Use a temp memory file for tests
from nexus import memory as memory_module
from nexus.memory import Memory, _is_sensitive


@pytest.fixture
def test_memory(tmp_path):
    """Create a Memory instance with a temp file."""
    mem_file = tmp_path / "test_memory.json"
    old_file = memory_module.MEMORY_FILE
    memory_module.MEMORY_FILE = str(mem_file)
    m = Memory()
    yield m
    memory_module.MEMORY_FILE = old_file


class TestPrivacyFilter:
    def test_allergy_blocked(self):
        assert _is_sensitive("I'm allergic to peanuts") is True

    def test_password_blocked(self):
        assert _is_sensitive("my password is hunter2") is True

    def test_medical_blocked(self):
        assert _is_sensitive("I have a medical diagnosis") is True

    def test_address_blocked(self):
        assert _is_sensitive("my address is 123 main street") is True

    def test_bank_blocked(self):
        assert _is_sensitive("my bank account is 12345") is True

    def test_aadhaar_blocked(self):
        assert _is_sensitive("my aadhaar number is 1234") is True

    def test_non_sensitive_allowed(self):
        assert _is_sensitive("I like chess") is False
        assert _is_sensitive("I play cricket") is False
        assert _is_sensitive("my favorite color is blue") is False


class TestAutoExtract:
    def test_likes_chess(self, test_memory):
        test_memory.auto_extract("I like chess")
        facts = test_memory.get_facts()
        assert any("chess" in f.lower() for f in facts)

    def test_plays_cricket(self, test_memory):
        test_memory.auto_extract("I play cricket")
        facts = test_memory.get_facts()
        assert any("cricket" in f.lower() for f in facts)

    def test_allergy_not_saved(self, test_memory):
        """Allergies must NEVER be auto-saved (Bug #20)."""
        test_memory.auto_extract("I'm allergic to peanuts")
        facts = test_memory.get_facts()
        assert not any("allerg" in f.lower() for f in facts)

    def test_live_in_not_auto_saved(self, test_memory):
        """Address/location must NEVER be auto-saved."""
        test_memory.auto_extract("I live in Mumbai")
        facts = test_memory.get_facts()
        assert not any("mumbai" in f.lower() for f in facts)

    def test_password_not_saved(self, test_memory):
        test_memory.auto_extract("my password is secret123")
        facts = test_memory.get_facts()
        assert not any("password" in f.lower() for f in facts)

    def test_medical_not_saved(self, test_memory):
        test_memory.auto_extract("I have diabetes")
        facts = test_memory.get_facts()
        assert not any("diabetes" in f.lower() for f in facts)


class TestExplicitMemory:
    def test_explicit_remember(self, test_memory):
        """Explicit 'remember this' can save anything the user chooses."""
        test_memory.remember("my favorite color is blue")
        facts = test_memory.get_facts()
        assert any("favorite color" in f.lower() for f in facts)

    def test_forget_all(self, test_memory):
        test_memory.remember("I like pizza")
        test_memory.forget_all()
        assert test_memory.get_facts() == []

    def test_no_duplicates(self, test_memory):
        test_memory.remember("I like chess")
        test_memory.remember("I like chess")
        test_memory.remember("i like chess")  # case-insensitive
        assert len(test_memory.get_facts()) == 1
