"""
Round 2 regression tests — one test per bug fixed after the independent review.

C1  dance/demo use blocking moves (moves are no longer dropped)
C2  spoken safety-stop is heard during blocking activities
C3  face recognizer model is loaded from disk / reset on delete
C4  STOP no longer clears FAULT
C5  watchdog does not fire during long simulated moves
C6  navigation no longer bails out at step 0 (is_stopped() at rest)
H1  guess-the-number terminates; quit words exit every game
H3  TTS preserves Unicode and picks an Indic voice
H4  stop_playback can interrupt a blocked finish_playback
H5  one transient ultrasonic miss does not deny movement
M1  shutdown handlers run in registration order
M2  "show me the news" is no longer a vision query
M3  quantized boxes are dequantized
L2  multi-word mood phrases ("thank you") count
L3  "I hate X" is stored with correct grammar
"""
import os
import sys
import time
import threading
import types

import pytest

from nexus.safety import SafetyController, STATE_FAULT, STATE_STOPPED
from nexus import motor as motor_mod
from nexus.motor import MotorController
from nexus.collision import CollisionSensor
from nexus.audio import AudioManager
from nexus import tts as tts_mod
from nexus import main as main_mod
from nexus import navigation as nav_mod
from nexus import games as games_mod
from nexus import mood as mood_mod
from nexus import memory as memory_mod
from nexus import vision as vision_mod
from nexus import shutdown as shutdown_mod
from nexus import face_recognition as face_rec_mod
from nexus.safety_listener import SafetyListener
import nexus.safety_listener as sl_mod
import numpy as np


def reset_motor_singleton():
    """Order-independent tests: other test files exercise the shared motor
    singleton and may leave it in FAULT/MOVING. Reset it to a clean STOPPED
    state before tests that depend on it."""
    m = main_mod.motor
    if not m._running:
        m.start()
    m.safety.request_stop(reason="test_reset")
    m.safety.clear_fault()
    sl_mod.safety_listener._stop_event.clear()
    return m


# ---------------------------------------------------------------- C4
class TestFaultStickiness:
    def test_stop_does_not_clear_fault(self):
        sc = SafetyController()
        sc.request_movement()
        sc.emergency_stop(reason="watchdog")
        assert sc.get_state() == STATE_FAULT
        sc.request_stop(reason="user said stop")
        assert sc.get_state() == STATE_FAULT, "STOP must not clear FAULT (C4)"
        assert sc.request_movement() is None, "movement must stay denied in FAULT"

    def test_clear_fault_still_recovers(self):
        sc = SafetyController()
        sc.emergency_stop(reason="watchdog")
        sc.clear_fault()
        assert sc.get_state() == STATE_STOPPED
        assert sc.request_movement() is not None

    def test_stop_from_moving_goes_to_stopped(self):
        sc = SafetyController()
        sc.request_movement()
        sc.request_stop()
        assert sc.get_state() == STATE_STOPPED


# ---------------------------------------------------------------- C5
class TestSimWatchdog:
    def test_long_simulated_move_is_not_interrupted(self):
        """A simulated move longer than the watchdog timeout must complete (C5)."""
        mc = MotorController()
        mc._watchdog._timeout = 0.5
        mc.start()
        try:
            result = mc.execute_move("forward", duration=1.2, source="sim",
                                     wait=True, timeout=5)
            assert result["status"] == "completed", result
            assert mc.safety.get_state() != STATE_FAULT
        finally:
            mc.stop()
            mc.join()

    def test_real_interrupt_still_works(self):
        """A genuine STOP still interrupts a long simulated move."""
        mc = MotorController()
        mc.start()
        try:
            def stopper():
                time.sleep(0.3)
                mc.stop(source="test_stop")
            threading.Thread(target=stopper, daemon=True).start()
            result = mc.execute_move("forward", duration=3.0, source="sim",
                                     wait=True, timeout=8)
            assert result["status"] == "interrupted"
        finally:
            mc.join()


