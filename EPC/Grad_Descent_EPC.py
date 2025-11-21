import os, random, time
import numpy as np
import os, socket
os.chdir("C:\\Users\\LjubljanaLab\\Desktop\\TempScans\\ScanCode\\AEPC\\PC_control_application")
from EPC import *

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
            print(f"Current time is: {time.strftime('%H:%M:%S', time.localtime())}")
            print(f"Temperature: {temp}, Received: {data}")
                    
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
            return int(clicks1), int(clicks4)
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
    I_H = I_H/(I_H + I_V)
    I_V = I_V/(I_H + I_V)
    print(f"I_H = {I_H}, I_V = {I_V}")
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
    t = 0.999
    I_target = np.array([t, 1-t])
    return np.sum((I - I_target)**2)

def compute_gradient(EPC, V):

    """ Compute numerical gradient for each voltage channel. """

    E0 = error_function(measure_intensities())
    grad = np.zeros(4)

    for i in range(4):
        V_test = V.copy()
        V_test[i] += delta_V
        set_voltage(EPC, V_test)
        time.sleep(0.5)
        E_new = error_function(measure_intensities())  # new error
        grad[i] = (E_new - E0) / delta_V  # gradient

    return grad

def update_voltages(EPC):

    """ Gradient descent step. Hopefully. """

    global V # Can be returned by compute_gradient, but eh.
    grad = compute_gradient(EPC, V)
    print(f"Gradient = {grad}")
    V -= alpha * grad
    V = np.clip(V, 0, 130)
    set_voltage(EPC, V)

#%%
s = np.array([1,2])

#%%
# Gotta start somewhere
V = np.array([65, 65, 65, 65], dtype=np.float64)
alpha = 0.5  # "Learning rate"
delta_V = 0.5 # V_step for gradient
temperature = 50 #from 10 to 70degC

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

