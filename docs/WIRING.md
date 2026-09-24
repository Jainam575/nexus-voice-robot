# 🔌 Wiring Guide

## Bill of materials

- Raspberry Pi 4 (32-bit Raspberry Pi OS Bookworm, Python 3.11)
- Raspberry Pi Camera Module (any revision — picamera2)
- USB microphone
- Speaker (3.5 mm jack or USB)
- 3.5" SPI TFT touchscreen with XPT2046 touch controller (the robot's "face")
- 2× L298N dual H-bridge motor driver boards
- 4× DC gear motors + wheels (4WD skid steer)
- Optional: HC-SR04 (or similar) ultrasonic/ToF distance sensor for collision safety

## GPIO map

> Pin numbers are **physical** pins on the 40-pin header; GPIO numbers are BCM.

### Motors (two L298N boards, one per side)

| GPIO | Physical pin | L298N input | Purpose |
|---|---|---|---|
| 5 | 29 | Board A ENA (or ENB) | Left/Right side A enable — PWM speed |
| 6 | 31 | Board A IN1 (or IN3) | Side A forward |
| 12 | 32 | Board A IN2 (or IN4) | Side A backward |
| 13 | 33 | Board B ENA (or ENB) | Side B enable — PWM speed |
| 16 | 36 | Board B IN1 (or IN3) | Side B forward |
| **19** | **35** | Board B IN2 (or IN4) | Side B backward |

> ⚠️ **Why GPIO 19 and not GPIO 26?** Our specific Pi has a dead GPIO 26
> (physical pin 37) — discovered during bring-up with `tools/motor_probe.py`.
> The default pin in the code is therefore 19 (physical pin 35, the pin
> between 33 and 37). If your Pi is healthy, just run with
> `NEXUS_MOTOR_B_IN4=26`.

### Collision sensor (optional)

| GPIO | Physical pin | Purpose |
|---|---|---|
| 20 | 38 | TRIG |
| 21 | 40 | ECHO |

Enable with `NEXUS_COLLISION_SENSOR=1` and `COLLISION_SENSOR_TYPE=ultrasonic`.

### Display (occupied — do not use for motors)

The 3.5" SPI display uses GPIO **17, 24, 25, 27, 8, 9, 10, 11, 7**.

## Direction logic

Each side needs two direction inputs; the enable pin carries PWM (speed):

```python
forward : IN1/IN3 = HIGH, IN2/IN4 = LOW    (both sides)
backward: IN1/IN3 = LOW,  IN2/IN4 = HIGH   (both sides)
left    : side A backward, side B forward
right   : side A forward,  side B backward
```

Because the two motors of a side are mirrored, "forward" means opposite
electrical polarity per side — the code handles this; just wire both motors
of a side in parallel to one channel's outputs.

## Everything is remappable in software

All six motor pins are env vars — no code changes needed:

```bash
export NEXUS_MOTOR_A_EN=5
export NEXUS_MOTOR_A_IN1=6
export NEXUS_MOTOR_A_IN2=12
export NEXUS_MOTOR_B_EN=13
export NEXUS_MOTOR_B_IN3=16
export NEXUS_MOTOR_B_IN4=19
```

If `turn left` / `turn right` come out mirrored (channel A/B wired to the
opposite sides of the robot), don't rewire — run with:

```bash
export NEXUS_MOTOR_SWAP_AB=1
```

## Bring-up procedure (recommended order)

1. **Per-channel test** — `python tools/motor_test.py`
   Runs each channel forward/backward separately. Any channel that only
   works in one direction has a loose direction wire.
2. **Pin probe** — `python tools/motor_probe.py`
   Turns each direction pin on, one at a time. Tells you exactly which
   pin→input pairing is broken.
3. **Wire finder** — `python tools/motor_finder.py`
   If a wire seems to be nowhere: cycles nearby free GPIOs one at a time
   so you can see where a stray wire actually landed.
4. **3.3V test** — `python tools/enable_hold.py`
   Holds the enables on; touch a direction wire to physical pin 1 (3.3 V).
   If the motor spins, the wire + driver are fine and the fault is on the
   Pi side. If not, reseat the wire at both ends (or replace it).

## Lessons learned the hard way

- **Pins die.** One GPIO on our Pi (physical pin 37) stopped driving. The
  probe/finder scripts above are how we isolated it in minutes.
- **Jumpers break internally** while looking perfect. Always try a second
  wire before blaming the board.
- **Power off before moving wires.** Hot-plugging jumpers can short two
  GPIOs for a split second — enough to kill a pin.
- You never need to reboot the Pi for a wire change — power off, rewire,
  power on, rerun the test script.