# ---------------------------------------------------------------- C1 / C6
class TestBlockingSequences:
    def test_consecutive_blocking_moves_all_complete(self):
        """The dance/demo pattern: many sequential moves, none dropped (C1)."""
        mc = MotorController()
        mc.start()
        try:
            results = []
            for d in ("forward", "left", "right", "back", "spin"):
                r = mc.execute_move(d, duration=0.2, source="dance_test",
                                    wait=True, timeout=5)
                results.append(r["status"])
            assert results == ["completed"] * 5, results
        finally:
            mc.stop()
            mc.join()

    def test_dance_executes_full_routine(self):
        """dance() must submit every move of the routine (C1) with wait=True."""
        routine = [("forward", 0.15, ""), ("left", 0.15, ""), ("spin", 0.15, "")]
        calls = []
        real_execute = main_mod.motor.execute_move

        def spy_execute(direction, duration=1.0, speed=80, source="", wait=False,
                        timeout=10.0):
            calls.append((direction, wait))
            return real_execute(direction, duration=duration, speed=speed,
                                source=source, wait=wait, timeout=timeout)

        monkey_patches = [
            (main_mod, "speak", lambda t, **kw: None),
            (main_mod.motor, "execute_move", spy_execute),
            (main_mod, "random", types.SimpleNamespace(choice=lambda r: routine)),
        ]
        backups = [(m, k, getattr(m, k)) for m, k, _ in monkey_patches]
        saved_start, saved_finish = sl_mod.safety_listener.start, sl_mod.safety_listener.finish
        try:
            reset_motor_singleton()
            for m, k, v in monkey_patches:
                setattr(m, k, v)
            sl_mod.safety_listener.start = lambda: None
            sl_mod.safety_listener.finish = lambda timeout=4.0: None
            main_mod.dance()
            main_mod.motor.stop()
            main_mod.motor.join()
        finally:
            for m, k, v in backups:
                setattr(m, k, v)
            sl_mod.safety_listener.start, sl_mod.safety_listener.finish = saved_start, saved_finish

        assert [c[0] for c in calls] == [m[0] for m in routine], calls
        assert all(c[1] for c in calls), "every dance move must use wait=True"

    def test_navigation_does_not_bail_at_step_0(self):
        """navigate_to_object must move/inspect, not return 'Navigation stopped.'
        before doing anything (C6)."""
        class FakeCam:
            available = True
            def capture(self):
                return np.zeros((480, 640, 3), dtype=np.uint8)

        class FakeVision:
            available = True
            def detect_objects(self, frame, threshold=0.5):
                # Wide box -> immediately "close" -> navigation should report reaching it
                return [{"label": "chair", "confidence": 0.9,
                         "box": [0.1, 0.1, 0.9, 0.9], "class_id": 56}]

        saved = (nav_mod.camera_manager, nav_mod.vision_system, nav_mod.speak)
        saved_sl = (sl_mod.safety_listener.start, sl_mod.safety_listener.finish)
        try:
            reset_motor_singleton()
            nav_mod.camera_manager = FakeCam()
            nav_mod.vision_system = FakeVision()
            nav_mod.speak = lambda t: None
            sl_mod.safety_listener.start = lambda: None
            sl_mod.safety_listener.finish = lambda timeout=4.0: None
            result = nav_mod.navigate_to_object("chair")
        finally:
            nav_mod.camera_manager, nav_mod.vision_system, nav_mod.speak = saved
            sl_mod.safety_listener.start, sl_mod.safety_listener.finish = saved_sl
            main_mod.motor.stop()
            main_mod.motor.join()

        assert result != "Navigation stopped.", result
        assert "chair" in result.lower()


