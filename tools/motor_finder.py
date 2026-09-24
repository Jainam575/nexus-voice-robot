#!/usr/bin/env python3
"""motor_finder.py — finds which Pi pin the left-pair BACKWARD wire is on.

RUN WITH THE ROBOT PROGRAM STOPPED and wheels off the ground:

    sudo pkill -f test15.py
    cd ~/Downloads && source ai_env/bin/activate
    python motor_finder.py

It turns each candidate GPIO on, one at a time for 3 seconds, with both
motor enables at full power. WATCH THE MOTORS during every test and note
the number on screen when the LEFT pair spins backward.

If the display flickers during one of the last two tests, that's normal.
"""
import time

import RPi.GPIO as GPIO

# (GPIO number, physical pin number on the 40-pin header)
CANDIDATES = [
    (2, 3),
    (3, 5),
    (4, 7),
    (18, 12),
    (22, 15),
    (23, 16),     # where the wire SHOULD be
    (19, 35),
    (24, 18),     # note: display may flicker on this one
]

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

for gpio, _ in CANDIDATES:
    GPIO.setup(gpio, GPIO.OUT)
    GPIO.output(gpio, 0)

# enable both motor channels at full power
for en in (5, 13):
    GPIO.setup(en, GPIO.OUT)
    GPIO.output(en, 1)

try:
    print("MOTOR WIRE FINDER — watch the LEFT pair, wheels off the ground!\n")
    for gpio, phys in CANDIDATES:
        print(f">>> GPIO {gpio:2d} (physical pin {phys:2d}) HIGH for 3 seconds ...")
        GPIO.output(gpio, 1)
        time.sleep(3)
        GPIO.output(gpio, 0)
        time.sleep(1.5)
    print("\nDONE — tell me the GPIO number that made the left pair spin backward.")
    print("If NOTHING spun the left pair backward, the wire is disconnected")
    print("somewhere between the Pi and the driver board — check the driver end.")
finally:
    GPIO.cleanup()
