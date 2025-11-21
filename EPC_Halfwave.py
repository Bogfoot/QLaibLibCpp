# Test EPCs
"""
Created on Fri Oct 17 19:37:01 2025

@author: Adrian
"""
#─────────────────────────────────────────────
#  IMPORTS AND CONFIGURATION
#───────────────────────────────────────────────
import os, time, csv, socket, json, numpy as np, pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

from scipy.optimize import least_squares
from scipy.optimize import curve_fit
from scipy.fft import fft, fftfreq
from numpy.polynomial.polynomial import polyfit
from scipy.signal import savgol_filter



import QuTAG_MC  # Ensure the QuTAG_MC library is accessible

SERVER_IP = "141.255.216.213"   # IP of EPC server
PORT = 65432                    # Port on EPC server

base_folder = os.path.join("Data", "EPC_Singles")
os.makedirs(base_folder, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H_%M_%S")
log_file = os.path.join(base_folder, f"EPC_singles_log_{timestamp}.csv")

exposure_time = 2             # [s] integration per point
voltages = np.linspace(0, 130, 130*2)       # DAC sweep values
channels = [1, 2, 3, 4, 5, 6, 7, 8]  # H1,V1,D1,A1,H2,V2,D2,A2

base_voltage = 0
alignment_voltages = []
for _ in range(4):
    alignment_voltages.append(base_voltage)

# Definitions
def send_voltages(V1, V2):
    """Send voltage arrays to both EPCs via the EPC server."""
    cmd = "SETV" + json.dumps({"V1": V1.tolist(), "V2": V2.tolist()})
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((SERVER_IP, PORT))
        s.sendall(cmd.encode('utf-8'))
        resp = s.recv(1024)
        print("[EPC Server]", resp.decode())

def stop_epc_server():
    """Stop the EPC server remotely."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((SERVER_IP, PORT))
        s.sendall(b"STOP")
        print("[EPC Server] STOP sent")



send_voltages(np.array(alignment_voltages), np.array(alignment_voltages))


# Set up TT
tt = QuTAG_MC.QuTAG()
tt.setExposureTime(int(exposure_time * 1000))
_, coincWin, expTime = tt.getDeviceParams()
print(f"Device ready | coincidence window = {coincWin} ps, exposure = {expTime} ms")

#%% ─────────────────────────────────────────────
#  TEST: VERIFY CHANNEL → EPC MAPPING
#───────────────────────────────────────────────
def test_epc_mapping(test_epc="EPC1", step_channel=0):
    """
    Sweep one DAC channel while others are 0.
    Observe which singles channels respond.
    """
    print(f"Testing mapping for {test_epc}, DAC{step_channel}")
    V1 = np.zeros(4)
    V2 = np.zeros(4)
    for j in range(0, 130, 20):
        if test_epc == "EPC1":
            V1[step_channel] = j
        else:
            V2[step_channel] = j

        send_voltages(V1, V2)
        time.sleep(0.5)
        time.sleep(exposure_time)
        data, updates = tt.getCoincCounters()
        singles = [data[ch] for ch in channels]
        print(f"Voltage={j:3d} | " + " | ".join([f"Ch{i}: {s}" for i, s in enumerate(singles)]))


    send_voltages(np.array(alignment_voltages), np.array(alignment_voltages))  # Reset
    print("Mapping test complete.\n")

# Example:
test_epc_mapping("EPC1", 0)
test_epc_mapping("EPC2", 0)

#%%          MAIN MEASUREMENT: SINGLES LOGGING


plt.ion()
fig, ax = plt.subplots(2, 1, figsize=(7, 6))
count_history, time_history, voltage_history = [], [], []

# Write CSV header
with open(log_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "timestamp", "crystal", "voltage",
        "H1", "V1", "D1", "A1", "H2", "V2", "D2", "A2"
    ])
send_voltages(np.zeros(4), np.zeros(4))

for i_crystal in range(4):
    print(f"\n=== Scanning Crystal {i_crystal + 1} ===")
    for j in voltages:
        # Set voltage for current crystal on both EPCs
        V1 = np.zeros(4)
        V2 = np.zeros(4)
        V1[i_crystal] = j
        V2[i_crystal] = j
        send_voltages(V1, V2)

        time.sleep(exposure_time)
        data, updates = tt.getCoincCounters()
        singles = [data[ch] for ch in channels]
        
        print(f"Crystal {i_crystal}, V={j}: " + " | ".join([f"Ch{i}: {s}" for i, s in enumerate(singles)]))

        ts = time.time()
        count_history.append(sum(singles))
        time_history.append(ts)
        voltage_history.append(j)

        # Append to log file
        with open(log_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([ts, i_crystal, j, *singles])

# 0 voltages after
send_voltages(np.array(alignment_voltages), np.array(alignment_voltages))
print("Singles scan completed.")


# CLEANUP

tt.deInitialize()
# stop_epc_server()   # Uncomment to stop server automatically
print("EPC singles logging finished.")


#%% Fitting, plotting, saving

# Sine function for curve fitting
def sin_fun(x, A, f, phi, offset):
    return A * np.sin(2 * np.pi * f * x + phi) + offset

def damped_sin_fun(x, A, f, phi, offset, gamma):
    return A * np.exp(-gamma * (x - x.min())) * np.sin(2 * np.pi * f * x + phi) + offset


# Load your data
# df = pd.read_csv(log_file)
df = pd.read_csv("Data\\EPC_Singles\\EPC_singles_log_20251028_142351.csv")

# Channel groups
channels_1 = ["H1", "V1", "D1", "A1"]
channels_2 = ["H2", "V2", "D2", "A2"]

win_len = 5
poly_ord = 3

# Frequency bounds based on expected ~60 V period
freq_lower = 1 / 90
freq_upper = 1 / 40
freq_grid = np.linspace(freq_lower, freq_upper, 30)

# Output storage
fit_results = []

# Create output folder
output_dir = "fit_plots"
os.makedirs(output_dir, exist_ok=True)

# Loop over crystals
for crystal in range(4):
    df_crystal = df[df["crystal"] == crystal]
    voltage = df_crystal["voltage"].to_numpy()

    print(f"\n[Crystal {crystal + 1}]")

    # ---- Alice ----
    plt.figure(figsize=(10, 6))
    for ch in channels_1:
        raw_intensity = df_crystal[ch].to_numpy()
        intensity = savgol_filter(raw_intensity, window_length=win_len, polyorder=poly_ord)

        A_guess = max(10, (np.max(intensity) - np.min(intensity)) / 2)
        offset_guess = np.mean(intensity)
        phi_guess = 0

        best_popt = None
        best_error = np.inf
        fallback = False

        for f_guess in freq_grid:
            try:
                popt, _ = curve_fit(
                    damped_sin_fun,
                    voltage,
                    intensity,
                    p0=[A_guess, f_guess, phi_guess, offset_guess, 0.001],
                    bounds=([0, freq_lower, -np.pi, 0, 0], [1e6, freq_upper, np.pi, 1e6, 1])
                )
                fit_curve = damped_sin_fun(voltage, *popt)
                error = np.sum((fit_curve - intensity) ** 2)
                if error < best_error:
                    best_popt = popt
                    best_error = error
            except RuntimeError:
                continue

        if best_popt is not None:
            fit_curve = damped_sin_fun(voltage, *best_popt)
            residuals = intensity - fit_curve
            ss_res = np.sum(residuals**2)
            ss_tot = np.sum((intensity - np.mean(intensity))**2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
            rmse = np.sqrt(ss_res / len(voltage))
            sigma = np.sqrt(np.maximum(intensity, 1))  # avoid sqrt(0)
            chi2_red = np.sum(((intensity - fit_curve) / sigma)**2) / (len(voltage) - len(best_popt))

        
            plt.plot(voltage, raw_intensity, 'o', label=ch)
            plt.plot(voltage, fit_curve, '-', label=f"{ch} fit")
        
            A, f, phi, offset, gamma = best_popt
            print(f"  {ch}: A={A:.1f}, f={1/f:.5f}, φ={phi:.2f}, γ={gamma:.3f}, offset={offset:.1f}, "
                  f"R²={r2:.4f}")#, χ²={chi2_red:.3g}, RMSE={rmse:.3g}")
        else:
            fallback = True
            b, m = polyfit(voltage, intensity, 1)
            fit_curve = m * voltage + b
            best_error = np.sum((fit_curve - intensity) ** 2)
            best_popt = [np.nan, np.nan, np.nan, np.nan, np.nan]
            plt.plot(voltage, raw_intensity, 'o', label=f"{ch} (raw)")
            plt.plot(voltage, fit_curve, '--', label=f"{ch} linear")
            print(f"  {ch}: Fit failed — linear fallback")

        # Append results
        amplitude, frequency, phase, offset, gamma = best_popt
        period = 1 / frequency if frequency and not np.isnan(frequency) else np.nan
        fit_results.append([
            crystal + 1, ch,
            amplitude, frequency, period, phase, offset, gamma,
            best_error, fallback
        ])

        # Residual plot
        plt.figure()
        plt.plot(voltage, intensity - fit_curve, 'k.', label=f"{ch} residuals")
        plt.axhline(0, color='gray', linestyle='--')
        plt.title(f"Residuals — Crystal {crystal + 1}, {ch}")
        plt.xlabel("Voltage (V)")
        plt.ylabel("Residuals")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f"crystal{crystal + 1}_{ch}_residuals.png"), dpi=200)
        plt.close()

    plt.title(f"Crystal {crystal + 1} — Channels H1, V1, D1, A1")
    plt.xlabel("Voltage (V)")
    plt.ylabel("Counts")
    plt.legend(ncol=2)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"crystal{crystal + 1}_side1.png"), dpi=300)
    plt.show()

    # ---- Bob ----
    plt.figure(figsize=(10, 6))
    for ch in channels_2:
        raw_intensity = df_crystal[ch].to_numpy()
        intensity = savgol_filter(raw_intensity, window_length=win_len, polyorder=poly_ord)

        A_guess = max(10, (np.max(intensity) - np.min(intensity)) / 2)
        offset_guess = np.mean(intensity)
        phi_guess = 0

        best_popt = None
        best_error = np.inf
        fallback = False

        for f_guess in freq_grid:
            try:
                popt, _ = curve_fit(
                    damped_sin_fun,
                    voltage,
                    intensity,
                    p0=[A_guess, f_guess, phi_guess, offset_guess, 0.001],
                    bounds=([0, freq_lower, -np.pi, 0, 0], [1e6, freq_upper, np.pi, 1e6, 1])
                )
                fit_curve = damped_sin_fun(voltage, *popt)
                error = np.sum((fit_curve - intensity) ** 2)
                if error < best_error:
                    best_popt = popt
                    best_error = error
            except RuntimeError:
                continue

        if best_popt is not None:
            fit_curve = damped_sin_fun(voltage, *best_popt)
            residuals = intensity - fit_curve
            ss_res = np.sum(residuals**2)
            ss_tot = np.sum((intensity - np.mean(intensity))**2)
            r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan
            rmse = np.sqrt(ss_res / len(voltage))
            sigma = np.sqrt(np.maximum(intensity, 1))  # avoid sqrt(0)
            chi2_red = np.sum(((intensity - fit_curve) / sigma)**2) / (len(voltage) - len(best_popt))

        
            plt.plot(voltage, raw_intensity, 'o', label=ch)
            plt.plot(voltage, fit_curve, '-', label=f"{ch} fit")
        
            A, f, phi, offset, gamma = best_popt
            print(f"  {ch}: A={A:.1f}, f={1/f:.5f}, φ={phi:.2f}, γ={gamma:.3f}, offset={offset:.1f}, "
                  f"R²={r2:.4f}")#, χ²={chi2_red:.3g}, RMSE={rmse:.3g}")
        else:
            fallback = True
            b, m = polyfit(voltage, intensity, 1)
            fit_curve = m * voltage + b
            best_error = np.sum((fit_curve - intensity) ** 2)
            best_popt = [np.nan, np.nan, np.nan, np.nan, np.nan]
            plt.plot(voltage, raw_intensity, 'o', label=f"{ch} (raw)")
            plt.plot(voltage, fit_curve, '--', label=f"{ch} linear")
            print(f"  {ch}: Fit failed — linear fallback")

        # Append results
        amplitude, frequency, phase, offset, gamma = best_popt
        period = 1 / frequency if frequency and not np.isnan(frequency) else np.nan
        fit_results.append([
            crystal + 1, ch,
            amplitude, frequency, period, phase, offset, gamma,
            best_error, fallback
        ])

        # Residual plot
        plt.figure()
        plt.plot(voltage, intensity - fit_curve, 'k.', label=f"{ch} residuals")
        plt.axhline(0, color='gray', linestyle='--')
        plt.title(f"Residuals — Crystal {crystal + 1}, {ch}")
        plt.xlabel("Voltage (V)")
        plt.ylabel("Residuals")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, f"crystal{crystal + 1}_{ch}_residuals.png"), dpi=200)
        plt.close()

    plt.title(f"Crystal {crystal + 1} — Channels H2, V2, D2, A2")
    plt.xlabel("Voltage (V)")
    plt.ylabel("Counts/cps")
    plt.legend(ncol=2)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, f"crystal{crystal + 1}_side2.png"), dpi=300)
    plt.show()

# Save results to CSV
with open("fit_results.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Crystal", "Channel",
        "Amplitude", "Frequency", "Period", "Phase", "Offset", "Gamma",
        "FitError", "FallbackUsed"
    ])
    writer.writerows(fit_results)
#%%
"""
Model_EPCs_normalized_proper.py
- Calibrates both EPCs (Alice & Bob) with normalized intensities.
- Uses PER-DEVICE half-wave periods extracted from fit.csv (Channel ...1 vs ...2).
- Prints per-crystal alpha [deg], delta0 [rad], normalized RMSE [%].
- Saves cal_alice.npy and cal_bob.npy (list of 4 dicts each).
- Provides J_epc / M_epc and a |D> optimizer demo for each EPC.

Run interactively:  python3 -i Model_EPCs_normalized_proper.py
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import least_squares, dual_annealing

# ---------------------------------------------------------------------
# Config: paths
# ---------------------------------------------------------------------
FIT_CSV   = "fit_results.csv     # columns include: Crystal, Channel, Period, ...
SWEEP_CSV = log_file # columns: timestamp, crystal, voltage, H1...A2

# ---------------------------------------------------------------------
# Load fit + sweep
# ---------------------------------------------------------------------
fit   = pd.read_csv(FIT_CSV)
sweep = pd.read_csv(SWEEP_CSV)

# crystal index: 1->0, ..., 4->3
fit["phys_crystal"] = fit["Crystal"].astype(int) - 1

# Build PER-DEVICE periods (median across H/V/D/A of that device)
def build_periods_per_device(fit_df):
    if "Channel" in fit_df.columns:
        fit1 = fit_df[fit_df["Channel"].astype(str).str.endswith("1")]
        fit2 = fit_df[fit_df["Channel"].astype(str).str.endswith("2")]
        periods_A = (fit1.groupby("phys_crystal")["Period"].median()
                        .reindex(range(4)).to_numpy())
        periods_B = (fit2.groupby("phys_crystal")["Period"].median()
                        .reindex(range(4)).to_numpy())
    else:
        # Fallback: if Channel column missing, use a common period (not ideal)
        per = (fit_df.groupby("phys_crystal")["Period"].median()
                 .reindex(range(4)).to_numpy())
        periods_A = per.copy()
        periods_B = per.copy()
    return periods_A.astype(float), periods_B.astype(float)

periods_A, periods_B = build_periods_per_device(fit)

# ---------------------------------------------------------------------
# Polarization utilities
# ---------------------------------------------------------------------
ANALYZERS = {
    "H": np.array([ 1.0, 0.0, 0.0]),
    "V": np.array([-1.0, 0.0, 0.0]),
    "D": np.array([ 0.0, 1.0, 0.0]),
    "A": np.array([ 0.0,-1.0, 0.0]),
}

def rot_matrix(axis, angle):
    """3x3 Rodrigues rotation of Stokes (Q,U,V) around 'axis' by 'angle'."""
    u = axis / np.linalg.norm(axis)
    ux, uy, uz = u
    K = np.array([[0, -uz, uy], [uz, 0, -ux], [-uy, ux, 0]])
    I = np.eye(3)
    return I + np.sin(angle)*K + (1 - np.cos(angle))*(K @ K)

def M_retarder(alpha, delta):
    """4x4 Mueller of a linear retarder with fast-axis 'alpha' and retardance 'delta'."""
    u = np.array([np.cos(2*alpha), np.sin(2*alpha), 0.0])  # equatorial axis
    R = rot_matrix(u, delta)
    M = np.eye(4)
    M[1:, 1:] = R
    return M

# ---------------------------------------------------------------------
# Fit one crystal for one device (normalized intensities)
# ---------------------------------------------------------------------
def fit_crystal_for_device(i, device, periods_vec):
    df = sweep[sweep["crystal"] == i].copy()
    if df.empty:
        raise ValueError(f"No data for crystal {i} in sweep file.")
    V = df["voltage"].to_numpy()

    if device == "Alice":
        cols = ["H1","V1","D1","A1"]
    elif device == "Bob":
        cols = ["H2","V2","D2","A2"]
    else:
        raise ValueError("device must be 'Alice' or 'Bob'.")

    y_raw = df[cols].to_numpy(dtype=float)
    y = y_raw / np.clip(y_raw.sum(axis=1, keepdims=True), 1e-12, None)  # probabilities per row
    P = float(periods_vec[i])

    # parameters: [alpha, delta0, th, ph, r]  (S_in = tanh(r)*[cos th cos ph, sin th cos ph, sin ph])
    def residuals(p):
        alpha, delta0, th, ph, r = p
        S_in = np.tanh(r) * np.array([np.cos(th)*np.cos(ph),
                                      np.sin(th)*np.cos(ph),
                                      np.sin(ph)])
        pred = []
        for v in V:
            delta = np.pi * v / P + delta0
            M = M_retarder(alpha, delta)
            S_out = (M @ np.r_[1.0, S_in])[1:]
            row = [0.5*(1.0 + A @ S_out) for A in ANALYZERS.values()]
            pred.append(row)
        pred = np.array(pred)
        return (pred - y).ravel()

    p0 = np.array([0.0, 0.0, 0.0, 0.0, 0.5])
    res = least_squares(residuals, p0, method="trf", max_nfev=10000)
    alpha, delta0, *_ = res.x
    rmse = np.sqrt(np.mean(res.fun**2))  # on normalized data → in [0,1]
    return {"period": P, "alpha": alpha, "delta0": delta0, "rmse": rmse}

# ---------------------------------------------------------------------
# Calibrate EPC
# ---------------------------------------------------------------------
def calibrate_epc(device, periods_vec, save_path):
    print(f"\n=== Calibrating {device} (normalized) ===")
    cal = [fit_crystal_for_device(i, device, periods_vec) for i in range(4)]
    for i, c in enumerate(cal):
        print(f"Crystal {i}:  P={c['period']:.3f} V, "
              f"alpha={np.degrees(c['alpha']):.2f}°, "
              f"delta0={c['delta0']:.3f} rad,  "
              f"Norm. RMSE={100*c['rmse']:.2f}%")
    np.save(save_path, cal, allow_pickle=True)
    return cal

cal_alice = calibrate_epc("Alice", periods_A, "cal_alice.npy")
cal_bob   = calibrate_epc("Bob",   periods_B, "cal_bob.npy")

# ---------------------------------------------------------------------
# Jones / Mueller models
# ---------------------------------------------------------------------
def R(alpha):
    c, s = np.cos(alpha), np.sin(alpha)
    return np.array([[c, s], [-s, c]], dtype=complex)

def J_waveplate(V, period, alpha, delta0=0.0):
    delta = np.pi * V / period + delta0
    D = np.diag([np.exp(1j*delta/2), np.exp(-1j*delta/2)])
    return R(-alpha) @ D @ R(alpha)

def J_epc(Vs, cal):
    """Vs: iterable of 4 voltages; cal: list of 4 dicts with keys period, alpha, delta0."""
    J = np.eye(2, dtype=complex)
    for i, V in enumerate(Vs):
        c = cal[i]
        J = J_waveplate(V, c["period"], c["alpha"], c["delta0"]) @ J
    return J

def M_epc(Vs, cal):
    M = np.eye(4)
    for i, V in enumerate(Vs):
        c = cal[i]
        delta = np.pi * V / c["period"] + c["delta0"]
        M = M_retarder(c["alpha"], delta) @ M
    return M

print("\nCalibration complete (normalized). "
      "Use J_epc(Vs, cal_alice) or J_epc(Vs, cal_bob) for simulation.")

# ---------------------------------------------------------------------
# Optional visualization
# ---------------------------------------------------------------------
def plot_epc_fits(cal, device, save_png=False, fname=None):
    print(f"\nPlotting {device} fits...")
    fig, axs = plt.subplots(2, 2, figsize=(10, 8), sharex=True)
    axs = axs.ravel()
    colors = {"H":"tab:red", "V":"tab:blue", "D":"tab:green", "A":"tab:orange"}

    for i, c in enumerate(cal):
        df = sweep[sweep["crystal"] == i].copy()
        V = df["voltage"].to_numpy()
        cols = ["H1","V1","D1","A1"] if device == "Alice" else ["H2","V2","D2","A2"]
        y_raw = df[cols].to_numpy(dtype=float)
        y = y_raw / np.clip(y_raw.sum(axis=1, keepdims=True), 1e-12, None)

        P  = c["period"]; a = c["alpha"]; d0 = c["delta0"]
        pred = []
        # For visualization only, pick a nominal input Stokes (e.g. vertical)
        S_in = np.array([0.0, 0.0, 1.0])
        for v in V:
            d = np.pi * v / P + d0
            M = M_retarder(a, d)
            S_out = (M @ np.r_[1.0, S_in])[1:]
            row = [0.5*(1.0 + A @ S_out) for A in ANALYZERS.values()]
            pred.append(row)
        pred = np.array(pred)

        ax = axs[i]
        for j, key in enumerate(["H","V","D","A"]):
            ax.plot(V, y[:, j], "o", color=colors[key], alpha=0.55, ms=3,
                    label=f"{key} meas" if i == 0 else None)
            ax.plot(V, pred[:, j], "-", color=colors[key], lw=1.2,
                    label=f"{key} fit" if i == 0 else None)

        ax.set_title(f"{device} Crystal {i} (alpha={np.degrees(a):.1f}°, delta0={d0:.2f})")
        ax.set_xlabel("Voltage [V]")
        ax.set_ylabel("Normalized intensity")
        ax.set_ylim(0, 1)

    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=2)
    fig.suptitle(f"{device} EPC fits", fontsize=14)
    fig.tight_layout()

    if save_png:
        fname = fname or f"fits_{device}.png"
        plt.savefig(fname, dpi=150)
        print(f"Saved {fname}")
        plt.close(fig)
    else:
        plt.show()

