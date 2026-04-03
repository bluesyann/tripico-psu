# AI Agent Instructions for Raspberry Pi Pico IV Characterization Project

---
name: 'Python Standards'
description: 'Coding conventions for Python files'
applyTo: '**/*.py'
---
# Python coding standards
- Follow the PEP 8 style guide.
- Use type hints for all function signatures.
- Write docstrings for public functions.
- Use 4 spaces for indentation.


## Project Overview
This is a complete IV (current-voltage) characterization system for electronic testing. It consists of:
- **Host PC (UserControl/)**: Python application for YAML-driven characterization, real-time plotting, and data export
- **Pico Firmware (Pico2Internal/)**: MicroPython running on RP2040 for hardware control, real-time measurement, and channel regulation

Files in these two folders are closely linked. The impact of any edit done in one file must be evaluated on the others and changes must be propagated from file to file. Generally speaking, editing one file will involve edits in all the other files, including yaml files if dictionnaries naming was affected.

## Architecture

### Host PC (UserControl)
- **run_carac.py**: Main orchestrator handling YAML config parsing, serial communication setup, async task management, and data export
- **serial_functions.py**: Serial protocol implementation (read loop, commands, panel state polling)
- **calib_functions.py**: Calibration data loading (offsets, coefficients) via interpolation
- **gui.py**: Tkinter-based real-time monitoring (optional alternative to CLI)
- **pispos_config.yaml**: Global config (channels, device paths, calibration folder, GUI settings)
- **schema.yaml**: JSON schema validation for input characterization YAML files

### Pico Firmware (Pico2Internal)
- **main.py**: Event loop handling serial communication, channel regulation, and data transmission
- **device.py**: Hardware initialization (I2C buses, INA3221 sensors, PWM outputs, UART)
- **config.py**: Pin definitions, PWM parameters, shunt resistor values
- **ina3221.py**: INA3221 driver for voltage/current measurement (3 channels per sensor)

## Key Patterns

### Host-Pico Communication
- **Serial Protocol**: UART-based text commands/responses (115200 baud default)
- **Command Format**: Space-separated fields, e.g., `a v 3.3` (channel a, voltage mode, 3.3V)
- **Commands**: `<channel> <mode>` (v/i/nc), `<channel> <value>` (setpoint), `<channel> <power>w` (max power), `sampling <freq>`, `voffset <value>`, `RELAYS <state>`, `STATE` (query panel)
- **Data Stream**: `<time> <ch> <current> <voltage> <setpoint> <ch> ...` sent at sampling_freq rate
- **Panel State**: Range selector position + push-pull switch states + safety relay state

### Pico Hardware Architecture
- **Dual INA3221 I2C Modules**: High-current (inaA, I2C0) + Low-current (inaB, I2C1) for 3 channels each
- **PWM Regulation**: 3 channels (pins 16-18) with 100kHz frequency, inverter logic (0% duty → full output after inversion)
- **Range Selector**: 5 GPIO pins (10-14) select shunt resistors (0.1Ω → 1kΩ)
- **Safety Relays**: Per-channel relay pins for power cutoff on overpowered conditions

### Async Architecture (Both Sides)
- **Pico**: MicroPython asyncio with concurrent serial_read, serial_write, watch_user_panel_state, channel regulation tasks
- **Host**: Python asyncio with concurrent read_serial_loop, run_sweep, plot_values, static_run tasks
- **Synchronization**: Async events shared between tasks; signal handlers (SIGINT/SIGTERM) set stop event

### Data Flow
Pico (regulate + measure) → Serial → Host (parse → channels dict) → Calibration (offset/coeff) → DataFrame → CSV export/plotting

## Development Workflow
```bash
# Host Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run characterization
python run_carac.py input_config.yaml -device /dev/ttyACM0 -baud 115200

# Debug mode
python run_carac.py input_config.yaml -d

# Pico Firmware
# Upload to RP2040 using MicroPico VSCode extension (paulober.pico-w-go)
# File structure: main.py, device.py, config.py, ina3221.py on Pico root
```

## Conventions
- **Logging Symbols**: Use ✓ ✗ ⚠ ℹ️ ⏳ for consistent log messages
- **Channel Naming**: Channels named 'a', 'b', 'c' (lowercase single letters)
- **Data Export**: CSV format with columns ['t', 'va', 'ia', 'spa', 'vb', 'ib', 'spb', ...]
- **Calibration Files**: Named like 'offsets_i_noload_range{0-4}.dat', 'coeffs_i_R{value}_range{0-4}.dat'
- **Signal Handling**: Graceful shutdown via SIGINT/SIGTERM with task cancellation

## Common Tasks
- **Add New Channel**: Update pispos_config.yaml channels array and schema.yaml minItems/maxItems
- **Modify Sweep Logic**: Edit serial_functions.py `run_sweep()` and update schema.yaml sweep properties
- **Add Plot Type**: Extend `plot_values()` in run_carac.py with new matplotlib configurations
- **Calibration Updates**: Modify calib_functions.py `load_calibration_files()` for new file formats
- **Update Pico Regulation**: Modify main.py `adjust_channel()` to change voltage/current setpoint logic or add new commands
- **Change PWM Frequency**: Update config.py `PWM_FREQ` and corresponding sampling strategy in main.py

## Channel Data Structure (Host)
Each channel dict: `{'Name', 'VData', 'IData', 'TData', 'SpData', 'SetPoint', 'MaxPower', 'ioffset', 'icoef'}`

## Pico Channel Data Structure
Each channel dict: `{'Name', 'V_SetPoint', 'I_SetPoint', 'V_Measured', 'I_Measured', 'MaxPower', 'PushPullConnected', 'SafetyRelayPin', 'V_offset', 'State'}`

## Dependencies
Core: pyserial, pyyaml, pandas, matplotlib, numpy, scipy, jsonschema
Install via: `pip install -r requirements.txt`

## Testing
- Validate YAML configs against schema.yaml using jsonschema
- Test serial communication with Pico device at /dev/ttyACM0
- Verify calibration data loading from configured folder</content>
<parameter name="filePath">/media/Bureau/Electronique/rpico-iv-characteriser/UserControl/.github/copilot-instructions.md