#!/usr/bin/env python3
"""enable_hold.py — holds both motor channels ENABLED at full power.

RUN WITH THE ROBOT PROGRAM STOPPED. It does nothing but enable the motors;
Ctrl+C to exit. While it's running, do the wire test:

1. Find the left board's BACKWARD input wire (the input wire that is NOT
   in pin 36).
2. Touch its metal tip to the Pi's 3.3V pin — physical pin 1, the CORNER
   pin at the end of the header near the SD card slot (pin 2 is its
   neighbor; pin 1 is the one on the outer edge, closest to the corner).
3. Watch the left pair:
   - SPINS BACKWARD -> wire + driver input are fine; the problem is only
     WHERE the wire sits on the Pi. Seat it firmly in pin 35 and retest.
   - NOTHING -> the wire or the driver input is bad. Reseat the wire at
     BOTH ends (Pi and driver board) and touch 3.3V again. Still nothing =
     that input on the driver board is damaged.
"""
import time

import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for p in (5, 13):
    GPIO.setup(p, GPIO.OUT)
    GPIO.output(p, 1)

print("Both motor channels ENABLED at full power.")
print("Now touch the left board's BACKWARD input wire to 3.3V (physical pin 1).")
print("Ctrl+C when done.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    GPIO.output(5, 0)
    GPIO.output(13, 0)
    GPIO.cleanup()
    print("Motors disabled. Done.")
