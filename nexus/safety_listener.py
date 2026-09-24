"""
Nexus Robot — Background Safety-Stop Listener (Round 2, C2)

The main loop is single-threaded: while dance(), demo mode, navigation, or a
voice movement is running, the robot never processes the microphone — so a
spoken "STOP!" could not interrupt any of those activities. Only the watchdog,
the collision sensor, or process shutdown could stop motion mid-activity.

This module closes that gap. During any blocking activity that moves the robot,
a small background thread records the microphone (only while the robot is NOT
speaking, to avoid self-hearing) and transcribes it. If the transcript is a
safety-stop phrase ("stop", "halt", "freeze", ... — the same strict
is_safety_stop() parser the main loop uses), it:

  1. calls motor.stop() immediately (STOP jumps the motor queue and
     invalidates the in-flight generation), and
  2. sets a stop-requested event the activity checks between every step so it
     aborts promptly.

Notes:
- Network caveat: transcription uses the Sarvam STT API, so this listener needs
  connectivity — exactly like every other voice feature. The watchdog and
  collision sensor remain the network-independent safety layers.
- Mic ownership: activities that use this listener must NOT record from the
  main thread while it is active (they don't — they're blocked), and recording
  is suppressed while TTS is speaking.
- A stale listener thread (one still finishing a read after finish()) cannot
  corrupt a later activity: each start() bumps an epoch, and a stale thread
  never sets the newer epoch's event.
"""
import threading
import time
import logging

from .audio import audio_manager
from .stt import transcribe
from .command_parser import is_safety_stop
from .motor import motor

logger = logging.getLogger("Nexus.SafetyListener")


class SafetyListener:
    """Hears spoken safety-stops while the main loop is blocked."""

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self._active = False
        self._epoch = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    @property
    def stop_requested(self):
        """True once a safety-stop phrase has been heard this activity."""
        return self._stop_event.is_set()

    # ------------------------------------------------------------------
    def start(self):
        """Begin listening. Called at the start of a blocking activity."""
        with self._lock:
            self._epoch += 1
            epoch = self._epoch
            self._active = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, args=(epoch,), daemon=True, name="safety-listener")
        self._thread.start()
        logger.info("Safety listener active — say 'stop' to halt the robot")

    def finish(self, timeout=4.0):
        """Stop listening at the end of a blocking activity. Idempotent.

        stop_requested stays readable after finish() so the caller can still
        check why an activity ended.
        """
        self._active = False
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
            if thread.is_alive():
                logger.info("Safety listener still finishing a pending read; "
                            "stale results will be ignored")
            self._thread = None

    # ------------------------------------------------------------------
    def _run(self, epoch):
        while self._active and epoch == self._epoch:
            try:
                # Never record while the robot is speaking (self-hearing)
                if audio_manager.is_speaking():
                    time.sleep(0.3)
                    continue
                ok, _ = audio_manager.record_to_wav(timeout_seconds=2)
                if not ok:
                    time.sleep(0.2)
                    continue
                txt, _err = transcribe()
                if txt and is_safety_stop(txt.lower().strip()):
                    logger.warning("SAFETY STOP heard during activity: %r", txt)
                    # STOP the motors right away — jumps the motor queue and
                    # invalidates the in-flight movement generation.
                    motor.stop(source="voice_safety_listener")
                    if epoch == self._epoch:
                        self._stop_event.set()
                    return
            except Exception as e:
                logger.error("Safety listener error: %s", e)
                time.sleep(0.5)


# Singleton
safety_listener = SafetyListener()
