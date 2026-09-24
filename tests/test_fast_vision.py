"""
Vision-performance pass tests — one class per required area (spec req. 10):

- VisionWorker startup/shutdown
- fresh cached detections
- stale cache behavior
- fast local vision route
- deep cloud-vision route
- local/cloud concurrent execution
- cloud vision failure fallback
- background memory saving
- thread-safe shared vision state
- latency instrumentation
"""
import threading
import time
import types

import numpy as np
import pytest

from nexus import vision as vision_mod
from nexus.vision import VisionWorker, save_vision_memory_async
from nexus import main as main_mod
from nexus.latency import LatencyRecorder, measure, latency
from nexus.command_parser import parse_movement_command  # unchanged-behavior guard

FRAME = np.zeros((480, 640, 3), dtype=np.uint8)
DETS = [{"label": "person", "confidence": 0.9, "box": [0.1, 0.1, 0.5, 0.5], "class_id": 0},
        {"label": "chair", "confidence": 0.8, "box": [0.2, 0.2, 0.6, 0.6], "class_id": 56}]


class FakeCamera:
    available = True
    def __init__(self, frame=FRAME):
        self.frame = frame
        self.captures = 0
    def capture(self):
        self.captures += 1
        return self.frame


class FakeVision:
    available = True
    def __init__(self, detections=DETS, delay=0.0):
        self._detections = detections
        self.delay = delay
        self.detect_calls = 0
        self.describe_calls = 0
    def detect_objects(self, frame, threshold=0.5):
        self.detect_calls += 1
        if self.delay:
            time.sleep(self.delay)
        return list(self._detections)
    def describe_scene(self, frame):
        self.describe_calls += 1
        if self.delay:
            time.sleep(self.delay)
        return "A person is sitting on a chair."


# ==================================================== startup / shutdown
class TestVisionWorkerLifecycle:
    def test_start_and_stop(self):
        worker = VisionWorker(camera=FakeCamera(), vision=FakeVision())
        assert worker.start() is True
        assert worker.is_running
        deadline = time.time() + 3
        while worker.get_snapshot() is None and time.time() < deadline:
            time.sleep(0.05)
        assert worker.get_snapshot() is not None, "worker should produce a snapshot"
        worker.stop()
        assert not worker.is_running
        assert worker._thread is None or not worker._thread.is_alive()

    def test_stop_is_idempotent(self):
        worker = VisionWorker(camera=FakeCamera(), vision=FakeVision())
        worker.start()
        worker.stop()
        worker.stop()  # must not raise

    def test_start_refused_when_vision_unavailable(self):
        worker = VisionWorker(camera=FakeCamera(),
                              vision=types.SimpleNamespace(available=False))
        assert worker.start() is False
        assert worker.is_running is False

    def test_worker_survives_camera_errors(self):
        class BoomCam:
            available = True
            def capture(self):
                raise RuntimeError("camera exploded")
        worker = VisionWorker(camera=BoomCam(), vision=FakeVision())
        worker.start()
        time.sleep(0.5)
        assert worker.is_running, "worker must survive capture errors"
        worker.stop()


# ==================================================== fresh cache
class TestFreshCache:
    def test_fresh_snapshot_returns_state(self):
        worker = VisionWorker(camera=FakeCamera(), vision=FakeVision())
        worker.start()
        deadline = time.time() + 3
        snap = None
        while snap is None and time.time() < deadline:
            snap = worker.get_snapshot(max_age=5.0)
            time.sleep(0.05)
        worker.stop()
        assert snap is not None
        assert snap["frame"] is not None
        assert [d["label"] for d in snap["detections"]] == ["person", "chair"]
        assert snap["timestamp"] > 0
        assert "description" in snap  # optional field present (req. 2)

    def test_description_round_trip(self):
        worker = VisionWorker(camera=FakeCamera(), vision=FakeVision())
        worker.set_description("a desk")
        assert worker.get_description() == "a desk"


# ==================================================== stale cache
class TestStaleCache:
    def test_stale_snapshot_returns_none(self):
        worker = VisionWorker(camera=FakeCamera(), vision=FakeVision())
        worker.start()
        deadline = time.time() + 3
        while worker.get_snapshot(max_age=5.0) is None and time.time() < deadline:
            time.sleep(0.05)
        worker.stop()
        # now the cache ages out
        assert worker.get_snapshot(max_age=0.05) is None or True
        time.sleep(0.1)
        assert worker.get_snapshot(max_age=0.05) is None, "stale data must be None"

    def test_missing_cache_returns_none(self):
        worker = VisionWorker(camera=FakeCamera(), vision=FakeVision())
        assert worker.get_snapshot() is None


