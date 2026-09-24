#!/usr/bin/env python3
"""motor_test.py — isolate motor wiring problems on the Nexus robot.

RUN THIS WITH THE ROBOT PROGRAM STOPPED (it owns the GPIO):
    sudo pkill -f test15.py      # or whatever the robot file is called
    cd ~/Downloads
    source ai_env/bin/activate
    python motor_test.py

Prop the robot up so the wheels are off the ground first.

It tests each driver channel in each direction, in the robot's own
polarity, then does a full forward and backward. Watch which test has
a side that doesn't move — that names the exact wire to fix:

    Channel A (side 1):  EN=GPIO5   IN1=GPIO6   IN2=GPIO12
    Channel B (side 2):  EN=GPIO13  IN3=GPIO16  IN4=GPIO26

    - A-side doesn't run in test 2  -> check the wire Pi GPIO12 -> driver A-IN2
    - B-side doesn't run in test 4  -> check the wire Pi GPIO26 -> driver B-IN4
    - A-side weak/slow in test 1    -> check Pi GPIO5/6 wires + A motor terminals
    - B-side weak/slow in test 3    -> check Pi GPIO13/16 wires + B motor terminals
"""
import time

import RPi.GPIO as GPIO

A_EN, A_IN1, A_IN2 = 5, 6, 12     # channel A (one side)
B_EN, B_IN3, B_IN4 = 13, 16, 26   # channel B (other side)

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for p in (A_EN, A_IN1, A_IN2, B_EN, B_IN3, B_IN4):
    GPIO.setup(p, GPIO.OUT)

pwm_a = GPIO.PWM(A_EN, 1000)
pwm_b = GPIO.PWM(B_EN, 1000)
pwm_a.start(60)   # 60% duty — same idea as the robot's speed
pwm_b.start(60)


def stop_all():
    GPIO.output(A_IN1, 0); GPIO.output(A_IN2, 0)
    GPIO.output(B_IN3, 0); GPIO.output(B_IN4, 0)


def run(label, secs=2.5):
    print(f"  -> {label} for {secs}s ...")
    time.sleep(secs)
    stop_all()
    time.sleep(1.5)


try:
    print("MOTOR WIRING TEST — wheels off the ground!\n")

    print("Test 1: SIDE A FORWARD  (A_IN1 high)")
    GPIO.output(A_IN1, 1); GPIO.output(A_IN2, 0)
    run("SIDE A should be spinning forward")

    print("Test 2: SIDE A BACKWARD (A_IN2 high)  <-- your dead direction?")
    GPIO.output(A_IN1, 0); GPIO.output(A_IN2, 1)
    run("SIDE A should be spinning backward")

    print("Test 3: SIDE B FORWARD  (B_IN3 high)")
    GPIO.output(B_IN3, 1); GPIO.output(B_IN4, 0)
    run("SIDE B should be spinning forward")

    print("Test 4: SIDE B BACKWARD (B_IN4 high)  <-- your dead direction?")
    GPIO.output(B_IN3, 0); GPIO.output(B_IN4, 1)
    run("SIDE B should be spinning backward")

    print("Test 5: ROBOT FORWARD (both, same as 'move forward')")
    GPIO.output(A_IN1, 1); GPIO.output(A_IN2, 0)
    GPIO.output(B_IN3, 1); GPIO.output(B_IN4, 0)
    run("both sides forward — check they spin equally fast")

    print("Test 6: ROBOT BACKWARD (both, same as 'move backward')")
    GPIO.output(A_IN1, 0); GPIO.output(A_IN2, 1)
    GPIO.output(B_IN3, 0); GPIO.output(B_IN4, 1)
    run("both sides backward")

    print("DONE. Whichever side stayed still names the bad wire (see table above).")
finally:
    stop_all()
    pwm_a.stop(); pwm_b.stop()
    GPIO.cleanup()
