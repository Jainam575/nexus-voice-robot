#!/usr/bin/env python3
"""motor_probe.py — tests each motor direction pin one at a time.

RUN WITH THE ROBOT PROGRAM STOPPED and wheels off the ground:

    sudo pkill -f test15.py
    cd ~/Downloads && source ai_env/bin/activate
    python motor_probe.py

Expected results (working wiring):
    A_IN1  -> right pair, forward
    A_IN2  -> right pair, backward
    B_IN3  -> left pair, forward
    B_IN4  -> left pair, backward

A line that does nothing = that wire/pin/driver input is broken.
"""
import time

import RPi.GPIO as GPIO

PINS = {
    "A_IN1": 6,    # physical pin 31
    "A_IN2": 12,   # physical pin 32
    "B_IN3": 16,   # physical pin 36
    "B_IN4": 23,   # physical pin 16 (pin 37 is dead on this Pi)
}
PHYSICAL = {5: 29, 6: 31, 12: 32, 13: 33, 16: 36, 23: 16}

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

for pin in PINS.values():
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, 0)

# enable both channels at full power so a direction pin shows movement
for en in (5, 13):
    GPIO.setup(en, GPIO.OUT)
    GPIO.output(en, 1)

try:
    print("MOTOR PIN PROBE — wheels off the ground!\n")
    for name, pin in PINS.items():
        print(f">>> {name} (GPIO {pin}, physical pin {PHYSICAL[pin]}) HIGH for 3 seconds ...")
        GPIO.output(pin, 1)
        time.sleep(3)
        GPIO.output(pin, 0)
        time.sleep(1.5)
    print("\nDONE — any pin that moved nothing is the broken wire.")
finally:
    GPIO.cleanup()
