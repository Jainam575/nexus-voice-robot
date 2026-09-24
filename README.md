# 🤖 Nexus — Voice-Controlled AI Robot

**Nexus** is a fully voice-controlled AI robot built from scratch on a Raspberry Pi by **Jainam Soni and his team** at **Shree Muktjivan Vidyalaya, Isanpur (Ahmedabad)**, showcased at **Science Spark 2026**.

It listens for a wake word, understands natural-language commands in **English and Gujarati**, sees and describes the world through a camera, recognises people's faces, navigates to objects, moves around on four wheels with collision-aware safety logic, shows a live animated face with moods — and even opens the event with a Gujarati welcome speech.

---

## ✨ Features

| Area | What it does |
|---|---|
| 🎤 **Voice interaction** | Wake word ("hey Nexus" — fuzzy-matched against mishearings like "hey nex", "hey macus"), continuous listening, natural conversation with an LLM |
| 🗣️ **Bilingual** | Commands in English (`en-IN`), replies in **Gujarati** (or any language — one env var) |
| 👁️ **Vision** | Cloud vision via a multimodal LLM ("what do you see?") **plus** fast offline object detection (TFLite SSD-MobileNet, 80 classes) |
| 🧭 **Object navigation** | "Find the bottle" — vision-guided driving toward an object, with a cloud-VLM fallback when the offline detector can't see the target, plus obstacle checks before every forward move |
| 👤 **Face recognition** | Learns faces ("remember my face as Snehal"), recognises them later ("who am I?") using Haar cascade detection + LBPH, with multi-cascade fallbacks, size-normalised crops, and privacy-first storage (0600 permissions, per-person folders) |
| 🌦️ **Weather & news** | Live weather via Open-Meteo with IP geolocation fallback; news headlines via Google News RSS |
| 😊 **Animated face** | Pygame face on a 3.5" touchscreen with moods (happy/sad/neutral…), camera preview mode, and boot-time expressions |
| 🚗 **4WD movement** | Two L298N drivers, four DC motors, skid steering, blocking command API with watchdog + collision interrupt |
| 🛑 **Safety** | Voice safety stop ("STOP!"), collision sensor integration, safety listener thread, demo-mode confirmation gate, motor self-test |
| 🎮 **Games** | Rock–paper–scissors, trivia, and more, played entirely by voice |
| 😴 **Sleep / wake** | Falls asleep after ~3 minutes of silence, wakes on hearing its name |
| 🧪 **302 automated tests** | Full regression suite for every subsystem |

## 📸 How it works

```
            ┌────────────┐   USB mic    ┌──────────────┐
 voice ───▶ │  arecord   │───────────▶ │ Sarvam STT  │──▶ text
            └────────────┘             └──────────────┘
                                                          │
                          ┌───────────────────────────────┤
                          ▼                               ▼
                 ┌────────────────┐              ┌────────────────┐
                 │ Command parser │              │  Sarvam chat   │
                 │ (rules first)  │              │  (fallback)    │
                 └───────┬────────┘              └────────────────┘
             ┌───────────┼─────────────┬───────────────┐
             ▼           ▼             ▼               ▼
        ┌────────┐ ┌───────────┐ ┌───────────┐ ┌──────────────┐
        │ Motors │ │ Navigation│ │  Vision   │ │ Face recogn.  │
        └────────┘ └───────────┘ └───────────┘ └──────────────┘
             │           │             │               │
             └────── GPIO / camera / cloud APIs ───────┘

            ┌────────────┐  speaker  ┌──────────────┐
 text ───▶  │ Sarvam TTS │────────▶ │  aplay       │──▶ voice out
            └────────────┘          └──────────────┘
```

The full module map is in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## 🔧 Hardware

| Part | Details |
|---|---|
| Brain | Raspberry Pi 4 (32-bit Raspberry Pi OS, Python 3.11) |
| Camera | Raspberry Pi Camera Module (picamera2) |
| Mic | USB microphone (`plughw:2,0`) |
| Sound | Speaker via `aplay` (device configurable, e.g. `TTS_DEVICE=default`) |
| Face | 3.5" SPI touchscreen (XPT2046) |
| Drive | 2× L298N motor drivers, 4× DC gear motors (4WD, skid steering) |
| Safety | Optional ultrasonic/ToF collision sensor on GPIO 20/21 |

## ⚡ Quick start

```bash
git clone https://github.com/Jainam575/nexus-voice-robot.git
cd nexus-voice-robot

# Python deps (on the Pi)
python3 -m venv ai_env
source ai_env/bin/activate
pip install -r requirements.txt
# OpenCV with face-recognition + Haar cascades (32-bit Pis need the piwheels build):
pip install --only-binary :all: "opencv-contrib-python-headless==4.10.0.84" "numpy<2"

# Keys (put these in ~/.bashrc so they survive every SSH session)
export SARVAM_API_KEY="..."          # speech + chat (dashboard.sarvam.ai)
export NEXUS_VISION_API_KEY="..."    # cloud vision
export NEXUS_VISION_BASE_URL="https://openrouter.ai/api/v1"
export NEXUS_VISION_MODEL="meta-llama/llama-4-scout"
export STT_LANGUAGE_CODE="en-IN"     # commands
export NEXUS_REPLY_LANGUAGE="Gujarati"  # answers
export TTS_DEVICE="default"
export DISPLAY=:0

# Run (two ways)
python run_nexus.py            # package form (23 modules)
python nexus_all_in_one.py     # single-file build (identical behaviour)
```

The robot speaks its Gujarati startup greeting, then *"I am Nexus, an AI robot created from scratch by Jainam Soni and his team…"* and starts listening.

## 🗣️ Voice commands

