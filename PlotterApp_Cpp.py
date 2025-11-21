import collections
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import FuncFormatter
import seaborn as sns
import os
import sys
import tempfile

dirname = os.path.dirname(__file__)
os.chdir(dirname)
sys.path.insert(0, dirname)

try:
    import QuTAG_MC
except ImportError:
    QuTAG_MC = None
    print("TT wrapper not found; running in offline mode.")

try:
    import coincfinder
except ImportError as exc:
    print("Failed to import coincfinder module:", exc)
    raise

SETTINGS_FILE = os.path.join(dirname, "plotter_settings.json")

DEFAULT_SETTINGS = {
    "delays_ps": {str(ch): 0 for ch in range(1, 9)},
    "histogram": {
        "window_ps": 200,
        "delay_start_ps": -15_000,
        "delay_end_ps": -8_000,
        "delay_step_ps": 50,
    },
    "window_seconds": 600
}


def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return {**DEFAULT_SETTINGS, **data}
        except Exception as exc:
            print("Failed to load settings; using defaults:", exc)
    return json.loads(json.dumps(DEFAULT_SETTINGS))


def save_settings(data: dict) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception as exc:
        print("Failed to save settings:", exc)


settings = load_settings()
WINDOW_SECONDS = settings.setdefault("window_seconds", 200)
save_settings(settings)
rolling_manager = coincfinder.RollingSingles(WINDOW_SECONDS)

# Initialize QuTAG device (if available)
tt = None
tt_connected = False
exposure_time = 0.5  # seconds
expTime = int(exposure_time * 1000)
coincWin = 200
if QuTAG_MC is not None:
    try:
        tt = QuTAG_MC.QuTAG()
        tt_connected = True
        tt.setExposureTime(int(expTime * 1000))
        _, coincWin, expTime = tt.getDeviceParams()
        print(f"Coincidence window: {coincWin} Bins\nExposure time: {expTime} ms")
    except Exception as exc:
        print("Failed to initialize QuTAG device:", exc)
        tt = None
        tt_connected = False

channels = list(range(1, 9))


AUTO_ALIGN_PAIRS = [
    (1, 5), (2, 6), (3, 7), (4, 8),
    (1, 6), (2, 5), (3, 8), (4, 7),
]
coincidences_type_I_0 = AUTO_ALIGN_PAIRS
coincidences_type_II = coincidences_type_I_0.copy()
coincidences = coincidences_type_I_0

singles_data = {ch: {"t": [], "counts": []} for ch in channels}
def initialize_coincidences_data(coinc_dict):
    return {coinc: {"t": [], "counts": []} for coinc in coinc_dict}

coincidences_data = initialize_coincidences_data(coincidences)

latest_duration_sec = 0.0
chunk_index = 0

def flatten_channel(singles_obj):
    if singles_obj is None:
        return []
    flattened = []
    for bucket in singles_obj.events_per_second:
        flattened.extend(bucket)
    return flattened


delay_vars = {}


def get_channel_delay(ch: int) -> float:
    var = delay_vars.get(ch)
    if var is None:
        return float(settings["delays_ps"].get(str(ch), 0.0))
    try:
        return float(var.get())
    except Exception:
        return 0.0


def set_channel_delay(ch: int, value: float) -> None:
    settings.setdefault("delays_ps", {})[str(ch)] = value
    save_settings(settings)
    var = delay_vars.get(ch)
    if var is not None:
        var.set(value)

newdata = 0
running = True

# Set up color maps
# Generate a list of distinct colors from the colormaps
color_bg = "#474747" #"#ffbbc8ae" # cmr.tropical(0.95) 
color_grid = '#ff646f6d'
colors = [
    "#FF595E",  # bright red
    "#FFCA3A",  # vivid yellow
    "#8AC926",  # lime green
    "#1982C4",  # azure blue
    "#6A4C93",  # violet purple
    "#FF924C",  # orange
    "#9D4EDD",  # purple
    "#2EC4B6",  # turquoise
    "#E71D36",  # scarlet
    "#F15BB5",  # magenta
    "#00BBF9",  # sky blue
    "#00F5D4",  # cyan mint
]

# General plot stuff
current_plot = "both"
legend_opacity = 0
contrast_str = "phi+I"
bell_states = ["phi+","phi+I","phi-","phi-I"]

