# TriPico PSU: 3-Channel Smart Power Supply & Curve Tracer
# RP2040 + INA3221 • Real-time I/V graphs • YAML automation

import asyncio
import time
from device import *

# default sampling frequency
sampling_freq = 1

# Current range switch
range_switch = None

ser = uart1


async def serial_write(channels: list):
    """Send periodic measurement updates from all channels over UART.

    Arguments:
        - channels: list: channel dictionaries to read and report.
    """
    global sampling_freq
    while True:
        # Update all channel measurements
        for ch in channels:
            get_values(ch)

        # Get current time in seconds since the program started
        current_time = time.ticks_ms() / 1000

        # send the values of all channels over UART
        message = f"{current_time} "
        for ch in channels:
            setpoint = ch.get("v_setpoint")
            if setpoint is None:
                setpoint = ch.get("i_setpoint")
            message += f"{ch.get('name')} {ch.get('i_measured')} {ch.get('v_measured')} {setpoint} "
        write_serial(message)
        # print("Sending message over UART:", message.strip())
        await asyncio.sleep_ms(int(1000 / sampling_freq))  # Send message every second


async def adjust_channel(ch: dict, row: list) -> None:
    """Update channel setpoints and modes from a host command.

    Arguments:
        - ch: dict: channel state dictionary to mutate.
        - row: list: parsed command elements (channel, command/value).
    """
    try:
        # Case when push-pull output is to be disconnected
        if row[1] == "nc":
            print(f"Push-pull output not used for channel {ch.get('name')}")

        elif row[1] == "v":
            if ch.get("v_setpoint") is None:
                ch["v_setpoint"] = 0
                ch["i_setpoint"] = None
                print(f"Channel {ch.get('name')} set to voltage regulation mode")

        elif row[1] == "i":
            if ch.get("i_setpoint") is None:
                ch["v_setpoint"] = None
                ch["i_setpoint"] = 0
                print(f"Channel {ch.get('name')} set to current regulation mode")

        elif is_numeric(row[1]):
            if ch.get("v_setpoint") is not None:
                ch["v_setpoint"] = float(row[1])
                print(f"Channel {ch.get('name')}: v_setpoint set to {float(row[1])}")
            else:
                ch["i_setpoint"] = float(row[1])
                print(f"Channel {ch.get('name')}: i_setpoint set to {float(row[1])}")

        elif row[1].endswith("w"):
            mp = row[1][:-1]
            try:
                value = float(mp)
                ch["max_power"] = value * 1000
                print(f"Channel {ch.get('name')}: max_power set to {value}")
            except ValueError:
                print(f"Cannot parse MaxPower value {mp}")

        else:
            print("Invalid parameter for channel adjustment:", row[1])

    except Exception as e:
        print("Error adjusting channel parameters:", e)


def set_voltage_offset(ch: dict, voltage: float) -> None:
    """Configure per-channel voltage offset for measurement correction.

    Arguments:
        - ch: dict: channel state dictionary.
        - voltage: float: offset to subtract from measured voltage.
    """
    try:
        ch["v_offset"] = voltage
        print(f"Voltage offset set to {voltage} V for channel {ch.get('name')}")
    except Exception as e:
        print(f"Error while setting voltage offset for channel {ch.get('name')}: {e}")


def is_numeric(string):
    """Check if a string can be converted to float.

    Arguments:
        - string: str: input to validate.

    Returns:
        - bool: True if numeric, False otherwise.
    """
    try:
        float(string)
        return True
    except ValueError:
        return False


