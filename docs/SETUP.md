# 🛠️ Setup Guide

Tested on: Raspberry Pi 4, 32-bit Raspberry Pi OS (Bookworm), Python 3.11.

## 1. System packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git
# picamera2 + tflite (if not already present on your OS image):
sudo apt install -y python3-picamera2 python3-numpy
```

## 2. Virtual environment

```bash
cd ~/Downloads   # or wherever you cloned the repo
python3 -m venv ai_env
source ai_env/bin/activate
```

> If you created the venv with `--system-site-packages`, system packages
> like `picamera2` and `tflite_runtime` are visible inside it. This is what
> we do — but note the numpy warning below.

## 3. Python dependencies

```bash
pip install -r requirements.txt
```

### ⚠️ The OpenCV / numpy trap (read this)

On a **32-bit Pi** there is no prebuilt OpenCV wheel on PyPI; pip falls back
to **compiling OpenCV from source** (hours, usually fails). Your pip is
already configured to use [piwheels](https://www.piwheels.org), which has
prebuilt wheels for specific versions. Use exactly this:

```bash
pip install --only-binary :all: "opencv-contrib-python-headless==4.10.0.84" "numpy<2"
```

Why these pins:

- **`opencv-contrib-python-headless`** — includes the `cv2.face` (LBPH)
  recognizer, the Haar cascade XML files, and doesn't need X11 libraries.
- **Version 4.10** — has an armv7l piwheels wheel; 4.14+ currently does not.
- **OpenCV 5.x** ships *empty* cascade data (`cv2/data/` has no XMLs) —
  face detection silently fails.
- **`numpy<2`** — system-compiled packages (`picamera2`, `tflite_runtime`)
  are built against numpy 1.x; installing numpy 2 in the venv shadows the
  system one and breaks the camera and TFLite at import.

## 4. TFLite object detection

Drop the COCO SSD-MobileNet model files next to the robot code:

- `detect.tflite`
- `coco_labels.txt` (or `labels.txt`)

If missing, the robot still runs — local detection is disabled and vision
falls back to the cloud VLM.

## 5. Environment variables

Put these in `~/.bashrc` so every SSH session has them (typing keys by hand
in fresh sessions caused us endless 401/403 typos):

```bash
export SARVAM_API_KEY="your-key"                      # dashboard.sarvam.ai
export NEXUS_VISION_API_KEY="your-openrouter-key"
export NEXUS_VISION_BASE_URL="https://openrouter.ai/api/v1"
export NEXUS_VISION_MODEL="meta-llama/llama-4-scout"
export STT_LANGUAGE_CODE="en-IN"                       # command language
export NEXUS_REPLY_LANGUAGE="Gujarati"                 # answer language
export TTS_DEVICE="default"                             # speaker
export DISPLAY=:0                                       # face display
# optional:
export NEXUS_MOTOR_B_IN4=19        # if pin 37 is dead on your Pi, else omit
export NEXUS_MOTOR_SWAP_AB=1       # only if turns are mirrored
```

Then `source ~/.bashrc` (or open a new SSH session).

### Full variable reference

| Variable | Default | Meaning |
|---|---|---|
| `SARVAM_API_KEY` | — | Sarvam AI (STT + TTS + chat). Required. |
| `SARVAM_STT_MODEL` | `saaras:v3` | STT model |
| `SARVAM_CHAT_MODEL` | `sarvam-105b-conversations` | Chat model |
| `SARVAM_VISION_MODEL` | `gemma4` | Sarvam vision (if whitelisted) |
| `NEXUS_VISION_API_KEY` | — | Alternate/primary vision VLM key |
| `NEXUS_VISION_BASE_URL` | — | e.g. `https://openrouter.ai/api/v1` |
| `NEXUS_VISION_MODEL` | `qwen/qwen3.6-27b` | VLM model name |
| `NEXUS_VISION_MODE` | `auto` | `fast` / `cloud` / `auto` |
| `STT_LANGUAGE_CODE` | `en-IN` | Listening language |
| `TTS_LANGUAGE_CODE` | `en-IN` | Fallback TTS language (Gujarati text auto-detects `gu-IN`) |
| `NEXUS_REPLY_LANGUAGE` | — | Forces all LLM replies into this language |
| `NEXUS_VOICE` | `shubh` | Bulbul TTS voice |
| `TTS_DEVICE` | `hw:1,0` | `aplay` device |
| `MIC_DEVICE` | `plughw:2,0` | `arecord` device |
| `NEXUS_STARTUP_GREETING` | built-in | Startup greeting; empty disables. `greeting.txt` next to the script also overrides |
| `NEXUS_SLEEP_THRESHOLD` | `180` | Seconds of silence before sleeping |
| `NEXUS_VISION_CACHE_AGE` | `2.0` | Seconds a captured frame is reused |
| `NEXUS_MOTOR_A_EN/_IN1/_IN2`, `NEXUS_MOTOR_B_EN/_IN3/_IN4` | 5/6/12, 13/16/19 | Motor GPIO pins |
| `NEXUS_MOTOR_SWAP_AB` | `0` | Swap channels A/B in software |
| `NEXUS_MOTOR_SELF_TEST` | `0` | Run motor self-test at boot |
| `MOTOR_COMMAND_TIMEOUT` | `10.0` | Max seconds per movement |
| `MOTOR_WATCHDOG_TIMEOUT` | `5.0` | Motor watchdog |
| `NEXUS_COLLISION_SENSOR` | `0` | Enable collision sensor |
| `COLLISION_SENSOR_TYPE` | `none` | `ultrasonic`/`tof`/`bumper` |
| `COLLISION_GPIO_TRIG/_ECHO` | `20`/`21` | Collision sensor pins |
| `FACE_CONFIDENCE_THRESHOLD` | `80` | LBPH distance threshold (lower = stricter) |
| `FACE_ENROLL_SAMPLES` | `12` | Photos captured per enrollment |
| `NEXUS_FACE_STORAGE` | `1` | Allow storing face data |
| `FACE_DATA_RETENTION` | `0` | Max samples kept per person |
| `NEXUS_CAMERA_SWAP` | `0` | Force R/B channel swap (driver quirks) |
| `NEXUS_DEMO_CONFIRMATION` | `1` | Require "confirm" for demo mode |
| `WEATHER_LOCATION` | auto (IP) | e.g. `"Ahmedabad"` |
| `NEWS_TOPIC` | general | News topic filter |
| `FACE_WIDTH` / `FACE_HEIGHT` / `FACE_FULLSCREEN` | 480/320/1 | Face display geometry |

## 6. Run it

```bash
python run_nexus.py        # package form
python nexus_all_in_one.py # single-file build — identical
```

Boot checklist (printed at startup): Microphone PASS, Camera OK, GPIO OK,
TFLite OK, STT/TTS/Chat OK, Face Recog OK. Then it speaks the Gujarati
greeting and starts listening.

## 7. Audio device sanity

```bash
arecord -l                 # find your mic card number
aplay -l                  # find your speaker
# test the mic:
arecord -D plughw:2,0 -f cd -d 3 /tmp/test.wav && aplay /tmp/test.wav
```

Set `MIC_DEVICE` / `TTS_DEVICE` to match your hardware.

## 8. Startup greeting

The robot speaks a Gujarati welcome (written for Science Spark 2026) at
every boot. To change it, create `greeting.txt` next to the script with any
text — one line per spoken sentence. To disable:
`export NEXUS_STARTUP_GREETING=""`.
