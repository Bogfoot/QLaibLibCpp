import os, random, time, socket, datetime
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

os.chdir("C:\\Users\\LjubljanaLab\\Desktop\\TempScans\\ScanCode\\AEPC\\PC_control_application")
from EPC import PolarizationDevice


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
            data = s.recv(1024).decode("utf-8")
                    
            # Check if the received data is an error message or a close oven message
            if "Error" in data:
                print(f"Error received from server: {data}")
                    
            # Parse the received data
            parts = data.split(", ")
            clicks1 = parts[0].split(": ")[1]
            clicks2 = parts[1].split(": ")[1]
            clicks3 = parts[2].split(": ")[1]
            clicks4 = parts[3].split(": ")[1]
            coincidences12 = parts[4].split(": ")[1]
            coincidences13 = parts[5].split(": ")[1]
            coincidences23 = parts[6].split(": ")[1]
            coincidences14 = parts[7].split(": ")[1]
            coincidences24 = parts[8].split(": ")[1]
            coincidences34 = parts[9].split(": ")[1]
            return int(clicks3), int(clicks4)
    except Exception as e:
        print(f"Exception caught:\n{e}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((host, port))
            s.sendall(b"STOP")
            data = s.recv(1024).decode("utf-8")
            print(f"Received: {data}")
            

def measure_intensities():
    # TODO: replace above values to the corresponding detector values
    hn, port, expT = '141.255.216.110', 65432, 1    # The port used by the server
    I_H, I_V = get_detector_values(hn, port, expT)  # Read H1, V1 detector
    print(f"I_H = {I_H}, I_V = {I_V}")
    total = I_H + I_V
    if total == 0:
        return np.array([0,0]) # Catch invalid
    I_H = I_H/total
    I_V = I_V/total
    return np.array([I_H, I_V])

def set_voltage(EPC, V):

    """ Apply voltages to all four DAC channels. Might have to change strategy
    depending on results next week. """

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
    t = 0.99999999
    I_target = np.array([t, 1-t])
    return np.sum((I - I_target)**2)

def compute_gradient(EPC, V):

    """ Compute numerical gradient for each voltage channel. """

    E0 = error_function(measure_intensities())
    grad = np.zeros(4)

    for i in range(4):
        V_test = V.copy()
        V_test[i] += delta_V
        os.system("mcp2210cli -spitxfer=28,4f -bd=100000, -cs=gp4 -md=1")
        set_voltage(EPC, V_test)
        time.sleep(0.5)
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
        
    f = open(data_file_name, 'a')
    f.write("\n")
    f.close()
    return grad

def adam_optimizer(V, grad, m, v, t, beta1=0.2, beta2=0.999, epsilon=1e-8, alpha=0.001):
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
    

def update_voltages(EPC):

    """ Gradient descent step. Hopefully. """

    global V, alpha, m, v, t
    grad = compute_gradient(EPC, V)
    # Adam optimizer
    t += 1
    # V, m, v = adam_optimizer(V, grad, m, v, t, alpha=alpha)
    # Regular Gradient
    # grad_M = np.linalg.norm(grad)
    # if grad_M > 1:
    #     alpha = min(0.1, alpha * 1.05)
    # else:
    #     alpha = max(0.001, alpha * 0.9)
    # print(f"Alpha = {alpha}")
    beta = 0.9
    m = beta * + (1 - beta) * grad
    V -= alpha * grad
    V = np.clip(V, 0, 130)
    print(f"Voltages = {V}")
    os.system("mcp2210cli -spitxfer=28,4f -bd=100000, -cs=gp4 -md=1")
    set_voltage(EPC, V)

# Gotta start somewhere
V = np.array([65, 65, 65, 65], dtype=np.float64)
alpha = 50  # "Learning rate"
delta_V = 0.5 # V_step for gradient
temperature = 50 #from 10 to 70degC

# Adam optimizer params
m = np.zeros(4)
v = np.zeros(4)
t = 0

# New data folder
folder_path = os.path.join("..", "..", "Data", "EPC")
if not os.path.exists(folder_path):
    os.makedirs(folder_path)

tl = time.localtime()
data_file_name = os.path.join("..", "..", "Data", "EPC" ,"alpha_" + str(alpha) +  "_delta_V_" + str(delta_V) + "_Errors" + str(datetime.date.today())+ time.strftime("%H_%M_%S", tl) + ".data")

print(f"File name of new data is: {data_file_name}")
f = open(data_file_name, "a")
f.write("# err1,err2,err3,err4\n")
f.close()
# EPC init
print("configure DAC6, DAC3-DAC0")
# NOTE: How to control multiple of these EPCS at the
# same time?
os.system("mcp2210cli -spitxfer=28,4f -bd=100000, -cs=gp4 -md=1")
EPC_1 = PolarizationDevice("0000872235")
# EPC_2 = PolarizationDevice("0001005125")
EPC_1.set_temperature(temperature)

# Control loop
while True:
    update_voltages(EPC_1)
        # NOTE: Considering on how to make adaptive timing, based on drift amount.
        # Hopefully it's not needed as this would complicate things by an
        # unpleasant amount. This would likely require monitoring inside this loop,
        # possibly with an "if" statement to selectively go into the gradient
        # control loop. The "benefit" may be that changing the voltage often is not
        # good, so reducing the number of changes may increase the lifetime of the EPC.
        # To be determined.
    time.sleep(1)

#%%
csv_files = [f for f in os.listdir(folder_path) if f.endswith('.data')]

df = pd.read_csv(data_file_name, skiprows=1, names=["err1","err2","err3","err4"])

if {'err1', "err2" ,"err3", "err4"}.issubset(df.columns):
    plt.figure(figsize=(10,6))
    arr = np.linspace(1, len(df["err1"]) + 1, len(df['err1']))
    plt.plot(arr, df['err1'], label='err1')
    plt.plot(arr, df['err2'], label='err2')
    plt.plot(arr, df['err3'], label='err3')
    plt.plot(arr, df['err4'], label='err4')
    
    plt.xlabel("Index/4s")
    plt.ylabel("Error Values")
    plt.yscale('log')
    plt.title("Error data")
    plt.grid(True)
    plt.legend()
    plt.show()
else:
    print("Error in columns")