- **"Hey Nexus"** — wake it from sleep (fuzzy-matched)
- **"move forward / backward / left / right"**, **"spin"**, **"stop"** — movement (durations and step counts supported: *"move forward for 3 seconds"*)
- **"find the bottle"** — vision-guided navigation to an object
- **"what do you see?"** (or **"શું દેખાય છે?"**) — cloud vision scene description
- **"what's the weather"**, **"news"**
- **"remember my face as <name>"**, **"who am I?"**, **"forget <name>"**
- **"demo"** → **"confirm"** — guided demo mode (weather + news + moves)
- **"play rock paper scissors"**, **"play trivia"** — games
- **"STOP!"** — immediate motor safety stop
- Anything else goes to the LLM for conversation

Full list: [`docs/COMMANDS.md`](docs/COMMANDS.md)

## 🔌 Wiring

| Pi GPIO | Physical pin | Goes to |
|---|---|---|
| 5 | 29 | Motor A enable (PWM) |
| 6 | 31 | Motor A forward |
| 12 | 32 | Motor A backward |
| 13 | 33 | Motor B enable (PWM) |
| 16 | 36 | Motor B forward |
| **19** | **35** | Motor B backward *(pin 37 / GPIO 26 is dead on our Pi — long story, see [docs/WIRING.md](docs/WIRING.md))* |
| 20 / 21 | 38 / 40 | Collision sensor trig / echo |
| — | — | 3.5" display uses GPIO 17, 24, 25, 27, 8, 9, 10, 11, 7 |

Every motor pin is overridable by env var (`NEXUS_MOTOR_B_IN4=19` etc.), and `NEXUS_MOTOR_SWAP_AB=1` swaps the two channels in software — so wiring mistakes are a config change, not a rebuild. Details: [`docs/WIRING.md`](docs/WIRING.md)

## ⚙️ Configuration (environment variables)

All settings are env vars — no code edits needed. Highlights (full list in [`docs/SETUP.md`](docs/SETUP.md)):

| Variable | Default | Meaning |
|---|---|---|
| `SARVAM_API_KEY` | — | Sarvam AI key (STT, TTS, chat) |
| `NEXUS_VISION_API_KEY` / `_BASE_URL` / `_MODEL` | — | Cloud vision (any OpenAI-compatible VLM, e.g. OpenRouter) |
| `NEXUS_VISION_MODE` | `auto` | `fast` = offline only, `cloud` = VLM only, `auto` = cloud if configured |
| `STT_LANGUAGE_CODE` | `en-IN` | Language the mic listens in |
| `NEXUS_REPLY_LANGUAGE` | — | e.g. `Gujarati` — all spoken answers switch language |
| `TTS_DEVICE` | `hw:1,0` | Audio out device |
| `NEXUS_STARTUP_GREETING` | built-in | Startup greeting text; empty string disables. A `greeting.txt` next to the script also overrides it |
| `NEXUS_MOTOR_*` | see wiring table | Per-pin GPIO remapping |
| `NEXUS_MOTOR_SWAP_AB` | `0` | Swap left/right channel mapping in software |
| `FACE_CONFIDENCE_THRESHOLD` | `80` | Lower = more lenient face matching |
| `NEXUS_CAMERA_SWAP` | `0` | Set to 1 if camera colours ever come out swapped |

## 📦 Repository layout

```
├── nexus/                 # source package (23 modules)
│   ├── main.py            #   voice loop, command routing, wake word
│   ├── stt.py / tts.py    #   Sarvam speech in/out + circuit breaker
│   ├── vision.py          #   TFLite + cloud vision
│   ├── navigation.py      #   vision-guided movement + VLM fallback
│   ├── face_recognition.py#   Haar + LBPH enrol/recognise
│   ├── motor.py           #   GPIO motor control, watchdog, safety
│   ├── face_display.py    #   pygame animated face
│   ├── audio.py           #   arecord/aplay, silence detection
│   └── ...                #   weather, news, games, mood, memory, ...
├── tests/                 # 302-test pytest suite
├── nexus_all_in_one.py    # single-file build of the whole robot
├── scripts/build_combined.py  # generates the single-file build
├── tools/                 # hardware bring-up & debugging scripts
│   ├── motor_test.py      #   per-channel motor isolation test
│   ├── motor_probe.py     #   pin-by-pin wiring probe
│   ├── motor_finder.py    #   hunts which pin a wire actually sits on
│   ├── enable_hold.py     #   enables motors for the 3.3V wire test
│   ├── motor2.py          #   original interactive f/b/l/r test
│   └── motor8.py          #   same, with the corrected GPIO 19 pin
└── docs/                  # wiring, setup, commands, troubleshooting,
                           # architecture, and the full project journey
```

## 🧪 Tests

```bash
pip install pytest
pytest tests/ -q
# 302 passed
```

The suite covers the parser, safety state machines, motor blocking semantics, navigation math, vision validation, games, memory, mood, and more — all hardware-mocked so it runs anywhere.

## 🩺 Troubleshooting

We hit (and fixed) a lot during this build — API credit errors, an OpenCV 5 wheel with no cascade files, a numpy 2.x vs picamera2 conflict, picamera2's inverted RGB/BGR naming, a dead GPIO pin, and a circuit breaker that made the robot go silently deaf. Every fix is documented with symptoms and solutions in [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## 🏫 Credits

Built by **Jainam Soni and team**, Shree Muktjivan Vidyalaya, Isanpur — for **Science Spark 2026**. 🙏 જય સ્વામિનારાયણ.

Powered by [Sarvam AI](https://sarvam.ai) (speech + chat), OpenRouter / Meta Llama 4 Scout (vision), OpenCV, TFLite, and pygame.

## 📄 License

MIT — see [LICENSE](LICENSE).