# Example (uncomment to view or save)
# plot_epc_fits(cal_alice, "Alice", save_png=True)
# plot_epc_fits(cal_bob,   "Bob",   save_png=True)

# ---------------------------------------------------------------------
# Target-state optimizer: make |D> from |H>
# ---------------------------------------------------------------------
ket_H = np.array([1.0+0j, 0.0+0j])
ket_D = np.array([0.3827, 0.9239])

def diag_fidelity(Vs, cal):
    J = J_epc(Vs, cal)
    psi = J @ ket_H
    psi /= np.linalg.norm(psi)
    return np.abs(np.vdot(ket_D, psi))**2  # phase-invariant |<D|psi>|^2

def cost(Vs, cal):
    return 1.0 - diag_fidelity(Vs, cal)

def periods_from_cal(cal):
    return np.array([c["period"] for c in cal], dtype=float)

# Alice
P_A = periods_from_cal(cal_alice)
bounds_A = [(0.0, p) for p in P_A]
res_A = dual_annealing(lambda v: cost(v, cal_alice), bounds=bounds_A, maxiter=256, seed=7)
Vs_A = np.mod(res_A.x, P_A)
F_A  = diag_fidelity(Vs_A, cal_alice)
psi_A = J_epc(Vs_A, cal_alice) @ ket_H
psi_A /= np.linalg.norm(psi_A)
S1_A = 2*np.real(np.conj(psi_A[0])*psi_A[1])
S2_A = 2*np.imag(np.conj(psi_A[1])*psi_A[0])
S3_A = np.abs(psi_A[0])**2 - np.abs(psi_A[1])**2