# ---------------------------------------------------------------- C2
class TestSafetyListener:
    def test_listener_hears_stop_and_stops_motor(self):
        import nexus.safety_listener as sl_mod

        heard = {"motor_stops": 0}
        fake_motor = types.SimpleNamespace(stop=lambda source="": heard.__setitem__("motor_stops", heard["motor_stops"] + 1))
        fake_audio = types.SimpleNamespace(
            is_speaking=lambda: False,
            record_to_wav=lambda timeout_seconds=2: (True, None),
        )
        fake_stt = types.SimpleNamespace(transcribe=lambda: ("stop", None))

        saved = (sl_mod.audio_manager, sl_mod.motor, sl_mod.transcribe)
        listener = SafetyListener()
        try:
            sl_mod.audio_manager = fake_audio
            sl_mod.motor = fake_motor
            sl_mod.transcribe = fake_stt.transcribe
            listener.start()
            deadline = time.time() + 5
            while not listener.stop_requested and time.time() < deadline:
                time.sleep(0.05)
            listener.finish()
        finally:
            sl_mod.audio_manager, sl_mod.motor, sl_mod.transcribe = saved

        assert listener.stop_requested, "listener should flag stop_requested"
        assert heard["motor_stops"] >= 1, "listener must call motor.stop()"

    def test_listener_finish_is_idempotent_and_quick(self):
        import nexus.safety_listener as sl_mod
        fake_audio = types.SimpleNamespace(
            is_speaking=lambda: False,
            record_to_wav=lambda timeout_seconds=2: (False, "no-audio"),
        )
        saved = sl_mod.audio_manager
        listener = SafetyListener()
        try:
            sl_mod.audio_manager = fake_audio
            t0 = time.time()
            listener.start()
            listener.finish()
            listener.finish()  # idempotent
            assert time.time() - t0 < 6
        finally:
            sl_mod.audio_manager = saved


# ---------------------------------------------------------------- C3
class TestFaceModelPersistence:
    def _fake_recognizer(self, tmp_path):
        """A stand-in LBPH recognizer that records read/train/save calls."""
        model_file = str(tmp_path / "lbph_trainer.yml")
        calls = {"read": 0, "save": 0, "trained": 0}

        class FakeRec:
            def read(self, path):
                calls["read"] += 1
                assert path == model_file
            def save(self, path):
                calls["save"] += 1
            def train(self, samples, labels):
                calls["trained"] += 1
            def predict(self, img):
                return (0, 10.0)
        return FakeRec(), model_file, calls

    def test_model_is_loaded_from_disk(self, tmp_path, monkeypatch):
        fake, model_file, calls = self._fake_recognizer(tmp_path)
        open(model_file, "w").write("fake-model")
        monkeypatch.setattr(face_rec_mod, "_face_recognizer", fake)
        monkeypatch.setattr(face_rec_mod, "FACE_RECOGNIZER_FILE", model_file)
        face_rec_mod._load_recognizer_from_disk()
        assert calls["read"] == 1, "saved model must be loaded at startup (C3)"

    def test_training_with_no_samples_removes_stale_model(self, tmp_path, monkeypatch):
        faces_dir = tmp_path / "known_faces"
        faces_dir.mkdir()
        model_file = str(faces_dir / "lbph_trainer.yml")
        label_map = str(faces_dir / "label_map.json")
        open(model_file, "w").write("stale")
        open(label_map, "w").write("{}")

        fake, _, calls = self._fake_recognizer(tmp_path)
        monkeypatch.setattr(face_rec_mod, "_face_recognizer", fake)
        monkeypatch.setattr(face_rec_mod, "FACE_RECOGNIZER_FILE", model_file)
        monkeypatch.setattr(face_rec_mod, "KNOWN_FACES_DIR", str(faces_dir))
        monkeypatch.setattr(face_rec_mod, "cv2",
                            types.SimpleNamespace(face=types.SimpleNamespace(
                                LBPHFaceRecognizer_create=lambda: fake,
                                imread=lambda *a, **k: None),
                                IMREAD_GRAYSCALE=0))
        face_rec_mod._train_recognizer()
        assert not os.path.exists(model_file), "stale trainer must be removed (C3)"
        assert not os.path.exists(label_map), "stale label map must be removed (C3)"


