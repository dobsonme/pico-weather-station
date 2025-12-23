# Setup – Pico Weather Station

This document describes step by step how to set up and run the weather station
based on the Raspberry Pi Pico W, the BME280 sensor, and the Waveshare Pico LCD 2" display.

---

## Required Components

- Raspberry Pi Pico W
- BME280 sensor (I2C)
- Waveshare Pico LCD 2"
- Connecting wires
- Molex power connector (optional)
- USB cable

---

## Wiring

### BME280 → Raspberry Pi Pico W (I2C)

| BME280 | Pico W |
|------|--------|
| VCC  | 3V3    |
| GND  | GND    |
| SDA  | GPIO 0 |
| SCL  | GPIO 1 |

---

### Waveshare Pico LCD 2"
The display is mounted directly onto the Pico (pin-compatible).

![Wiring diagram](wiring.png)

---

## Connecting the Pico W to the BME280
The sensor can be connected directly to the station, however for convenience
the use of a connector is recommended.  
In this project, a Molex power connector is used.

---

## Environment Setup

The project uses **MicroPython**.

1. Download the MicroPython firmware for the Raspberry Pi Pico W
2. Connect the Pico W to your computer while holding the **BOOTSEL** button
3. Copy the `.uf2` firmware file to the device
4. After rebooting, the Pico will be ready to use

---

## Uploading Files

Copy the contents of the `src/` directory to the Raspberry Pi Pico W:

- `main.py`
- `bme280_float.py`
- `st7789py.py`
- `status.html`
- `temperature_data.txt`
- `tft_buttons.py`
- `tft_config1.py`
- `vga2_8x8.py`
- `vga2_bold_16x16.py`
- `vga2_bold_16x32.py`
- `secrets.py.example`

You can use:
- Thonny
- mpremote
- rshell

---

## First Boot

1. Reset the Pico W
2. The LCD screen should display:
   - current temperature
   - daily minimum and maximum temperature
   - pressure / average pressure
   - humidity / humidity range
   - dew point temperature
   - date and time
   - device IP address

---

## Troubleshooting

### No data from the BME280
- check the SDA/SCL connections
- make sure I2C is configured on GPIO 0/1

### Display not responding
- check whether the display is properly seated
- verify the 3.3 V power supply

---

## Technical Information

- I2C bus speed: 10 kHz
- BME280 address: 0x76 (default)
- Power supply: 3.3 V

