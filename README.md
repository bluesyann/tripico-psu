# TriPico PSU

TriPico PSU is a 3-channel Raspberry Pi Pico based instrument that can be used as:

- A programmable multi-channel power supply
- A live voltmeter/ammeter front end with real-time plots
- A curve tracer driven by YAML characterization recipes

The project is split into three parts:

- Hardware: PCB, enclosure panel, and wiring assets in [hardware/README.md](hardware/README.md)
- Firmware (Pico): MicroPython control loop in [firmware/README.md](firmware/README.md)
- Software (PC): GUI and YAML runner in [software/README.md](software/README.md)

<img src="docs/pictures/global_view.jpg" width="700"/>

### Picture Insertion Block: Full Build Overview

Use this block when you have a cleaner hero photo than global_view.jpg.

```md
![TriPico PSU - complete build](docs/pictures/overview_complete_build.jpg)
```

## What The System Does

The Pico firmware regulates 3 channels, reads voltage/current through INA3221 sensors, and streams measurements over serial. On the computer side, you can:

- Use a live GUI for interactive control and monitoring
- Run scripted sweeps/static tests from YAML files
- Save CSV data and generate plots for analysis

## Build And Run (Step By Step)

### 1) Build The Hardware

### Picture Insertion Block: Build Steps Collage

Add one image showing PCB + panel + enclosure parts before assembly.

```md
![Hardware build steps](docs/pictures/build_steps_collage.jpg)
```

1. Open the KiCad files and fabricate/assemble the PCB.
2. Build the front panel/enclosure from the provided enclosure assets.
3. Wire the panel elements (switches, relays, connectors, LEDs) to the PCB.

Detailed files and notes are in [hardware/README.md](hardware/README.md).

### 2) Flash The Pico Firmware

### Picture Insertion Block: Pico Flashing

Show your firmware upload workflow or MicroPython file layout.

```md
![Firmware flashing workflow](docs/pictures/pico_firmware_upload.jpg)
```

1. Copy all files from the firmware folder to the Pico:
	 - config.py
	 - device.py
	 - ina3221.py
	 - main.py
2. Reboot the board and verify serial output appears.

Firmware details are in [firmware/README.md](firmware/README.md).

### 3) Set Up The Computer Software

### Picture Insertion Block: Software Setup

Optional terminal screenshot after successful dependency install.

```md
![Host software setup](docs/pictures/software_setup_terminal.jpg)
```

1. Create a Python virtual environment.
2. Install dependencies from software/requirements.txt.
3. Configure software/tripico-psu_config.yaml for your serial port and calibration folder.

Software details are in [software/README.md](software/README.md).

### 4) Use It

### Picture Insertion Block: First Run

Add one screenshot with the GUI connected and channels active.

```md
![First successful run](docs/pictures/first_run_connected_gui.jpg)
```

- GUI mode (interactive bench use):
	- Run software/tripico-psu_gui.py
	- Connect to the Pico
	- Set channel mode (V or mA), setpoint, and max power

- YAML mode (automation and characterization):
	- Run software/tripico-psu_run_yaml.py with one YAML recipe from software/examples
	- Capture sweeps/static runs to CSV and optional plots

## Typical Practical Uses

### Standalone power supply behavior

### Picture Insertion Block: Power Supply Mode

```md
![Power supply mode example](docs/pictures/mode_power_supply.jpg)
```

- Set channels in voltage or current mode
- Apply max-power protection per channel
- Monitor live values and status (regulation/saturation/alerts)

### Digital voltmeter/ammeter style usage

### Picture Insertion Block: Meter Mode

```md
![Voltmeter ammeter mode example](docs/pictures/mode_meter.jpg)
```

- Use one or more channels as sensing points
- Observe time-series voltage/current in the GUI
- Switch measurement range from the front panel selector

### Curve tracer usage

### Picture Insertion Block: Curve Tracer Plot

```md
![Curve tracer example plot](docs/pictures/mode_curve_tracer_plot.jpg)
```

- Define nested sweeps in YAML (for example transistor curves)
- Plot I-V behavior in real time
- Export data for offline analysis

## Example Screens

- GUI examples:
	- [docs/pictures/gui.png](docs/pictures/gui.png)
	- [docs/pictures/gui2.png](docs/pictures/gui2.png)

## Current Status

This repository already contains working code and build assets. Hardware assembly details are intentionally partial and should be completed with your own wiring/BOM documentation as you finalize your build.