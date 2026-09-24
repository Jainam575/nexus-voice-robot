"""
Nexus Robot — Navigation (Review P1 #15, #16)

Uses bounding-box size as proximity indicator + obstacle check.
Does NOT use blind fixed timers — re-detects after each step.
Safety controller can interrupt at any point.

Fixes:
- Every movement checks the execute_move result (accepted/rejected) and
  reacts accordingly (Review #15).
- Every movement uses the blocking motor API with a timeout, so no
  navigation loop can leave a command running indefinitely (Review #16).
- Collision sensor is checked via SafetyController before/while moving
  (Review #6).

NOTE: This is APPROXIMATE navigation for a demo robot without depth
sensors. True collision avoidance requires ToF/ultrasonic/LiDAR (Review #6).
"""
import logging

from .config import (NAV_BBOX_CLOSE_THRESHOLD, NAV_MAX_STEPS,
                     MOTOR_COMMAND_TIMEOUT, NEXUS_VISION_API_KEY,
                     NEXUS_VISION_BASE_URL, NEXUS_VISION_MODEL)
from .camera import camera_manager
from .vision import vision_system, OpenAI
from .motor import motor
from .tts import speak
from .face_display import face

logger = logging.getLogger("Nexus.Navigation")


def _vlm_ask(frame, question):
    """Ask the configured cloud vision LLM a yes/no-ish question about a
    frame. Returns its short answer text, or None when unavailable/failing.
    Used as the perception fallback for navigation — the tiny offline COCO
    detector misses many everyday objects (bottles, remotes, cups)."""
    if frame is None:
        return None
    if not (NEXUS_VISION_API_KEY and NEXUS_VISION_BASE_URL):
        return None
    if OpenAI is None:
        return None
    try:
        img_b64 = vision_system._encode_frame_b64(frame)
        client = vision_system._alt_vision_client()
        resp = client.chat.completions.create(
            model=NEXUS_VISION_MODEL,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": question},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}],
            max_tokens=5)
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("VLM navigation question failed: %s", e)
        return None


def _vlm_locate_object(frame, target_object):
    """Cloud-VLM fallback for find_object_position(): ask where the target
    is in the frame (LEFT / CENTER / RIGHT / NO). Returns a synthetic
    position dict compatible with the navigation loop, or None."""
    ans = _vlm_ask(frame,
                   f"Is there a {target_object} visible in this image? "
                   "Answer with exactly one word: LEFT, CENTER, RIGHT, or NO.")
    if not ans:
        return None
    a = ans.upper()
    if "LEFT" in a:
        cx = 0.2
    elif "RIGHT" in a:
        cx = 0.8
    elif ("CENTER" in a) or ("MIDDLE" in a) or ("FRONT" in a):
        cx = 0.5
    else:
        return None
    logger.info("VLM located %s at %s (center_x=%.1f)",
                target_object, a.split()[0] if a.split() else a, cx)
    return {"found": True, "center_x": cx, "center_y": 0.5,
            "label": target_object, "box_width": 0.2, "confidence": 0.6}


def find_object_position(detections, target_object):
    """Find target object in detections. Returns dict with found/center/bbox_width."""
    target_lower = target_object.lower()
    for det in detections:
        if target_lower in det['label'].lower():
            box = det['box']
            box_width = box[3] - box[1]
            return {
                'found': True,
                'center_x': (box[1] + box[3]) / 2,
                'center_y': (box[0] + box[2]) / 2,
                'confidence': det['confidence'],
                'label': det['label'],
                'box_width': box_width,
            }
    return {'found': False}


def _check_obstacle_ahead(detections, target_label):
    """Check for obstacles in the center of frame."""
    for det in detections:
        if det['label'].lower() == target_label.lower():
            continue
        box = det['box']
        center_x = (box[1] + box[3]) / 2
        box_width = box[3] - box[1]
        if 0.3 < center_x < 0.7 and box_width > 0.15:
            return det['label']
    return None


