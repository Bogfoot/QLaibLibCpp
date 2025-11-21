"""
Created on Tue Nov 18 14:35:17 2025

@author: Adrian
"""

import time
import csv
import sys
import os
import tempfile
import numpy as np
import matplotlib.pyplot as plt


try:
    import QuTAG_MC
except ImportError as exc:
    print("ERROR: Failed to import QuTAG_MC:", exc)
    sys.exit(1)

try:
    import coincfinder
except ImportError as e:
    print("ERROR: Failed to import coincfinder module:", e)
    sys.exit(1)


# ===========================
# Config
# ===========================
EXPOSURE_SEC = 1            # integration time per measurement (seconds)
COINC_WINDOW_PS = 200       # coincidence window in picoseconds
COINC_WINDOW_S = COINC_WINDOW_PS * 1e-12  # coincidence window [s]

DELAY_START_PS = 0    # search range for auto-delay (start)
DELAY_END_PS   = 20000      # search range for auto-delay (end)
DELAY_STEP_PS  = 10         # delay step for auto-delay search

# Optional logging of each measurement
LOG_FILE_QBER = "qber_live_log.csv"

# reference pairs used for delays
REF_PAIRS = [(1, 5), (2, 6), (3, 7), (4, 8)]  # H/H, V/V, D/D, A/A
REF_PAIR_KEYS = [f"{a}/{b}" for a, b in REF_PAIRS]


# ===========================
# Helpers
# ===========================

def init_tagger():
    """Initialize QuTAG and set exposure time."""
    tt = QuTAG_MC.QuTAG()
    tt.setExposureTime(int(EXPOSURE_SEC * 1000))  # ms
    _, coincWin, expTime = tt.getDeviceParams()
    print("QuTAG initialized:")
    print(f"  Coincidence window (bins): {coincWin}")
    print(f"  Exposure time (ms): {expTime}")
    return tt


