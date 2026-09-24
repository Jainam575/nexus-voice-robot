#!/usr/bin/env python3

"""
L298N Motor Driver Test Script for Raspberry Pi 4 Model B
Controls two DC motors with commands: forward, backward, left, right, spin

UPDATED: GPIO pins changed to avoid conflict with 3.5" RPi Display (XPT2046)
"""

import RPi.GPIO as GPIO
import time
import sys

# L298N Motor Driver GPIO Pin Configuration (UPDATED - No conflict with 3.5" display)
# These BCM pins map to physical pins 29, 31, 32, 33, 36, 16

# Motor A (Left Motor pair)
MOTOR_A_EN = 5    # Enable pin for Motor A (PWM)   - Physical pin 29
MOTOR_A_IN1 = 6   # Input 1 for Motor A            - Physical pin 31
MOTOR_A_IN2 = 12  # Input 2 for Motor A            - Physical pin 32

# Motor B (Right Motor pair)
MOTOR_B_EN = 13   # Enable pin for Motor B (PWM)   - Physical pin 33
MOTOR_B_IN3 = 16  # Input 3 for Motor B            - Physical pin 36
MOTOR_B_IN4 = 23  # Input 4 for Motor B            - Physical pin 16 (pin 37 is DEAD on this Pi)

# Motor speed (0-100)
DEFAULT_SPEED = 70

class MotorController:
    def __init__(self):
        """Initialize GPIO pins and PWM for motor control"""
        # Set GPIO mode
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup GPIO pins
        GPIO.setup(MOTOR_A_IN1, GPIO.OUT)
        GPIO.setup(MOTOR_A_IN2, GPIO.OUT)
        GPIO.setup(MOTOR_A_EN, GPIO.OUT)
        
        GPIO.setup(MOTOR_B_IN3, GPIO.OUT)
        GPIO.setup(MOTOR_B_IN4, GPIO.OUT)
        GPIO.setup(MOTOR_B_EN, GPIO.OUT)
        
        # Initialize PWM on enable pins (1000 Hz frequency)
        self.pwm_a = GPIO.PWM(MOTOR_A_EN, 1000)
        self.pwm_b = GPIO.PWM(MOTOR_B_EN, 1000)
        
        # Start PWM with 0 duty cycle
        self.pwm_a.start(0)
        self.pwm_b.start(0)
        
        print("Motor controller initialized!")
        print(f"Motor A (Left):  EN={MOTOR_A_EN}(pin29), IN1={MOTOR_A_IN1}(pin31), IN2={MOTOR_A_IN2}(pin32)")
        print(f"Motor B (Right): EN={MOTOR_B_EN}(pin33), IN3={MOTOR_B_IN3}(pin36), IN4={MOTOR_B_IN4}(pin37)")
        print("Display pins (17, 24, 25, 27, 8, 9, 10, 11, 7) are safe!\n")
    
    def set_motor_a(self, direction, speed):
        """
        Control Motor A (Left pair)
        direction: 1 (forward), -1 (backward), 0 (stop)
        speed: 0-100
        """
        if direction == 1:  # Forward
            GPIO.output(MOTOR_A_IN1, GPIO.HIGH)
            GPIO.output(MOTOR_A_IN2, GPIO.LOW)
        elif direction == -1:  # Backward
            GPIO.output(MOTOR_A_IN1, GPIO.LOW)
            GPIO.output(MOTOR_A_IN2, GPIO.HIGH)
        else:  # Stop
            GPIO.output(MOTOR_A_IN1, GPIO.LOW)
            GPIO.output(MOTOR_A_IN2, GPIO.LOW)
        
        self.pwm_a.ChangeDutyCycle(speed)
    
    def set_motor_b(self, direction, speed):
        """
        Control Motor B (Right pair)
        direction: 1 (forward), -1 (backward), 0 (stop)
        speed: 0-100
        """
        if direction == 1:  # Forward
            GPIO.output(MOTOR_B_IN3, GPIO.HIGH)
            GPIO.output(MOTOR_B_IN4, GPIO.LOW)
        elif direction == -1:  # Backward
            GPIO.output(MOTOR_B_IN3, GPIO.LOW)
            GPIO.output(MOTOR_B_IN4, GPIO.HIGH)
        else:  # Stop
            GPIO.output(MOTOR_B_IN3, GPIO.LOW)
            GPIO.output(MOTOR_B_IN4, GPIO.LOW)
        
        self.pwm_b.ChangeDutyCycle(speed)
    
    def move_forward(self, speed=DEFAULT_SPEED, duration=None):
        """Move both motor pairs forward"""
        print(f"Moving forward at speed {speed}%")
        self.set_motor_a(1, speed)
        self.set_motor_b(1, speed)
        if duration:
            time.sleep(duration)
            self.stop()
    
    def move_backward(self, speed=DEFAULT_SPEED, duration=None):
        """Move both motor pairs backward"""
        print(f"Moving backward at speed {speed}%")
        self.set_motor_a(-1, speed)
        self.set_motor_b(-1, speed)
        if duration:
            time.sleep(duration)
            self.stop()
    
    def turn_left(self, speed=DEFAULT_SPEED, duration=None):
        """Turn left - left pair backward, right pair forward"""
        print(f"Turning left at speed {speed}%")
        self.set_motor_a(-1, speed)
        self.set_motor_b(1, speed)
        if duration:
            time.sleep(duration)
            self.stop()
    
    def turn_right(self, speed=DEFAULT_SPEED, duration=None):
        """Turn right - left pair forward, right pair backward"""
        print(f"Turning right at speed {speed}%")
        self.set_motor_a(1, speed)
        self.set_motor_b(-1, speed)
        if duration:
            time.sleep(duration)
            self.stop()
    
    def spin_around(self, speed=DEFAULT_SPEED, duration=2):
        """Spin 360 degrees - both pairs in opposite directions"""
        print(f"Spinning around at speed {speed}%")
        self.set_motor_a(1, speed)
        self.set_motor_b(-1, speed)
        time.sleep(duration)
        self.stop()
    
    def stop(self):
        """Stop both motor pairs"""
        print("Stopping motors")
        self.set_motor_a(0, 0)
        self.set_motor_b(0, 0)
    
    def cleanup(self):
        """Clean up GPIO"""
        self.stop()
        self.pwm_a.stop()
        self.pwm_b.stop()
        GPIO.cleanup()
        print("GPIO cleaned up")


