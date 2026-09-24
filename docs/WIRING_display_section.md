### Face display (3.5\" SPI TFT — jumper-wired, only the necessary pins)

The 3.5\" display ("3.5inch RPi Display" / XPT2046-style) is designed to
sit directly on the whole 40-pin header. We jumper it instead, wiring
**only the pins the screen actually needs** — the rest of the header stays
free for the motor drivers and sensors:

| Display pin | Pi GPIO | Physical pin | Purpose |
|---|---|---|---|
| VCC | 3.3 V | 1 | Power |
| GND | GND | 6 | Ground |
| LCD_CS | 8 (CE0) | 24 | SPI chip select |
| LCD_CLK / SCK | 11 (SCLK) | 23 | SPI clock |
| LCD_MOSI / DIN | 10 (MOSI) | 19 | SPI data |
| LCD_DC / RS | 25 | 22 | Data/command select |
| LCD_RST | 17 | 11 | Reset |
| BL | 27 | 13 | Backlight (can also tie to 3.3 V) |

Eight wires and the screen works. **Touch is not wired** — the robot's face
needs no touch input — so we skip the three touch pins (TP_CS → GPIO 7/pin
26, TP_IRQ → GPIO 24/pin 18, LCD_MISO → GPIO 9/pin 21). Wire them too if
you ever want touch.

Photos of the actual wiring: [header close-up](photos/display-header-closeup.jpg),
[jumpered display](photos/display-jumper-wiring.jpg), [robot overview](photos/robot-gpio-wiring.jpg).

For the driver installation see
[RASPBERRY_PI_SETUP.md](RASPBERRY_PI_SETUP.md).

## Direction logic