async def serial_read(channels: list):
    """Read and parse commands received from the host via host_serial.

    Arguments:
        - channels: list: channel state dictionaries that can be updated.
    """
    global sampling_freq
    serial_buffer = ""
    while True:
        if ser.any():
            data = ser.read(ser.any())
            if data is not None:
                # Append new data to buffer
                serial_buffer += data.decode("utf-8")

                # Process complete lines (ending with \n or \r)
                while "\n" in serial_buffer:
                    # Split on \n
                    if "\n" in serial_buffer:
                        line, serial_buffer = serial_buffer.split("\n", 1)
                        line = line.strip()

                        # Skip empty lines
                        if not line:
                            break

                        print("Received data over UART:", line)
                        # parse and update setpoints if needed
                        try:
                            processed = False
                            row = line.split(" ")
                            if len(row) == 3:
                                if row[1] == "sampling":
                                    sampling_freq = float(row[2])
                                    print(
                                        f"Updated sampling frequency to {sampling_freq} Hz"
                                    )
                                    processed = True
                                elif row[2] == "STATE":
                                    send_user_panel_state(channels)
                                    processed = True
                                elif row[1] == "voffset":
                                    for ch in channels:
                                        set_voltage_offset(ch, float(row[2]))
                                    processed = True
                                elif row[1] == "RELAYS":
                                    setpoint = int(row[2])
                                    for ch in channels:
                                        print(
                                            f"Setting safety relay of channel {ch.get('name')} to {setpoint}"
                                        )
                                        ch["safety_relay_pin"].value(not setpoint)
                                    processed = True
                            elif len(row) == 2:
                                for ch in channels:
                                    if ch.get("name") == row[0]:
                                        await adjust_channel(ch, row)
                                        processed = True
                                        break

                            if not processed:
                                print("Unknown command: ", line)

                        except Exception as e:
                            print("Error parsing command:", e)
                        break
        await asyncio.sleep_ms(10)  # Check for incoming data every x ms


def send_user_panel_state(channels: list) -> None:
    """Send panel state to the host, including range and push-pull states."""
    global range_switch
    message = f"STATE {range_switch}"

    for ch in channels:
        message += f" {ch.get('pushpull_connected')}"
        if ch.get("pushpull_connected"):
            ch["state"] = ""

    message += f" {sractivate.value()}"
    write_serial(message)


def write_serial(message: str) -> None:
    """Write the provided message to host_serial (USB) and optionally debug UART.

    If using USB CDC mode, this is the host link. UART1 remains available as
    debug channel.
    """
    message += "\n"
    try:
        ser.write(message.encode("utf-8"))
    except Exception:
        pass


async def watch_user_panel_state(channels: list):
    """Monitor hardware switches and update channel states accordingly.

    Arguments:
        - channels: list: channel state dictionaries.
    """
    print("Starting range selector monitoring...")
    global range_switch
    while True:
        # Read the state of the five GPIO pins of the range selector
        n = 0
        selected = None
        for i, _ in enumerate(RANGE_SELECTOR_PINS):
            val = range_selector_pins[i].value()
            n += val
            if val == 0:
                selected = i
        if n == 4 and selected is not None:
            if range_switch is None or selected != range_switch:
                print(f"Selected shunt resistor: {selected}")
                for ch in channels:
                    ch["range"] = selected
                    ch["rshunt"] = SHUNTS[selected]
                range_switch = selected
                write_serial(f"Range {range_switch} selected")
        else:
            print(
                "Invalid shunt resistor selection:",
                [pin.value() for pin in range_selector_pins],
            )
            for ch in channels:
                ch["rshunt"] = None

        # Read push-pull switch states
        for ch in channels:
            swstate = not bool(ch["switch_pin"].value())
            if swstate != ch.get("pushpull_connected"):
                print(f"Push-pull switch set to {swstate} on channel {ch.get('name')}")
                ch["pushpull_connected"] = swstate
                write_serial(f"CH {ch.get('name')} PushPullConnected {swstate}")
        await asyncio.sleep_ms(50)