# ==================================================== routes through main handler
def _patched_main(monkeypatch, worker, cam, vis, spoken):
    """Patch main-module collaborators for _handle_vision_query tests."""
    monkeypatch.setattr(main_mod, "vision_worker", worker)
    monkeypatch.setattr(main_mod, "camera_manager", cam)
    monkeypatch.setattr(main_mod, "vision_system", vis)
    monkeypatch.setattr(main_mod, "speak", lambda t, **kw: spoken.append(t))
    saved = vision_mod.save_vision_memory
    saved_async = main_mod.save_vision_memory_async
    saved_ctx = (vision_mod.vision_context.description,
                 vision_mod.vision_context.timestamp)
    monkeypatch.setattr(main_mod, "save_vision_memory_async",
                        lambda frame, desc: spoken.append(("MEM", desc)))
    return saved, saved_async, saved_ctx


class TestFastLocalRoute:
    def test_simple_question_answers_from_cache_without_cloud(self, monkeypatch):
        cam = FakeCamera()
        vis = FakeVision()
        worker = VisionWorker(camera=cam, vision=vis)
        worker.start()
        deadline = time.time() + 3
        while worker.get_snapshot(max_age=5.0) is None and time.time() < deadline:
            time.sleep(0.05)
        worker.stop()

        spoken = []
        _patched_main(monkeypatch, worker, cam, vis, spoken)
        latency.reset()
        main_mod._handle_vision_query("what do you see?")

        # Fast path: local answer, NO cloud call, NO "Let me look around"
        assert any(isinstance(s, str) and "I can see person" in s for s in spoken)
        assert not any(isinstance(s, str) and "Let me look around" in s for s in spoken)
        assert vis.describe_calls == 0, "fast path must NOT call cloud vision"
        assert latency.last("e2e_vision_fast") is not None

    def test_classification(self):
        assert main_mod.is_detailed_vision_query("Describe this scene in detail.") is True
        assert main_mod.is_detailed_vision_query("what is this person doing") is True
        assert main_mod.is_detailed_vision_query("explain what is happening") is True
        assert main_mod.is_detailed_vision_query("what do you see") is False
        assert main_mod.is_detailed_vision_query("what is in front of you") is False
        assert main_mod.is_detailed_vision_query("what objects are there") is False

    def test_movement_parser_unchanged_by_vision_work(self):
        # guard: vision changes must not weaken the founder-demo parser fix
        assert parse_movement_command("You are right.")[0] is False
        assert parse_movement_command("turn right")[1] == "right"


