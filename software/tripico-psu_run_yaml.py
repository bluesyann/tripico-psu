from pathlib import Path
import yaml
from jsonschema import validate, ValidationError
import pandas as pd
import asyncio

import matplotlib.pyplot as plt

plt.ion()  # Enable interactive mode

import os
import signal


def is_valid_file(parser, arg):
    """Argparse type helper to validate that the provided path exists.

    Arguments:
        - parser: argparse.ArgumentParser: used to report errors.
        - arg: str: path argument from CLI.

    Returns:
        - Path: validated path object.
    """
    if not os.path.isfile(arg):
        parser.error(f"The file {arg} does not exist!")
    else:
        return Path(arg)


import argparse

parser = argparse.ArgumentParser(
    description="Run voltage sweeps or monitor the multichannel Voltage/Current sensing inteface."
)
parser.add_argument(
    "file",
    type=lambda x: is_valid_file(parser, x),
    help="YAML file describing the process.",
)
parser.add_argument(
    "-device",
    type=str,
    default="/dev/ttyACM0",
    help="Path to the Raspberry Pico device.",
)
parser.add_argument(
    "-baud", type=int, default=115200, help="Baud rate for serial communication."
)
parser.add_argument(
    "-d", "--debug", action="store_true", help="Activate debug logging."
)
parser.add_argument(
    "--no-prompt",
    action="store_true",
    help="Don't wait for interactive prompt at the end of a characterization",
)
args = parser.parse_args()


import logging
from logging.handlers import RotatingFileHandler

level = logging.INFO

# File handler (as you have it)
file_handler = RotatingFileHandler(
    "tripico-psu_run_yaml.log",
    maxBytes=1 * 1024 * 1024,  # 1MB
    backupCount=1,
)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

# Stream handler (for terminal output)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

# Configure logging with both handlers
logging.basicConfig(
    level=level,
    handlers=[file_handler, stream_handler]
)

import serial_functions as serfn
import calib_functions as calfn

PLOT_INTERVAL = 1.0  # seconds


def validate_yaml(data_file: Path, schema_file: Path) -> bool:
    """Validate YAML data against a JSON schema.

    Arguments:
        - data_file: Path: path to YAML file with input configuration.
        - schema_file: Path: path to schema YAML file.

    Returns:
        - bool: True if validation succeeds, False on error.
    """
    logging.info(f"ℹ️ Checking if {data_file} has a valid schema")

    # Load YAML files
    with open(data_file) as f:
        data = yaml.safe_load(f)
    with open(schema_file) as f:
        schema = yaml.safe_load(f)

    try:
        validate(instance=data, schema=schema)
        logging.info("✓ Valid YAML!")
        return True
    except ValidationError as e:
        logging.error(f"✗ Validation failed: {e.message}")
        return False


def create_channels(config: dict) -> list:
    """Create channel data containers from setup configuration."""
    channel_names = config.get("setup", {}).get("channels", [])
    default_setpoint = config.get("setup", {}).get("setpoint", 0)
    default_max_power = config.get("setup", {}).get("max_power", 1)

    channels = []
    for name in channel_names:
        channels.append(
            {
                "name": name,
                "v_data": [],
                "i_data": [],
                "t_data": [],
                "sp_data": [],
                "setpoint": default_setpoint,
                "max_power": default_max_power,
                "i_offset": None,
                "i_coef": 1.0,
            }
        )
    return channels


def get_channel_time_series(channels: list) -> pd.DataFrame:
    """Aggregate channel time-series into a single normalized DataFrame."""
    df = pd.DataFrame()
    if not channels:
        logging.warning("No channels provided to build time series")
        return df

    try:
        for ch in channels:
            chdf = pd.DataFrame(
                list(zip(ch["t_data"], ch["v_data"], ch["i_data"], ch["sp_data"])),
                columns=["t", f"v{ch['name']}", f"i{ch['name']}", f"sp{ch['name']}"],
            )
            df = chdf if df.empty else pd.merge(df, chdf, on="t", how="outer")

        if not df.empty:
            df["t"] = df["t"] - df["t"].min()

        return df
    except Exception as e:
        logging.error("Error while building the dataframe from channels: %s", e)
        return pd.DataFrame()


async def static_run(static: dict) -> None:
    """Hold current setpoints for a fixed duration during a static test.

    Arguments:
        - static: dict: contains `duration` in seconds.

    Returns:
        - None
    """
    duration = static["duration"]
    logging.info(f"⏳ getting data for {duration} seconds...")
    await asyncio.sleep(duration)
    logging.info("✓ Static run completed.")