# ---------------------------------------------------------------- H1
class TestGuessTheNumberTerminates:
    def test_silence_consumes_attempts_and_terminates(self):
        calls = {"n": 0}

        def listen(timeout=10):
            calls["n"] += 1
            return None  # always silent

        spoken = []
        engine = games_mod.GameEngine(speak_callback=spoken.append,
                                      listen_callback=listen)
        t0 = time.time()
        engine.play_guess_the_number()  # must RETURN (old version looped forever)
        assert time.time() - t0 < 10
        assert calls["n"] == 7, "7 attempts -> 7 listens, no refunds (H1)"
        assert any("out of guesses" in s.lower() for s in spoken)

    def test_quit_word_exits_game(self):
        def listen(timeout=10):
            return "stop playing this game"
        engine = games_mod.GameEngine(speak_callback=lambda t: None,
                                      listen_callback=listen)
        engine.play_guess_the_number()  # must return immediately
        # no assertion needed beyond returning — the old version never returned

    def test_rps_quit_word(self):
        engine = games_mod.GameEngine(speak_callback=lambda t: None,
                                      listen_callback=lambda timeout=5: "quit")
        engine.play_rock_paper_scissors()

    def test_trivia_quit_word(self):
        engine = games_mod.GameEngine(speak_callback=lambda t: None,
                                      listen_callback=lambda timeout=10: "cancel")
        engine.play_trivia()

    def test_simon_no_longer_matches_know(self):
        """'know' must not score as a 'no' response (L6)."""
        words_answer = "I know the answer"
        words = set(games_mod.normalize_answer(words_answer).split())
        assert not (words & {"didnt", "no", "not", "never"})


# ---------------------------------------------------------------- H3
class TestUnicodeTTS:
    def test_clean_text_preserves_devanagari(self):
        assert tts_mod.clean_text("नमस्ते दोस्त") == "नमस्ते दोस्त"

    def test_clean_text_preserves_accents(self):
        assert tts_mod.clean_text("café") == "café"

    def test_clean_text_strips_markup_symbols(self):
        assert tts_mod.clean_text("hello *world* #robot!") == "hello world robot"

    def test_language_detection(self):
        assert tts_mod.detect_language_code("नमस्ते") == "hi-IN"
        assert tts_mod.detect_language_code("কেমন আছো") == "bn-IN"
        assert tts_mod.detect_language_code("வணக்கம்") == "ta-IN"
        assert tts_mod.detect_language_code("hello there") == "en-IN"


# ---------------------------------------------------------------- H4
class TestPlaybackStop:
    def test_stop_playback_interrupts_blocked_wait(self):
        """finish_playback must not hold the lock while waiting (H4)."""
        am = AudioManager()
        terminated = threading.Event()

        class FakeProc:
            def __init__(self):
                self.stdin = types.SimpleNamespace(close=lambda: None)
            def wait(self, timeout=None):
                # Simulate a hung aplay: block until terminated
                if not terminated.wait(timeout=timeout or 10):
                    import subprocess
                    raise subprocess.TimeoutExpired(cmd="aplay", timeout=timeout)
            def terminate(self):
                terminated.set()
            def kill(self):
                terminated.set()

        proc = FakeProc()
        am._playback_process = proc

        def finisher():
            am.finish_playback(proc, block=True, timeout=10)
        t = threading.Thread(target=finisher, daemon=True)
        t.start()
        time.sleep(0.2)
        t0 = time.time()
        am.stop_playback()  # must not block on the lock while finisher waits
        assert time.time() - t0 < 2, "stop_playback blocked behind finish_playback"
        t.join(timeout=5)
        assert not t.is_alive()
        assert am._playback_process is None


# ---------------------------------------------------------------- H5
class TestCollisionTransientFailures:
    def _sensor_with(self, readings):
        sensor = CollisionSensor(sensor_type="ultrasonic", enabled=True)
        sensor._reading_ttl = 0  # deterministic: always take a fresh reading
        it = iter(readings)

        def read():
            try:
                return next(it)
            except StopIteration:
                return None
        sensor._distance_func = read
        return sensor

    def test_single_transient_failure_does_not_report_collision(self):
        sensor = self._sensor_with([0.5, 0.5, None, 0.5])
        assert sensor.get_distance() == (False, 0.5)
        assert sensor.get_distance() == (False, 0.5)
        # one transient miss: no collision yet (H5)
        assert sensor.is_collision_imminent() is False

    def test_three_consecutive_failures_fail_safe(self):
        sensor = self._sensor_with([0.5, None, None, None])
        assert sensor.get_distance() == (False, 0.5)
        for _ in range(3):
            collided, _ = sensor.get_distance()
        assert collided is True, "3 consecutive failures -> fail-safe collision"

    def test_good_reading_resets_failure_counter(self):
        sensor = self._sensor_with([0.5, None, 0.5, None, None, None])
        sensor.get_distance()  # good
        sensor.get_distance()  # 1 miss
        sensor.get_distance()  # good -> reset
        collided = False
        for _ in range(2):
            collided, _ = sensor.get_distance()  # 2 misses only
        assert collided is False