class TestDeepCloudRoute:
    def test_detailed_question_uses_cloud(self, monkeypatch):
        cam = FakeCamera()
        vis = FakeVision()
        worker = VisionWorker(camera=cam, vision=vis)
        worker.start()
        deadline = time.time() + 3
        while worker.get_snapshot(max_age=5.0) is None and time.time() < deadline:
            time.sleep(0.05)
        worker.stop()

        spoken = []
        _patched_main(monkeypatch, worker, cam, vis, spoken)
        latency.reset()
        main_mod._handle_vision_query("describe this scene in detail.")

        assert vis.describe_calls == 1, "deep route must call cloud vision"
        assert any(isinstance(s, str) and "A person is sitting" in s for s in spoken)
        # 2026-09 spec: the VLM answer is spoken as-is; local COCO labels are
        # only used as the cloud-FAILURE fallback (they mislabel close faces).
        assert not any(isinstance(s, str) and "I can specifically detect" in s for s in spoken)
        assert worker.get_description() == "A person is sitting on a chair."
        assert latency.last("e2e_vision_cloud") is not None

    def test_simple_question_goes_cloud_when_api_key_set(self, monkeypatch):
        """Cloud-first (user preference 2026-09): with an API key present,
        'what do you see?' must use the Sarvam vision model, not the offline
        COCO detector that mislabels close-up faces as 'handbag'."""
        cam = FakeCamera()
        vis = FakeVision()
        worker = VisionWorker(camera=cam, vision=vis)
        worker.start()
        deadline = time.time() + 3
        while worker.get_snapshot(max_age=5.0) is None and time.time() < deadline:
            time.sleep(0.05)
        worker.stop()

        spoken = []
        _patched_main(monkeypatch, worker, cam, vis, spoken)
        monkeypatch.setattr(main_mod, "SARVAM_KEY", "test-key")
        main_mod._handle_vision_query("what do you see?")

        assert vis.describe_calls == 1, "API key present -> cloud-first"
        assert any(isinstance(s, str) and "A person is sitting" in s for s in spoken)

    def test_simple_question_stays_fast_when_mode_fast(self, monkeypatch):
        """NEXUS_VISION_MODE=fast restores the offline route even with a key."""
        cam = FakeCamera()
        vis = FakeVision()
        worker = VisionWorker(camera=cam, vision=vis)
        worker.start()
        deadline = time.time() + 3
        while worker.get_snapshot(max_age=5.0) is None and time.time() < deadline:
            time.sleep(0.05)
        worker.stop()

        spoken = []
        _patched_main(monkeypatch, worker, cam, vis, spoken)
        monkeypatch.setattr(main_mod, "SARVAM_KEY", "test-key")
        monkeypatch.setenv("NEXUS_VISION_MODE", "fast")
        try:
            main_mod._handle_vision_query("what do you see?")
        finally:
            monkeypatch.delenv("NEXUS_VISION_MODE", raising=False)

        assert vis.describe_calls == 0, "fast mode must stay offline"
        assert any(isinstance(s, str) and "I can see" in s for s in spoken)

    def test_cloud_failure_falls_back_to_local(self, monkeypatch):
        class FailingCloud(FakeVision):
            def describe_scene(self, frame):
                self.describe_calls += 1
                raise RuntimeError("cloud down")

        cam = FakeCamera()
        vis = FailingCloud()
        worker = VisionWorker(camera=cam, vision=vis)
        worker.start()
        deadline = time.time() + 3
        while worker.get_snapshot(max_age=5.0) is None and time.time() < deadline:
            time.sleep(0.05)
        worker.stop()

        spoken = []
        _patched_main(monkeypatch, worker, cam, vis, spoken)
        main_mod._handle_vision_query("describe this scene in detail.")

        assert vis.describe_calls == 1
        assert any(isinstance(s, str) and "I had trouble with the cloud" in s for s in spoken), spoken
        assert any(isinstance(s, str) and "person" in s for s in spoken)

    def test_no_cache_and_no_detections_still_cloud_fallback(self, monkeypatch):
        cam = FakeCamera()
        vis = FakeVision(detections=[])
        worker = VisionWorker(camera=cam, vision=vis)   # never started: no cache

        spoken = []
        _patched_main(monkeypatch, worker, cam, vis, spoken)
        main_mod._handle_vision_query("what do you see?")
        # local had nothing useful → cloud allowed (spec req. 3)
        assert vis.describe_calls == 1


class TestConcurrentExecution:
    def test_local_and_cloud_run_concurrently(self, monkeypatch):
        """A detailed query with no cache needs BOTH local detection and
        cloud vision; two 0.4 s jobs must finish in < 0.9 s if concurrent."""
        cam = FakeCamera()
        vis = FakeVision(delay=0.4)
        worker = VisionWorker(camera=cam, vision=vis)  # never started: no cache

        spoken = []
        _patched_main(monkeypatch, worker, cam, vis, spoken)
        t0 = time.perf_counter()
        main_mod._handle_vision_query("describe this scene in detail.")
        elapsed = time.perf_counter() - t0

        assert vis.describe_calls == 1
        assert vis.detect_calls == 1
        assert elapsed < 0.9, f"local+cloud appear sequential ({elapsed:.2f}s)"


# ==================================================== background memory saving
class TestBackgroundMemorySaving:
    def test_async_save_does_not_block_and_runs_offthread(self, monkeypatch):
        saved_calls = []

        def slow_save(frame, description):
            time.sleep(0.3)          # simulate a slow SD card
            saved_calls.append((threading.current_thread().ident, description))

        monkeypatch.setattr(vision_mod, "save_vision_memory", slow_save)
        t0 = time.perf_counter()
        save_vision_memory_async(FRAME, "a test description")
        enqueue_time = time.perf_counter() - t0
        assert enqueue_time < 0.05, "enqueue must never block on the disk write"

        deadline = time.time() + 5
        while not saved_calls and time.time() < deadline:
            time.sleep(0.05)
        assert saved_calls, "background save must eventually run"
        thread_id, desc = saved_calls[0]
        assert thread_id != threading.current_thread().ident, \
            "save must happen on a background thread"
        assert desc == "a test description"

    def test_bounded_queue_never_blocks(self, monkeypatch):
        monkeypatch.setattr(vision_mod, "save_vision_memory",
                            lambda f, d: time.sleep(0.2))
        t0 = time.perf_counter()
        for _ in range(60):          # far more than the queue size (20)
            save_vision_memory_async(FRAME, "x")
        assert time.perf_counter() - t0 < 1.0, "a full queue must drop, not block"


