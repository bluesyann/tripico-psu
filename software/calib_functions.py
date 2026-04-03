from pathlib import Path
import pandas as pd
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.stats import linregress

import logging

# ✓ ✗ ⚠ ℹ️ ⏳


OFFSETS_I_FILENAME = "offsets_i_noload_range"
COEFFS_I_FILENAME = "coeffs_i"


def load_calibration_files(range_index: int, channels: list, dir: Path) -> None:
    """Load calibration files for ammeter range r (0-4)"""

    calfile = dir / f"{OFFSETS_I_FILENAME}{range_index}.dat"
    logging.info(f"ℹ️ Trying to read offset file {calfile}...")
    df = pd.DataFrame()
    try:
        df = pd.read_csv(calfile)
        logging.info(f"✓ Loaded {len(df)} calibration points")
    except Exception as e:
        logging.warning(f"⚠ No calibration available for range {range_index}: {e}")

    # Process channels if data loaded
    if not df.empty:
        cols = df.columns.to_list()
        logging.debug("Dataframe columns: %s", cols)

        for ch in channels:
            channel_name = ch.get("name", ch.get("Name", ""))
            i_col, v_col = f"i{channel_name}", f"v{channel_name}"
            if v_col in cols and i_col in cols:
                logging.info("ℹ️ Loading current offsets for channel %s", channel_name)
                cal = df[[i_col, v_col]].copy()
                cal = cal.sort_values(v_col).reset_index(drop=True)
                ch["i_offset"] = resample_xy(cal, v_col, i_col, 300, 3).rename(
                    columns={v_col: "v", i_col: "i"}
                )
            else:
                logging.warning(
                    "Column %s or %s missing from I offsets table", v_col, i_col
                )

    logging.info(f"ℹ️ Getting Ammeters coeficients for range {range_index}...")
    try:
        # Get the apropriate file
        for f in dir.iterdir():
            if f.name.startswith(COEFFS_I_FILENAME) and f.name.endswith(
                f"range{range_index}.dat"
            ):
                # Get the resistor value from the filename _R1k_range
                R = f.name.split("_")[2][1:-1]
                logging.info(f"✓ Found a file for R={R} kOmhs ({f.name})")

                df = pd.DataFrame
                df = pd.read_csv(f)
                logging.debug(f"✓ Loaded {len(df)} calibration points")
                if not df.empty:
                    calculate_ammeter_coefs(df, float(R), channels, "va")
    except Exception as e:
        logging.warning(
            f"⚠ Cannot set a current coefficient for range {range_index}: {e}"
        )


def calculate_ammeter_coefs(df: pd.DataFrame, R: float, channels: list, chvref: str):
    """Compute and apply calibration coefficients for current channels.

    This function performs a linear regression between the measured
    reference voltage column and current column in the calibration DataFrame,
    and updates the channel dictionary with an `i_coef` gain factor.

    Arguments:
        - df: pd.DataFrame: calibration data containing columns for reference
          voltage and current per channel.
        - R: float: nominal shunt resistance used in the measurement setup
          (kΩ unit 1/kΩ conversion handled externally).
        - channels: list: list of channel dictionaries to update with coefficients.
        - chvref: str: name of the voltage reference column in `df`.

    Returns:
        - None
    """
    for ch in channels:
        channel_name = ch.get("name", ch.get("Name", None))
        if not channel_name:
            logging.warning("Skipping channel with no name in coefficient calculation")
            continue

        try:
            i_col = f"i{channel_name}"
            if chvref in df.columns and i_col in df.columns:
                result = linregress(df[chvref], df[i_col])
                logging.debug(
                    "Channel %s: y = %.4fx + %.4f (R² = %.4f)",
                    channel_name,
                    result.slope,
                    result.intercept,
                    result.rvalue**2,
                )
                ch["i_coef"] = float(1 / (R * result.slope))
            else:
                logging.warning(
                    "Column %s or %s missing from I coefficients table", chvref, i_col
                )
                ch["i_coef"] = 1.0
        except Exception as e:
            logging.warning(
                "⚠ Error calculating coefficient for channel %s: %s", channel_name, e
            )
            ch["i_coef"] = 1.0


def resample_xy(df: pd.DataFrame, x: str, y: str, n: int, sigma: int):
    """Smooth and resample x/y calibration points to a regular grid.

    Applies a Gaussian filter to the y values, then linearly interpolates
    into `n` evenly spaced x points between the min and max of the original.

    Arguments:
        - df: pd.DataFrame: calibration data with columns for x and y.
        - x: str: column name for independent variable (e.g., voltage).
        - y: str: column name for dependent variable (e.g., current offset).
        - n: int: number of samples in output table.
        - sigma: int: gaussian filter sigma for smoothing.

    Returns:
        - DataFrame: resampled values as columns x and y.
    """
    df = df[[x, y]]  # Ensure the df has only two columns
    df = df.sort_values(x).drop_duplicates(subset=[x])
    df[y] = gaussian_filter1d(df[y].values, sigma=sigma)

    # Define new regular x grid (100 points over your range of interest)
    xmin, xmax = df[x].min(), df[x].max()
    x_new = np.linspace(xmin, xmax, n)

    # Interpolate y onto the regular grid
    y_new = np.interp(x_new, df[x].values, df[y].values)

    return pd.DataFrame({x: x_new, y: y_new})