# ---------------------------------------------------------------- M1
class TestShutdownOrder:
    def test_handlers_run_in_registration_order(self):
        sm = shutdown_mod.ShutdownManager()
        order = []
        sm.register_handler("first", lambda: order.append("first"))
        sm.register_handler("second", lambda: order.append("second"))
        sm.register_handler("third", lambda: order.append("third"))
        sm.shutdown()
        assert order == ["first", "second", "third"]


# ---------------------------------------------------------------- M2
class TestVisionQueryPhrases:
    def test_show_me_news_is_not_a_vision_query(self):
        assert main_mod.is_vision_query("show me the news") is False
        assert main_mod.is_vision_query("show me what you see") is True
        assert main_mod.is_vision_query("what do you see") is True


# ---------------------------------------------------------------- M3
class TestBoxDequantization:
    def test_quantized_boxes_are_dequantized(self, monkeypatch):
        scale, zp = 0.005, 5
        # boxes quantized: (q - zp) * scale -> normalized coordinates
        q_boxes = np.array([[[10, 20, 100, 150]]], dtype=np.uint8)   # [1,1,4]
        q_scores = np.array([[155]], dtype=np.uint8)                 # [1,1] -> (155-5)*0.005=0.75
        q_classes = np.array([[0]], dtype=np.int64)

        class FakeInterpreter:
            def set_tensor(self, idx, data):
                pass
            def invoke(self):
                pass
            def get_tensor(self, idx):
                return {0: q_boxes, 1: q_classes, 2: q_scores}[idx]

        vs = vision_mod.VisionSystem()
        vs.available = True
        vs.interpreter = FakeInterpreter()
        vs.labels = ["person"]
        vs.input_details = [{"index": 0, "dtype": np.uint8, "shape": [1, 300, 300, 3]}]
        vs.output_details = [
            {"index": 0, "name": "", "shape": [1, 1, 4], "dtype": np.uint8, "quantization": (scale, zp)},
            {"index": 1, "name": "", "shape": [1, 1], "dtype": np.int64, "quantization": (0.0, 0)},
            {"index": 2, "name": "", "shape": [1, 1], "dtype": np.uint8, "quantization": (scale, zp)},
        ]
        vs.output_map = {"boxes": 0, "classes": 1, "scores": 2}
        monkeypatch.setattr(vision_mod, "prepare_input", lambda d, f: np.zeros((1, 4), dtype=np.uint8))

        detections = vs.detect_objects(np.zeros((480, 640, 3), dtype=np.uint8))
        assert len(detections) == 1
        d = detections[0]
        assert abs(d["confidence"] - 0.75) < 1e-6, "scores must be dequantized"
        # boxes must be dequantized too (M3): (q - zp) * scale
        expected_box = ((q_boxes.astype(np.float32) - zp) * scale)[0, 0].tolist()
        assert d["box"] == pytest.approx(expected_box, rel=1e-6), \
            "quantized box outputs must be dequantized (M3)"


# ---------------------------------------------------------------- L2 / L3
class TestMoodAndMemoryPolish:
    def test_thank_you_counts_as_positive(self):
        m = mood_mod.Mood()
        m.analyze_user_text("thank you so much")
        assert m.get_mood() == "happy"

    def test_shut_up_counts_as_negative(self):
        m = mood_mod.Mood()
        m.analyze_user_text("hey shut up right now")
        assert m.get_mood() == "annoyed"

    def test_i_hate_grammar(self):
        m = memory_mod.Memory()
        m.forget_all()
        m.auto_extract("I hate onions", "")
        facts = m.get_facts()
        assert facts == ["User hates onions"], facts
        m.forget_all()