async def plot_values(channels: list, par: dict, dir: Path):
    """Plot channel quantity over time using a live matplotlib loop.

    Arguments:
        - channels: list: list of channel dictionaries with time series.
        - par: dict: plotting parameters (x, y, color, labels, file, etc.).
        - dir: Path: folder to save plot files when requested.

    Returns:
        - None
    """
    _, ax = plt.subplots()
    logging.info(f"ℹ️ Starting plot for {par}")
    while True:
        try:
            df = get_channel_time_series(channels)

            if len(df) > 5:
                logging.debug(f"Plotting {len(df)} data points")

                ax.clear()  # Clear the axes
                size = par.get("size", 10)  # Default dot size
                if par.get("color") is not None:
                    for y in par["y"]:
                        ax.scatter(
                            df[par["x"]], df[y], label=y, c=df[par["color"]], s=size
                        )
                else:
                    for y in par["y"]:
                        ax.scatter(df[par["x"]], df[y], label=y, s=size)
                ax.set_xlabel(par["xlabel"])
                ax.set_ylabel(par["ylabel"])
                ax.set_title(par["name"])
                ax.grid()
                plt.draw()  # Update the plot
                if "file" in par:
                    plt.savefig(dir / par["file"])  # Save the figure to file
                plt.pause(0.01)  # Small pause to allow rendering
        except Exception as e:
            logging.error(f"Error while drawing chart: {e}")

        await asyncio.sleep(PLOT_INTERVAL)


async def main() -> None:
    """Entry point for running the full characterization workflow.

    Reads configuration, initializes hardware, executes sweeps/static tests,
    and saves CSV output as configured.

    Arguments:
        - None

    Returns:
        - None
    """
    usr_file = args.file
    working_dir = usr_file.parents[0]

    # Read global configuration file
    config_path = Path("tripico-psu_config.yaml")
    config = yaml.safe_load(config_path.read_text())
    if not config:
        logging.error("✗ Unable to read %s", config_path)
        return

    channels = create_channels(config)
    if not channels:
        logging.error("✗ No channels were configured. Check pispos_config.yaml")
        return

    # Validate input YAML file against schema
    usr_input_path = Path(usr_file)
    validation_schema_path = Path("validation_schema.yaml")
    if not validate_yaml(usr_input_path, validation_schema_path):
        return

    usr_input = yaml.safe_load(usr_input_path.read_text())

    ser = serfn.setup_serial_link(args.device, args.baud)
    if ser is None:
        logging.error("✗ Could not connect to serial device %s", args.device)
        return

    try:
        for carac in usr_input.get("caracs", []):
            logging.info("ℹ️ Running characterization: %s", carac.get("name"))

            range_index = serfn.wait_until_panel_ready(ser, carac["init"])
            calibration_folder = Path(config["setup"]["calibration_folder"])
            calfn.load_calibration_files(range_index, channels, calibration_folder)

            serfn.initialize_channels(carac["init"], ser)

            events = []
            tasks = [asyncio.create_task(serfn.read_serial_loop(ser, events, channels))]
            if "sweep" in carac:
                tasks.append(asyncio.create_task(serfn.run_sweep(carac["sweep"], ser)))
            elif "static" in carac:
                tasks.append(asyncio.create_task(static_run(carac["static"])))
            else:
                logging.error(
                    "✗ No sweep or static defined in carac %s", carac.get("name")
                )
                serfn.initialize_channels(None, ser)
                continue

            for chart in carac.get("plots", []):
                tasks.append(
                    asyncio.create_task(plot_values(channels, chart, working_dir))
                )

            stop_event = asyncio.Event()
            loop = asyncio.get_running_loop()

            def signal_handler() -> None:
                logging.info("ℹ️ Signal received, stopping tasks...")
                stop_event.set()

            for s in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(s, signal_handler)
                except NotImplementedError:
                    pass

            _, pending = await asyncio.wait(
                tasks + [asyncio.create_task(stop_event.wait())],
                return_when=asyncio.FIRST_COMPLETED,
            )

            if stop_event.is_set():
                logging.info("✓ Stopping due to external signal")
            else:
                logging.info("✓ First task completed; canceling others")

            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

            serfn.initialize_channels(None, ser)

            if "datafile" in carac:
                data_df = get_channel_time_series(channels)
                output_path = working_dir / carac["datafile"]
                data_df.to_csv(output_path, index=False)
                logging.info("✓ Results saved to %s", output_path)

            if not args.no_prompt:
                try:
                    await asyncio.to_thread(
                        input, "Press Enter to end this characterization"
                    )
                except Exception as e:
                    logging.warning("Could not display prompt: %s", e)

    except Exception as e:
        logging.error("✗ Unexpected failure in main: %s", e)

    finally:
        serfn.close_serial_link(ser)


if __name__ == "__main__":
    asyncio.run(main())
