"""
Nexus Robot — TTS Manager (Review P0 #7, #8)

TTS coordinates with AudioManager so that:
- The speaking state is always set and restored via try/finally (Review #7).
- Playback process state is owned by AudioManager with ONE lock (Review #8).
- No component directly manipulates the aplay process.

The AudioManager.stop_playback() terminates the exact tracked process
(no pkill).
"""
import threading
import time
import re
import unicodedata
import logging
import requests

from .config import (SARVAM_KEY, NEXUS_VOICE, TTS_LANGUAGE_CODE, SAMPLE_RATE)
from .audio import audio_manager
from .latency import latency

logger = logging.getLogger("Nexus.TTS")

# Lock so only one speak() call runs at a time (Review #8)
_tts_lock = threading.Lock()

UNWANTED = r"[\#\*\;\:\'\"\!\(\)\@\&\%\$\^\{\}\[\]\|\<\>\?/]"

# Script ranges → Sarvam language codes (H3). Text written in an Indian
# script is spoken with the matching bulbul voice instead of being stripped.
_SCRIPT_LANGUAGE_MAP = [
    ("\u0900-\u097F", "hi-IN"),   # Devanagari (Hindi, Marathi, ...)
    ("\u0980-\u09FF", "bn-IN"),   # Bengali
    ("\u0A00-\u0A7F", "pa-IN"),   # Gurmukhi (Punjabi)
    ("\u0A80-\u0AFF", "gu-IN"),   # Gujarati
    ("\u0B00-\u0B7F", "or-IN"),   # Odia
    ("\u0B80-\u0BFF", "ta-IN"),   # Tamil
    ("\u0C00-\u0C7F", "te-IN"),   # Telugu
    ("\u0C80-\u0CFF", "kn-IN"),   # Kannada
    ("\u0D00-\u0D7F", "ml-IN"),   # Malayalam
]


def detect_language_code(text):
    """Pick a TTS language code from the script of the text (H3)."""
    for rng, code in _SCRIPT_LANGUAGE_MAP:
        if re.search(f"[{rng}]", text):
            return code
    return TTS_LANGUAGE_CODE


def clean_text(text):
    """Clean text for speech WITHOUT stripping non-ASCII (H3).

    Previously this removed every non-ASCII character, so Hindi/Bengali/Tamil
    text was silently deleted before it ever reached the TTS API. Unicode
    letters are now preserved; only ASCII markup symbols are removed.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(UNWANTED, " ", text)
    return re.sub(r"\s+", " ", text).strip()


def stop_playback():
    """Stop current TTS playback via AudioManager (Review #8)."""
    audio_manager.stop_playback()


def speak(text, voice=None, block=True, safety_delay=0.15, temperature=0.4,
          face_callback=None):
    """
    Stream TTS from Sarvam and play via aplay.

    Owns the AudioManager speaking-state via try/finally (Review #7):
        set_speaking(True)
        → playback
        → set_speaking(False) [always, even on error]

    Playback process state is managed by AudioManager (Review #8).
    """
    voice = voice or NEXUS_VOICE
    text = clean_text(text)
    if not text:
        return

    if not SARVAM_KEY:
        logger.warning("TTS skipped — no API key")
        return

    # Speak non-Latin text with the matching Indic voice (H3)
    language_code = detect_language_code(text)

    if face_callback:
        face_callback("talking")

    with _tts_lock:
        audio_manager.set_speaking(True)
        t_tts = time.perf_counter()
        try:
            _speak_internal(text, voice, block, temperature, face_callback,
                            language_code)
        except Exception as e:
            logger.error("TTS error: %s", e, exc_info=True)
            # Fallback to espeak if available (Review #8)
            audio_manager.fallback_tts(text)
        finally:
            # Measured as 'tts' — fetch + playback (vision-performance pass)
            latency.record("tts", time.perf_counter() - t_tts)
            # ALWAYS restore speaking state (Review #7)
            audio_manager.set_speaking(False)
            time.sleep(safety_delay)
            if face_callback:
                face_callback("idle")


def _speak_internal(text, voice, block, temperature, face_callback,
                    language_code=TTS_LANGUAGE_CODE):
    """Stream from Sarvam and pipe to aplay via AudioManager."""
    proc = audio_manager.start_playback()
    if proc is None:
        return

    try:
        with requests.post(
            "https://api.sarvam.ai/text-to-speech/stream",
            json={
                "text": text,
                "language_code": language_code,
                "speaker": voice,
                "model": "bulbul:v3",
                "output_audio_codec": "linear16",
                "speech_sample_rate": SAMPLE_RATE,
                "temperature": temperature,
            },
            headers={"api-subscription-key": SARVAM_KEY,
                     "Content-Type": "application/json"},
            stream=True, timeout=40
        ) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=4096):
                if chunk and proc and proc.stdin:
                    try:
                        proc.stdin.write(chunk)
                        proc.stdin.flush()
                    except BrokenPipeError:
                        break

        audio_manager.finish_playback(proc, block=block)
    except requests.exceptions.ConnectionError:
        logger.error("TTS: cannot reach Sarvam — network unavailable")
        audio_manager.stop_playback()
    except requests.exceptions.Timeout:
        logger.error("TTS: Sarvam timeout")
        audio_manager.stop_playback()
    except Exception:
        audio_manager.stop_playback()
        raise