async def send_channels_state(channels: list):
    """Send current channel internal status (saturation/regulation) to host.

    Arguments:
        - channels: list: channel states to evaluate and report.
    """
    while True:
        for ch in channels:
            if ch.get("safety_relay_on") and ch.get("pushpull_connected"):
                if ch.get("duty") == 0 and ch.get("state") != "Saturation High":
                    print(f"Ch {ch.get('name')} running on saturation High")
                    ch["state"] = "Saturation High"
                    write_serial(f"State {ch.get('name')} Saturation High")

                elif (
                    ch.get("duty") == PWM_RESOLUTION
                    and ch.get("state") != "Saturation Low"
                ):
                    print(f"Ch {ch.get('name')} running on saturation Low")
                    ch["state"] = "Saturation Low"
                    write_serial(f"State {ch.get('name')} Saturation Low")

                elif ch.get("state") != "PID Regulation":
                    if (
                        0.05 * PWM_RESOLUTION
                        < ch.get("duty", 0)
                        < 0.95 * PWM_RESOLUTION
                    ):
                        print(f"Ch {ch.get('name')} regulating")
                        ch["state"] = "PID Regulation"
                        write_serial(f"State {ch.get('name')} PID Regulation")

        await asyncio.sleep_ms(500)


async def regulator(ch: dict):
    """Run PID regulation loop for a given channel.

    Adjusts PWM duty cycle to track setpoint in voltage or current mode.

    Arguments:
        - ch: dict: channel parameters and measured state.

    Returns:
        - None
    """
    se_old = 0  # Stores the error signal for the derivative calculation
    ise = 0  # Integral of the error signal
    while True:
        try:
            i, v = poll_sensors(ch)
        except Exception as e:
            print(f"Error getting i and v on channel {ch.get('name')}: {e}")
            i, v = None, None

        # Skip regulation if sensors return None values
        if v is None or i is None:
            await asyncio.sleep_ms(PID_DT)
            continue

        ch["i_measured"] = i
        ch["v_measured"] = v

        Ki = 1e-4  # integral gain for voltage regulation
        Kp = 5e-3  # proportional gain for voltage regulation
        Kd = 5e-1  # derivative gain for voltage regulation

        se = 0  # error signal
        if ch.get("i_setpoint") is None and ch.get("v_setpoint") is not None:
            se = ch["v_setpoint"] - ch["v_measured"]
        elif ch.get("v_setpoint") is None and ch.get("i_setpoint") is not None:
            """Current regulation with gain scheduling based on setpoint magnitude."""
            if ch["i_setpoint"] < 1e-6:
                ch["i_setpoint"] = 1e-6
            se = 1 - ch.get("i_measured", 0) / ch["i_setpoint"]

        else:
            print("Error: Cant tell wether voltage or current must be regulated.")
            await asyncio.sleep_ms(PID_DT)
            continue

        # PWM Regulation Logic
        ise = se * PID_DT
        dse = (se - se_old) / PID_DT  # Derivative of error
        increment = (
            Kp * se + Kd * dse + Ki * ise
        ) * PWM_RESOLUTION  # Required voltage variation for this iteration

        # Apply the rising time limit
        if abs(increment) > MAX_PWM_INCREMENT:
            increment = MAX_PWM_INCREMENT if increment > 0 else -MAX_PWM_INCREMENT

        ch["duty"] -= int(increment)
        # Clamp duty cycle to valid range when saturation occurs
        if ch["duty"] < 0:
            ch["duty"] = 0
            ise = 0  # Reset the integrator
        elif ch["duty"] > PWM_RESOLUTION:
            ch["duty"] = PWM_RESOLUTION
            ise = 0  # Reset the integrator
        ch["pwm"].duty_u16(ch["duty"])

        # Update old error and damp the integrator
        se_old = se
        ise *= 0.99

        await asyncio.sleep_ms(PID_DT)


def update_load(ch: dict) -> float:
    """
    This function calculate the load on the channel by calculating v/i
    To avoid instability, the load is averaged over several iterations
    Iterations are stored in the array 'Load'
    Argument: channel dictionnary
    Returns: average load
    """
    if ch.get("i_measured") not in (None, 0):
        R = 1e3 * ch.get("v_measured", 0) / ch["i_measured"]
    else:
        R = 1e6  # If no current, assume 1 Mohm

    if len(ch.get("load", [])) > 10:  # Remove the oldest value from the array
        ch["load"].pop(0)

    ch.setdefault("load", []).append(R)
    return sum(ch["load"]) / len(ch["load"])