selected_channels = None
histogram_params = settings.get("histogram", {}).copy()
COINC_WINDOW_PS = histogram_params.get("window_ps", 500)

def initialize_selected_channels():
    return {ch: tk.BooleanVar(value=True) for ch in channels}


# Timestamp helpers
def capture_timestamps_to_file(silent: bool = False):
    if not tt_connected or tt is None:
        if not silent:
            messagebox.showwarning("Capture", "Time tagger not connected.")
        return None
    if not hasattr(tt, "writeTimestamps"):
        if not silent:
            messagebox.showerror("Capture", "writeTimestamps not available on this device.")
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bin", dir=dirname)
    tmp.close()
    try:
        tt.writeTimestamps(tmp.name, tt.FILEFORMAT_BINARY)
        return tmp.name
    except Exception as exc:
        os.unlink(tmp.name)
        if not silent:
            messagebox.showerror("Capture", f"Failed to record timestamps: {exc}")
        else:
            print("Failed to record timestamps:", exc)
        return None

def load_bin_file(path: str, show_messages: bool = True) -> bool:
    if not os.path.exists(path):
        if show_messages:
            messagebox.showerror("Load", "Selected file does not exist.")
        return False
    try:
        singles_map, duration_sec = coincfinder.read_file_auto(path)
        rolling_manager.append_chunk(singles_map)
    except Exception as exc:
        if show_messages:
            messagebox.showerror("Load", f"Failed to read file: {exc}")
        else:
            print("Failed to read file:", exc)
        return False

    flattened = {}
    for ch in channels:
        singles_obj = singles_map.get(ch)
        flat = flatten_channel(singles_obj) if singles_obj else []
        if flat:
            flattened[ch] = flat
    if not flattened:
        if show_messages:
            messagebox.showwarning("Load", "No timestamps found for selected channels.")
        return False

    global latest_duration_sec
    latest_duration_sec = duration_sec
    if show_messages and 'root' in globals():
        try:
            root.after(0, apply_flattened_data, flattened, duration_sec)
        except Exception as exc:
            print("Failed to refresh plots:", exc)
    else:
        apply_flattened_data(flattened, duration_sec)
    return True


def update_live_series(flattened: dict, duration_sec: float) -> None:
    global chunk_index
    chunk_index += 1
    span = duration_sec if duration_sec else max(exposure_time, 1e-3)
    time_val = chunk_index * span

    for ch in channels:
        t_series = singles_data[ch]["t"]
        c_series = singles_data[ch]["counts"]
        count = len(flattened.get(ch, [])) / span
        t_series.append(time_val)
        c_series.append(count)
        if len(t_series) > 200:
            t_series.pop(0)
            c_series.pop(0)

    for label, (ch1, ch2) in coincidences.items():
        rate = 0.0
        if ch1 in flattened and ch2 in flattened:
            offsets = [int(round(get_channel_delay(ch1))), int(round(get_channel_delay(ch2)))]
            rate = coincfinder.count_nfold_coincidences(
                [flattened[ch1], flattened[ch2]],
                coinc_window_ps=int(round(COINC_WINDOW_PS)),
                offsets_ps=offsets,
            ) / span
        t_series = coincidences_data[label]["t"]
        c_series = coincidences_data[label]["counts"]
        t_series.append(time_val)
        c_series.append(rate)
        if len(t_series) > 200:
            t_series.pop(0)
            c_series.pop(0)


def apply_flattened_data(flattened, duration_sec):
    update_live_series(flattened, duration_sec)
    refresh_current_plots()


def prompt_load_bin_dialog():
    path = filedialog.askopenfilename(
        parent=root,
        title="Select BIN file",
        filetypes=(("BIN files", "*.bin"), ("All files", "*.*")),
    )
    if path:
        load_bin_file(path)


def get_histogram_params_ps() -> tuple[int, int, int, int]:
    window_ps = int(round(hist_window_var.get()))
    start_ps = int(round(hist_start_var.get()))
    end_ps = int(round(hist_end_var.get()))
    step_ps = max(1, int(round(hist_step_var.get())))
    return window_ps, start_ps, end_ps, step_ps


def latest_trace_for_channel(channel: int) -> list[int]:
    chunk = rolling_manager.latest_chunk(channel)
    trace: list[int] = []
    for bucket in chunk:
        trace.extend(bucket)
    return trace