def record_chunk_to_singles(tt, exposure_sec):
    """
    Use writeTimestamps() to record a chunk into a temporary BIN file,
    then parse it with coincfinder.read_file_auto and delete the file.

    Returns:
        singles_map: dict[int, Singles]
        duration_sec: float (measurement duration from file)
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
    filename = tmp.name
    tmp.close()

    try:
        # Start recording timestamps to BIN file
        tt.writeTimestamps(filename, tt.FILEFORMAT_BINARY)

        # Integration / exposure
        time.sleep(exposure_sec)

        # Stop recording
        tt.writeTimestamps("", tt.FILEFORMAT_NONE)

        # Let coincfinder ingest the file
        singles_map, duration_sec = coincfinder.read_file_auto(filename)

    finally:
        # Clean up temp file
        try:
            os.unlink(filename)
        except OSError:
            pass
    for ch, s in singles_map.items():
        count = sum(len(bucket) for bucket in s.events_per_second)
        print(f"Channel {ch}: {count} timestamps")
    return singles_map, duration_sec


def flatten_singles_channel(singles_map, channel):
    s = singles_map.get(channel)
    if s is None:
        return []

    # Convert each bucket to a NumPy array
    arrays = [np.asarray(bucket, dtype=np.int64)
              for bucket in s.events_per_second if bucket]

    if not arrays:
        return []

    # Efficiently concatenate all buckets
    return np.concatenate(arrays)



def auto_find_delays(tt):
    """
    Measure once (via writeTimestamps) and find best delays for REF_PAIRS
    using coincfinder.find_best_delay_ps on the flattened timetag arrays.

    Returns:
        best_delays: dict like {"1/5": delay_ps, "2/6": ..., ...}
    """
    print("\n=== Auto delay calibration ===")
    print(f"Exposure for calibration: {EXPOSURE_SEC} s")

    singles_map, duration_sec = record_chunk_to_singles(tt, EXPOSURE_SEC)

    for ch, s in singles_map.items():
        count = sum(len(bucket) for bucket in s.events_per_second)
        print(f"Channel {ch}: {count} timestamps")
    # crude sanity check
    if not singles_map or duration_sec <= 0:
        print("No valid timestamps during calibration. Using zero delays.")
        return {k: 0.0 for k in REF_PAIR_KEYS}

    best_delays = {}

    for chA, chB in REF_PAIRS:
        key = f"{chA}/{chB}"

        tA = flatten_singles_channel(singles_map, chA)
        tB = flatten_singles_channel(singles_map, chB)

        if len(tA) == 0 or len(tB) == 0:
            print(f"  Pair {key}: no events, delay set to 0 ps")
            best_delays[key] = 0.0
            continue

        best = coincfinder.find_best_delay_ps(
            tA,
            tB,
            coinc_window_ps=COINC_WINDOW_PS,
            delay_start_ps=DELAY_START_PS,
            delay_end_ps=DELAY_END_PS,
            delay_step_ps=DELAY_STEP_PS,
        )
        best_delays[key] = float(best)
        print(f"  Pair {key}: best delay = {best:.1f} ps")

    print("=== Calibration done ===\n")
    return best_delays


def ensure_log_header(path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "visibility_mean",
            "vis_HV",
            "vis_DA",
            "QBER_total",
            "QBER_HV",
            "QBER_DA",
            "C_HH",
            "C_VV",
            "C_DD",
            "C_AA",
            "C_HV",
            "C_VH",
            "C_DA",
            "C_AD",
        ])


def measure_visibility(tt, best_delays):
    """
    Record one chunk with writeTimestamps(), ingest it with coincfinder,
    compute coincidences for same-basis (like) and cross-basis (opposite)
    detector pairs, and return full stats.

    Returns:
        dict with:
            - vis_HV, vis_DA, visibility
            - QBER_HV, QBER_DA, QBER_total
            - contrast_HV, contrast_DA, total_contrast
            - total_coinc
            - coincidences: [C_HH, C_VV, C_DD, C_AA, C_HV, C_VH, C_DA, C_AD]
            - accidentals:  [A_HH, A_VV, A_DD, A_AA, A_HV, A_VH, A_DA, A_AD]
            - counts map C[label]
            - accidentals map A[label]
    """
    singles_map, duration_sec = record_chunk_to_singles(tt, EXPOSURE_SEC)
    print(f"Measurement duration: {duration_sec}")
    if not singles_map or duration_sec <= 0:
        print("No valid timestamps.")
        return None

    # --- coincidence & accidental counters ---
    C = {lbl: 0 for lbl in ["HH", "VV", "DD", "AA", "HV", "VH", "DA", "AD"]}
    A = {lbl: 0.0 for lbl in ["HH", "VV", "DD", "AA", "HV", "VH", "DA", "AD"]}

    # Map channel -> reference pair key to grab the calibrated delay
    ref_pair_map = {
        1: "1/5", 2: "2/6", 3: "3/7", 4: "4/8",
        5: "1/5", 6: "2/6", 7: "3/7", 8: "4/8",
    }

    def count_pair(chA, chB):
        """Count true coincidences and estimate accidentals for a pair."""
        tA = flatten_singles_channel(singles_map, chA)
        tB = flatten_singles_channel(singles_map, chB)
        nA = len(tA)
        nB = len(tB)
        if nA == 0 or nB == 0:
            return 0, 0.0

        ref_key = ref_pair_map.get(chA, ref_pair_map.get(chB, None))
        delay = best_delays.get(ref_key, 0.0)

        coinc = coincfinder.count_coincidences_with_delay_ps(
            tA, tB, COINC_WINDOW_PS, delay
        )

        # accidental estimate: 2 * N_A * N_B * tau / T
        acc = 2.0 * nA * nB * COINC_WINDOW_S / duration_sec

        return coinc, acc

    # Like (same basis)
    C["HH"], A["HH"] = count_pair(1, 5)
    C["VV"], A["VV"] = count_pair(2, 6)
    C["DD"], A["DD"] = count_pair(3, 7)
    C["AA"], A["AA"] = count_pair(4, 8)

    # Opposite (cross basis)
    C["HV"], A["HV"] = count_pair(1, 6)
    C["VH"], A["VH"] = count_pair(2, 5)
    C["DA"], A["DA"] = count_pair(3, 8)
    C["AD"], A["AD"] = count_pair(4, 7)

    # --- Compute visibilities / contrasts / QBER ---
    C_HH, C_VV, C_DD, C_AA = C["HH"], C["VV"], C["DD"], C["AA"]
    C_HV, C_VH, C_DA, C_AD = C["HV"], C["VH"], C["DA"], C["AD"]

    vis_HV = (C_HH + C_VV - C_HV - C_VH) / (
        C_HH + C_VV + C_HV + C_VH + 1e-9
    )
    vis_DA = (C_DD + C_AA - C_DA - C_AD) / (
        C_DD + C_AA + C_DA + C_AD + 1e-9
    )

    visibility = np.clip((vis_HV + vis_DA) / 2.0, +1e-2, .99)
    contrast_HV = (C_HH + C_VV) / (C_HV + C_VH + 1e-9)
    contrast_DA = (C_DD + C_AA) / (C_DA + C_AD + 1e-9)
    total_coinc = C_HH + C_VV + C_DD + C_AA + C_HV + C_VH + C_DA + C_AD
    total_contrast = ((C_HH + C_VV + C_DD + C_AA) /
                      (C_HV + C_VH + C_DA + C_AD + 1e-9))

    coincidences = [C_HH, C_VV, C_DD, C_AA, C_HV, C_VH, C_DA, C_AD]
    accidentals = [A["HH"], A["VV"], A["DD"], A["AA"],
                   A["HV"], A["VH"], A["DA"], A["AD"]]

    QBER_HV = (1 - vis_HV) / 2
    QBER_DA = (1 - vis_DA) / 2
    QBER_total = (1 - visibility) / 2

    # Optional logging (unchanged)
    ts = time.time()
    ensure_log_header(LOG_FILE_QBER)
    with open(LOG_FILE_QBER, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            ts,
            round(visibility, 4),
            round(vis_HV, 4),
            round(vis_DA, 4),
            round(QBER_total, 4),
            round(QBER_HV, 4),
            round(QBER_DA, 4),
            C_HH, C_VV, C_DD, C_AA,
            C_HV, C_VH, C_DA, C_AD
        ])

    return {
        "vis_HV": vis_HV,
        "vis_DA": vis_DA,
        "visibility": visibility,
        "QBER_HV": QBER_HV,
        "QBER_DA": QBER_DA,
        "QBER_total": QBER_total,
        "contrast_HV": contrast_HV,
        "contrast_DA": contrast_DA,
        "total_contrast": total_contrast,
        "total_coinc": total_coinc,
        "coincidences": coincidences,
        "accidentals": accidentals,
        "C": C,
        "A": A,
    }



# ===========================
# Main loop
# ===========================
def init_live_plot_line(window=200):
    """
    Prepare a live line plot with 8 curves.
    Returns (fig, ax, lines, labels, history).
    """

    labels = ["HH", "VV", "DD", "AA", "HV", "VH", "DA", "AD"]
    colors = plt.cm.tab10(np.linspace(0, 1, len(labels)))

    plt.ion()
    fig, ax = plt.subplots(figsize=(10, 6))

    lines = []
    for c, lbl in zip(colors, labels):
        line, = ax.plot(
            [], [],
            marker="o",
            markersize=3,
            linewidth=1.2,
            alpha=0.9,
            color=c,
            label=lbl,
        )
        lines.append(line)

    ax.set_title("Live Coincidences Over Time")
    ax.set_xlabel("Measurement index")
    ax.set_ylabel("Coincidences per chunk")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right")

    # history dict: label -> list of values
    history = {lbl: [] for lbl in labels}
    history["_x"] = []
    history["_window"] = window

    return fig, ax, lines, labels, history


def update_live_plot_line(ax, lines, labels, history, stats, i):
    """Update the live line plot using the new stats."""

    C_list = stats["coincidences"]
    window = history["_window"]

    # Append new values
    history["_x"].append(i)
    for lbl, val in zip(labels, C_list):
        history[lbl].append(val)

    # Keep only last N points
    if len(history["_x"]) > window:
        history["_x"] = history["_x"][-window:]
        for lbl in labels:
            history[lbl] = history[lbl][-window:]

    # Update plot lines
    for line, lbl in zip(lines, labels):
        line.set_data(history["_x"], history[lbl])

    # Adjust limits
    if len(history["_x"]) > 1:
        ax.set_xlim(history["_x"][0], history["_x"][-1])

    # Compute y max safely: only use sequence-type entries (lists/arrays)
    yvals = []
    for lbl, vals in history.items():
        if lbl in ("_x", "_window"):
            continue
        # only consider list-like things
        if isinstance(vals, (list, tuple, np.ndarray)) and len(vals) > 0:
            yvals.append(vals)

    if yvals:
        ymax = max(max(v) for v in yvals)
    else:
        ymax = 0

    ax.set_ylim(0, max(1, ymax * 1.25))

    ax.set_title(f"Live Coincidences (total = {stats['total_coinc']})")

    plt.pause(0.001)



def main():
    tt = init_tagger()

    try:
        best_delays = auto_find_delays(tt)
        print("Using delays (ps):")
        for k in REF_PAIR_KEYS:
            print(f"  {k}: {best_delays.get(k, 0.0):+.1f} ps")
        print("")

        # --- init live line plot ---
        fig, ax, lines, labels, history = init_live_plot_line(window=200)

        i = 0
        print("Starting live monitor. Press Ctrl+C to stop.\n")

        while True:
            i += 1
            stats = measure_visibility(tt, best_delays)
            if stats is None:
                continue

            C = stats["C"]
            A = stats["A"]
            vis_HV = stats["vis_HV"]
            vis_DA = stats["vis_DA"]
            visibility = stats["visibility"]
            QBER_total = stats["QBER_total"]
            QBER_HV = stats["QBER_HV"]
            QBER_DA = stats["QBER_DA"]
            contrast_HV = stats["contrast_HV"]
            contrast_DA = stats["contrast_DA"]
            total_coinc = stats["total_coinc"]

            # ---- terminal printout ----
            print(f"--- Measurement #{i} (Δt = {EXPOSURE_SEC:.3f} s) ---")
            print("Coincidences (true (accidentals)):")
            print(
                f"  HH={C['HH']:6d} ({int(round(A['HH'])):3d}) "
                f"VV={C['VV']:6d} ({int(round(A['VV'])):3d}) "
                f"DD={C['DD']:6d} ({int(round(A['DD'])):3d}) "
                f"AA={C['AA']:6d} ({int(round(A['AA'])):3d})"
            )
            print(
                f"  HV={C['HV']:6d} ({int(round(A['HV'])):3d}) "
                f"VH={C['VH']:6d} ({int(round(A['VH'])):3d}) "
                f"DA={C['DA']:6d} ({int(round(A['DA'])):3d}) "
                f"AD={C['AD']:6d} ({int(round(A['AD'])):3d})"
            )


            print(
                f"V(HV)={vis_HV:+.3f}, V(DA)={vis_DA:+.3f}, "
                f"Mean V={visibility:+.3f}"
            )
            print(
                f"Contrast HV={contrast_HV:.3f}, Contrast DA={contrast_DA:.3f}"
            )
            print(
                f"QBER total={QBER_total:.3f}, "
                f"QBER_HV={QBER_HV:.3f}, QBER_DA={QBER_DA:.3f}"
            )
            print("")

            # ---- update live plot (if window still exists) ----
            if plt.fignum_exists(fig.number):
                update_live_plot_line(ax, lines, labels, history, stats, i)
            # else: silently continue acquisition headless

    except KeyboardInterrupt:
        print("Interrupted by user, shutting down...")
    finally:
        try:
            tt.deInitialize()
        except Exception:
            pass

if __name__ == "__main__":
    main()

