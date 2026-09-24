# 🛤️ Project Journey

The honest log of how this robot came together — including every wall we
hit. Each of these is documented as a fix in
[TROUBLESHOOTING.md](TROUBLESHOOTING.md); this is the story version.

## Phase 1 — A single 4,000-line script

The robot started as one large script, developed on the Pi over SSH.
Voice in, voice out, motor movement, a pygame face — it worked, and
that's what mattered. But every change meant scrolling through thousands
of lines, and every "quick test" was a full robot boot.

## Phase 2 — Refactoring into a package + tests

The monolith was split into the `nexus/` package: one module per
subsystem, a single `config.py` where every setting became an
environment variable. A pytest suite grew alongside it until it covered
**302 tests** — parser grammar, safety state machines, motor semantics,
navigation math, vision validation. From then on, every fix came with a
regression test.

## Phase 3 — Vision

- An offline TFLite object detector (SSD-MobileNet, COCO classes) for
  fast local answers.
- A cloud vision path (multimodal LLM over an OpenAI-compatible API) for
  descriptions and questions.
- "Find the bottle" navigation combining both: locate → turn → approach
  with obstacle checks → announce arrival.

## Phase 4 — The bring-up war stories

Things that actually happened, roughly in order:

1. **OpenCV on a 32-bit Pi** — pip tried compiling OpenCV from source
   (hours, then failure). The fix: piwheels-pinned
   `opencv-contrib-python-headless==4.10.0.84`. Then OpenCV 5 wheels
   shipped *empty cascade data* and face detection silently died.
2. **numpy 2 vs system picamera2/tflite** — a working camera broke after
   an install because the venv's numpy shadowed the system one the C
   extensions were built against. Pinned `numpy<2`.
3. **Camera colors inverted** — blue looked yellow in vision answers.
   picamera2's format names are the *reverse* of the byte order they
   return (a documented libcamera quirk). Solution: request RGB888 to
   get real BGR.
4. **Weather TLS errors** — the old provider served an expired TLS cert;
   weather was rebuilt on Open-Meteo with IP geolocation.
5. **API credits** — a `402 Payment Required` from Sarvam mid-demo (top
   up, it recovers). Later a `403` from a hand-typed key with a missing
   character. All keys went into `~/.bashrc` after that.
6. **The STT circuit breaker** — after repeated failures the robot went
   deaf *by design* (open → 60 s → half-open probe). Scary until you
   read the log.
7. **One motor side wouldn't go backward** — the bring-up saga: swapped
   wires, replaced jumpers, probed every GPIO, wrote
   `motor_finder.py` to sweep candidate pins, and finally did the 3.3 V
   touch test with `enable_hold.py`. Verdict: **the Pi's physical pin 37
   is dead**. The backward signal moved to GPIO 19 (pin 35) — and the
   code gained env-var pin remapping (`NEXUS_MOTOR_B_IN4=19`) plus a
   software channel-swap flag (`NEXUS_MOTOR_SWAP_AB`) so no future
   wiring surprise needs a code rebuild.
8. **The wake word** — "hey Nexus" transcribed as "hey macus", "hey
   nex", "lexus". Fixed with fuzzy matching (edit distance ≤ 3).

## Phase 5 — Single-file deploy

For the Pi, `scripts/build_combined.py` generates
`nexus_all_in_one.py` — one file, 6,400+ lines, same 302 tests pass
against it. No venv package juggling on the robot itself.

## Phase 6 — Science Spark 2026

- Replies switched to Gujarati (`NEXUS_REPLY_LANGUAGE=Gujarati`); TTS
  auto-detects the script of each spoken line.
- A Gujarati startup welcome was added for the event — and made
  editable at runtime via `greeting.txt` or `NEXUS_STARTUP_GREETING`,
  because event scripts change the night before.

## What we'd do differently

- Put env keys in `~/.bashrc` on day one (so many 401/403s were typos).
- Pin the OpenCV/numpy versions in the first install.
- Write the motor bring-up scripts (`tools/`) before the first motor
  failure, not during it.