async def do_nothing():
    """Idle task that keeps the asyncio event loop alive.

    Returns:
        - None
    """
    while True:
        await asyncio.sleep_ms(0)


def poll_sensors(ch: dict) -> tuple:
    """Read voltage/current from INA3221 sensors for the channel.

    Arguments:
        - ch: dict: channel state including range and devices.

    Returns:
        - tuple: (i_mA, v_V) measured current in mA and voltage in V.
    """
    try:
        # Get the data from the High Current device (range=0)
        if ch.get("range") == 0:
            v = ch["high_i_device"].bus_voltage(ch["bus_id"])
            i = 1e3 * ch["high_i_device"].current(ch["bus_id"]) * 0.1
        else:
            v = ch["low_i_device"].bus_voltage(ch["bus_id"])
            i = 1e3 * ch["low_i_device"].current(ch["bus_id"]) * 0.1

        if ch.get("v_offset") is not None:
            v -= ch["v_offset"]

        if ch.get("rshunt") is None:
            print(f"Shunt undefined for channel {ch.get('name')}")
            return (None, v)

        i /= ch["rshunt"]

        # print("Polled values on ch",ch['Name'], i, v)
        # time.sleep(0.5)
        return (i, v)

    except Exception as e:
        print(f"Error polling sensors on channel {ch.get('name')}: {e}")
        ch["safety_relay_on"] = False
        ch["safety_relay_pin"].value(1)
        return (None, None)


def get_values(ch: dict) -> bool:
    """Update channel measured values by polling sensors.

    Arguments:
        - ch: dict: channel state dictionary.

    Returns:
        - bool: True if measurement successful, False otherwise.
    """
    try:
        i, v = poll_sensors(ch)
        ch["i_measured"] = i
        ch["v_measured"] = v
        return True
    except Exception as e:
        print(f"Error getting i and v on channel {ch.get('name')}: {e}")
        return False


async def test_pwm_output():
    """Exercise PWM output over full duty cycle range for debugging.

    Iterates the PWM duty cycle in increments and prints the measured voltage.

    Arguments:
        - None

    Returns:
        - None
    """
    for duty in range(0, PWM_RESOLUTION + 1, 1000):
        pwmc.duty_u16(duty)
        # print(f"Set duty cycle to {duty}/{PWM_RESOLUTION}")
        await asyncio.sleep(0.5)
        # get the voltage after the push pull
        v = inaA.bus_voltage(
            3
        )  # Assuming channel 1 is connected to the push-pull output
        # print(f"Measured voltage: {v} V")
        print(f"{duty}\t{v}")


async def safety_relays_control(channels: list) -> None:
    """Monitor each channel and trigger safety relays on limit violations.

    Checks for over-voltage, over-current, and max power breach, then opens
    the corresponding relay and reports alert state over UART.

    Arguments:
        - channels: list: monitored channel dictionaries.

    Returns:
        - None
    """
    # On startup, activate all the relays
    for ch in channels:
        ch["safety_relay_pin"].value(0)
    last_button_state = True

    while True:
        await asyncio.sleep_ms(100)
        for ch in channels:
            currently_on = ch.get("safety_relay_on", False)
            v = ch.get("v_measured")
            i = ch.get("i_measured")
            message = ""

            if v is not None and v + ch.get("v_offset", 0) > MAX_VOLTAGE:
                ch["safety_relay_on"] = False
                message = "Max voltage reached"

            if ch.get("range") is not None and i is not None:
                if abs(i) > MAX_CURRENTS.get(ch["range"], 0):
                    ch["safety_relay_on"] = False
                    message = "Max current reached"

            if ch.get("max_power") is not None and v is not None and i is not None:
                if abs(i * v) > ch["max_power"]:
                    ch["safety_relay_on"] = False
                    message = f"Max power reached: {int(abs(i*v))} mW"

            if ch.get("safety_relay_on", False) != currently_on:
                ch["safety_relay_pin"].value(1)
                print(
                    f"Ch {ch.get('name')}: SafetyRelayOn from {currently_on} to {ch.get('safety_relay_on')}"
                )
                ch["state"] = "Alert"
                print(message)
                write_serial(f"CH {ch.get('name')} Alert {message}")

        button_state = bool(sractivate.value())
        if button_state and button_state != last_button_state:
            print("User-button pressed, reactivating safety relays")
            for ch in channels:
                ch["safety_relay_on"] = True
                ch.get("safety_relay_pin").value(0)
                write_serial(
                    f"CH {ch.get('name')} PushPullConnected {ch.get('pushpull_connected')}"
                )

        last_button_state = button_state


