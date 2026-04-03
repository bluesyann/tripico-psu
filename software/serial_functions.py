import serial
import asyncio
import numpy as np
from time import sleep

import logging

# ✓ ✗ ⚠ ℹ️ ⏳


STANDBY = {
    "voffset": 0,
    "sampling": 1,
    "channels": [
        {"name": "a", "control": "v"},
        {"name": "b", "control": "v"},
        {"name": "c", "control": "v"},
    ],
}

VOLTAGE_OFFSET_TIME = 2
SLOW_LOOP_TIME = 1
FAST_LOOP_TIME = 1e-3
WRITE_DELAY = 1e-1


def setup_serial_link(device: str, baud: int):
    """Open and configure the serial connection to the Pico device.

    Arguments:
        - device: str: path to the serial device (e.g. /dev/ttyACM0).
        - baud: int: baud rate for communication.

    Returns:
        - serial.Serial or None: serial object if successful, otherwise None.
    """
    try:
        ser = serial.Serial(device, baud, timeout=1)

        # Purge the serial buffer
        ser.reset_input_buffer()
        return ser
    except Exception as e:
        logging.error(f"Error while setting up serial connection: {e}")
        return None


def close_serial_link(ser: serial.Serial) -> None:
    """Close the serial connection if it is open.

    Arguments:
        - ser: serial.Serial: serial connection to close.

    Returns:
        - None
    """
    if ser is not None:
        try:
            ser.close()
            logging.info("Serial port closed")
        except Exception as e:
            logging.error(f"Error closing serial port: {e}")


def get_current_config(ser: serial.Serial) -> dict:
    """Ask the Pico for current panel and relay status.

    Arguments:
        - ser: serial.Serial: serial connection.

    Returns:
        - dict: current configuration.
    """
    logging.info("ℹ️ Asking for board state...")
    safe_write(ser, "USER PANEL STATE")

    for _ in range(10):
        while ser.in_waiting > 0:
            line = ser.readline().decode("utf-8").strip()
            if line.startswith("STATE"):
                logging.debug("STATE line: %s", line)
                try:
                    parts = line.split()
                    return {
                        "ammeter_range": int(parts[1]),
                        "a_pushpull_connected": parts[2],
                        "b_pushpull_connected": parts[3],
                        "c_pushpull_connected": parts[4],
                        "relay_powered": parts[5],
                        "communicating": True,
                    }
                except Exception as e:
                    logging.error("✗ Error parsing board state: %s", e)
                    logging.error("✗ Line content: %s", line)
        sleep(SLOW_LOOP_TIME)

    return {"communicating": False}


def main_button_ready(init: dict, relays_powered: bool) -> bool:
    """Validate that the main relay switch state matches requested channel power state.

    Arguments:
        - init: dict: initialization configuration.
        - relays_powered: bool: whether relays are powered.

    Returns:
        - bool: True if ready.
    """
    need_power = any(ch.get("control") != "nc" for ch in init.get("channels", []))
    logging.debug("Main switch state=%s, power required=%s", relays_powered, need_power)

    if relays_powered and not need_power:
        logging.warning("No channel requires power but main switch is ON")
        return False

    if not relays_powered and need_power:
        logging.warning("At least one channel requires power but main switch is OFF")
        return False

    return True


def wait_until_panel_ready(ser: serial.Serial, init: dict) -> int|None:
    """Wait until panel switches match desired configuration in a `carac` section.

    Arguments:
        - ser: serial.Serial: serial connection.
        - init: dict: initialization configuration.

    Returns:
        - int | None: range index or None.
    """
    ready = False
    range_index = None

    while not ready:
        board_state = get_current_config(ser)
        logging.debug("Current board state: %s", board_state)

        if not board_state.get("communicating", False):
            logging.warning("ℹ⚠ Cannot get a response from board")
        else:
            try:
                ready = True
                range_index = int(board_state.get("ammeter_range", -1))
                if range_index != int(init.get("range", -1)):
                    logging.warning(
                        "⚠ Ammeter range must be set to %s", init.get("range")
                    )
                    ready = False

                if not main_button_ready(
                    init, bool(int(board_state.get("relay_powered", "0")))
                ):
                    ready = False

                for ch in init.get("channels", []):
                    channel_name = ch.get("name") or ch.get("Name")
                    required_state = ch.get("control")
                    current_state = board_state.get(
                        f"{channel_name}_pushpull_connected", "False"
                    )
                    logging.debug(
                        "Required state for channel %s: %s (current=%s)",
                        channel_name,
                        required_state,
                        current_state,
                    )

                    if required_state == "nc" and current_state == "True":
                        logging.info("ℹ️ Disable push-pull output for %s", channel_name)
                        ready = False
                    if required_state != "nc" and current_state == "False":
                        logging.info("ℹ️ Enable push-pull output for %s", channel_name)
                        ready = False
            except Exception as e:
                logging.error("Error while checking panel state: %s", e)
                ready = False

        sleep(SLOW_LOOP_TIME)

    return range_index


