"""
Nexus Robot — Face Display (pygame animated robot face)

Rendered on the MAIN thread (SDL/pygame is unreliable from background threads).
Mood and robot state are separated — this module just renders what it's told.
"""
import math
import random
import threading
import time
import logging

from .config import FACE_WIDTH, FACE_HEIGHT, FACE_FULLSCREEN, MOOD_COLORS

logger = logging.getLogger("Nexus.FaceDisplay")

try:
    import pygame
    PYGAME_AVAILABLE = True
except Exception:
    pygame = None
    PYGAME_AVAILABLE = False

FACE_BG = (8, 10, 18)

try:
    import os
    os.environ.setdefault("SDL_NOMOUSE", "1")
    if os.environ.get("FACE_FBDEV"):
        os.environ.setdefault("SDL_VIDEODRIVER", "fbcon")
        os.environ["SDL_FBDEV"] = os.environ["FACE_FBDEV"]
except Exception:
    pass


class FaceDisplay:
    """Animated robot face. State is set externally; rendering happens in tick()."""

    VALID_STATES = {"idle", "listening", "thinking", "talking", "happy", "sad",
                    "moving", "asleep", "playing", "navigating", "guarding"}

    def __init__(self):
        self.state = "idle"
        self._mood = "neutral"
        self._running = False
        self._lock = threading.Lock()
        self._screen = None
        self._clock = None
        self._blink_timer = time.time() + random.uniform(2, 5)
        self._blink_progress = 0.0
        self._blinking = False
        self._look_x = 0.0
        self._look_target = 0.0
        self._look_timer = time.time() + random.uniform(1.5, 3.5)
        self._move_look = 0.0
        self._move_until = 0.0
        self._talk_phase = 0.0
        self._camera_mode = False
        self._camera_frame = None
        self._sleep_z_phase = 0.0
        self._excite_bounce = 0.0

    def start(self):
        if not PYGAME_AVAILABLE:
            logger.warning("pygame not installed — face display disabled")
            return
        if self._screen is not None:
            return
        try:
            pygame.init()
            flags = pygame.FULLSCREEN if FACE_FULLSCREEN else 0
            self._screen = pygame.display.set_mode((FACE_WIDTH, FACE_HEIGHT), flags)
            pygame.mouse.set_visible(False)
            pygame.display.set_caption("Nexus Face")
        except Exception as e:
            logger.error("Face display init failed: %s", e)
            self._screen = None
            return
        self._clock = pygame.time.Clock()
        self._running = True
        logger.info("Face display started")

    def set_state(self, state):
        if state in self.VALID_STATES and self._screen is not None:
            with self._lock:
                self.state = state

    def set_mood(self, m):
        with self._lock:
            self._mood = m if m in MOOD_COLORS else "neutral"

    def nudge_look(self, direction, hold_seconds=0.9):
        if self._screen is None:
            return
        bias = {"left": -1.0, "right": 1.0, "forward": 0.0, "back": 0.0, "spin": 1.0, "stop": 0.0}.get(direction, 0.0)
        with self._lock:
            self._move_look = bias
            self._move_until = time.time() + hold_seconds
            self.state = "moving"

    def show_camera_frame(self, frame):
        if self._screen is None:
            return
        with self._lock:
            self._camera_mode = True
            self._camera_frame = frame

    def update_camera_frame(self, frame):
        if self._screen is None:
            return
        with self._lock:
            if self._camera_mode:
                self._camera_frame = frame

    def hide_camera(self):
        with self._lock:
            self._camera_mode = False
            self._camera_frame = None

    def stop(self):
        self._running = False
        if PYGAME_AVAILABLE:
            try:
                pygame.quit()
            except Exception:
                pass

    def request_stop(self):
        """Ask the render loop to stop without touching pygame — safe to call
        from a background thread (unlike stop())."""
        self._running = False

    _printed_error = False

    def tick(self):
        if self._screen is None or not self._running:
            return
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self._running = False
        try:
            self._draw_frame()
        except Exception as e:
            if not self._printed_error:
                logger.error("Face render error: %s", e)
                self._printed_error = True
        self._clock.tick(30)

    def _draw_frame(self):
        now = time.time()
        with self._lock:
            move_active = now < self._move_until
            if self.state == "moving" and not move_active:
                self.state = "idle"
            state = self.state
            move_look = self._move_look
            camera_mode = self._camera_mode
            camera_frame = self._camera_frame
            current_mood = self._mood

        screen = self._screen
        screen.fill(FACE_BG)

        if camera_mode and camera_frame is not None:
            try:
                import cv2
                rgb = cv2.cvtColor(camera_frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[0], rgb.shape[1]
                surf = pygame.image.frombuffer(rgb.tobytes(), (w, h), "RGB")
                surf = pygame.transform.scale(surf, (FACE_WIDTH, FACE_HEIGHT))
                screen.blit(surf, (0, 0))
                pygame.draw.rect(screen, (60, 200, 255), screen.get_rect(), 4)
            except Exception as e:
                if not self._printed_error:
                    logger.error("Camera preview render error: %s", e)
                    self._printed_error = True
            pygame.display.flip()
            return

        cx, cy = FACE_WIDTH // 2, FACE_HEIGHT // 2
        eye_w, eye_h = int(FACE_WIDTH * 0.14), int(FACE_HEIGHT * 0.28)
        eye_gap = int(FACE_WIDTH * 0.22)
        eye_y = cy - int(FACE_HEIGHT * 0.08)

        if state == "sad":
            color = (230, 100, 90)
        elif state == "thinking":
            color = (230, 190, 60)
        elif state == "moving":
            color = (170, 120, 255)
        else:
            color = MOOD_COLORS.get(current_mood, (60, 200, 255))

        # Sleeping animation
        if state == "asleep":
            self._sleep_z_phase += 0.02
            for side in (-1, 1):
                ex = cx + side * eye_gap
                pygame.draw.line(screen, color, (ex - eye_w // 2, eye_y), (ex + eye_w // 2, eye_y), 5)
            try:
                font = pygame.font.Font(None, int(FACE_HEIGHT * 0.18))
                for i, z_char in enumerate(["z", "Z", "Z"]):
                    zy = eye_y - int(FACE_HEIGHT * 0.15) - i * int(FACE_HEIGHT * 0.1)
                    zx = cx + int(FACE_WIDTH * 0.12) + i * int(FACE_WIDTH * 0.06)
                    offset = math.sin(self._sleep_z_phase + i * 1.2) * 4
                    alpha = max(30, 200 - i * 60)
                    z_surf = font.render(z_char, True, color)
                    z_surf.set_alpha(alpha)
                    screen.blit(z_surf, (zx, zy + offset))
            except Exception:
                pass
            breath = (math.sin(self._sleep_z_phase * 0.7) * 0.5 + 0.5)
            mh = max(3, int(breath * FACE_HEIGHT * 0.04))
            rect = pygame.Rect(0, 0, int(FACE_WIDTH * 0.12), mh)
            rect.center = (cx, cy + int(FACE_HEIGHT * 0.22))
            pygame.draw.ellipse(screen, color, rect)
            pygame.display.flip()
            return

        # Look direction
        if state == "moving" and move_active:
            self._look_target = move_look
        elif now > self._look_timer:
            self._look_target = random.uniform(-1, 1)
            self._look_timer = now + random.uniform(1.5, 4.0)
        self._look_x += (self._look_target - self._look_x) * (0.25 if state == "moving" else 0.05)
        look_offset = int(self._look_x * FACE_WIDTH * 0.05)

        # Blinking
        if state != "moving" and current_mood != "excited":
            if not self._blinking and now > self._blink_timer:
                self._blinking = True
            if self._blinking:
                self._blink_progress += 0.25
                if self._blink_progress >= 1.0:
                    self._blink_progress = 0.0
                    self._blinking = False
                    self._blink_timer = now + random.uniform(2.5, 6.0)
        else:
            self._blinking = False
            self._blink_progress = 0.0
        blink_scale = abs(math.sin(self._blink_progress * math.pi)) if self._blinking else 0.0

        bounce_y = 0
        if current_mood == "excited" and state not in ("talking", "thinking", "asleep"):
            self._excite_bounce += 0.15
            bounce_y = int(math.sin(self._excite_bounce) * FACE_HEIGHT * 0.03)

        for side in (-1, 1):
            ex = cx + side * eye_gap + look_offset
            h = int(eye_h * (1 - 0.85 * blink_scale))
            if current_mood == "sleepy":
                h = int(h * 0.45)
            elif current_mood == "annoyed":
                h = int(h * 0.55)
            elif current_mood == "excited":
                h = int(h * 1.15)
            elif current_mood == "curious":
                h = int(h * (1.15 if side > 0 else 0.9))
            rect = pygame.Rect(0, 0, eye_w, max(h, 4))
            rect.center = (ex, eye_y + bounce_y)
            try:
                pygame.draw.rect(screen, color, rect, border_radius=eye_w // 3)
            except TypeError:
                pygame.draw.rect(screen, color, rect)
            if state == "happy" or current_mood == "happy":
                cover = pygame.Rect(0, 0, eye_w + 6, eye_h // 2)
                cover.midtop = (ex, eye_y + bounce_y)
                pygame.draw.ellipse(screen, FACE_BG, cover)

        mouth_y = cy + int(FACE_HEIGHT * 0.22)

        if state == "talking":
            self._talk_phase += 0.35
            open_amt = (math.sin(self._talk_phase) * 0.5 + 0.5) * random.uniform(0.6, 1.0)
            mh = max(4, int(open_amt * FACE_HEIGHT * 0.12))
            rect = pygame.Rect(0, 0, int(FACE_WIDTH * 0.28), mh)
            rect.center = (cx, mouth_y)
            pygame.draw.ellipse(screen, color, rect)
        elif state == "happy" or current_mood == "happy":
            rect = pygame.Rect(0, 0, int(FACE_WIDTH * 0.28), int(FACE_HEIGHT * 0.14))
            rect.center = (cx, mouth_y - int(FACE_HEIGHT * 0.02))
            pygame.draw.arc(screen, color, rect, math.pi * 1.15, math.pi * 1.85, 6)
        elif state == "sad":
            rect = pygame.Rect(0, 0, int(FACE_WIDTH * 0.28), int(FACE_HEIGHT * 0.14))
            rect.center = (cx, mouth_y + int(FACE_HEIGHT * 0.05))
            pygame.draw.arc(screen, color, rect, math.pi * 0.15, math.pi * 0.85, 6)
        elif state == "listening":
            pygame.draw.circle(screen, color, (cx, mouth_y), max(4, int(FACE_HEIGHT * 0.02)))
        elif state == "thinking":
            for i in range(3):
                phase = (now * 3 + i * 0.6) % (2 * math.pi)
                r = int(4 + 3 * (math.sin(phase) * 0.5 + 0.5))
                pygame.draw.circle(screen, color, (cx - 24 + i * 24, mouth_y), r)
        elif state == "moving":
            pygame.draw.circle(screen, color, (cx, mouth_y), max(5, int(FACE_HEIGHT * 0.03)))
        elif current_mood == "annoyed":
            pygame.draw.line(screen, color, (cx - int(FACE_WIDTH * 0.1), mouth_y), (cx + int(FACE_WIDTH * 0.1), mouth_y), 6)
        elif current_mood == "excited":
            rect = pygame.Rect(0, 0, int(FACE_WIDTH * 0.3), int(FACE_HEIGHT * 0.16))
            rect.center = (cx, mouth_y)
            pygame.draw.arc(screen, color, rect, math.pi * 1.1, math.pi * 1.9, 7)
        else:
            pygame.draw.line(screen, color, (cx - int(FACE_WIDTH * 0.14), mouth_y), (cx + int(FACE_WIDTH * 0.14), mouth_y), 4)

        pygame.display.flip()


# Singleton
face = FaceDisplay()
