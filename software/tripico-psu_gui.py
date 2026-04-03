import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from pathlib import Path
import serial_functions as serfn
import calib_functions as calfn
import yaml

import logging
from logging.handlers import RotatingFileHandler

level = logging.INFO

# File handler (as you have it)
file_handler = RotatingFileHandler(
    "tripicu-psu_gui.log",
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


class RealTimeGUI:
    def __init__(self):
        """Initialize the GUI application windows, widgets, and channels.

        Loads configuration from `pispos_config.yaml`, creates plot areas,
        channel controls, and initial state for asynchronous polling.
        """
        self.root = tk.Tk()
        self.root.title(config["gui"]["name"])
        self.root.geometry(f"{config['gui']['sizex']}x{config['gui']['sizey']}")

        # Serial connection
        self.ser = None
        self.device_var = None
        self.connection_status = None

        # Board state
        self.events = []  # Buffer to store events coming from the board
        self.range = None
        self.sampling_freq = config["gui"]["sampling_frequency"]
        self.graph_duration = config["gui"]["chart_duration"]

        # Channel definitions
        self.calibpath = Path(config["setup"].get("calibration_folder", ""))
        self.channel_names = config["setup"].get("channels", [])
        fg_channel_colors = config["gui"].get("foreground_channels_colors", {})
        bg_channel_colors = config["gui"].get("background_channels_colors", {})
        self.channels = []

        for name in self.channel_names:
            self.channels.append(
                {
                    "name": name,
                    "v_data": [],
                    "i_data": [],
                    "t_data": [],
                    "sp_data": [],
                    "setpoint": config["setup"].get("setpoint", 0),
                    "unit": config["setup"].get("unit", "v"),
                    "max_power": config["setup"].get("max_power", 1),
                    "i_offset": None,
                    "i_coef": 1.0,
                    # GUI elements
                    "fg_color": fg_channel_colors.get(name, "#000000"),
                    "bg_color": bg_channel_colors.get(name, "#FFFFFF"),
                    "setpoint_entry": None,
                    "unit_buttons": None,
                    "max_power_entry": None,
                    "ivp_monitor": None,
                    "status_box": None,
                }
            )

        self.setup_layout()
        # Running flag used to stop recurring callbacks on shutdown
        self._running = True
        # Bind window close (top-right cross) to graceful shutdown handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_layout(self) -> None:
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # GAUCHE: Colonne verticale simple
        left_column = tk.Frame(main_frame, width=340)
        left_column.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_column.pack_propagate(False)  # ← UNIQUEMENT ICI

        # Connection EN HAUT
        connection_panel = tk.LabelFrame(left_column, text="Connection")
        connection_panel.pack(fill=tk.X, pady=(10, 5))
        self.create_connection_section(connection_panel)

        # Channels EN DESSOUS
        control_panel = tk.LabelFrame(left_column, text="Channel Controls")
        control_panel.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        for ch in self.channels:
            self.create_channel_section(control_panel, ch)

        # RIGHT: PLOTS
        plot_frame = tk.Frame(main_frame)
        plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.fig = Figure(figsize=(10, 8))
        self.fig.subplots_adjust(
            left=0.08, right=0.98, top=0.95, bottom=0.08, hspace=0.05
        )

        self.ax_voltage = self.fig.add_subplot(2, 1, 1)
        self.voltage_lines = {}
        for ch in self.channels:
            (self.voltage_lines[ch["name"]],) = self.ax_voltage.plot(
                [], [], color=ch["fg_color"], label=f"Ch {ch['name']}", lw=2
            )
        self.ax_voltage.set_ylabel("Voltage (V)")
        self.ax_voltage.grid(True)
        self.ax_voltage.legend()
        self.ax_voltage.tick_params(axis="x", bottom=False, labelbottom=False)

        self.ax_current = self.fig.add_subplot(2, 1, 2, sharex=self.ax_voltage)
        self.current_lines = {}
        for ch in self.channels:
            (self.current_lines[ch["name"]],) = self.ax_current.plot(
                [], [], color=ch["fg_color"], label=f"Ch {ch['name']}", lw=2
            )
        self.ax_current.set_xlabel("Time (s)")
        self.ax_current.set_ylabel("Current (mA)")
        self.ax_current.grid(True)
        self.ax_current.legend()

        self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def create_channel_section(self, parent: tk.Frame, ch: dict) -> None:
        # Line 1: channel title
        ch_frame = tk.LabelFrame(
            parent,
            text=f"Channel {ch['name']}",
            font=("Arial", 12, "bold"),
            fg=ch["fg_color"],
            bg=ch["bg_color"],
            padx=8,
            pady=5,
        )
        ch_frame.pack(fill=tk.X, padx=8, pady=5)

        # Line 2: Voltage-Current-Power monitor
        ch["ivp_monitor"] = tk.Label(
            ch_frame,
            text="nd mA @ nd V  [ nd W ]",
            font=("Arial", 11, "bold"),
            fg=ch["fg_color"],
            bg=ch["bg_color"],
        )
        ch["ivp_monitor"].pack(fill=tk.X, pady=(5, 0))

        # Line 3: Setpoint | V/mA toggles
        row1 = tk.Frame(ch_frame, bg=ch["bg_color"])
        row1.pack(fill=tk.X, pady=(5, 2))
        row1.grid_columnconfigure(0, weight=1)
        row1.grid_columnconfigure(1, weight=1)

        setpoint_frame = tk.Frame(row1, bg=ch["bg_color"])
        setpoint_frame.grid(row=0, column=0, sticky="w", padx=(5, 5))

        ch["setpoint_entry"] = tk.Entry(
            setpoint_frame, font=("Arial", 12), width=10, justify=tk.CENTER
        )
        ch["setpoint_entry"].insert(0, "0.0")
        ch["setpoint_entry"].pack(anchor=tk.W, pady=(0, 5))

        toggle_frame = tk.Frame(row1, bg=ch["bg_color"])
        toggle_frame.grid(row=0, column=1, sticky="e", padx=(5, 5))

        ch["unit_buttons"] = {"V": None, "mA": None}
        ch["unit_buttons"]["V"] = tk.Button(
            toggle_frame,
            text="V",
            width=6,
            fg="White",
            font=("Arial", 10, "bold"),
            command=lambda c=ch: self.toggle_unit(c, "V"),
        )
        ch["unit_buttons"]["V"].config(bg=ch["fg_color"], relief=tk.RAISED)
        ch["unit_buttons"]["V"].pack(side=tk.LEFT, padx=(0, 3))

        ch["unit_buttons"]["mA"] = tk.Button(
            toggle_frame,
            text="mA",
            width=6,
            fg="White",
            font=("Arial", 10, "bold"),
            command=lambda c=ch: self.toggle_unit(c, "mA"),
        )
        ch["unit_buttons"]["mA"].config(bg="darkgray", relief=tk.SUNKEN)
        ch["unit_buttons"]["mA"].pack(side=tk.LEFT)

        # Line 3: Max power
        row2 = tk.Frame(ch_frame, bg=ch["bg_color"])
        row2.pack(fill=tk.X, pady=(5, 2))
        row2.grid_columnconfigure(0, weight=1)
        row2.grid_columnconfigure(1, weight=1)

        power_frame = tk.Frame(row2, bg=ch["bg_color"])
        power_frame.grid(row=0, column=0, sticky="w", padx=(5, 5))
        tk.Label(
            power_frame,
            text="Max Power:",
            bg=ch["bg_color"],
            font=("Arial", 11, "bold"),
        ).pack(anchor=tk.W, pady=(5, 2))

        entry_frame = tk.Frame(row2, bg=ch["bg_color"])
        entry_frame.grid(row=0, column=1, sticky="e", padx=(5, 5))
        ch["max_power_entry"] = tk.Entry(
            entry_frame, font=("Arial", 12), width=8, justify=tk.CENTER
        )
        ch["max_power_entry"].insert(0, "1.0")
        ch["max_power_entry"].pack(side=tk.LEFT, padx=(0, 3))
        tk.Label(entry_frame, text="W", bg=ch["bg_color"], font=("Arial", 11)).pack(
            side=tk.LEFT
        )

        update_btn = tk.Button(
            ch_frame,
            text="Update",
            command=lambda c=ch: self.update_channel(c),
            bg="#e0e0e0",
            fg="Black",
            font=("Arial", 10, "bold"),
            width=8,
        )
        update_btn.pack(fill=tk.X, pady=(5, 0))

        ch["status_box"] = tk.Label(
            ch_frame,
            text="Undefined",
            font=("Arial", 12, "bold"),
            fg="gray",
            bg="lightgray",
            relief=tk.RIDGE,
            padx=10,
            pady=3,
        )
        ch["status_box"].pack(fill=tk.X, pady=(2, 5))

    def toggle_unit(self, ch: dict, unit: str) -> None:
        ch["unit"] = unit
        for u, btn in ch["unit_buttons"].items():
            if u == unit:
                btn.config(bg=ch["fg_color"], relief=tk.RAISED)
            else:
                btn.config(bg="darkgray", relief=tk.SUNKEN)

    def update_channel(self, ch: dict) -> None:
        try:
            ch["setpoint"] = float(ch["setpoint_entry"].get())
            ch["max_power"] = float(ch["max_power_entry"].get())
            logging.info(
                "Channel %s updated: %s %s, Max Power: %s W",
                ch["name"],
                ch["setpoint"],
                ch.get("unit"),
                ch["max_power"],
            )

            regulation = "v"
            if ch.get("unit") == "mA":
                regulation = "i"

            cmd = f"{ch['name']} {regulation}"
            serfn.safe_write(self.ser, cmd)

            cmd = f"{ch['name']} {ch['setpoint']}"
            serfn.safe_write(self.ser, cmd)

            cmd = f"{ch['name']} {ch['max_power']}w"
            serfn.safe_write(self.ser, cmd)

        except ValueError:
            logging.error("Invalid numeric values for Channel %s", ch.get("name", "?"))

    def update_events(self) -> None:
        """
        This function watches the content of the event_list and
        eventually update GUI textboxes or trigger relays in case of overload
        """
        for event in self.events:
            logging.info(f"Event recieved: {event}")
            ep = event.split(" ")
            if "PushPullConnected" in event and len(ep) == 4:
                try:
                    n = self.channel_names.index(ep[1])
                    if ep[3] == "True":
                        self.root.after(
                            0,
                            self.channels[n]["status_box"].config(
                                text="Push-pull output connected", fg="green"
                            ),
                        )
                    else:
                        self.root.after(
                            0,
                            self.channels[n]["status_box"].config(
                                text="Push-pull output disconnected", fg="gray"
                            ),
                        )
                except Exception as e:
                    logging.error("Error parsing switch state: %s", e)
            elif "Range" in event and len(ep) == 3:
                try:
                    self.range = int(ep[1])
                    # Update the calibrations for the new range
                    try:
                        calfn.load_calibration_files(
                            self.range, self.channels, self.calibpath
                        )
                    except Exception as e:
                        logging.error(
                            f"Error getting the calibration for range {self.range}: {e}"
                        )
                except Exception as e:
                    logging.error(f"Error parsing range: {e}")
            elif "State" in event and len(ep) >= 3:
                try:
                    n = self.channel_names.index(ep[1])
                    message = " ".join(ep[2:])
                    color = "green"
                    if "Saturation" in message:
                        color = "red"
                    self.root.after(
                        0, self.channels[n]["StatusBox"].config(text=message, fg=color)
                    )
                except Exception as e:
                    logging.error(f"Error parsing state: {e}")
            elif "Alert " in event:
                try:
                    n = self.channel_names.index(ep[1])
                    message = " ".join(ep[3:])
                    self.root.after(
                        0, self.channels[n]["StatusBox"].config(text=message, fg="red")
                    )
                except Exception as e:
                    logging.error(f"Error parsing alert: {e}")

        self.events.clear()
        if self._running:
            self.root.after(100, self.update_events)

    def update_plot(self) -> None:
        try:
            # Update the sampling frequency from the GUI if is it has changed
            f = float(self.sampling_var.get())
            if f != self.sampling_freq:
                if f >= 1 and f <= 20:
                    logging.info(
                        f"Updating sampling frequency from {self.sampling_freq} to {f} Hz"
                    )
                    serfn.safe_write(self.ser, f"set sampling {f}")
                    self.sampling_freq = f

            # Update the graph duration from the GUI if it has changed
            d = float(self.time_var.get())
            if d != self.graph_duration:
                if d >= 5 and d <= 1000:
                    logging.info(
                        f"Updating graph duration from {self.graph_duration} to {d} s"
                    )
                    self.graph_duration = d

            # Remove oldest points from the dataset
            max_points = int(self.graph_duration * self.sampling_freq)
            logging.debug("Removing oldest points")
            for ch in self.channels:
                if len(ch["v_data"]) > max_points:
                    ch["v_data"] = ch["v_data"][-max_points:]
                if len(ch["i_data"]) > max_points:
                    ch["i_data"] = ch["i_data"][-max_points:]
                if len(ch["t_data"]) > max_points:
                    ch["t_data"] = ch["t_data"][-max_points:]

            # Update the plots
            for ch in self.channels:
                if len(ch["t_data"]) > 0:
                    t_relative = [x - ch["t_data"][-1] for x in ch["t_data"]]
                    self.voltage_lines[ch["name"]].set_data(t_relative, ch["v_data"])
                    self.current_lines[ch["name"]].set_data(t_relative, ch["i_data"])

            # Set voltage plot style
            self.ax_voltage.relim()
            self.ax_voltage.autoscale_view()
            self.ax_voltage.set_xlim(-self.graph_duration, 0)

            # Set current plot style
            self.ax_current.relim()
            self.ax_current.autoscale_view()
            self.ax_current.set_xlim(-self.graph_duration, 0)

            self.canvas.draw()
        except Exception as e:
            logging.error(f"Error while updating the charts: {e}")

        if self._running:
            self.root.after(int(1000 / self.sampling_freq), self.update_plot)

    def read_serial(self):
        """Poll serial data periodically and buffer incoming events."""
        if not self._running:
            return
        if self.ser is None:
            logging.debug("Serial connection not set")
            if self._running:
                self.root.after(1000, self.read_serial)
        else:
            try:
                serfn.read_serial_values(self.ser, self.events, self.channels)
            except Exception as e:
                logging.error(f"Error while reading serial: {e}")
            if self._running:
                self.root.after(1, self.read_serial)

    def on_close(self) -> None:
        """Gracefully stop recurring callbacks, close serial port and destroy the Tk window."""
        logging.info("Shutting down GUI gracefully...")
        # Prevent further callbacks
        self._running = False
        # Try to close serial port if open
        try:
            serfn.close_serial_link(self.ser)
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def get_user_panel(self) -> None:
        """
        To run once on startup to get switches states
        Subsequent events will be parsed by update_events function
        """
        if self.ser is not None:
            config = serfn.get_current_config(self.ser)
            if not config["communicating"]:
                # Close the connection of no answer from the pico
                self.ser = None
            else:
                # Set the ammeter range and load the calibration
                self.range = int(config["ammeter_range"])
                try:
                    calfn.load_calibration_files(
                        self.range, self.channels, self.calibpath
                    )
                except Exception as e:
                    logging.error(
                        f"Error getting the calibration for range {self.range}: {e}"
                    )
                for ch in self.channels:
                    logging.debug(
                        f"Checking channel {ch['name']} state: switch on {config[f"{ch['name']}_pushpull_connected"]}"
                    )
                    if config[f"{ch['name']}_pushpull_connected"] == "True":
                        self.root.after(
                            0, ch["status_box"].config(text=f"Regulating", fg="green")
                        )
                    else:
                        self.root.after(
                            0,
                            ch["status_box"].config(
                                text=f"Push-pull output disconnected", fg="gray"
                            ),
                        )

    def update_ivp_monitor(self) -> None:
        for ch in self.channels:
            i, v = None, None
            if len(ch["v_data"]) > 0:
                v = ch["v_data"][-1]
            if len(ch["i_data"]) > 0:
                i = ch["i_data"][-1]
            if i is not None and v is not None:
                punit = "mW"
                p = i * v  # milliwatts since I is in mA
                if p > 100:
                    punit = "W"
                    p *= 1e-3
                ch["IVPmonitor"].config(
                    text=f"{i:.3f} mA @ {v:.2f} V  [ {p:.3f} {punit} ]"
                )
        self.root.after(50, self.update_ivp_monitor)

    def create_connection_section(self, parent):
        """Create the connection panel with device selection and status widgets.

        Args:
            parent: tk.Frame: parent frame to attach controls.
        """
        # Ligne 1: Device (gauche) | Baudrate (droite) - HORIZONTAUX
        main_row = tk.Frame(parent)
        main_row.pack(fill=tk.X, pady=(10, 8))
        main_row.grid_columnconfigure(0, weight=1)
        main_row.grid_columnconfigure(1, weight=1)

        # GAUCHE: Device + Dropdown
        device_frame = tk.Frame(main_row)
        device_frame.grid(row=0, column=0, sticky="w", padx=(10, 5), pady=2)

        tk.Label(device_frame, text="Device:", font=("Arial", 11, "bold")).pack(
            anchor=tk.W
        )
        import glob

        self.device_ports = [
            p for p in glob.glob(config["setup"]["device"]) if "Bluetooth" not in p
        ]
        self.device_ports = self.device_ports or ["No device found"]

        self.device_var = tk.StringVar(value=self.device_ports[0])
        self.device_dropdown = ttk.Combobox(
            device_frame,
            textvariable=self.device_var,
            values=self.device_ports,
            width=18,
            state="readonly",
        )
        self.device_dropdown.pack(anchor=tk.W, pady=(0, 3))

        # DROITE: Baudrate + Textbox
        baud_frame = tk.Frame(main_row)
        baud_frame.grid(row=0, column=1, sticky="e", padx=(5, 10), pady=2)

        tk.Label(baud_frame, text="Baudrate:", font=("Arial", 11, "bold")).pack(
            anchor=tk.E
        )
        self.baud_var = tk.StringVar(value="115200")
        baud_entry = tk.Entry(
            baud_frame,
            textvariable=self.baud_var,
            font=("Arial", 12),
            width=12,
            justify=tk.CENTER,
        )
        baud_entry.pack(anchor=tk.E, pady=(0, 3))

        # Ligne 2: Connect button pleine largeur
        connect_btn = tk.Button(
            parent,
            text="Connect",
            command=self.connect_pico,
            bg="#2196F3",
            fg="white",
            font=("Arial", 12, "bold"),
            height=1,
            relief=tk.RAISED,
        )
        connect_btn.pack(fill=tk.X, padx=10, pady=(0, 8))

        # Line 3: Status connection
        self.connection_status = tk.Label(
            parent,
            text="Disconnected",
            font=("Arial", 11, "bold"),
            fg="red",
            bg="#f8f9fa",
            relief=tk.RIDGE,
            pady=5,
            height=1,
        )
        self.connection_status.pack(fill=tk.X, padx=10, pady=(0, 5))

        # Line 4: Time window and sampling frequency
        row4 = tk.Frame(parent)
        row4.pack(fill=tk.X, pady=(10, 8))
        row4.grid_columnconfigure(0, weight=1)
        row4.grid_columnconfigure(1, weight=1)

        # Left: Sampling frequency
        sampling_frame = tk.Frame(row4)
        sampling_frame.grid(row=0, column=0, sticky="w", padx=(10, 5), pady=2)
        tk.Label(
            sampling_frame, text="Sampling (Hz):", font=("Arial", 11, "bold")
        ).pack(anchor=tk.W)
        self.sampling_var = tk.StringVar(value=self.sampling_freq)
        sampling_entry = tk.Entry(
            sampling_frame,
            textvariable=self.sampling_var,
            font=("Arial", 12),
            width=12,
            justify=tk.CENTER,
        )
        sampling_entry.pack(anchor=tk.W, pady=(0, 3))

        # Right: Time window
        time_frame = tk.Frame(row4)
        time_frame.grid(row=0, column=1, sticky="e", padx=(5, 10), pady=2)
        tk.Label(time_frame, text="Time window (s):", font=("Arial", 11, "bold")).pack(
            anchor=tk.W
        )
        self.time_var = tk.StringVar(value=self.graph_duration)
        time_entry = tk.Entry(
            time_frame,
            textvariable=self.time_var,
            font=("Arial", 12),
            width=12,
            justify=tk.CENTER,
        )
        time_entry.pack(anchor=tk.W, pady=(0, 3))

    def connect_pico(self):
        """Open serial connection and set initial panel state from Pico."""
        try:
            port = self.device_var.get()
            baud = int(self.baud_var.get())

            self.ser = serfn.setup_serial_link(port, baud)
            self.get_user_panel()
            if self.ser is None:
                self.connection_status.config(text=f"No reply from {port}", fg="red")
            else:
                self.connection_status.config(
                    text=f"Connected: {port} @ {baud}", fg="green"
                )
                logging.info(f"Connected to {port} @ {baud}")

                # Set the sampling frequency to 10 Hz
                serfn.safe_write(self.ser, f"set sampling {self.sampling_freq}")

        except Exception as e:
            self.connection_status.config(text=f"Connection failed: {str(e)}", fg="red")
            logging.error(f"Connection error: {e}")
            self.ser = None

    def run(self):
        """Start GUI polling loops and enter the Tkinter main event loop."""
        self.read_serial()
        self.update_events()
        self.update_ivp_monitor()
        self.update_plot()
        self.root.mainloop()


if __name__ == "__main__":
    try:
        # Read global configuration file
        config_path = Path("tripico-psu_config.yaml")
        config = yaml.safe_load(config_path.read_text())
        if config is not None:
            app = RealTimeGUI()
            app.run()
        else:
            logging.error(f"Cant open configuration yaml file {config_path}")
    except Exception as e:
        logging.error(f"Error while opening {config_path}: {e}")
