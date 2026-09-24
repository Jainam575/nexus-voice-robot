# 🩺 Troubleshooting

Every problem below actually happened during this build. Symptoms → cause → fix.

## Table of contents

1. [Sarvam API returns 402 / 403](#sarvam-api-402--403)
2. [STT circuit breaker opened — robot went deaf](#stt-circuit-breaker)
3. [Camera: FAIL / TFLite: FAIL after an opencv install](#camera--tflite-fail-after-opencv-install)
4. [Face Recog: FAIL — no Haar cascades](#face-recog-fail--no-haar-cascades)
5. [pip compiling OpenCV from source for hours](#pip-compiling-opencv-from-source)
6. [Camera colors inverted (blue↔yellow, skin→blue)](#camera-colors-inverted)
7. [One motor side never goes backward](#one-motor-side-never-goes-backward)
8. [Robot turns when asked to go straight](#robot-turns-when-asked-to-go-straight)
9. [Wake word barely works ("hey macus"?)](#wake-word-barely-works)
10. ["Move forward" gets an LLM answer instead of moving](#move-forward-answered-by-llm)
11. [Face enrollment captures nothing](#face-enrollment-captures-nothing)
12. [Weather says nothing / TLS errors](#weather-tls-errors)
13. [TTS silent — no sound from speaker](#tts-silent)

---

## Sarvam API 402 / 403

**Symptom:** TTS raises `402 Client Error: Payment Required` or `403
Forbidden`; STT fails 3 times and the circuit breaker opens.

- `402` — the account is out of credits. Top up at dashboard.sarvam.ai
  (credits never expire; STT ≈ ₹30/hour of audio, TTS ≈ ₹15/10k chars).
- `403` — key rejected: usually a typo from hand-typing the export in a
  fresh SSH session. Verify:

  ```bash
  curl -s -X POST https://api.sarvam.ai/text-to-speech/stream \
    -H "api-subscription-key: $SARVAM_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"text":"hello","target_language_code":"en-IN"}' \
    -o /dev/null -w "%{http_code}\n"
  ```

  `200` = key fine. Anything else: re-copy the key, put the export in
  `~/.bashrc`, open a new session.

## STT circuit breaker

**Symptom:** log floods with `STT circuit breaker open — skipping request`;
the robot ignores you completely.

After 3 consecutive STT failures the breaker opens for 60 s, then
half-opens and retries. It will say out loud: *"Speech recognition is
failing. Please check my internet connection and API key."* The robot stays
alive and recovers by itself once the underlying error (usually 402/403
above) is fixed.

## Camera / TFLite: FAIL after opencv install

**Symptom:** after installing an OpenCV package, boot check shows
`Camera: FAIL` and `TFLite: FAIL`.

Cause: pip pulled **numpy 2.x** into the venv; `picamera2` and
`tflite_runtime` are system packages compiled against numpy 1.x.

Fix:

```bash
pip uninstall -y opencv-contrib-python numpy
pip install --only-binary :all: "opencv-contrib-python-headless==4.10.0.84" "numpy<2"
```

## Face Recog: FAIL — no Haar cascades

**Symptom:** boot check prints `Face Recog: FAIL`.

Causes, in order of likelihood:

1. **OpenCV 5.x installed** — the 5.0 wheels ship an *empty* cascade folder.
   Pin to 4.x (command above).
2. Cascade XMLs not found anywhere — the code also looks in the script
   directory and `/usr/share/opencv*/haarcascades`, so you can drop
   `haarcascade_frontalface_default.xml` next to the script as a fallback.

## pip compiling OpenCV from source

**Symptom:** `Building wheel for opencv-contrib-python …` runs for hours.

Cause: no prebuilt wheel for your platform on PyPI. On Raspberry Pi OS, pip
should use piwheels; some versions (4.14+) have no piwheels build yet. Pin
a version that does — 4.10.0.84, 4.11.0.86, 4.12.0.88 all have armv7l
wheels. Use `--only-binary :all:` to make pip fail instead of compiling.

## Camera colors inverted

**Symptom:** blue looks yellow, skin looks blue — in the face preview *and*
in cloud-vision descriptions.

Cause: picamera2's format names are **inverted** relative to the actual
byte order (a libcamera/DRM naming quirk): requesting `BGR888` returns
RGB-ordered bytes, which OpenCV then treats as BGR. Documented in the
Picamera2 manual: "RGB888 - ordered [B, G, R]. BGR888 - ordered [R, G, B]".

Fix (already in this code): request `RGB888` to get true BGR. If a future
driver changes behavior: `export NEXUS_CAMERA_SWAP=1` flips the channels
back.

## One motor side never goes backward

**Symptom:** forward works both sides; backward/turning only spins one
side.

Isolate with the tools in `tools/`:

1. `motor_test.py` — per channel per direction.
2. `motor_probe.py` — each direction pin fired individually.
3. `motor_finder.py` — sweeps candidate GPIOs to find where a stray wire
   actually sits.
4. `enable_hold.py` — hold enables on, touch the wire to 3.3 V (physical
   pin 1). Spins = wire+driver fine.

Outcomes we hit: loose jumper (replace it), dead GPIO pin (remap with
`NEXUS_MOTOR_B_IN4=<gpio>` — our Pi's physical pin 37 is dead, we use
GPIO 19/pin 35).

## Robot turns when asked to go straight

Direction wires of one side crossed → that side runs backward when told to
run forward → pivot instead of straight line. Swap the two direction input
wires for that side at the driver board (or at the Pi).

If only turn directions are mirrored (left command → right turn), that's
the A/B channels being on opposite sides: `export NEXUS_MOTOR_SWAP_AB=1`.

## Wake word barely works

Fixed by fuzzy matching: any word within edit distance 3 of "nexus" wakes
the robot. If your STT language is set to something else (`gu-IN` while you
speak English, for example), transcripts come out wrong — check
`STT_LANGUAGE_CODE`. Ground truth for what the robot heard is the `You:`
line in the terminal.

## "Move forward" answered by LLM

The parser needs the `You:` transcript to actually contain the command. If
the mic heard something else, the command falls through to the chat model.
Check the `You:` line; if it shows the right words, look for
`Nexus.Parser: Movement parsed` in the log.

## Face enrollment captures nothing

- Look for `Enroll frame N/36: WxH brightness=B faces=F` log lines.
- `brightness` near 0 → dark room / camera problem.
- `faces=0` with normal brightness → move closer (face must be ≥60 px),
  face the camera, good light. Four cascades are tried per frame; it's
  quite forgiving.
- Enrollment only records when **exactly one** face is visible.
- Recognition failing after a successful enroll → enroll again in better
  light (more varied samples = better LBPH model).

## Weather TLS errors

wttr.in serves an expired TLS certificate — the weather provider was
replaced with Open-Meteo (geocoding + forecast + WMO code map, IP
geolocation via ipapi.co → ip-api.com fallback). If `WEATHER_LOCATION` is
empty it auto-locates by IP.

## TTS silent

Check `aplay -l` and set `TTS_DEVICE` to a listed device (or `default`).
Test manually:

```bash
speaker-test -c2 -twav
```