def interactive_mode(controller):
    """Interactive command mode for testing motors"""
    print("\n" + "="*50)
    print("Motor Test - Interactive Mode")
    print("="*50)
    print("Commands:")
    print("  f - Move Forward")
    print("  b - Move Backward")
    print("  l - Turn Left")
    print("  r - Turn Right")
    print("  s - Spin Around")
    print("  x - Stop")
    print("  q - Quit")
    print("="*50 + "\n")
    
    try:
        while True:
            cmd = input("Enter command (f/b/l/r/s/x/q): ").strip().lower()
            
            if cmd == 'f':
                controller.move_forward(duration=2)
            elif cmd == 'b':
                controller.move_backward(duration=2)
            elif cmd == 'l':
                controller.turn_left(duration=1)
            elif cmd == 'r':
                controller.turn_right(duration=1)
            elif cmd == 's':
                controller.spin_around()
            elif cmd == 'x':
                controller.stop()
            elif cmd == 'q':
                print("Exiting...")
                break
            else:
                print("Invalid command! Use f/b/l/r/s/x/q")
    
    except KeyboardInterrupt:
        print("\nInterrupted by user")


def demo_sequence(controller):
    """Run a demonstration sequence of all movements"""
    print("\n" + "="*50)
    print("Running Demo Sequence")
    print("="*50 + "\n")
    
    try:
        print("Test 1: Forward")
        controller.move_forward(speed=60, duration=2)
        time.sleep(1)
        
        print("\nTest 2: Backward")
        controller.move_backward(speed=60, duration=2)
        time.sleep(1)
        
        print("\nTest 3: Turn Right")
        controller.turn_right(speed=60, duration=1.5)
        time.sleep(1)
        
        print("\nTest 4: Turn Left")
        controller.turn_left(speed=60, duration=1.5)
        time.sleep(1)
        
        print("\nTest 5: Spin Around")
        controller.spin_around(speed=60, duration=2)
        time.sleep(1)
        
        print("\nDemo sequence completed!")
        
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
        controller.stop()


def main():
    """Main function"""
    print("L298N Motor Driver Test Script (Display Compatible)")
    print("Press Ctrl+C to exit at any time\n")
    
    # Initialize motor controller
    controller = MotorController()
    
    try:
        # Check command line arguments
        if len(sys.argv) > 1:
            mode = sys.argv[1].lower()
            if mode == 'demo':
                demo_sequence(controller)
            elif mode == 'interactive':
                interactive_mode(controller)
            else:
                print(f"Unknown mode: {mode}")
                print("Usage: python3 motor2_updated.py [demo|interactive]")
        else:
            # Default to interactive mode
            interactive_mode(controller)
    
    except KeyboardInterrupt:
        print("\n\nProgram interrupted by user")
    
    finally:
        # Clean up GPIO
        controller.cleanup()
        print("Program ended")


if __name__ == "__main__":
    main()