def has_histogram_data() -> bool:
    for ch in channels:
        if rolling_manager.latest_chunk(ch):
            return True
    return False


def capture_and_store_chunk():
    path = capture_timestamps_to_file()
    if path:
        if load_bin_file(path, show_messages=True):
            try:
                os.unlink(path)
            except OSError:
                pass
            refresh_current_plots()


def plot_histogram_action():
    ch_a = hist_channel_a_var.get()
    ch_b = hist_channel_b_var.get()
    trace_a = latest_trace_for_channel(ch_a)
    trace_b = latest_trace_for_channel(ch_b)
    if not trace_a or not trace_b:
        messagebox.showwarning("Histogram", "Capture or load timestamps first.")
        return
    window_ps, start_ps, end_ps, step_ps = get_histogram_params_ps()
    histogram = coincfinder.compute_coincidences_for_range_ps(
        trace_a,
        trace_b,
        coinc_window_ps=window_ps,
        delay_start_ps=start_ps,
        delay_end_ps=end_ps,
        delay_step_ps=step_ps,
    )
    if not histogram:
        messagebox.showinfo("Histogram", "No coincidences found for selected range.")
        return
    hist_ax.clear()
    delays_ns = [entry[0] for entry in histogram]
    counts = [entry[1] for entry in histogram]
    hist_ax.plot(delays_ns, counts, linewidth=2, color="tab:blue")
    hist_ax.set_xlabel("Delay (ns)")
    hist_ax.set_ylabel("Coincidences")
    hist_ax.set_title(f"Histogram Ch {ch_a} vs {ch_b}")
    hist_ax.grid(True, linestyle=":")
    hist_canvas.draw_idle()


def auto_set_selected_pair():
    ch_a = hist_channel_a_var.get()
    ch_b = hist_channel_b_var.get()
    trace_a = latest_trace_for_channel(ch_a)
    trace_b = latest_trace_for_channel(ch_b)
    if not trace_a or not trace_b:
        messagebox.showwarning("Auto-set", "Capture or load timestamps first.")
        return
    window_ps, start_ps, end_ps, step_ps = get_histogram_params_ps()
    best_delay = coincfinder.find_best_delay_ps(
        trace_a,
        trace_b,
        coinc_window_ps=window_ps,
        delay_start_ps=start_ps,
        delay_end_ps=end_ps,
        delay_step_ps=step_ps,
    )
    set_channel_delay(ch_b, best_delay)
    messagebox.showinfo(
        "Auto-set",
        f"Best delay for channel {ch_b} relative to {ch_a}: {best_delay:.1f} ps",
    )


def open_auto_align_dialog():
    if not has_histogram_data():
        messagebox.showwarning("Auto align", "Capture or load timestamps first.")
        return

    dialog = tk.Toplevel(root)
    dialog.title("Select coincidences")
    vars_map = {}
    ttk.Label(dialog, text="Select coincidence pairs to align:").pack(padx=10, pady=10)
    list_frame = ttk.Frame(dialog)
    list_frame.pack(padx=10, pady=5)
    for pair in AUTO_ALIGN_PAIRS:
        label = f"{pair[0]}/{pair[1]}"
        var = tk.BooleanVar(value=True)
        vars_map[pair] = var
        ttk.Checkbutton(list_frame, text=label, variable=var).pack(anchor="w")

    def on_ok():
        selections = [pair for pair, var in vars_map.items() if var.get()]
        dialog.destroy()
        if selections:
            run_auto_align(selections)

    ttk.Button(dialog, text="Align", command=on_ok).pack(pady=10)


