# 🍓 Raspberry Pi Setup — from a blank SD card

Everything you need to go from an untouched Raspberry Pi 4 to a robot-ready
system. Once this guide is done, continue with [SETUP.md](SETUP.md) for the
robot software itself.

## 1. What you need

- Raspberry Pi 4 (a Pi 3/5 works too; the wheel pins in this repo were
  verified on a Pi 4)
- microSD card, **16 GB or larger**, class 10 / A1
- Official 5 V / 3 A USB-C power supply (the Pi is picky about this)
- A computer with a microSD card reader
- USB microphone + speaker (or a USB headset)
- Raspberry Pi Camera Module
- WiFi network (2.4 GHz works best with the Pi's antenna)

## 2. Flash the OS — Raspberry Pi Imager

1. Download **Raspberry Pi Imager** from
   [rpf.io/imager](https://www.raspberrypi.com/software/) and install it
   on your computer.
2. Click **Choose Device** → **Raspberry Pi 4**.
3. Click **Choose OS** → **Raspberry Pi OS (other)** →
   **Raspberry Pi OS (32-bit)** — the one *with* desktop.
   - Why 32-bit? Every pinned wheel in this repo
     (`opencv-contrib-python-headless==4.10.0.84`, `numpy<2` from
     piwheels) was verified on 32-bit Bookworm (armv7l). The 64-bit OS
     also works, but the pins were not tested there.
   - Why "with desktop"? The robot's animated face (pygame) draws on the
     desktop display.
4. Insert the microSD card, click **Choose Storage**, select it.
5. Click **Next** → **Edit Settings** (or the gear icon) and set:

   | Setting | Value |
   |---|---|
   | Hostname | `nexus` |
   | Username / password | your choice (we use `jainam`) |
   | Enable SSH | ✅ ON, allow password authentication |
   | WiFi | your SSID + password, wireless country `IN` |
   | Locale / timezone | `Asia/Kolkata`, keyboard for your language |

6. **Save** → confirm erasing the card → wait ~5–10 minutes.

Configuring SSH + WiFi in the Imager means you never need to connect a
monitor or keyboard to the Pi — it boots headless and you SSH in.

## 3. First boot and SSH

Boot the Pi with the card inserted (no screen needed). Give it 2–3
minutes, then from your computer:

```bash
ssh jainam@nexus.local        # or ssh jainam@<ip from your router page>
```

From a phone, any SSH app (Termius, JuiceSSH, the built-in SSH Shell app)
works the same way — that's how this robot was developed.

If `nexus.local` doesn't resolve, find the Pi's IP in your router's client
list and use that instead.

## 4. First-login housekeeping

```bash
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

## 5. raspi-config essentials

```bash
sudo raspi-config
```

- **Interface Options → Camera** → enabled (the modern stack — no legacy
  camera mode needed, the code uses picamera2/libcamera)
- **Interface Options → SPI** → enabled (the face display needs it; the
  display driver usually enables it itself, but set it now anyway)
- **System Options → Boot / Auto Login** → **Desktop, automatically logged
  in** (the face renders on the desktop)
- **Localisation Options** → timezone `Asia/Kolkata`
- **Advanced Options → Audio** → the output your speaker is on
  (headphone jack vs HDMI vs USB)

Reboot after changing these.

## 6. Test the camera

```bash
rpicam-still -o /tmp/test.jpg     # Bookworm's camera tool
```

No error = camera OK. If it fails: power off, reseat the ribbon cable
(blue side toward the USB ports, into the **CAM** port, not the DSI
port), and check the small lock tab is pushed back in.

## 7. Face display driver (3.5\" SPI TFT)

The "3.5inch RPi Display" needs a vendor driver that sets up the SPI
framebuffer:

1. Power the Pi off. Wire the display to the GPIO header with the jumper
   wires — pinout in [WIRING.md](WIRING.md) (eight wires, no touch
   needed).
2. Boot and SSH in. Install the driver from the **seller's wiki** for your
   exact board — it's usually a one-line download that enables the SPI
   overlay in `/boot/firmware/config.txt` and reboots the Pi with the
   desktop mirrored to the 3.5\" screen. (Waveshare calls theirs
   "LCD-show"; most generic "3.5inch RPi Display" boards use the same
   family of drivers.)
3. After it reboots, the desktop should appear on the little screen.

Keep the driver page bookmarked — it also tells you how to calibrate
touch (not needed for this robot) and how to revert to HDMI if you ever
need a big screen for debugging.

## 8. Audio check

```bash
arecord -l                       # list recording (mic) devices
aplay -l                         # list playback devices
speaker-test -c2 -twav           # sound from the speaker?
arecord -D plughw:2,0 -f cd -d 3 /tmp/t.wav && aplay /tmp/t.wav   # mic test
```

Note the card numbers — they become `MIC_DEVICE` and `TTS_DEVICE` in the
robot's environment (`plughw:<card>,0` / `hw:<card>,0`).

## 9. Power wiring (important!)

- The Pi runs from its USB-C supply.
- The **motors run from the battery pack through the L298N drivers,
  never from the Pi's 5 V rail** — motors on the Pi's supply cause
  brownouts and random crashes.
- Connect a **common ground**: battery minus, L298N GND and Pi GND must
  all be connected together.

## 10. Next step

The system is ready — continue with [SETUP.md](SETUP.md) to install the
robot software, set your API keys, and run Nexus.
