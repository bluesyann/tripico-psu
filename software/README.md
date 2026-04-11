<p align="center">
  <img src="../docs/pictures/tripico_logo_software.png" width="110" alt="TriPico Software Logo"/>
</p>

<h1 align="center">Software Guide</h1>
<p align="center"><strong>Host PC Application (GUI + YAML Automation)</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/Language-Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Badge"/>
  <img src="https://img.shields.io/badge/UI-Tkinter%20%2B%20Matplotlib-7C3AED?style=for-the-badge" alt="UI Badge"/>
  <img src="https://img.shields.io/badge/Automation-YAML%20Sweeps-0F766E?style=for-the-badge" alt="Automation Badge"/>
</p>

# 💻 Software (Host Computer)

> Interactive GUI and YAML automation runner that connects over serial to the Pico firmware.

This software provides two complementary modes for interacting with the hardware:

## Picture Insertion Block: Software Overview

```md
![Host software overview](../docs/pictures/sw_overview_gui_and_yaml.jpg)
```

**Two Operating Modes**:

- Interactive GUI mode via tripico-psu_gui.py
- YAML automation mode via tripico-psu_run_yaml.py

## 📚 Files Overview

- tripico-psu_gui.py
	- Desktop GUI for live monitoring and manual channel control
	- Connects over serial to the Pico firmware
	- Displays real-time voltage/current charts and channel states

- tripico-psu_run_yaml.py
	- CLI runner for scripted characterization workflows
	- Validates YAML inputs against validation_schema.yaml
	- Executes sweeps/static runs, writes CSV, optionally saves plots

- serial_functions.py
	- Serial protocol helpers (send commands, parse incoming data)
	- Sweep engine and panel-state checks

- calib_functions.py
	- Loads and applies calibration offsets/gains from external files

- tripico-psu_config.yaml
	- Global host settings (channels, serial device pattern, GUI config, calibration path)

- validation_schema.yaml
	- YAML schema for characterization recipe validation

- examples/
	- Example characterization files for transistor and source testing

## 🐍 Python Environment Setup

## Picture Insertion Block: Dependency Install

```md
![Python environment and dependency install](../docs/pictures/sw_install_dependencies_terminal.jpg)
```

From this folder:

```bash
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
```

On Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## ⚙️ Configuration

## Picture Insertion Block: Config File Example

```md
![tripico-psu_config.yaml annotated example](../docs/pictures/sw_config_yaml_example.jpg)
```

Edit tripico-psu_config.yaml before running:

- setup.channels: active channels (typically a, b, c)
- setup.device: serial device glob
	- Linux example: /dev/ttyACM*
	- Windows example: COM3
- setup.calibration_folder: path to calibration files
- gui.*: GUI size/colors/sampling/time-window defaults

## 🖥️ Run The GUI (Interactive Mode)

## Picture Insertion Block: GUI Main Window

You can use one of the existing screenshots first, then replace with your own later.

```md
![GUI screenshot](../docs/pictures/gui.png)
```

```bash
python tripico-psu_gui.py
```

Workflow:

1. Select serial port and baudrate.
2. Click Connect.
3. Per channel, set value/unit/max power and click Update.
4. Watch live charts and status fields.

Expected channel status messages include:

- PID Regulation
- Saturation High / Saturation Low
- Alert and push-pull connection state changes

## Picture Insertion Block: GUI Status States

```md
![GUI channel states example](../docs/pictures/sw_gui_channel_states.jpg)
```

## 📈 Run YAML Characterization (Automation Mode)

## Picture Insertion Block: YAML Runner In Terminal

```md
![YAML run from terminal](../docs/pictures/sw_yaml_run_terminal.jpg)
```

```bash
python tripico-psu_run_yaml.py examples/npn_output_characteristics.yaml -device /dev/ttyACM0 -baud 115200
```

Useful options:

- -d / --debug: verbose logging
- --no-prompt: do not wait for Enter between characterizations

The runner will:

1. Load tripico-psu_config.yaml.
2. Validate the input YAML against validation_schema.yaml.
3. Ensure panel/range state is ready.
4. Initialize channels on the Pico.
5. Run sweep/static sequence.
6. Save output CSV when datafile is defined.

## YAML Recipe Structure (Quick Reference)

## Picture Insertion Block: YAML Recipe Annotated

```md
![Annotated characterization YAML](../docs/pictures/sw_yaml_recipe_annotated.jpg)
```

Main keys:

- comment
- caracs: list of characterizations

Per characterization:

- name
- init:
	- range
	- voffset
	- sampling
	- channels: Name, control, initvalue, max_power
- either static or sweep
- optional plots
- optional datafile

Nested sweeps are supported with sweep.sweep for curve tracing.

## Serial Link Expectations

## Picture Insertion Block: Parsed Data And Events

```md
![Data and event parsing overview](../docs/pictures/sw_serial_data_and_events.jpg)
```

- Default baudrate: 115200
- The host expects periodic samples in one line containing timestamp + all channels
- Events (range changes, alerts, state changes) are parsed separately

## Notes

- The software is tightly coupled to firmware command names and channel fields.
- If you rename YAML keys or channel dictionary fields, update GUI/runner/serial helpers together.