def run_auto_align(pairs):
    window_ps, start_ps, end_ps, step_ps = get_histogram_params_ps()
    results = []
    for ref, target in pairs:
        trace_ref = latest_trace_for_channel(ref)
        trace_target = latest_trace_for_channel(target)
        if not trace_ref or not trace_target:
            continue
        best = coincfinder.find_best_delay_ps(
            trace_ref,
            trace_target,
            coinc_window_ps=window_ps,
            delay_start_ps=start_ps,
            delay_end_ps=end_ps,
            delay_step_ps=step_ps,
        )
        set_channel_delay(target, best)
        results.append((target, best))

    if not results:
        messagebox.showinfo("Auto align", "No delays were updated (insufficient data).")
        return

    popup = tk.Toplevel(root)
    popup.title("Alignment results")
    ttk.Label(popup, text="Updated delays (ps):").pack(padx=10, pady=10)
    for ch, delay in results:
        ttk.Label(popup, text=f"Channel {ch}: {delay:.1f}").pack(anchor="w", padx=10)
    ttk.Button(popup, text="Close", command=popup.destroy).pack(pady=10)

    for label, (ch1, ch2) in coincidences.items():
        counts = 0
        if ch1 in flattened and ch2 in flattened:
            offsets = [int(round(get_channel_delay(ch1))), int(round(get_channel_delay(ch2)))]
            counts = coincfinder.count_nfold_coincidences(
                [flattened[ch1], flattened[ch2]],
                coinc_window_ps=int(round(COINC_WINDOW_PS)),
                offsets_ps=offsets,
            )
        t_series = coincidences_data[label]["t"]
        c_series = coincidences_data[label]["counts"]
        t_series.append(time_val)
        c_series.append(counts / rate_divisor if rate_divisor else counts)
        if len(t_series) > 200:
            t_series.pop(0)
            c_series.pop(0)
# Function to format x-axis labels
def format_time(x, _):
    if x < 60:
        return f"{int(x)}"
    elif x < 3600:
        m, s = divmod(x, 60)
        return f"{int(m):02d}:{int(s):02d}"
    elif x < 86400:
        h, m = divmod(x // 60, 60)
        s = x % 60
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
    else:
        d, h = divmod(x // 3600, 24)
        m = (x % 3600) // 60
        s = x % 60
        return f"{int(d)}d {int(h):02d}:{int(m):02d}:{int(s):02d}"


def update_Contrast():
    """
        Needs to be updated for type-II
    """
    global contrast_str
    if  coincidences_data["1/4"]["counts"][-1] > coincidences_data["2/4"]["counts"][-1] or coincidences_data["2/3"]["counts"][-1] > coincidences_data["1/3"]["counts"][-1]:
        coinc14 = coincidences_data["1/4"]["counts"][-1]
        coinc23 = coincidences_data["2/3"]["counts"][-1]
        coinc13 = coincidences_data["1/3"]["counts"][-1]
        coinc24 = coincidences_data["2/4"]["counts"][-1]
    else:
        coinc14 = coincidences_data["1/3"]["counts"][-1]
        coinc23 = coincidences_data["2/4"]["counts"][-1]
        coinc13 = coincidences_data["1/4"]["counts"][-1]
        coinc24 = coincidences_data["2/3"]["counts"][-1]

    # Update contrast based on the selected Bell state
    if contrast_str == "phi+":
        # Logic for phi+
        return (coinc14 + coinc23) / (coinc13 + coinc24)
    elif contrast_str == "phi+I":
        # phi+I
        return (coinc14 + coinc23) / (coinc13 + coinc24)
    elif contrast_str == "phi-":
        # phi-
        return (coinc14 + coinc23) / (coinc13 + coinc24)
    elif contrast_str == "phi-I":
        # phi-I
        return (coinc14 + coinc23) / (coinc13 + coinc24)

def update_Heralding(pair=None):
    """
    If `pair` is given, returns heralding efficiency for that coincidence pair.
    Otherwise, returns a dictionary with heralding efficiencies for all pairs.
    """
    def compute_heralding(p):

        ch1, ch2 = map(int, p.split("/"))
        if singles_data[ch1]["counts"] and singles_data[ch2]["counts"] and coincidences_data[p]["counts"]:
            s1 = np.int64(singles_data[ch1]["counts"][-1])
            s2 = np.int64(singles_data[ch2]["counts"][-1])
            c = coincidences_data[p]["counts"][-1]
            if s1 > 0 and s2 > 0 and c > 0:
                heralding = c / np.sqrt(s1 * s2)
                # print(p, c, s1, s2, heralding)
                return round(heralding*100,2)
            else:
                return 0
        return 0

    if pair:
        return compute_heralding(pair)
    else:
        return {p: compute_heralding(p) for p in coincidences}


# Plotting functions
time_label = "Time [dd hh:mm:ss]"

# Function to update contrast string when radio button is selected
def select_state():
    global contrast_str
    contrast_str = selected_state.get()
    plot_coincidences(ax2)
    canvas_widget.draw()

def plot_singles(ax):
    ax.cla()
    plt.rcParams["font.family"] = "monospace"
    ax.set_title("Singles", fontsize=14, fontweight="bold")
    ax.set_xlabel(time_label, fontsize=12, fontweight="bold")
    ax.set_ylabel(f"Countrate [1/{expTime/1000}s]", fontsize=12, fontweight="bold")
    ax.set_facecolor(color_bg)
    plotted = False
    color_idx = 0
    for ch in channels:
        if selected_channels[ch].get():
            t_data = singles_data[ch]["t"]
            counts_data = singles_data[ch]["counts"]
            if t_data and counts_data:
                last_value = counts_data[-1]
                color = colors[color_idx]
                label = f"Ch {ch}: {last_value}"  # Show the last value
                ax.plot(t_data, counts_data, label=label, linewidth=2, color=color)
                color_idx += 1
                plotted = True
    if plotted:
        legend = ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, 1.15),
            fancybox=False,
            shadow=False,
            ncol=5,
        )
        legend.get_frame().set_alpha(legend_opacity)
    ax.xaxis.set_major_formatter(FuncFormatter(format_time))
    ax.tick_params(axis="x", labelsize=10)
    ax.tick_params(axis="y", labelsize=10)
    
    ax.grid(color=color_grid, linestyle=':', linewidth=1)
    
    if zeroscale.get():
        ax.set_ylim(bottom=0)


