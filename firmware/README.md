<p align="center">
  <img src="../docs/pictures/tripico_logo_firmware.png" width="110" alt="TriPico Firmware Logo"/>
</p>

<h1 align="center">Firmware Guide</h1>
<p align="center"><strong>Raspberry Pi Pico + MicroPython</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/Board-RP2040%20Pico-CC0000?style=for-the-badge&logo=raspberrypi&logoColor=white" alt="Board Badge"/>
  <img src="https://img.shields.io/badge/Language-MicroPython-2B2728?style=for-the-badge&logo=micropython&logoColor=white" alt="Language Badge"/>
  <img src="https://img.shields.io/badge/Core-Asyncio%20Control%20Loop-0F766E?style=for-the-badge" alt="Core Badge"/>
</p>

# 🔧 Firmware (Raspberry Pi Pico / MicroPython)

> Complete control loop and measurement streaming for the Raspberry Pi Pico board.

This firmware orchestrates the core device behavior: 3-channel regulation, continuous measurement through INA3221 sensors, safety relay management, and serial communication with the host computer.

## Picture Insertion Block: Firmware Context

```md
![Pico firmware context](../docs/pictures/fw_pico_board_context.jpg)
```

Specifically, it handles:

- 3-channel regulation (voltage or current mode)
- Voltage/current measurements through INA3221 devices
- Safety relay management
- Front-panel switch monitoring
- Serial communication with the host computer

## 📋 Files Overview

- main.py
  - Async entry point and task orchestration
  - Serial RX/TX, regulation loops, state reporting, safety logic

- device.py
  - Hardware initialization (I2C, INA3221, PWM, GPIO, UART)
  - Exposes initialized peripheral objects used by main.py

- config.py
  - Pin mapping and constants
  - PWM settings, range mapping, current limits, safety thresholds

- ina3221.py
  - INA3221 MicroPython driver used for bus voltage and shunt current readings

## 🔌 Hardware Mapping (From Firmware Perspective)

## Picture Insertion Block: Firmware Pinout

```md
![Pico pin mapping used by firmware](../docs/pictures/fw_gpio_mapping_diagram.jpg)
```

- PWM outputs: GPIO 18/17/16 (channels A/B/C)
- INA3221 high-current device on I2C0 (GPIO 8/9)
- INA3221 low-current device on I2C1 (GPIO 2/3)
- Range selector inputs: GPIO 10..14
- Push-pull switch inputs: GPIO 19/20/21
- Safety relays outputs: GPIO 26/27/28
- Safety relay re-enable button: GPIO 22
- UART1 serial: TX GPIO 4, RX GPIO 5

## 🔄 Runtime Architecture

## Picture Insertion Block: Async Task Diagram

```md
![Firmware async task flow](../docs/pictures/fw_async_tasks_flow.jpg)
```

The runtime consists of independent asynchronous tasks that work in parallel without blocking:

- watch_user_panel_state: reads range selector and push-pull switches
- serial_read: parses host commands
- serial_write: sends periodic measurements
- regulator (one per channel): closes control loop
- send_channels_state: emits saturation/regulation states
- safety_relays_control: enforces limits and handles reset button

Each channel dictionary stores setpoints, measurements, state, and hardware references.

## 📡 Host Command Protocol

## Picture Insertion Block: Serial Protocol Cheat Sheet

```md
![Firmware serial command cheat sheet](../docs/pictures/fw_serial_commands_cheatsheet.jpg)
```

The firmware parses line-based commands and supports:

- set sampling <Hz>
- set voffset <V>
- SAFETY RELAYS <0|1>
- USER PANEL STATE
- <channel> v
- <channel> i
- <channel> nc
- <channel> <value>
- <channel> <max_power>w

Where <channel> is a, b, or c.

## Data Stream Format

## Picture Insertion Block: Sample Serial Capture

```md
![Serial data stream capture](../docs/pictures/fw_serial_stream_capture.jpg)
```

The firmware periodically sends one line with:

- elapsed_time_s
- per channel: name i_measured_mA v_measured_V setpoint

Example shape:

```text
12.340 a 5.1 3.30 3.30 b 0.2 1.80 2.00 c 0.0 0.00 0.00
```

Additional event lines are emitted for:

- Range changes
- Channel regulation/saturation state
- Alert conditions
- Push-pull switch changes

## Safety Logic

## Picture Insertion Block: Safety Events

```md
![Safety relay and alert behavior](../docs/pictures/fw_safety_relays_alerts.jpg)
```

Safety relay control checks:

- Max voltage (MAX_VOLTAGE)
- Max current per selected range (MAX_CURRENTS)
- Per-channel max power (from host command)

On violation, relay opens and an Alert event is sent to host.

## Deploy To Pico

## Picture Insertion Block: File Layout On Pico

```md
![Files copied to Pico root](../docs/pictures/fw_files_on_pico_root.jpg)
```

Copy these files to the Pico filesystem root:

- config.py
- device.py
- ina3221.py
- main.py

Then reset the board. main.py starts automatically.

## Tuning Notes

- PID_DT and gain terms in main.py affect regulation stability.
- PWM_FREQ and MAX_PWM_INCREMENT in config.py affect response and smoothness.
- Range selector logic assumes exactly one active (grounded) range pin.

## Debugging Tips

- Open serial logs to verify command parsing and state transitions.
- Check range selector inputs if current reads as None.
- Confirm INA3221 wiring/addressing if channels stop reporting.