def _do_move(direction, duration, source, timeout=MOTOR_COMMAND_TIMEOUT):
    """
    Execute a movement and check its result (Review #15).
    Uses the blocking API so navigation waits for completion before
    issuing the next command — this prevents commands being rejected
    because a prior movement is still active (Review #2).
    Every movement has a timeout (Review #16).
    """
    result = motor.execute_move(
        direction, duration=duration, source=source,
        wait=True, timeout=timeout,
    )
    status = result.get("status")
    if status == "denied":
        logger.warning("Navigation move denied: %s (%s)", direction, result.get("reason"))
        return False
    if status == "timeout":
        logger.warning("Navigation move timed out: %s", direction)
        return False
    if status == "interrupted":
        # Interrupted by STOP or collision — navigation should stop
        logger.info("Navigation move interrupted: %s (%s)", direction, result.get("reason"))
        return False
    return True


def navigate_to_object(target_object):
    """
    Navigate toward a target object using vision-guided steps.
    Stops when object bounding box is large enough (close).
    Checks for obstacles before each forward move.
    Safety controller can interrupt at any point.

    Every movement checks its result (Review #15) and has a timeout
    (Review #16). A voice safety-stop is heard via the SafetyListener (C2/C6).
    """
    from .safety_listener import safety_listener

    logger.info("Navigation started: target=%s", target_object)
    speak(f"Looking for {target_object}.")

    safety_listener.start()
    try:
        return _navigate_loop(target_object, safety_listener)
    finally:
        safety_listener.finish()
        face.hide_camera()

def _navigate_loop(target_object, safety_listener):
    vlm_guided_steps = 0
    for step in range(NAV_MAX_STEPS):
        # Abort only on a FAULT or a stop explicitly requested by the safety
        # listener. NOTE: is_stopped() is True whenever the robot is at rest
        # between moves (STOPPED is the normal state), so it must NOT be used
        # as the abort condition — doing so made navigation bail out at step 0
        # without ever moving (C6).
        if motor.safety.is_fault() or safety_listener.stop_requested:
            return "Navigation stopped."

        frame = camera_manager.capture()
        if frame is None:
            return "I cannot see right now."

        # Show the camera preview on the robot's face while navigating
        # (2026-09 fix: the preview used to stay hidden, so it looked like
        # the camera never opened during "find the X").
        face.show_camera_frame(frame)

        detections = vision_system.detect_objects(frame)
        position = find_object_position(detections, target_object)

        if not position['found']:
            # Cloud-VLM fallback (2026-09): the offline COCO detector only
            # knows 80 classes and misses many everyday objects — ask the
            # configured vision LLM where the target is.
            vpos = _vlm_locate_object(frame, target_object)
            if vpos:
                position = vpos
                vlm_guided_steps += 1
                if vlm_guided_steps >= 2:
                    close = _vlm_ask(
                        frame,
                        f"Is the {target_object} close to the camera now, "
                        "filling a large part of the image? Answer YES or NO.")
                    if close and "YES" in close.upper():
                        speak(f"I've reached the {target_object}!")
                        return f"I reached the {target_object}!"

        if not position['found']:
            speak(f"I don't see {target_object}. Let me look around.")
            if not _do_move("right", 1.5, "nav_search"):
                return "I had to stop searching."
            frame = camera_manager.capture()
            position = find_object_position(vision_system.detect_objects(frame), target_object)
            if not position['found']:
                if not _do_move("left", 3.0, "nav_search"):
                    return "I had to stop searching."
                frame = camera_manager.capture()
                position = find_object_position(vision_system.detect_objects(frame), target_object)
                if not position['found']:
                    return f"I cannot find {target_object} nearby."

        label = position['label']
        center_x = position['center_x']
        box_width = position.get('box_width', 0)

        # Stop condition: object is large enough → close
        if box_width > NAV_BBOX_CLOSE_THRESHOLD:
            speak(f"I've reached the {label}!")
            return f"I reached the {label}!"

        # Obstacle check before forward
        obstacle = _check_obstacle_ahead(detections, label)
        if obstacle:
            speak(f"I see a {obstacle} in the way. Stopping for safety.")
            return f"Obstacle ({obstacle}) detected near the {label}. Stopped for safety."

        # Center the object
        if center_x < 0.35:
            if not _do_move("left", 0.5, "nav_center"):
                return "Navigation stopped."
        elif center_x > 0.65:
            if not _do_move("right", 0.5, "nav_center"):
                return "Navigation stopped."

        # Forward — short steps, re-check after each
        if 0.35 <= center_x <= 0.65:
            speak(f"Moving toward the {label}.")
            if not _do_move("forward", 1.0, "nav_forward"):
                return "Navigation stopped."

    return f"I got close to the {target_object} but couldn't reach it."