def plot_coincidences(ax):
    ax.cla()
    plt.rcParams["font.family"] = "monospace"
    ax.set_title(f"Coincidences | {contrast_str} {round(update_Contrast(),2)}", fontsize=14, fontweight="bold")
    ax.set_xlabel(time_label, fontsize=12, fontweight="bold")
    ax.set_ylabel(f"Countrate [1/{expTime/1000}s]", fontsize=12, fontweight="bold")
    plotted = False
    ax.set_facecolor(color_bg)
    color_idx = 0
    active_channels = [ch for ch in channels if selected_channels[ch].get()]
    for coinc in coincidences:
        ch1, ch2 = map(int, coinc.split("/"))
        herald = round(update_Heralding(coinc),4)
        if ch1 in active_channels and ch2 in active_channels:
            t_data = coincidences_data[coinc]["t"]
            counts_data = coincidences_data[coinc]["counts"]
            if t_data and counts_data:
                last_value = counts_data[-1]
                color = colors[color_idx+4]
                color_idx += 1
                label = f"Coinc {coinc}: {last_value} | Heralding: {herald}%"  # Show the last value
                ax.plot(t_data, counts_data, label=label, linewidth=2, color=color)
                plotted = True
    
    if plotted:
        legend = ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, 1.15),
            fancybox=False,
            shadow=False,
            ncol=5,
        )
        legend.get_frame().set_alpha(legend_opacity)
        
    ax.xaxis.set_major_formatter(FuncFormatter(format_time))
    ax.tick_params(axis="x", labelsize=10)
    ax.tick_params(axis="y", labelsize=10)
    ax.grid(color=color_grid, linestyle=':', linewidth=1)
    if zeroscale.get():
        ax.set_ylim(bottom=0)

def plot_heralding():
    global current_plot, ax1, ax2
    current_plot = "heralding"
    ax1.set_visible(False)
    ax2.set_visible(False)
    ax3.set_visible(True)
    

def show_singles():
    global current_plot, ax1, ax2
    current_plot = "singles"
    ax1.set_visible(True)
    ax2.set_visible(False)
    ax1.set_position([0.1, 0.15, 0.85, 0.65])
    canvas_widget.draw()


def show_coincidences():
    global current_plot, ax1, ax2
    current_plot = "coincidences"
    ax1.set_visible(False)
    ax2.set_visible(True)
    ax2.set_position([0.1, 0.15, 0.85, 0.65])
    canvas_widget.draw()


def show_both():
    global current_plot, ax1, ax2
    current_plot = "both"
    ax1.set_visible(True)
    ax2.set_visible(True)
    ax1.set_position([0.1, 0.6, 0.85, 0.35])
    ax2.set_position([0.1, 0.1, 0.85, 0.35])
    canvas_widget.draw()


def refresh_current_plots():
    if current_plot == "singles":
        plot_singles(ax1)
    elif current_plot == "coincidences":
        plot_coincidences(ax2)
    else:
        plot_singles(ax1)
        plot_coincidences(ax2)
    canvas_widget.draw_idle()