print("\nAlice → |D> best (within 1-period bounds)")
print("Vs [V] =", np.round(Vs_A, 3))
print("Fidelity =", F_A)
print("Jones out =", psi_A)
print("Stokes (S1,S2,S3) ≈", np.array([S1_A, S2_A, S3_A]))

# Bob
P_B = periods_from_cal(cal_bob)
bounds_B = [(0.0, p) for p in P_B]
res_B = dual_annealing(lambda v: cost(v, cal_bob), bounds=bounds_B, maxiter=256, seed=11)
Vs_B = np.mod(res_B.x, P_B)
F_B  = diag_fidelity(Vs_B, cal_bob)
psi_B = J_epc(Vs_B, cal_bob) @ ket_H
psi_B /= np.linalg.norm(psi_B)
S1_B = 2*np.real(np.conj(psi_B[0])*psi_B[1])
S2_B = 2*np.imag(np.conj(psi_B[1])*psi_B[0])
S3_B = np.abs(psi_B[0])**2 - np.abs(psi_B[1])**2

print("\nBob → |D> best (within 1-period bounds)")
print("Vs [V] =", np.round(Vs_B, 3))
print("Fidelity =", F_B)
print("Jones out =", psi_B)
print("Stokes (S1,S2,S3) ≈", np.array([S1_B, S2_B, S3_B]))