async def main():
    """Entry point for Pico firmware operation.

    Initializes channel parameters, creates asynchronous tasks for sensor
    reading, regulation control, serial communication and safety checks.

    Arguments:
        - None

    Returns:
        - None
    """
    print("Starting the program...")

    # Define channels parameters
    channels = [
        {
            "name": "a",
            "v_setpoint": 0.0,
            "i_setpoint": None,
            "v_offset": 0.0,
            "max_power": None,
            "v_measured": None,
            "i_measured": None,
            "range": None,
            "rshunt": None,
            "load": [],
            "duty": 0,
            "pushpull_connected": True,
            "state": "",
            "safety_relay_pin": sra,
            "safety_relay_on": True,
            "switch_pin": ppswitcha,
            "pwm": pwma,
            "high_i_device": inaA,
            "low_i_device": inaB,
            "bus_id": 1,
        },
        {
            "name": "b",
            "v_setpoint": 0.0,
            "i_setpoint": None,
            "v_offset": 0.0,
            "max_power": None,
            "v_measured": None,
            "i_measured": None,
            "range": None,
            "rshunt": None,
            "load": [],
            "duty": 0,
            "pushpull_connected": False,
            "state": "",
            "safety_relay_pin": srb,
            "safety_relay_on": True,
            "switch_pin": ppswitchb,
            "pwm": pwmb,
            "high_i_device": inaA,
            "low_i_device": inaB,
            "bus_id": 2,
        },
        {
            "name": "c",
            "v_setpoint": 0.0,
            "i_setpoint": None,
            "v_offset": 0.0,
            "max_power": None,
            "v_measured": None,
            "i_measured": None,
            "range": None,
            "rshunt": None,
            "load": [],
            "duty": 0,
            "pushpull_connected": False,
            "state": "",
            "safety_relay_pin": src,
            "safety_relay_on": True,
            "switch_pin": ppswitchc,
            "pwm": pwmc,
            "high_i_device": inaA,
            "low_i_device": inaB,
            "bus_id": 3,
        },
    ]

    # Start range selector monitoring task
    asyncio.create_task(watch_user_panel_state(channels))

    # Start serial communication task
    asyncio.create_task(serial_write(channels))
    asyncio.create_task(serial_read(channels))
    asyncio.create_task(send_channels_state(channels))

    # Start the regulation tasks
    for ch in channels:
        asyncio.create_task(regulator(ch))

    # Safety relays task
    asyncio.create_task(safety_relays_control(channels))

    # Start do_nothing task to keep the event loop running
    asyncio.create_task(do_nothing())


# Create an Event Loop
loop = asyncio.get_event_loop()
# Create a task to run the main function
loop.create_task(main())
# loop.create_task(test_pwm_output())

try:
    # Run the event loop indefinitely
    loop.run_forever()
except Exception as e:
    print("Error occurred: ", e)
except KeyboardInterrupt:
    print("Program Interrupted by the user")