def submit_exposure_time(text):
    global exposure_time, expTime, newdata
    try:
        new_exposure_time = int(text)
        if 1 <= new_exposure_time <= 10000:
            exposure_time = new_exposure_time / 1000
            tt.setExposureTime(new_exposure_time)
            _, _, expTime = tt.getDeviceParams()
            print(f"Updated exposure time: {expTime} ms")

            # Clear the plot data
            for ch in channels:
                singles_data[ch]["t"].clear()
                singles_data[ch]["counts"].clear()

            for coinc in coincidences:
                coincidences_data[coinc]["t"].clear()
                coincidences_data[coinc]["counts"].clear()

            newdata = 0
        else:
            print("Exposure time must be between 1 and 10000 ms.")
    except ValueError:
        print("Invalid input. Please enter an integer between 1 and 10000.")


def open_channel_settings():
    channel_settings_window = tk.Toplevel()
    channel_settings_window.title("Channel Settings")
    ttk.Label(
        channel_settings_window, text="Channel settings can be configured here."
    ).pack(pady=10)
    ttk.Button(
        channel_settings_window, text="Close", command=channel_settings_window.destroy
    ).pack(pady=5)



def on_key_press(event):
    if event.char == "1":
        show_singles()
    elif event.char == "2":
        show_coincidences()
    elif event.char == "3":
        show_both()
    elif event.char == "q":
        on_close()

# Initialize Tkinter
root = tk.Tk()
root.title("QuTAG Plotter App")
# root.state('zoomed')  # Start the application maximized

# Initialize selected_channels after creating the root window
selected_channels = initialize_selected_channels()
selected_state = tk.StringVar(value=bell_states[0])  # Default to the first state

# selected_state = initialize_selected_states()

# Create a notebook for tabs
notebook = ttk.Notebook(root)
notebook.pack(fill=tk.BOTH, expand=True)

# Create frames for each tab
plotting_tab = ttk.Frame(notebook)
settings_tab = ttk.Frame(notebook)
histogram_tab = ttk.Frame(notebook)

# Add tabs to the notebook
notebook.add(plotting_tab, text="Plotting")
notebook.add(settings_tab, text="Settings")
notebook.add(histogram_tab, text="Histogram")

# Plotting tab
main_frame = ttk.Frame(plotting_tab)
main_frame.pack(fill=tk.BOTH, expand=True)

# Create Matplotlib canvas
canvas = plt.Figure()
ax1 = canvas.add_subplot(211)
ax2 = canvas.add_subplot(212)

canvas_widget = FigureCanvasTkAgg(canvas, master=main_frame)
canvas_widget.get_tk_widget().pack(fill=tk.BOTH, expand=True)

button_frame = ttk.Frame(plotting_tab)
button_frame.pack()

h, w = 2, 10
singles_button = tk.Button(button_frame, text="Singles", command=show_singles, height=h, width=w).pack(
    side=tk.LEFT
)
# ToolTip(singles_button, "Show the Singles plot")

coincidences_button = tk.Button(
    button_frame, text="Coincidences", command=show_coincidences, height=h, width=w
).pack(side=tk.LEFT)
# ToolTip(coincidences_button, "Show the Coincidences plot")

both_button = tk.Button(button_frame, text="Both", command=show_both, height=h, width=w).pack(
    side=tk.LEFT
)

tk.Label(button_frame, text="Exposure time (ms):").pack(side=tk.LEFT)

exposure_textbox = ttk.Entry(button_frame, width=5)
exposure_textbox.insert(0, str(int(exposure_time * 1000)))
exposure_textbox.pack(side=tk.LEFT)


def on_exposure_enter(event):
    submit_exposure_time(exposure_textbox.get())
    root.focus_set()


exposure_textbox.bind("<Return>", on_exposure_enter)


# Histogram tab
hist_main_frame = ttk.Frame(histogram_tab)
hist_main_frame.pack(fill=tk.BOTH, expand=True)

hist_controls = ttk.Frame(hist_main_frame)
hist_controls.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

hist_plot_frame = ttk.Frame(hist_main_frame)
hist_plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

hist_fig = plt.Figure(figsize=(5, 4))
hist_ax = hist_fig.add_subplot(111)
hist_canvas = FigureCanvasTkAgg(hist_fig, master=hist_plot_frame)
hist_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