def set_safety_relays(ser, state):
    """Set all safety relays to opened or closed state via Pico command.

    Arguments:
        - ser: serial.Serial: serial connection.
        - state: str: 'OPENED' to disable outputs, otherwise enable outputs.

    Returns:
        - None
    """
    logging.info(f"Setting safety relays to {state}")
    if state == "OPENED":
        safe_write(ser, f"SAFETY RELAYS 0")
    else:
        safe_write(ser, f"SAFETY RELAYS 1")


def initialize_channels(init: dict|None, ser: serial.Serial) -> None:
    """Apply initial configuration for channels and timing on the Pico.

    Arguments:
        - init: dict: startup configuration block with voffset, sampling and channels.
        - ser: serial.Serial: open connection to send init commands.

    Returns:
        - None
    """
    logging.info("ℹ️ Initializing channels and timing settings...")
    set_safety_relays(ser, "OPENED")

    if init is None:
        init = STANDBY

    for parameter in ["voffset", "sampling"]:
        value = init.get(parameter, STANDBY[parameter])
        safe_write(ser, f"set {parameter} {value}")

    for ch in init.get("channels", []):
        channel_name = ch.get("name") or ch.get("Name")
        control_mode = ch.get("control")

        if not channel_name or not control_mode:
            logging.warning(
                "Skipping channel initialization due to missing name/control: %s", ch
            )
            continue

        safe_write(ser, f"{channel_name} {control_mode}")

        init_value = ch.get("initvalue", 0)
        safe_write(ser, f"{channel_name} {init_value}")

        max_power = ch.get("max_power", ch.get("max power", 1))
        safe_write(ser, f"{channel_name} {max_power}w")

    sleep(VOLTAGE_OFFSET_TIME)
    set_safety_relays(ser, "CLOSED")


def safe_write(ser: serial.Serial, cmd: str) -> None:
    """Safely send a command string to the Pico without blocking.

    Arguments:
        - ser: serial.Serial: open serial connection.
        - cmd: str: command to send (without trailing newline).

    Returns:
        - None
    """
    if ser is not None:
        try:
            logging.debug(f"ℹ️ Sending to serial {cmd}")
            ser.write(f"{cmd}\n".encode("utf-8"))
            ser.flush()
        except Exception as e:
            logging.error(f"Error while sending data to serial: {e}")
    else:
        logging.error(f"Cant send data to serial, port is not ready")
    sleep(WRITE_DELAY)


async def run_sweep(sweep: dict, ser: serial.Serial) -> bool:
    """Execute a channel sweep sequence by sending successive setpoint commands.

    Arguments:
        - sweep: dict: contains channel, timestep, and values/range for the sweep.
        - ser: serial.Serial: active serial connection to send commands.

    Returns:
        - bool: True when sweep completes successfully.
    """
    ch = sweep["channel"]
    dt = sweep["timestep"]
    logging.info(f"ℹ️ Running channel {ch} sweep with config: {sweep}")

    # Convert range to list if needed
    format_sweep_values(sweep)
    logging.debug(f"Sweep values: {sweep['value_list']}")

    for sp in sweep["value_list"]:
        logging.debug(f"ℹ️ Setting channel {ch} setpoint to: {sp}")

        # Prepare command to send to Pico
        safe_write(ser, f"{ch} {sp}")

        await asyncio.sleep(dt)

        # Run another nested sweeps if defined
        if "sweep" in sweep:
            await run_sweep(sweep["sweep"], ser)
            await asyncio.sleep(dt)
    logging.info(f"✓ Completed sweep for channel {ch}")
    return True


