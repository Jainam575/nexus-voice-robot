"""
Expanded tests for face recognition — missing directory, deletion,
camera injection, storage disable (Review #12, #13, #14).
"""
import os
import pytest
import tempfile
from unittest.mock import MagicMock, patch
from nexus import face_recognition as fr
from nexus.face_recognition import delete_all_faces, delete_face, sanitize_name


class TestDeleteAllFacesMissingDir:
    """Review #14 — deleting all faces must not fail if directory missing."""

    def test_missing_dir_returns_success(self):
        with patch.object(fr, 'KNOWN_FACES_DIR', '/nonexistent/path/xyz'):
            result = delete_all_faces()
            assert "deleted" in result.lower() or "all face data" in result.lower()

    def test_missing_dir_no_exception(self):
        with patch.object(fr, 'KNOWN_FACES_DIR', '/nonexistent/abc/def/ghi'):
            # Must not raise
            result = delete_all_faces()
            assert isinstance(result, str)


class TestDeleteFaceMissing:
    """Delete a face that doesn't exist."""

    def test_delete_nonexistent_face(self):
        with patch.object(fr, 'KNOWN_FACES_DIR', '/nonexistent/path/xyz'):
            result = delete_face("nobody")
            assert "don't have" in result.lower() or "no face data" in result.lower()


class TestCameraManagerInjection:
    """Review #12 — enroll_face uses the supplied camera manager."""

    def test_injected_manager_is_used(self):
        """If a camera_manager is passed, enroll_face must use it, not the
        module-level singleton."""
        mock_cam = MagicMock()
        mock_cam.capture.return_value = None  # no frames → enrollment fails early

        with patch.object(fr, 'FACE_STORAGE_ENABLED', True), \
             patch.object(fr, 'FACE_CASCADE_AVAILABLE', True):
            result = fr.enroll_face("testuser", camera_manager=mock_cam,
                                    tts_callback=None, num_samples=1)
            # Should have called capture on the injected manager
            assert mock_cam.capture.called
            assert mock_cam.capture.call_count >= 1


class TestStorageDisabled:
    """Review #13 — face storage can be disabled."""

    def test_enrollment_refused_when_disabled(self):
        with patch.object(fr, 'FACE_STORAGE_ENABLED', False):
            result = fr.enroll_face("someone", camera_manager=MagicMock())
            assert "disabled" in result.lower()


class TestSanitizeName:
    """Name sanitization prevents path traversal."""

    def test_basic(self):
        assert sanitize_name("John") == "john"

    def test_spaces(self):
        assert sanitize_name("John Doe") == "john_doe"

    def test_path_traversal(self):
        sanitized = sanitize_name("../../../etc/passwd")
        assert ".." not in sanitized
        assert "/" not in sanitized
        assert "\\" not in sanitized

    def test_empty(self):
        assert sanitize_name("") == "unknown"

    def test_special_chars(self):
        assert sanitize_name("test@#$") == "test"