hist_channel_a_var = tk.IntVar(value=channels[0])
hist_channel_b_var = tk.IntVar(value=channels[1])
hist_window_var = tk.DoubleVar(value=histogram_params.get("window_ps", 500))
hist_start_var = tk.DoubleVar(value=histogram_params.get("delay_start_ps", -5_000))
hist_end_var = tk.DoubleVar(value=histogram_params.get("delay_end_ps", 5_000))
hist_step_var = tk.DoubleVar(value=histogram_params.get("delay_step_ps", 50))

ttk.Label(hist_controls, text="Channel A").pack(anchor="w")
ttk.Combobox(hist_controls, textvariable=hist_channel_a_var,
             values=channels, state="readonly", width=5).pack(anchor="w", pady=2)
ttk.Label(hist_controls, text="Channel B").pack(anchor="w")
ttk.Combobox(hist_controls, textvariable=hist_channel_b_var,
             values=channels, state="readonly", width=5).pack(anchor="w", pady=2)

ttk.Label(hist_controls, text="Window (ps)").pack(anchor="w", pady=(10, 0))
window_entry = ttk.Entry(hist_controls, textvariable=hist_window_var, width=10)
window_entry.pack(anchor="w")

ttk.Label(hist_controls, text="Delay start (ps)").pack(anchor="w")
start_entry = ttk.Entry(hist_controls, textvariable=hist_start_var, width=10)
start_entry.pack(anchor="w")

ttk.Label(hist_controls, text="Delay end (ps)").pack(anchor="w")
end_entry = ttk.Entry(hist_controls, textvariable=hist_end_var, width=10)
end_entry.pack(anchor="w")

ttk.Label(hist_controls, text="Delay step (ps)").pack(anchor="w")
step_entry = ttk.Entry(hist_controls, textvariable=hist_step_var, width=10)
step_entry.pack(anchor="w")

ttk.Button(hist_controls, text="Capture timestamps", command=lambda: capture_and_store_chunk()).pack(fill=tk.X, pady=5)
ttk.Button(hist_controls, text="Load BIN...", command=prompt_load_bin_dialog).pack(fill=tk.X, pady=2)
ttk.Button(hist_controls, text="Plot histogram", command=lambda: plot_histogram_action()).pack(fill=tk.X, pady=2)
ttk.Button(hist_controls, text="Auto-set delay", command=lambda: auto_set_selected_pair()).pack(fill=tk.X, pady=2)
ttk.Button(hist_controls, text="Auto align channels", command=lambda: open_auto_align_dialog()).pack(fill=tk.X, pady=2)

def on_histogram_params_changed(_event=None):
    histogram_params["window_ps"] = float(hist_window_var.get())
    histogram_params["delay_start_ps"] = float(hist_start_var.get())
    histogram_params["delay_end_ps"] = float(hist_end_var.get())
    histogram_params["delay_step_ps"] = float(hist_step_var.get())
    settings["histogram"] = histogram_params
    save_settings(settings)
    global COINC_WINDOW_PS
    COINC_WINDOW_PS = histogram_params["window_ps"]

for entry in (window_entry, start_entry, end_entry, step_entry):
    entry.bind("<FocusOut>", on_histogram_params_changed)

# Settings tab
settings_frame = ttk.Frame(settings_tab)
# settings_frame.pack(fill=tk.BOTH, expand=True)
# Center the content inside settings_frame
settings_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

ttk.Label(settings_frame, text="Channel Settings", font=("Arial", 14)).pack(pady=10)
# Pack the button just below the two frames
ttk.Button(
    settings_frame, text="Open Channel Settings", command=open_channel_settings
).pack(side=tk.TOP, pady=20)

# Settings tab (modification for bell_states radio buttons)
ttk.Label(settings_frame, text="Select Bell State", font=("Arial", 14)).pack(pady=10)

ttk.Label(settings_frame, text="Source Type", font=("Arial", 14)).pack(pady=10)
source_type = tk.StringVar(value="Type-I/0")

def select_source_type():
    global coincidences, coincidences_data
    selected = source_type.get()
    if selected == "Type-I/0":
        coincidences = coincidences_type_I_0
    else:
        coincidences = coincidences_type_II

    coincidences_data = initialize_coincidences_data(coincidences)
    plot_coincidences(ax2)
    canvas_widget.draw()

