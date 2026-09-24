"""
Nexus Robot — Audio Manager (Review P0 #7, #8)

Centralized coordinator for microphone recording AND TTS playback.
The AudioManager is the single owner of:
- the current playback process (Review #8 — one lock)
- the speaking state (Review #7 — TTS sets/restores it via try/finally)
- stop playback
- fallback TTS

No other component directly manipulates the playback process.
When TTS is speaking, microphone recording is suppressed so the robot
never hears its own voice.
"""
import subprocess
import threading
import time
import wave
import logging
import os

try:
    import audioop
except Exception:  # Python 3.13+ removed audioop
    audioop = None

from .config import (MIC_DEVICE, SAMPLE_RATE, CHANNELS, AUDIO_FORMAT,
                     AUDIO_FILE, RECORD_SECONDS_MAX, RMS_SILENCE_THRESHOLD,
                     VAD_MODE, FRAME_DURATION_MS)
from .latency import measure

logger = logging.getLogger("Nexus.Audio")

# Optional VAD
try:
    import webrtcvad
    VAD_AVAILABLE = True
except Exception:
    webrtcvad = None
    VAD_AVAILABLE = False
    logger.info("webrtcvad unavailable — using RMS threshold fallback")


class AudioManager:
    """
    Coordinates mic + speaker, and OWNS all TTS playback process state
    (Review #8). When TTS is speaking, recording is suppressed to avoid
    the robot hearing its own voice (Review #7).
    """

    def __init__(self):
        # Speaking state (Review #7)
        self._speaking = False
        self._speaking_lock = threading.Lock()
        self._recording_lock = threading.Lock()

        # Centralized playback process state (Review #8) — ONE lock
        self._playback_lock = threading.Lock()
        self._playback_process = None

    # ------------------------------------------------------------------
    # Speaking state (Review #7)
    # ------------------------------------------------------------------
    def set_speaking(self, value: bool):
        """TTS calls this to indicate playback in progress."""
        with self._speaking_lock:
            self._speaking = value

    def is_speaking(self):
        with self._speaking_lock:
            return self._speaking

    # ------------------------------------------------------------------
    # Centralized playback management (Review #8)
    # ------------------------------------------------------------------
    def start_playback(self):
        """Launch aplay for TTS output. Returns the process. Only one
        playback at a time (guarded by _playback_lock)."""
        with self._playback_lock:
            # Kill any stale playback first
            self._terminate_playback_locked()
            proc = subprocess.Popen(
                ["aplay", "-D", os.environ.get("TTS_DEVICE", "hw:1,0"),
                 "-f", AUDIO_FORMAT, "-c", str(CHANNELS), "-r", str(SAMPLE_RATE)],
                stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self._playback_process = proc
            return proc

    def get_playback_process(self):
        with self._playback_lock:
            return self._playback_process

    def finish_playback(self, proc, block=True, timeout=30):
        """Close stdin and optionally wait for the process to finish.

        The lock is NOT held during wait() (H4) so stop_playback() can terminate
        the process immediately even while a blocking wait is in flight (e.g. on
        shutdown). Without this, a hung aplay would block shutdown forever.
        """
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
            if block:
                proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("aplay did not finish in %ss — terminating", timeout)
            self._terminate_proc(proc)
        except Exception as e:
            logger.warning("Playback finish error: %s", e)
        finally:
            with self._playback_lock:
                if self._playback_process is proc:
                    self._playback_process = None

    def stop_playback(self):
        """Stop current TTS playback by terminating the exact tracked process
        (no pkill — Review #8). Runs outside the lock (H4) so it can interrupt
        a blocking finish_playback()."""
        with self._playback_lock:
            proc = self._playback_process
            self._playback_process = None
        if proc is not None:
            self._terminate_proc(proc)

    @staticmethod
    def _terminate_proc(proc):
        try:
            proc.terminate()
            proc.wait(timeout=1)
        except Exception:
            try:
                proc.kill()
            except Exception as e:
                logger.warning("Failed to kill aplay: %s", e)

    def _terminate_playback_locked(self):
        proc = self._playback_process
        self._playback_process = None
        if proc is not None:
            self._terminate_proc(proc)

    def fallback_tts(self, text):
        """Fallback TTS via espeak when the primary path fails."""
        try:
            subprocess.run(["espeak", text],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Microphone
    # ------------------------------------------------------------------
    def validate_microphone(self) -> tuple:
        """
        Real microphone validation. Returns (ok: bool, message: str).
        Takes the recording lock (L8) so it cannot spawn a second arecord
        alongside an active recording.
        """
        with self._recording_lock:
            return self._validate_microphone_internal()

    def _validate_microphone_internal(self) -> tuple:
        try:
            proc = subprocess.Popen(
                ["arecord", "-D", MIC_DEVICE, "-f", AUDIO_FORMAT,
                 "-r", str(SAMPLE_RATE), "-c", str(CHANNELS), "-t", "raw"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            time.sleep(0.3)
            data = proc.stdout.read(1600)
            proc.terminate()
            proc.wait(timeout=1)

            if len(data) < 800:
                return False, f"device '{MIC_DEVICE}' produced no audio data"
            return True, f"device '{MIC_DEVICE}' working"

        except FileNotFoundError:
            return False, "arecord not found — install alsa-utils"
        except subprocess.TimeoutExpired:
            return False, f"device '{MIC_DEVICE}' unavailable (timeout)"
        except Exception as e:
            return False, f"device '{MIC_DEVICE}' error: {e}"

    def record_to_wav(self, timeout_seconds=RECORD_SECONDS_MAX,
                      out_file=AUDIO_FILE) -> tuple:
        """
        Record from mic to WAV file. Returns (ok, error).
        Skips recording while TTS is speaking (self-hearing prevention).
        """
        # Don't record while we're speaking (Review #7)
        if self.is_speaking():
            time.sleep(0.3)
            if self.is_speaking():
                return False, "tts-speaking"

        with self._recording_lock:
            # Measured as 'mic_recording' (vision-performance pass, req. 6)
            with measure("mic_recording"):
                return self._record_internal(timeout_seconds, out_file)

    def _record_internal(self, timeout_seconds, out_file):
        frame_ms = FRAME_DURATION_MS
        frame_bytes = int(SAMPLE_RATE * (frame_ms / 1000.0) * 2)

        try:
            proc = subprocess.Popen(
                ["arecord", "-D", MIC_DEVICE, "-f", AUDIO_FORMAT,
                 "-r", str(SAMPLE_RATE), "-c", str(CHANNELS), "-t", "raw"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
        except Exception as e:
            return False, f"arecord-failed:{e}"

        vad = webrtcvad.Vad(VAD_MODE) if VAD_AVAILABLE else None
        frames = bytearray()
        start_time = time.time()
        saw_speech = False
        consecutive_silence = 0
        max_silence_after_speech = int(0.5 / (frame_ms / 1000.0)) + 1

        try:
            while time.time() - start_time <= timeout_seconds:
                chunk = proc.stdout.read(frame_bytes)
                if not chunk or len(chunk) < frame_bytes:
                    break
                frames.extend(chunk)

                is_speech = False
                if vad:
                    try:
                        is_speech = vad.is_speech(chunk, sample_rate=SAMPLE_RATE)
                    except Exception:
                        pass
                elif audioop is not None:
                    try:
                        is_speech = audioop.rms(chunk, 2) > RMS_SILENCE_THRESHOLD
                    except Exception:
                        pass

                if is_speech:
                    saw_speech = True
                    consecutive_silence = 0
                elif saw_speech:
                    consecutive_silence += 1

                if saw_speech and consecutive_silence >= max_silence_after_speech:
                    break
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        if not frames:
            return False, "no-audio"

        # Phantom-wake fix (2026-09): a muted/disconnected mic that still
        # enumerates as a device records pure zeros — that is NOT speech.
        # Never send speech-free audio to STT (it hallucinates words like
        # "hello" out of pure silence). Only enforced when a speech
        # detector (webrtcvad or audioop RMS) was actually available.
        if not saw_speech and (vad is not None or audioop is not None):
            return False, "silent"

        try:
            with wave.open(out_file, "wb") as outw:
                outw.setnchannels(CHANNELS)
                outw.setsampwidth(2)
                outw.setframerate(SAMPLE_RATE)
                outw.writeframes(bytes(frames))
        except Exception:
            return False, "write-failed"

        if os.path.getsize(out_file) < 2000 if os.path.exists(out_file) else True:
            return False, "silent"

        return True, None


# Singleton
audio_manager = AudioManager()