def read_serial_values(ser: serial.Serial, events: list, channels: list) -> None:
    """Read and parse incoming serial lines from Pico into channel buffers.

    Arguments:
        - ser: serial.Serial: serial connection.
        - events: list: list to append events.
        - channels: list: list of channels.

    Returns:
        - None
    """
    if ser.in_waiting < 1:
        return

    line = ser.readline().decode("utf-8", errors="ignore").strip()
    if not line:
        return

    logging.debug("Received from Pico: %s", line)

    parts = line.split()
    expected_tokens = 1 + 4 * len(channels)

    if len(parts) != expected_tokens:
        logging.debug("Received event: %s", line)
        events.append(line)
        return

    try:
        t = float(parts[0])
    except ValueError as e:
        logging.error("Invalid timestamp in serial data: %s", e)
        events.append(line)
        return

    for idx, channel in enumerate(channels):
        chan_name = channel.get("name", "unknown")
        try:
            i_value = parts[4 * idx + 2]
            i_val = float(i_value) if i_value != "None" else float("nan")
        except Exception as e:
            logging.warning("Parsing current failed for channel %s: %s", chan_name, e)
            i_val = float("nan")

        try:
            v_value = parts[4 * idx + 3]
            v_val = float(v_value) if v_value != "None" else float("nan")
        except Exception as e:
            logging.warning("Parsing voltage failed for channel %s: %s", chan_name, e)
            v_val = float("nan")

        try:
            sp_value = parts[4 * idx + 4]
            sp_val = float(sp_value) if sp_value != "None" else float("nan")
        except Exception as e:
            logging.warning("Parsing setpoint failed for channel %s: %s", chan_name, e)
            sp_val = float("nan")

        try:
            if channel.get("i_offset") is not None:
                df = channel["i_offset"]
                i_bias = np.interp(
                    v_val, df["v"].values, df["i"].values, left=0, right=0
                )
                i_val = (i_val - i_bias) * channel.get("i_coef", 1.0)
        except Exception as e:
            logging.warning(
                "Error applying calibration for channel %s: %s", chan_name, e
            )

        channel["i_data"].append(i_val)
        channel["v_data"].append(v_val)
        channel["t_data"].append(t)
        channel["sp_data"].append(sp_val)


async def read_serial_loop(ser: serial.Serial, events: list, channels: list) -> None:
    """Run read_serial_values function within an async loop.

    Arguments:
        - ser: serial.Serial: serial connection.
        - events: list: list to append events.
        - channels: list: list of channels.

    Returns:
        - None
    """
    logging.info("ℹ️ Clearing serial input buffer before starting data collection")
    ser.reset_input_buffer()
    while True:
        if ser is not None:
            read_serial_values(ser, events, channels)
        await asyncio.sleep(FAST_LOOP_TIME)


def format_sweep_values(sweep: dict) -> None:
    """Normalize the sweep definition into a concrete value_list.

    Supports either explicit `values` or a `start`/`stop`/`step` range. Optionally
    mirrors list for `option: symmetric`.

    Arguments:
        - sweep: dict: sweep configuration to mutate in-place.

    Returns:
        - None
    """
    if "value_list" not in sweep:
        # if range and step provided, generate values
        if "values" not in sweep:
            try:
                sweep["value_list"] = range_float(
                    sweep["start"], sweep["stop"], sweep["step"]
                )
            except Exception as e:
                logging.error(f"✗ Error generating sweep values: {e}")
        # if values is a string, convert to list
        else:
            try:
                sweep["value_list"] = sweep[
                    "values"
                ]  # list of values were already provided in the yaml
            except Exception as e:
                logging.error(f"✗ Error parsing sweep values: {e}")
        # append the first value to the end of the list
        # so that at the end of the sweep it comes back to the initial value
        # sweep['value_list'].append(sweep['value_list'][0])
        if "option" in sweep and sweep["option"] == "symmetric":
            sweep["value_list"] = sweep["value_list"] + list(
                reversed(sweep["value_list"])
            )


def range_float(start, stop, step):
    """Return floating point range values inclusively between start and stop.

    Works similarly to `range` but supports non-integer steps and includes
    the stop point when within tolerance.

    Arguments:
        - start: float: beginning value.
        - stop: float: ending value.
        - step: float: incremental step.

    Returns:
        - list[float]: generated values.
    """
    step = abs(step)  # ensure step is positive

    reversed = False
    if start > stop:  # handle decreasing ranges
        buf = start
        start = stop
        stop = buf
        reversed = True

    current = start
    values = []
    while current < stop + 0.001:  # Adding a small tolerance to include stop value
        values.append(current)
        current += step
    if reversed:
        values = values[::-1]
    return [round(v, 2) for v in values]