# ==================================================== thread safety
class TestThreadSafeVisionState:
    def test_concurrent_readers_and_writer(self):
        worker = VisionWorker(camera=FakeCamera(), vision=FakeVision())
        worker.start()
        errors = []

        def reader():
            try:
                for _ in range(200):
                    snap = worker.get_snapshot(max_age=60)
                    if snap is not None:
                        assert "frame" in snap and "detections" in snap
                        assert isinstance(snap["detections"], list)
            except Exception as e:      # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        deadline = time.time() + 2
        while any(t.is_alive() for t in threads) and time.time() < deadline:
            time.sleep(0.05)
        worker.stop()
        for t in threads:
            t.join(timeout=2)
        assert not errors, errors


# ==================================================== latency instrumentation
class TestLatencyInstrumentation:
    def test_recorder_record_and_summary(self):
        rec = LatencyRecorder()
        rec.record("stt", 0.5)
        rec.record("stt", 0.7)
        s = rec.summary()["stt"]
        assert s["count"] == 2
        assert s["last_s"] == 0.7
        assert abs(s["avg_s"] - 0.6) < 1e-9
        assert s["max_s"] == 0.7

    def test_measure_context_manager(self):
        rec = LatencyRecorder()
        import nexus.latency as lat_mod
        saved = lat_mod.latency
        lat_mod.latency = rec
        try:
            with measure("demo_metric"):
                time.sleep(0.05)
        finally:
            lat_mod.latency = saved
        last = rec.last("demo_metric")
        assert last is not None and last >= 0.05

    def test_bounded_samples(self):
        rec = LatencyRecorder(max_samples=5)
        for i in range(50):
            rec.record("x", i)
        assert rec.summary()["x"]["count"] == 5

    def test_detect_objects_records_tflite_metrics(self, monkeypatch):
        import numpy as np
        from nexus.vision import VisionSystem

        class FakeInterpreter:
            def set_tensor(self, idx, data): pass
            def invoke(self): pass
            def get_tensor(self, idx):
                return {0: np.array([[[10, 20, 100, 150]]], dtype=np.uint8),
                        1: np.array([[0]], dtype=np.int64),
                        2: np.array([[155]], dtype=np.uint8)}[idx]

        vs = VisionSystem()
        vs.available = True
        vs.interpreter = FakeInterpreter()
        vs.labels = ["person"]
        vs.input_details = [{"index": 0, "dtype": np.uint8, "shape": [1, 300, 300, 3]}]
        vs.output_details = [
            {"index": 0, "name": "", "shape": [1, 1, 4], "dtype": np.uint8, "quantization": (0.005, 5)},
            {"index": 1, "name": "", "shape": [1, 1], "dtype": np.int64, "quantization": (0.0, 0)},
            {"index": 2, "name": "", "shape": [1, 1], "dtype": np.uint8, "quantization": (0.005, 5)},
        ]
        vs.output_map = {"boxes": 0, "classes": 1, "scores": 2}
        monkeypatch.setattr(vision_mod, "prepare_input",
                            lambda d, f: np.zeros((1, 4), dtype=np.uint8))
        latency.reset()
        dets = vs.detect_objects(np.zeros((480, 640, 3), dtype=np.uint8))
        assert len(dets) == 1
        assert latency.last("tflite_preprocess") is not None
        assert latency.last("tflite_inference") is not None

    def test_vision_routes_record_e2e(self, monkeypatch):
        cam = FakeCamera()
        vis = FakeVision()
        worker = VisionWorker(camera=cam, vision=vis)
        worker.start()
        deadline = time.time() + 3
        while worker.get_snapshot(max_age=5.0) is None and time.time() < deadline:
            time.sleep(0.05)
        worker.stop()
        spoken = []
        _patched_main(monkeypatch, worker, cam, vis, spoken)
        latency.reset()
        main_mod._handle_vision_query("what do you see?")
        assert latency.last("e2e_vision_fast") is not None
        main_mod._handle_vision_query("describe this scene in detail.")
        assert latency.last("e2e_vision_cloud") is not None
