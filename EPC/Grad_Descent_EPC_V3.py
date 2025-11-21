import os, random, time, socket, datetime, subprocess
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.fft import fft, fftfreq
import QuTAG_MC as qt

os.chdir("C:\\Users\\LjubljanaLab\\Desktop\\TempScans\\ScanCode\\AEPC\\PC_control_application")
from EPC import PolarizationDevice

sig_err = 0.99999
# Gotta start somewhere
# V = np.array([55.59811564, 116.58949608, 129.62801259, 2.68490311], dtype=np.float64)      # 14.03.2025.
# V = np.array([54.84217993, 116.08120006, 129.46099595, 1.34877751], dtype=np.float64)        # 15.03.2025.
# V = np.array([66.49688638, 32.6834726, 6.65841635, 121.91545606], dtype=np.float64)           # 15.03.2025 Not as good as above.
# V = np.array([65, 65, 65, 65], dtype=np.float64)
V = np.array([0, 0, 0, 0], dtype=np.float64)
alpha = 0.2  # "Learning rate" -- "Large" in beginning, become smaller during iterations - can be tuned.
delta_V = 0.01 # V_step for gradient -- 
epsilon=1e-6
expT = 1        # Exposure time
measure_slp = 0.1 # Time between two measurements to sleep for

# Adam optimizer params
m = np.zeros(4)
v = np.zeros(4)
t = 0

