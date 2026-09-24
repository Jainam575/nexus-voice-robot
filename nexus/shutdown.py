"""
Nexus Robot — Centralized Shutdown Manager (Bug #23)

Idempotent shutdown that handles all cleanup:
1. STOP motors
2. Disable motor output
3. Stop camera
4. Stop recording (if active)
5. Stop TTS
6. Stop background threads
7. Close GPIO
8. Close UI
9. Flush logs

Calling shutdown twice is safe (idempotent).
"""
import threading
import logging

logger = logging.getLogger("Nexus.Shutdown")


class ShutdownManager:
    """Centralized, idempotent shutdown (Bug #23)."""

    def __init__(self):
        self._shutdown_done = False
        self._lock = threading.Lock()
        self._handlers = []

    def register_handler(self, name, handler):
        """Register a cleanup handler. Handlers run in REGISTRATION order
        (Round 2, M1): the first-registered handler runs first, matching the
        documented shutdown sequence. (Previously they ran in reverse, which
        put the motor GPIO teardown before the motor STOP and stopped TTS
        last.)"""
        self._handlers.append((name, handler))

    def shutdown(self, reason=""):
        """
        Execute full shutdown sequence. Idempotent — safe to call multiple times.
        """
        with self._lock:
            if self._shutdown_done:
                logger.info("Shutdown already complete — skipping (idempotent)")
                return
            self._shutdown_done = True

        logger.info("Shutdown initiated (reason=%s)", reason)

        # Execute handlers in registration order (M1)
        for name, handler in list(self._handlers):
            try:
                logger.info("Shutdown step: %s", name)
                handler()
            except Exception as e:
                logger.error("Shutdown handler '%s' failed: %s", name, e, exc_info=True)

        logger.info("Shutdown complete")

    @property
    def is_shutdown(self):
        return self._shutdown_done


# Singleton
shutdown_manager = ShutdownManager()
