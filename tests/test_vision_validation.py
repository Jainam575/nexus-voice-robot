"""
Expanded tests for vision — strict tensor validation, quantized input
handling, vision TTL, atomic writes (Review #9, #10, #11, #25, #26).
"""
import json
import os
import time
import pytest
from unittest.mock import MagicMock, patch
from nexus.vision import (identify_tflite_outputs, atomic_write_json, VisionContext)
from nexus import vision as vision_module


class TestStrictTensorValidation:
    """Review #10 — strict output tensor validation."""

    def test_valid_signature(self):
        details = [
            {"name": "StatefulPartitionedCall/model/tf_op_layer_boxes", "shape": [1, 10, 4], "index": 0},
            {"name": "StatefulPartitionedCall/model/tf_op_layer_classes", "shape": [1, 10], "index": 1},
            {"name": "StatefulPartitionedCall/model/tf_op_layer_scores", "shape": [1, 10], "index": 2},
        ]
        result = identify_tflite_outputs(details)
        assert result == {"boxes": 0, "classes": 1, "scores": 2}

    def test_n_mismatch_disabled(self):
        """Different N values across tensors → detection disabled."""
        details = [
            {"name": "boxes", "shape": [1, 10, 4], "index": 0},
            {"name": "classes", "shape": [1, 10], "index": 1},
            {"name": "scores", "shape": [1, 20], "index": 2},
        ]
        assert identify_tflite_outputs(details) is None

    def test_missing_boxes_disabled(self):
        details = [
            {"name": "classes", "shape": [1, 10], "index": 0},
            {"name": "scores", "shape": [1, 10], "index": 1},
        ]
        assert identify_tflite_outputs(details) is None

    def test_wrong_boxes_shape_disabled(self):
        details = [
            {"name": "boxes", "shape": [1, 10, 5], "index": 0},
            {"name": "classes", "shape": [1, 10], "index": 1},
            {"name": "scores", "shape": [1, 10], "index": 2},
        ]
        assert identify_tflite_outputs(details) is None

    def test_no_names_valid_fallback(self):
        """Two [1,N] tensors with matching N → unambiguous fallback."""
        details = [
            {"name": "Identity", "shape": [1, 10, 4], "index": 0},
            {"name": "Identity_1", "shape": [1, 10], "index": 1},
            {"name": "Identity_2", "shape": [1, 10], "index": 2},
        ]
        result = identify_tflite_outputs(details)
        assert result is not None
        assert result["boxes"] == 0

    def test_ambiguous_fallback_disabled(self):
        """Three 2D tensors without names → ambiguous → disabled."""
        details = [
            {"name": "Identity", "shape": [1, 10, 4], "index": 0},
            {"name": "Identity_1", "shape": [1, 10], "index": 1},
            {"name": "Identity_2", "shape": [1, 10], "index": 2},
            {"name": "Identity_3", "shape": [1, 10], "index": 3},
        ]
        assert identify_tflite_outputs(details) is None

    def test_batch_not_1_disabled(self):
        details = [
            {"name": "boxes", "shape": [2, 10, 4], "index": 0},
            {"name": "classes", "shape": [1, 10], "index": 1},
            {"name": "scores", "shape": [1, 10], "index": 2},
        ]
        assert identify_tflite_outputs(details) is None


class TestQuantizedInput:
    """Review #9 — quantized input handling with scale/zero_point."""

    @pytest.fixture(autouse=True)
    def mock_cv2(self):
        """cv2 is not available in the sandbox; mock resize/resize."""
        import numpy as np
        with patch.object(vision_module, 'cv2', MagicMock()) as mock_cv2:
            mock_cv2.resize = lambda frame, size: frame[:size[1], :size[0]] if len(size) == 2 else frame
            yield

    def test_prepare_input_float32(self):
        import numpy as np
        from nexus.vision import prepare_input
        detail = {"shape": [1, 4, 4, 3], "dtype": np.float32, "index": 0}
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        result = prepare_input(detail, frame)
        assert result.dtype == np.float32
        assert result.max() <= 1.0

    def test_prepare_input_uint8(self):
        import numpy as np
        from nexus.vision import prepare_input
        detail = {"shape": [1, 4, 4, 3], "dtype": np.uint8,
                  "index": 0, "quantization": (0.003921568, 0)}
        frame = np.full((8, 8, 3), 255, dtype=np.uint8)
        result = prepare_input(detail, frame)
        assert result.dtype == np.uint8

    def test_prepare_input_int8(self):
        import numpy as np
        from nexus.vision import prepare_input
        detail = {"shape": [1, 4, 4, 3], "dtype": np.int8,
                  "index": 0, "quantization": (0.003921568, -128)}
        frame = np.full((8, 8, 3), 255, dtype=np.uint8)
        result = prepare_input(detail, frame)
        assert result.dtype == np.int8

    def test_unsupported_dtype_rejected(self):
        import numpy as np
        from nexus.vision import prepare_input
        detail = {"shape": [1, 4, 4, 3], "dtype": np.float16, "index": 0}
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        result = prepare_input(detail, frame)
        assert result is None


class TestVisionTTL:
    """Review #11 — stale vision data is never presented as current."""

    def test_fresh_context(self):
        ctx = VisionContext()
        ctx.set("a person and a chair")
        assert ctx.get_fresh() == "a person and a chair"

    def test_expired_context(self):
        ctx = VisionContext()
        ctx.set("old description")
        ctx.timestamp = time.time() - 999  # simulate age
        assert ctx.get_fresh() is None

    def test_empty_context(self):
        ctx = VisionContext()
        assert ctx.get_fresh() is None


class TestAtomicWrites:
    """Review #25, #26 — atomic JSON writes."""

    def test_atomic_write_json(self, tmp_path):
        target = tmp_path / "data.json"
        atomic_write_json(str(target), {"key": "value"})
        assert json.loads(target.read_text()) == {"key": "value"}

    def test_atomic_write_replaces_existing(self, tmp_path):
        target = tmp_path / "data.json"
        target.write_text(json.dumps({"old": True}))
        atomic_write_json(str(target), {"new": True})
        assert json.loads(target.read_text()) == {"new": True}

    def test_atomic_write_no_tmp_left_behind(self, tmp_path):
        target = tmp_path / "data.json"
        atomic_write_json(str(target), {"a": 1})
        tmp = tmp_path / "data.json.tmp"
        assert not tmp.exists()

    def test_atomic_write_failure_keeps_original(self, tmp_path):
        """If the atomic write fails, the original file is intact."""
        target = tmp_path / "data.json"
        target.write_text(json.dumps({"original": True}))
        # Simulate a failure by making json.dump fail with a non-serializable object
        try:
            atomic_write_json(str(target), {"bad": object()})
        except Exception:
            pass
        # Original should still be readable (atomic rename never happened)
        assert json.loads(target.read_text()) == {"original": True}