def get_detector_values(hn: str, port: int, exposure_time_TT: float):
    host = hn  # The server's hostname or IP address
    port = port  # The port used by the server
    
    command = f"EXPOSURE{exposure_time_TT}"
    command = command.encode(encoding="utf-8")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall(command)
    try:           
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            s.sendall(b"GATHER DATA")
            # s.sendall(b"STOP")
            data = s.recv(1024).decode("utf-8")
                    
            # Check if the received data is an error message or a close oven message
            if "Error" in data:
                print(f"Error received from server: {data}")
                    
            # Parse the received data
            parts = data.split(", ")
            # clicks1 = parts[0].split(": ")[1]
            # clicks2 = parts[1].split(": ")[1]
            clicks3 = parts[2].split(": ")[1]
            clicks4 = parts[3].split(": ")[1]
            # coincidences12 = parts[4].split(": ")[1]
            # coincidences13 = parts[5].split(": ")[1]
            # coincidences23 = parts[6].split(": ")[1]
            # coincidences14 = parts[7].split(": ")[1]
            # coincidences24 = parts[8].split(": ")[1]
            # coincidences34 = parts[9].split(": ")[1]
            return int(clicks3), int(clicks4)
    except Exception as e:
        print(f"Exception caught:\n{e}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            s.sendall(b"STOP")
            data = s.recv(1024).decode("utf-8")
            print(f"Received: {data}")

def measure_intensities():
    global expT
    hn, port = '141.255.216.110', 65432
    I_V, I_H = get_detector_values(hn, port, expT)
    print(f"H: {I_H}, V: {I_V}")
    total = I_H + I_V
    if total == 0:
        return np.array([0, 0])
    
    I_H /= total
    I_V /= total
    
    return np.array([I_H, I_V])



def set_voltage(EPC, V):

    """ Apply voltages to all four DAC channels. 
    #NOTE: Decided not to do this -> Might have to change strategy
    depending on results next week. 
    #NOTE: I don't think there's anything to be changed here.
    """

    # TODO: Next aproach would be to selectively probe each crystal
    # individually to see which one has the most "positive" effect towards the
    # target intensity
    
    EPC.set_voltage("DAC0", V[0])
    EPC.set_voltage("DAC1", V[1])
    EPC.set_voltage("DAC2", V[2])
    EPC.set_voltage("DAC3", V[3])

def error_function(I):

    """ Define target polarization state (modify as needed). """
    
    # Example: Correcting polarization to H as there could be a PBS in front of
    # the EPC
    I_target = np.array([sig_err, 1-sig_err])
    # This can be changed to whatever works best
    return np.sum((I - I_target)**2)

def compute_gradient(EPC, V):
    global convergence_factor
    """ Compute numerical gradient for each voltage channel. """

    E0 = error_function(measure_intensities())
    grad = np.zeros(4)

    for i in range(4):
        V_test = V.copy()
        V_test[i] += delta_V
        set_voltage(EPC, V_test)
        time.sleep(measure_slp)
        E_new = error_function(measure_intensities())  # new error
        print(f"Error = {E_new}")
        if i == 3:
            f = open(data_file_name, "a")
            f.write(f"{E_new}")
            f.close()
        else:
            f = open(data_file_name, "a")
            f.write(f"{E_new},")
            f.close()

        grad[i] = (E_new - E0) / delta_V  # gradient 
    print(convergence_factor)
    if E_new < 1 - sig_err:
        convergence_factor = True
    f = open(data_file_name, 'a')
    f.write("\n")
    f.close()
    print(f"Gradient: {grad}")
    return grad

def adam_optimizer(V, grad, m, v, t, beta1=0.9, beta2=0.999, epsilon=1e-8, alpha=0.001):
    # first moment
    m = beta1 * m + (1 - beta1) * grad     
    # second moment
    v = beta2 * v + (1 - beta2) * (grad**2)
        
    # Bias corrections
    m_hat = m / ( 1 - beta1**t )    
    v_hat = v / ( 1 - beta2**t )
    
    V = -alpha * m_hat / (np.sqrt(v_hat) + epsilon)
    V = np.clip(V, 0, 130)
    
    return V, m, v
    
def adam_optimizer_V2(V, grad, m, v, t, beta1=0.95, beta2=0.999, epsilon=1e-6, alpha=0.001):
    
    m = beta1 * m + (1 - beta1) * grad
    v = beta2 * v + (1 - beta2) * (grad ** 2)
    
    m_hat = m / (1 - beta1 ** t)
    v_hat = v / (1 - beta2 ** t)
    
    # Added learning rate scheduling
    decay_rate = 0.99
    alpha = alpha * (decay_rate ** t)
    
    V -= alpha * m_hat / (np.sqrt(v_hat) + epsilon)
    V = np.clip(V, 0, 130)
    
    return V, m, v

def compute_hessian(EPC, V, delta_V):
    """
    
    """
    n = len(V)
    H = np.zeros((n, n))
    E0 = error_function(measure_intensities())
    print(f"E0 error = {E0}")
    for i in range(n):
        for j in range(n):
            if i == j:
                V_test = V.copy()
                V_test[i] += delta_V
                set_voltage(EPC, V_test)
                time.sleep(measure_slp)
                E_ij = error_function(measure_intensities())
                print(f"E_ij error = {E_ij}")
                H[i, j] = (E_ij - 2 * E0 + E0) / (delta_V * 2)
            else:
                V_test = V.copy()
                V_test[i] += delta_V
                V_test[j] += delta_V
                set_voltage(EPC, V_test)
                time.sleep(measure_slp)
                E_ij = error_function(measure_intensities())
                print(f"E_ij error = {E_ij}")
                V_test[j] -= delta_V
                set_voltage(EPC, V_test)
                time.sleep(measure_slp)
                E_i = error_function(measure_intensities())
                print(f"E_i error = {E_i}")
                V_test[i] -= delta_V
                V_test[j] += delta_V
                set_voltage(EPC, V_test)
                time.sleep(measure_slp)
                E_j = error_function(measure_intensities())
                print(f"E_j error = {E_j}")
                H[i, j] = (E_ij - E_i - E_j + E0) / (delta_V * 2)
    return H

def newton_update(EPC, delta_V):
    """ Add description """
    global V
    grad = compute_gradient(EPC, V)
    H = compute_hessian(EPC, V, delta_V)
    # print(f"Hessian = {H}")
    H_inv = np.linalg.inv(H + 1e-4 * np.eye(len(V)))  # Regularization
    # print(f"Inverse Hessian = {H_inv}")
    V = V - np.dot(H_inv, grad)
    V = np.clip(V, 0, 130)
    print(V)
    set_voltage(EPC, V)
    # return V_new

def update_voltages_V0(EPC):
    global V
    grad = compute_gradient(EPC, V)
    V -= alpha * grad
    V = np.clip(V, 0, 130)
    print(f"Voltages = {V}")
    set_voltage(EPC, V)

def update_voltages_V1(EPC):
    
    global V, alpha, m, v, t
    grad = compute_gradient(EPC, V)
    # Adam optimizer method
    # t += 1
    # V, m, v = adam_optimizer(V, grad, m, v, t, alpha=alpha)
    # V, m, v = adam_optimizer(V, grad, m, v, t, alpha=alpha)
    # Regular Gradient
    # grad_M = np.linalg.norm(grad)
    # if grad_M > 1:
    #     alpha = min(0.1, alpha * 1.05)
    # else:
    #     alpha = max(0.001, alpha * 0.9)
    # print(f"Alpha = {alpha}")
    
    # Basic adam optimizer method with momentum without velocity
    beta = 0.9
    m = beta * + (1 - beta) * grad
    V -= alpha * m * grad
    V = np.clip(V, 0, 130)
    print(f"Voltages = {V}")
    set_voltage(EPC, V)

def update_voltages_V2(EPC):
    global V, alpha, m, v, t
    grad = compute_gradient(EPC, V)
    t += 1
    V, m, v = adam_optimizer_V2(V, grad, m, v, t, alpha=alpha)
    print(f"Voltages = {V}")
    set_voltage(EPC, V)
    
#%%

# TODO: TEST THIS || DONE
# Logging folder
folder_path = os.path.join("..", "..", "Data", "EPC")
if not os.path.exists(folder_path):
    os.makedirs(folder_path)
print("configure DAC6, DAC3-DAC0")
# Initialize MCP2210CLI with subprocess
subprocess.run(
    ["mcp2210cli", "-spitxfer=28,4f", "-bd=100000,", "-cs=gp4", "-md=1"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL
)
temperature = 50 #from 10 to 70degC
EPC_1 = PolarizationDevice("0000872235")
# EPC_2 = PolarizationDevice("0001005125")
EPC_1.set_temperature(temperature)
# EPC_2.set_temperature(temperature)
set_voltage(EPC_1, V)
# set_voltage(EPC_2, V)
# %%
tl = time.localtime()
curr_date = str(datetime.date.today())+ time.strftime("%H_%M_%S", tl)
# data_file_name = os.path.join("..", "..", "Data", "EPC" ,"alpha_" + str(alpha) +  "_delta_V_" + str(delta_V) + "_Errors" + str(datetime.date.today())+ time.strftime("%H_%M_%S", tl) + ".data")

data_file_name = os.path.join(folder_path,"alpha_" + str(alpha) +  "_delta_V_" + str(delta_V) + "_Errors_" + curr_date + ".data")
print(f"File name of new data is: {data_file_name}")
f = open(data_file_name, "a")
f.write("# err1,err2,err3,err4\n")
f.close()

#%%
# Control loops
convergence_factor = False
# for _ in range(5):
#     newton_update(EPC_1, delta_V)
#     time.sleep(0.1)

while True:
    # update_voltages_V0(EPC_1)
    # update_voltages_V1(EPC_1)
    update_voltages_V2(EPC_1)
    
    time.sleep(0.1)
#%%
fp = "C:\\Users\\LjubljanaLab\\Desktop\\TempScans\\ScanCode\\Data\\EPC"
# fn = os.path.join(folder_path, "alpha_0.2_delta_V_0.5_Errors_2025-03-1517_37_20.data")
fn = os.path.join(fp, "alpha_0.2_delta_V_0.5_Errors_2025-03-1612_21_59.data")
print(fn)
df = pd.read_csv(fn , skiprows=1, names=["err1","err2","err3","err4"])
# df = pd.read_csv(data_file_name, skiprows=1, names=["err1","err2","err3","err4"])

if {'err1', "err2" ,"err3", "err4"}.issubset(df.columns):
    plt.figure(figsize=(10,6))
    arr = np.linspace(1, len(df["err1"]) + 1, len(df['err1']))
    plt.plot(arr, df['err1'], label='err1')
    plt.plot(arr, df['err2'], label='err2')
    plt.plot(arr, df['err3'], label='err3')
    plt.plot(arr, df['err4'], label='err4')
    
    plt.xlabel("Time/s")
    plt.ylabel("Target Error")
    plt.yscale('log')
    plt.title("Error data")
    plt.grid(True)
    plt.legend()
    plt.show()
else:
    print("Error in columns")
#%% Some analisys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.signal import correlate

# Load Data
df = pd.read_csv(fn, skiprows=1, names=["err1", "err2", "err3", "err4"])

if not {'err1', 'err2', 'err3', 'err4'}.issubset(df.columns):
    print("Error in columns")
    exit()

# Define pseudo-time based on index
time = np.arange(len(df))

# Exponential Decay Function
def exp_decay(t, A, lambda_, C):
    return A * np.exp(-lambda_ * t) + C

# Analyze Each Error Column
for err_col in df.columns:
    error = df[err_col].values

    # Plot Error Data
    plt.figure(figsize=(8,5))
    plt.plot(time, error, label=f"{err_col}")
    plt.xlabel("Index (time step)")
    plt.ylabel("Error Value")
    plt.yscale("log")
    plt.title(f"{err_col} Over Time")
    plt.grid()
    plt.legend()
    plt.show()

    # Fit Exponential Decay
    try:
        popt, _ = curve_fit(exp_decay, time, error, maxfev=5000)
        A, lambda_, C = popt
        half_life = np.log(2) / lambda_

        print(f"\n{err_col}: A={A:.3f}, $\lambda$={lambda_:.6f}, C={C:.3f}")
        print(f"{err_col} Half-life: {half_life:.3f} time steps")

        # Plot Exponential Fit
        plt.figure(figsize=(8,5))
        plt.plot(time, error, label="Actual Error")
        plt.plot(time, exp_decay(time, *popt), label="Exponential Fit", linestyle="dashed")
        plt.xlabel("Index (time step)")
        plt.ylabel("Error Value")
        plt.yscale("log")
        plt.title(f"Exponential Decay Fit for {err_col}")
        plt.legend()
        plt.grid()
        plt.show()
    
    except RuntimeError:
        print(f"Could not fit an exponential decay to {err_col}.")

    # Compute Derivative
    error_derivative = np.gradient(error)

    plt.figure(figsize=(8,5))
    plt.plot(time, error_derivative, label=f"d({err_col})/dt")
    plt.xlabel("Index (time step)")
    plt.ylabel("Derivative")
    plt.title(f"Derivative of {err_col}")
    plt.grid()
    plt.legend()
    plt.show()

    # Compute Autocorrelation Function (ACF)
    acf = correlate(error - np.mean(error), error - np.mean(error), mode="full")
    acf = acf[len(acf)//2:]  # Keep only positive lags
    lags = np.arange(len(acf))

    plt.figure(figsize=(8,5))
    plt.plot(lags, acf, label=f"ACF of {err_col}")
    plt.xlabel("Lag")
    plt.ylabel("Autocorrelation")
    plt.title(f"Autocorrelation Function of {err_col}")
    plt.grid()
    plt.legend()
    plt.show()

    # FFT for Frequency Analysis
    N = len(time)
    freqs = fftfreq(N, 1)  # Assuming uniform sampling
    fft_values = np.abs(fft(error))

    plt.figure(figsize=(8,5))
    plt.plot(freqs[:N//2], fft_values[:N//2])
    plt.xlabel("Frequency")
    plt.ylabel("Magnitude")
    plt.title(f"FFT of {err_col}")
    plt.grid()
    plt.show()
#%%
# Use index as time
time = np.arange(len(df))

# Plot Errors
plt.figure(figsize=(10,6))
plt.plot(time, df['err1'], label='err1')
plt.plot(time, df['err2'], label='err2')
plt.plot(time, df['err3'], label='err3')
plt.plot(time, df['err4'], label='err4')

plt.xlabel("Index (Time Steps)")
plt.ylabel("Error Values")
plt.yscale('log')
plt.title("Error Data")
plt.grid(True)
plt.legend()
plt.show()

for col in df.columns:
    error = df[col].values
    popt, _ = curve_fit(exp_decay, time, error, maxfev=5000)
    A, lambda_, C = popt
    half_life = np.log(2) / lambda_

    print(f"{col} - Fitted parameters: A={A:.3f}, $\lambda$={lambda_:.3f}, C={C:.3f}")
    print(f"{col} - Half-life of decay: {half_life:.3f} time steps")

    # Plot Exponential Fit
    plt.figure(figsize=(8,5))
    plt.plot(time, error, label="Actual Error")
    plt.plot(time, exp_decay(time, *popt), label="Exponential Fit", linestyle="dashed")
    plt.xlabel("Index (Time Steps)")
    plt.ylabel("Error")
    plt.yscale("log")
    plt.title(f"Exponential Decay Fit - {col}")
    plt.legend()
    plt.grid()
    plt.show()

# Compute Derivative
plt.figure(figsize=(10,6))
for col in df.columns:
    error_derivative = np.gradient(df[col], time)
    plt.plot(time, error_derivative, label=f"d({col})/dt")

plt.xlabel("Index (Time Steps)")
plt.ylabel("Error Derivative")
plt.title("Error Derivative Over Time")
plt.legend()
plt.grid()
plt.show()

# Autocorrelation Function (ACF)
plt.figure(figsize=(10,6))
for col in df.columns:
    acf = correlate(df[col] - np.mean(df[col]), df[col] - np.mean(df[col]), mode="full")
    acf = acf[len(acf)//2:]  # Keep only the positive lag part
    plt.plot(acf[:200], label=f"ACF - {col}")  # First 200 lags

plt.xlabel("Lag (Time Steps)")
plt.ylabel("Autocorrelation")
plt.title("Autocorrelation Function of Errors")
plt.legend()
plt.grid()
plt.show()

# FFT for Frequency Analysis
plt.figure(figsize=(10,6))
N = len(time)
dt = 1  # Assuming each index is 1 time step
freqs = fftfreq(N, dt)

for col in df.columns:
    fft_values = np.abs(fft(df[col]))
    plt.plot(freqs[:N//2], fft_values[:N//2], label=f"FFT - {col}")

plt.xlabel("Frequency (1/Time Steps)")
plt.ylabel("Magnitude")
plt.title("FFT of Error Signals")
plt.legend()
plt.grid()
plt.show()


#%%

# Logging folder
folder_path = os.path.join("..", "..", "Data", "EPC")
os.makedirs(folder_path, exist_ok=True)

# TimeTagger setup
exposure_time_timetagger = 5  # seconds
tt = qt.QuTAG()
timebase = tt.getTimebase()
print("Device timebase:", timebase, "s")
tt.setExposureTime(exposure_time_timetagger * 1000)

# Channel config
channels = [1, 2, 3, 4]
tt.enableChannels(channels)

# Output files
li_file = os.path.join(folder_path, "LIs_log.csv")
ri_file = os.path.join(folder_path, "RIs_log.csv")
with open(li_file, "w") as f:
    f.write("i,j,H,V\n")
with open(ri_file, "w") as f:
    f.write("i,j,H,V\n")

def get_singles():
    time.sleep(exposure_time_timetagger)
    data, _ = tt.getCoincCounters()
    # Normalize each H/V pair
    left_total = data[1] + data[2]
    right_total = data[3] + data[4]
    left_norm = np.array([data[1] / left_total, data[2] / left_total]) if left_total > 0 else np.zeros(2)
    right_norm = np.array([data[4] / right_total, data[3] / right_total]) if right_total > 0 else np.zeros(2)
    return left_norm, right_norm

# Voltage scan
voltages = np.arange(130)
LIs = np.zeros((130, 4, 2))
RIs = np.zeros((130, 4, 2))

for i in range(4):
    voltage = np.zeros(4)
    for j in range(130):
        print(f"Crystal[{i}]_voltage({j})")
        voltage[i] = j
        set_voltage(EPC_1, voltage)
        set_voltage(EPC_2, voltage)
        time.sleep(0.1)
        LI, RI = get_singles()
        LIs[j, i, :] = LI
        RIs[j, i, :] = RI

        # Append to file
        with open(li_file, "a") as f:
            f.write(f"{i},{j},{LI[0]:.6f},{LI[1]:.6f}\n")
        with open(ri_file, "a") as f:
            f.write(f"{i},{j},{RI[0]:.6f},{RI[1]:.6f}\n")

        print("L:", LI)
        print("R:", RI)

tt.deInitialize()
np.save(os.path.join(folder_path, "LIsEPC2.npy"), LIs)
np.save(os.path.join(folder_path, "LIsEPC1.npy"), RIs)
#%%
tt.deInitialize()
#%%
V = np.array([0,0,0,0])
set_voltage(EPC_1, V)
# set_voltage(EPC_2, V)
# print(get_singles())
#%%
# Is_File = os.path.join(folder_path, "Is.npy")
# Is = np.load(Is_File)

import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
voltages = np.arange(130)
def sin_fun(x, A, B, C, D):
    """Simple sinusoidal function for curve fitting."""
    return A * np.sin(B * x + C) + D


def Plot_Is_from_csv(df):
    """
    Plot and fit sinusoidal intensity data from a CSV file
    with columns: i (crystal index), j (voltage index), H, V.
    """
    crystals = sorted(df['i'].unique())

    for i_crystal in crystals:
        # Extract and sort data for this crystal
        subset = df[df['i'] == i_crystal].sort_values('j')
        voltages = subset['j'].to_numpy()
        I_H = subset['H'].to_numpy()
        I_V = subset['V'].to_numpy()

        # --- Initial parameter guesses ---
        guess_H = [(max(I_H)-min(I_H))/2, (8/130), 0, np.mean(I_H)]
        guess_V = [(max(I_V)-min(I_V))/2, (8/130), 0, np.mean(I_V)]

        # --- Fit sinusoidal curves ---
        try:
            popt_H, _ = curve_fit(sin_fun, voltages, I_H, p0=guess_H)
        except RuntimeError:
            print(f"Fit failed for H detector of crystal {i_crystal}")
            continue

        try:
            popt_V, _ = curve_fit(sin_fun, voltages, I_V, p0=guess_V)
        except RuntimeError:
            print(f"Fit failed for V detector of crystal {i_crystal}")
            continue

        # --- Plot measured and fitted data ---
        plt.figure(figsize=(7, 4))
        plt.plot(voltages, I_H, 'r.', label='H data')
        plt.plot(voltages, I_V, 'b.', label='V data')
        plt.plot(voltages, sin_fun(voltages, *popt_H), 'r-', label='H fit')
        plt.plot(voltages, sin_fun(voltages, *popt_V), 'b-', label='V fit')
        plt.xlabel('Voltage index (j)')
        plt.ylabel('Measured intensity')
        plt.title(f'Crystal {i_crystal}')
        plt.legend()
        plt.tight_layout()
        plt.show()

        # --- Print fit parameters ---
        A_H, B_H, C_H, D_H = popt_H
        A_V, B_V, C_V, D_V = popt_V
        print(f"Crystal {i_crystal}:")
        print(f"  H → Amplitude={A_H:.4f}, Frequency={B_H:.4f}, Phase={C_H:.4f}, Offset={D_H:.4f}")
        print(f"  V → Amplitude={A_V:.4f}, Frequency={B_V:.4f}, Phase={C_V:.4f}, Offset={D_V:.4f}")
        print()

def Plot_Is(Is):
    for i in range(4):
        plt.figure()
        # FFT analysis for Detector V
        N = len(Is[:, i, 0])
        T = voltages[1] - voltages[0]  # Assuming uniform voltage steps
        yf_v = fft(Is[:, i, 0])
        xf_v = fftfreq(N, T)[:N//2]
        
        # FFT analysis for Detector H
        yf_h = fft(Is[:, i, 1])
        xf_h = fftfreq(N, T)[:N//2]
        
        initial_guess_1 = [(max(Is[:, i, 0]) - min(Is[:, i, 0]))/2, (8/130), 0, np.mean(Is[:, i, 0])]
        initial_guess_2 = [(max(Is[:, i, 1]) - min(Is[:, i, 1]))/2, (8/130), 0, np.mean(Is[:, i, 1])]
        try:
            popt_1, pcov_1 = curve_fit(sin_fun, voltages, Is[:, i, 0], p0=initial_guess_1)
        except RuntimeError:
            print(f"Fit failed for Measurement 1 of Crystal {i+1}")
            continue
        try:
           popt_2, pcov_2 = curve_fit(sin_fun, voltages, Is[:, i, 1], p0=initial_guess_2)
        except RuntimeError:
           print(f"Fit failed for Measurement 2 of Crystal {i+1}")
           continue
       
        plt.plot(voltages, Is[:, i, 0], label='Measurement 1', linestyle='-', color='b')
        plt.plot(voltages, Is[:, i, 1], label='Measurement 2', linestyle='--', color='r')
        plt.plot(voltages, sin_fun(voltages, *popt_1), '-', label='Fitted Curve 1')
        plt.plot(voltages, sin_fun(voltages, *popt_2), '-', label='Fitted Curve 2')
        plt.xlabel('Voltage Setting')
        plt.ylabel('Measured Intensity')
        plt.title(f'Crystal {i+1}')
        plt.legend()
        plt.show()
        amplitude_1, frequency_1, phase_shift_1, offset_1 = popt_1
        print(f"Amplitude: {amplitude_1}")
        print(f"Frequency: {frequency_1}")
        print(f"Phase Shift: {phase_shift_1}")
        print(f"Offset: {offset_1}")
        print("\n")
        amplitude_2, frequency_2, phase_shift_2, offset_2 = popt_2
        print(f"Amplitude: {amplitude_2}")
        print(f"Frequency: {frequency_2}")
        print(f"Phase Shift: {phase_shift_2}")
        print(f"Offset: {offset_2}")
        print("\n")

#%%
import pandas as pd
import os

folder_path = os.path.join("..", "..", "Data", "EPC")
li_file = os.path.join(folder_path, "LIs_log.csv")
ri_file = os.path.join(folder_path, "RIs_log.csv")

LIs_log = pd.read_csv(li_file)
RIs_log = pd.read_csv(ri_file)

# Plot for Left or Right EPC dataset
Plot_Is_from_csv(LIs_log)
Plot_Is_from_csv(RIs_log)

#%% Imports
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# Model:
# I_H(j) = (1+δ)/2 + (V/2) * sin(B*j + C)
# I_V(j) = (1-δ)/2 - (V/2) * sin(B*j + C)
# with k = B/4  (rad of fast-axis per step),  α0 = (C - π/2)/4
def hv_model_concat(j_all, V, delta, B, C, jH, jV):
    # j_all is a dummy required by curve_fit; we feed explicit jH/jV via closure
    H_pred = 0.5*(1+delta) + 0.5*V*np.sin(B*jH + C)
    V_pred = 0.5*(1-delta) - 0.5*V*np.sin(B*jV + C)
    return np.concatenate([H_pred, V_pred])

def initial_guesses(j, H, Vsig):
    mH, mV = np.mean(H), np.mean(Vsig)
    delta0 = np.clip(mH - 0.5*(mH+mV), -0.3, 0.3)  # small H/V bias
    ampH = 0.5*(np.max(H) - np.min(H))
    ampV = 0.5*(np.max(Vsig) - np.min(Vsig))
    V0 = np.clip(2*np.mean([ampH, ampV]), 0.1, 0.95)  # modulation depth
    B0 = 0.07  # rad/step, close to what you observed (≈0.075–0.078)
    C0 = 0.0
    return V0, delta0, B0, C0

def joint_fit_one_crystal(df, crystal, normalize=True, bounds=None):
    """
    Jointly fit H & V for one crystal index 'crystal' in a DataFrame with columns: i (crystal), j (voltage), H, V.
    Returns dict with parameters and 1-σ uncertainties; makes a plot.
    """
    sub = df[df['i'] == crystal].sort_values('j').copy()
    j = sub['j'].to_numpy().astype(float)
    H = sub['H'].to_numpy().astype(float)
    Vsig = sub['V'].to_numpy().astype(float)

    if normalize:
        total = H + Vsig + 1e-12
        H = H/total
        Vsig = Vsig/total

    # Initial guesses and bounds
    p0 = initial_guesses(j, H, Vsig)
    if bounds is None:
        # V in [0,1.2]; δ in [-0.5,0.5]; B in [0.01,0.2]; C in [-π,π]
        bounds = ([0.0, -0.5, 0.01, -np.pi],
                  [1.2,  0.5, 0.20,  np.pi])

    # Build concatenated target
    y = np.concatenate([H, Vsig])
    # Closure to pass separate j for H and V
    f = lambda j_all, Vp, delt, Bb, Cc: hv_model_concat(j_all, Vp, delt, Bb, Cc, j, j)

    popt, pcov = curve_fit(f, j, y, p0=p0, bounds=bounds, maxfev=20000)
    Vp, delt, Bb, Cc = popt
    perr = np.sqrt(np.diag(pcov)) if pcov is not None else np.full_like(popt, np.nan)
    Vp_e, delt_e, Bb_e, Cc_e = perr

    # Derived physical params
    k = Bb/4.0
    k_e = Bb_e/4.0
    alpha0 = (Cc - np.pi/2.0)/4.0
    alpha0_e = Cc_e/4.0

    # Predictions
    H_fit = 0.5*(1+delt) + 0.5*Vp*np.sin(Bb*j + Cc)
    V_fit = 0.5*(1-delt) - 0.5*Vp*np.sin(Bb*j + Cc)

    # Plot
    plt.figure(figsize=(7,4))
    plt.plot(j, H, 'r.', label='H data')
    plt.plot(j, Vsig, 'b.', label='V data')
    plt.plot(j, H_fit, 'r-', label='H fit')
    plt.plot(j, V_fit, 'b-', label='V fit')
    plt.xlabel('Voltage index j')
    plt.ylabel('Normalized intensity' if normalize else 'Intensity (a.u.)')
    plt.title(f'Crystal {crystal} — joint fit')
    plt.legend()
    plt.tight_layout()
    plt.show()

    # Residuals summary (optional print)
    resH = H - H_fit
    resV = Vsig - V_fit
    rmseH = np.sqrt(np.mean(resH**2))
    rmseV = np.sqrt(np.mean(resV**2))

    return {
        'crystal': crystal,
        'V': Vp, 'V_err': Vp_e,
        'delta': delt, 'delta_err': delt_e,
        'B': Bb, 'B_err': Bb_e,
        'C': Cc, 'C_err': Cc_e,
        'k': k, 'k_err': k_e,
        'alpha0': alpha0, 'alpha0_err': alpha0_e,
        'RMSE_H': rmseH, 'RMSE_V': rmseV
    }

def jones_rot_retarder(alpha, Gamma):
    c, s = np.cos(alpha), np.sin(alpha)
    R = np.array([[c, -s],[s, c]], dtype=complex)
    D = np.diag([np.exp(-1j*Gamma/2), np.exp(+1j*Gamma/2)])
    return R.conj().T @ D @ R

def jones_gain_from_delta(delta):
    # H/V gain imbalance (post-retarder), ignore overall scale
    return np.diag([np.sqrt(1+delta), np.sqrt(1-delta)])

def crystal_jones(k, alpha0, V, delta, j):
    Gamma = 2*np.arcsin(np.clip(np.sqrt(V), 0, 1))
    alpha = alpha0 + k*j
    return jones_gain_from_delta(delta) @ jones_rot_retarder(alpha, Gamma)

#%% Fit all crystals in a CSV and save a results table
import os

def fit_all_crystals(csv_path, normalize=True, save_results=True, out_csv=None):
    df = pd.read_csv(csv_path)
    crystals = sorted(df['i'].unique())
    results = []
    for c in crystals:
        res = joint_fit_one_crystal(df, c, normalize=normalize)
        results.append(res)
        # nice console print
        print(f"\nCrystal {c}:")
        print(f"  V = {res['V']:.4f} ± {res['V_err']:.4f}")
        print(f"  δ = {res['delta']:.4f} ± {res['delta_err']:.4f}")
        print(f"  B = {res['B']:.6f} ± {res['B_err']:.6f} rad/step")
        print(f"  k = {res['k']:.6f} ± {res['k_err']:.6f} rad/step")
        print(f"  α0 = {np.degrees(res['alpha0']):.2f}° ± {np.degrees(res['alpha0_err']):.2f}°")
        print(f"  RMSE(H)={res['RMSE_H']:.4e}, RMSE(V)={res['RMSE_V']:.4e}")

    res_df = pd.DataFrame(results)
    if save_results:
        if out_csv is None:
            base, name = os.path.split(csv_path)
            stem = os.path.splitext(name)[0]
            out_csv = os.path.join(base, f"{stem}_jointfit_params.csv")
        res_df.to_csv(out_csv, index=False)
        print(f"\nSaved parameter table → {out_csv}")
    return res_df

# Example usage:
# folder_path = os.path.join("..", "..", "Data", "EPC")
# li_csv = os.path.join(folder_path, "LIs_log.csv")
# fit_all_crystals(li_csv, normalize=True)
fit_all_crystals(li_file)
#%% Example: simulate one crystal’s Jones matrix and intensity curve

# Example parameters from your fit table (Crystal 0)
k      = 0.018804     # rad/step
alpha0 = np.radians(-3.50)
V      = 0.6579
delta  = -0.0704

voltages = np.arange(130)
IH_pred, IV_pred = [], []

for j in voltages:
    Ji = crystal_jones(k, alpha0, V, delta, j)
    Eout = Ji @ np.array([1, 0])    # H input field
    IH_pred.append(np.abs(Eout[0])**2)
    IV_pred.append(np.abs(Eout[1])**2)

import matplotlib.pyplot as plt
plt.figure(figsize=(7,4))
plt.plot(voltages, IH_pred, 'r-', label='I_H predicted')
plt.plot(voltages, IV_pred, 'b-', label='I_V predicted')
plt.xlabel("Voltage index j")
plt.ylabel("Normalized intensity")
plt.legend(); plt.tight_layout()
plt.show()