ttk.Radiobutton(
    settings_frame, text="Type-II", variable=source_type, value="Type-II", command=select_source_type
).pack(anchor="w")
ttk.Radiobutton(
    settings_frame, text="Type-I/0", variable=source_type, value="Type-I/0", command=select_source_type
).pack(anchor="w")


# Create a frame for checkboxes and radio buttons side by side
checkbox_frame = ttk.Frame(settings_frame)
checkbox_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)

radiobutton_frame = ttk.Frame(settings_frame)
radiobutton_frame.pack(side=tk.LEFT, padx=10, pady=10, fill=tk.Y)

# Add checkboxes to the checkbox_frame
ttk.Label(checkbox_frame, text="Channel Settings", font=("Arial", 14)).pack(anchor="n")
for ch in channels:
    ttk.Checkbutton(
        checkbox_frame, text=f"Channel {ch}", variable=selected_channels[ch]
    ).pack(anchor="w", pady=5)

# Add radio buttons to the radiobutton_frame
ttk.Label(radiobutton_frame, text="Bell States", font=("Arial", 14)).pack(anchor="n")
for state in bell_states:
    ttk.Radiobutton(
        radiobutton_frame, text=state, variable=selected_state, value=state, command=select_state
    ).pack(anchor="n", pady=5)

zeroscale = tk.BooleanVar(value=True)
y0_button = ttk.Checkbutton(button_frame, text="y@0", variable=zeroscale).pack(side=tk.LEFT, padx=5)

ttk.Label(button_frame, text="Coinc window (ps):").pack(side=tk.LEFT, padx=(20, 5))
coinc_window_var = tk.DoubleVar(value=COINC_WINDOW_PS)
coinc_entry = ttk.Entry(button_frame, textvariable=coinc_window_var, width=6)
coinc_entry.pack(side=tk.LEFT)


def on_coinc_window_change(_event=None):
    global COINC_WINDOW_PS
    try:
        value = float(coinc_window_var.get())
    except Exception:
        value = COINC_WINDOW_PS
        coinc_window_var.set(value)
    COINC_WINDOW_PS = value
    histogram_params["window_ps"] = value
    settings["histogram"] = histogram_params
    save_settings(settings)


coinc_entry.bind("<FocusOut>", on_coinc_window_change)

delay_frame = ttk.LabelFrame(settings_frame, text="Channel delays (ps)")
delay_frame.pack(padx=10, pady=10, fill=tk.X)


def on_delay_changed(ch):
    try:
        value = float(delay_vars[ch].get())
    except Exception:
        value = 0.0
        delay_vars[ch].set(value)
    set_channel_delay(ch, value)


cols = 3
for idx, ch in enumerate(channels):
    row = idx // cols
    col = idx % cols
    ttk.Label(delay_frame, text=f"Ch {ch}").grid(row=row * 2, column=col, padx=5, pady=(5, 0))
    var = tk.DoubleVar(value=settings["delays_ps"].get(str(ch), 0.0))
    delay_vars[ch] = var
    entry = ttk.Entry(delay_frame, textvariable=var, width=8)
    entry.grid(row=row * 2 + 1, column=col, padx=5, pady=(0, 5))
    entry.bind("<FocusOut>", lambda _e, channel=ch: on_delay_changed(channel))

ttk.Button(delay_frame, text="Auto Align...", command=open_auto_align_dialog).grid(
    row=(len(channels) // cols + 1) * 2, column=0, columnspan=cols, pady=10
)


root.bind("<KeyPress>", on_key_press)


def update_plot():
    global running
    while running and tt_connected:
        path = capture_timestamps_to_file(silent=True)
        if path:
            if load_bin_file(path, show_messages=False):
                try:
                    os.unlink(path)
                except OSError:
                    pass
                root.after(0, refresh_current_plots)
        time.sleep(exposure_time)


def on_close():
    global running
    running = False
    if tt is not None:
        try:
            tt.deInitialize()
        except Exception:
            pass
        print("Deinitializing TT and Closing")
    root.destroy()


root.protocol("WM_DELETE_WINDOW", on_close)


# Example function to start the update loop in a separate thread
def start_update_thread():
    if not tt_connected:
        print("Time tagger not connected; use 'Capture timestamps' or 'Load BIN' to analyze data.")
        return
    update_thread = threading.Thread(target=update_plot, daemon=True)
    update_thread.start()


start_update_thread()

# Run the Tkinter main loop
root.mainloop()
