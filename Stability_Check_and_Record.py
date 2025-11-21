#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
QBER optimization with coincfinder-based acquisition.

Flow:
    1) Initialize QuTAG_MC
    2) Auto-calibrate delays with coincfinder.find_best_delay_ps
    3) Enter monitoring loop:
           measure QBER
           if visibility < threshold → run Nelder–Mead over EPC voltages
           log everything
"""

import os, sys, csv, json, time, tempfile, datetime
import numpy as np

# ─────────────────────────────────────────────
#  EXTERNAL LIBRARIES (hardware & coincidence)
# ─────────────────────────────────────────────

try:
    import QuTAG_MC as qt
except ImportError as exc:
    print("ERROR: Failed to import QuTAG_MC:", exc)
    sys.exit(1)

try:
    import coincfinder
except ImportError as e:
    print("ERROR: Failed to import coincfinder module:", e)
    sys.exit(1)

from EPC import PolarizationDevice

from scipy.optimize import minimize


# ─────────────────────────────────────────────
#  GLOBAL CONFIG
# ─────────────────────────────────────────────

EXPOSURE_SEC      = 1.0          # integration time per QBER measurement (seconds)
COINC_WINDOW_PS   = 200          # coincidence window in picoseconds
COINC_WINDOW_S    = COINC_WINDOW_PS * 1e-12

DELAY_START_PS    = 8000            # search range for auto-delay (start)
DELAY_END_PS      = 12000        # search range for auto-delay (end)
DELAY_STEP_PS     = 10           # delay step for auto-delay search

VISIBILITY_STOPPING_THRESHOLD = 0.91  # if vis ≥ this, system considered "good"
STEP_SIZE         = 5.0          # base voltage step (V) for simplex
V_STEP            = 0.1          # quantization step (V)
MAX_V             = 130.0        # EPC max voltage

SLEEP_TIMER       = 10           # seconds between checks when stable
RECORD_RAW_MODE = True
RAW_EXPOSURE_SEC = 10 * 60

# Reference pairs used for delay calibration (like-basis)
REF_PAIRS = [(1, 5), (2, 6), (3, 7), (4, 8)]  # H/H, V/V, D/D, A/A
REF_PAIR_KEYS = [f"{a}/{b}" for a, b in REF_PAIRS]

# Base directory for logs/state
try:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE_DIR = os.getcwd()

DATA_DIR = os.path.join(BASE_DIR, "Data")
VIS_DIR  = os.path.join(DATA_DIR, "Visibility")
RAW_DIR  = os.path.join(DATA_DIR, "RAW")
os.makedirs(VIS_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)

LOG_FILE_QBER = os.path.join(VIS_DIR, "qber_live_log.csv")
STATE_FILE    = os.path.join(BASE_DIR, "optimizer_state.json")

# ─────────────────────────────────────────────
#  HARDWARE VOLTAGE CONTROL (ADAPT TO YOUR SETUP)
# ─────────────────────────────────────────────

EPC1 = PolarizationDevice(0)
EPC2 = PolarizationDevice(1)

temperature = 50

def set_voltage(epc, V):
    for i in range(4):
        epc.set_voltage(f"DAC{i}", V[i])
        time.sleep(0.001)

for epc in [EPC1, EPC2]:
    if epc == EPC1:
        print(f"Setting themperature of EPC1 to {temperature}")
        epc.set_temperature(temperature)
    else:
        print(f"Setting themperature of EPC2 to {temperature}")
        epc.set_temperature(temperature)
        
time.sleep(10)
for epc in [EPC1, EPC2]:
        set_voltage(epc, [0,0,0,0])
        time.sleep(1)

def send_voltages(V1, V2):

    # Replace these with your actual driver calls
    if EPC1 is not None:
        set_voltage(EPC1, V1)
    if EPC2 is not None:
        set_voltage(EPC2, V2)


# ─────────────────────────────────────────────
#  STATE PERSISTENCE
# ─────────────────────────────────────────────

def ensure_state_file():
    """Create Data folder and default state if missing."""
    os.makedirs(os.path.join(BASE_DIR, "Data"), exist_ok=True)
    if not os.path.exists(STATE_FILE):
        default_state = {
            "qber": {"best_V": [65.0]*8, "best_visibility": 0.95},
            "S": {"best_V": [65.0]*8, "best_S": 2.4},
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        with open(STATE_FILE, "w") as f:
            json.dump(default_state, f, indent=2)
        print(f"[State] Created default optimizer_state.json at {STATE_FILE}")

def load_optimizer_state():
    ensure_state_file()
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_optimizer_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)
    print(f"[State] Saved optimizer state to {STATE_FILE}")


# ─────────────────────────────────────────────
#  QUANTUM TIMETAGGER SETUP & ACQUISITION
# ─────────────────────────────────────────────

def init_tagger():
    """Initialize QuTAG and set exposure time."""
    tt = qt.QuTAG()
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

    return singles_map, duration_sec


def flatten_singles_channel(singles_map, channel):
    """Flatten singles_map[channel].events_per_second into one int64 array."""
    s = singles_map.get(channel)
    if s is None:
        return np.array([], dtype=np.int64)

    arrays = [
        np.asarray(bucket, dtype=np.int64)
        for bucket in s.events_per_second if bucket
    ]

    if not arrays:
        return np.array([], dtype=np.int64)

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

    singles_map, duration_sec = record_chunk_to_singles(tt, 5)

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


# ─────────────────────────────────────────────
#  QBER MEASUREMENT (COINCFINDER BACKEND)
# ─────────────────────────────────────────────

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
    print(f"Measurement duration: {duration_sec:.3f} s")

    if not singles_map or duration_sec <= 0:
        print("No valid timestamps.")
        return None

    # coincidence & accidental counters
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

    C_HH, C_VV, C_DD, C_AA = C["HH"], C["VV"], C["DD"], C["AA"]
    C_HV, C_VH, C_DA, C_AD = C["HV"], C["VH"], C["DA"], C["AD"]

    vis_HV = (C_HH + C_VV - C_HV - C_VH) / (
        C_HH + C_VV + C_HV + C_VH + 1e-9
    )
    vis_DA = (C_DD + C_AA - C_DA - C_AD) / (
        C_DD + C_AA + C_DA + C_AD + 1e-9
    )

    visibility      = np.clip((vis_HV + vis_DA) / 2.0, +1e-2, .99)
    contrast_HV     = (C_HH + C_VV) / (C_HV + C_VH + 1e-9)
    contrast_DA     = (C_DD + C_AA) / (C_DA + C_AD + 1e-9)
    total_coinc     = C_HH + C_VV + C_DD + C_AA + C_HV + C_VH + C_DA + C_AD
    total_contrast  = ((C_HH + C_VV + C_DD + C_AA) /
                       (C_HV + C_VH + C_DA + C_AD + 1e-9))

    coincidences    = [C_HH, C_VV, C_DD, C_AA, C_HV, C_VH, C_DA, C_AD]
    accidentals     = [A["HH"], A["VV"], A["DD"], A["AA"],
                       A["HV"], A["VH"], A["DA"], A["AD"]]

    QBER_HV         = (1 - vis_HV) / 2
    QBER_DA         = (1 - vis_DA) / 2
    QBER_total      = (1 - visibility) / 2

    # Logging
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


def measure_visibility_for_optimizer(tt, best_delays):
    """
    Adapter around coincfinder-based measure_visibility() so the optimizer
    can keep using:  (-visibility, QBER_total, total_coinc).
    """
    stats = measure_visibility(tt, best_delays)
    if stats is None:
        # Fall back to "bad" visibility if something went wrong
        return -0.01, 0.5, 0

    visibility   = float(stats["visibility"])
    QBER_total   = float(stats["QBER_total"])
    total_coinc  = int(stats["total_coinc"])

    # Optimizer minimizes, so return -visibility
    return -visibility, QBER_total, total_coinc


# ─────────────────────────────────────────────
#  RAW BIN RECORDING (OPTIONAL)
# ─────────────────────────────────────────────

def record_raw_BIN(tt, exposure_sec):
    """
    Store a raw BIN file to Data/RAW/ with timestamp in filename.
    """
    t = time.localtime()
    fname = f"{datetime.date.today()}_{time.strftime('%H_%M_%S', t)}_exp_{exposure_sec:.1f}s.bin"
    filename = os.path.join(RAW_DIR, fname)

    try:
        tt.writeTimestamps(filename, tt.FILEFORMAT_BINARY)
        time.sleep(exposure_sec)
        tt.writeTimestamps("", tt.FILEFORMAT_NONE)
        print(f"[RAW] Saved new BIN file: {filename}")
        time.sleep(0.001)
    except Exception as e:
        print(f"[RAW] Caught {e}")
    return os.path.exists(filename)


# ─────────────────────────────────────────────
#  QBER OPTIMIZATION (NELDER–MEAD)
# ─────────────────────────────────────────────

def run_qber_optimization(tt, best_delays, start_V, step):
    """
    Run Nelder–Mead optimization for visibility with early stop + autosave,
    using coincfinder-based acquisition.
    """

    def quantize(V):
        return np.clip(np.round(V / V_STEP) * V_STEP, 0, MAX_V)

    best_V   = start_V.copy()
    best_vis = -1.0
    state    = load_optimizer_state()

    def objective(V):
        nonlocal best_V, best_vis
        V = quantize(V)
        V1, V2 = V[:4], V[4:]
        send_voltages(V1, V2)

        neg_vis, QBER, total_coinc = measure_visibility_for_optimizer(tt, best_delays)
        vis = -neg_vis

        # Save iteration result
        iter_data = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "voltages": V.tolist(),
            "visibility": float(vis),
            "QBER": float(QBER),
            "coinc": int(total_coinc),
        }
        iterlog_path = os.path.join(VIS_DIR, "qber_iterlog.csv")
        with open(iterlog_path, "a", newline="") as f:
            csv.writer(f).writerow(iter_data.values())

        # Update best
        if vis > best_vis:
            best_vis = vis
            best_V = V.copy()

        # Continuous state save
        state["qber"] = {
            "best_V": best_V.tolist(),
            "best_visibility": float(best_vis),
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        save_optimizer_state(state)

        # Early stopping
        if vis >= VISIBILITY_STOPPING_THRESHOLD:
            print(f"[QBER Opt] Reached visibility {vis:.3f} ≥ {VISIBILITY_STOPPING_THRESHOLD}. Stopping early.")
            raise StopIteration



        return -vis

    n_params = len(start_V)
    initial_simplex = np.vstack(
        [start_V] +
        [start_V + step * np.eye(n_params)[i] for i in range(n_params)]
    )

    try:
        res = minimize(
            objective,
            start_V,
            method="Nelder-Mead",
            options={
                "maxiter": 200,
                "xatol": 0.2,
                "fatol": 1e-3,
                "disp": True,
                "initial_simplex": initial_simplex
            }
        )
    except StopIteration:
        print("[QBER Opt] Early termination triggered.")
        res = None

    send_voltages(best_V[:4], best_V[4:])
    return res, best_V, best_vis, True


def optimize_contrast(tt, best_delays):
    """
    Maintains QBER optimization (visibility) using coincfinder backend.

    Modes:
      - Online-only (RECORD_RAW_MODE = False):
            measure QBER → correct if needed → measure QBER → ...

      - Raw+online (RECORD_RAW_MODE = True):
            record RAW BIN → measure QBER → correct if needed → record RAW → ...
    """
    print("\n[QBER Optimizer] Starting monitoring loop...")

    state = load_optimizer_state()
    last_state = state.get("qber", {})

    best_V        = np.array(last_state.get("best_V", [65.0] * 8), dtype=float)
    best_vis_prev = float(last_state.get("best_visibility", 0.95))

    loop_idx = 0

    while True:
        loop_idx += 1

        # ────────────── RAW MODE (optional) ──────────────
        if RECORD_RAW_MODE:
            print(
                f"[QBER Optimizer] Loop #{loop_idx}: "
                f"recording RAW BIN (exp = {RAW_EXPOSURE_SEC:.1f} s) before QBER measurement..."
            )
            ok = record_raw_BIN(tt, RAW_EXPOSURE_SEC)
            if not ok:
                print("[QBER Optimizer] WARN: RAW BIN file not created.")

        # ────────────── QBER MEASUREMENT ──────────────
        neg_vis_now, QBER_now, total_coinc = measure_visibility_for_optimizer(
            tt, best_delays
        )
        vis_now = -neg_vis_now
        qber_now = QBER_now

        print(
            f"[QBER Optimizer] #{loop_idx} vis={vis_now:.3f} "
            f"(QBER={qber_now*100:.1f}%), stored best={best_vis_prev:.3f}, "
            f"total coincidences={total_coinc}"
        )

        # ────────────── STABLE REGION ──────────────
        if vis_now >= VISIBILITY_STOPPING_THRESHOLD:
            print(
                f"[QBER Optimizer] System stable (vis={vis_now:.3f} ≥ "
                f"{VISIBILITY_STOPPING_THRESHOLD:.3f}) — sleeping {SLEEP_TIMER} s."
            )
            for _ in range(SLEEP_TIMER):
                time.sleep(1)
            continue

        # ────────────── NEED CORRECTION ──────────────
        drift = abs(vis_now - best_vis_prev)
        step = STEP_SIZE * (0.2 if drift < 0.1 else 0.5 if drift < 0.5 else 1.0)
        print(f"[QBER Optimizer] Visibility dropped (Δ={drift:.3f}) → "
              f"re-optimizing with step={step:.1f}")

        res, best_V_new, best_vis_new, _ = run_qber_optimization(
            tt, best_delays, best_V, step
        )
        best_V, best_vis_prev = best_V_new, best_vis_new

        state["qber"] = {
            "best_V": best_V.tolist(),
            "best_visibility": float(best_vis_prev),
            "last_update": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        save_optimizer_state(state)

        # Small pause before next cycle (lets the system settle)
        time.sleep(SLEEP_TIMER)



# ─────────────────────────────────────────────
#  MAIN ENTRY POINT
# ─────────────────────────────────────────────

def main():
    tt = init_tagger()

    try:
        # 1) Auto delay calibration
        best_delays = auto_find_delays(tt)
        print("Using delays (ps):")
        for k in REF_PAIR_KEYS:
            print(f"  {k}: {best_delays.get(k, 0.0):+.1f} ps")
        print("")

        # 2) Start QBER optimizer loop
        optimize_contrast(tt, best_delays)

    except KeyboardInterrupt:
        print("Interrupted by user, shutting down...")
    finally:
        try:
            tt.deInitialize()
        except Exception:
            pass


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
