import time
import numpy as np
from functions import *

def random_matrix(n):
    m = np.random.rand(1, n)
    m = np.vstack((m, 1 - m))
    for r in m:
        yield (r[0], r[1])

def get_detector_values():

    """ Replace with actual detector readings (Should be normalized to sum 1).
    Usually from the time tagger. """

    # To get different values each time
    # H = random.uniform(0, 1)
    # V = 1 - H
    return random_matrix(200)

def measure_intensities():
    # TODO: replace above values to the corresponding detector values
    I_H, I_V = get_detector_values()  # Read H detector
    return np.array([I_H, I_V])

def set_voltage(V):

    """ Apply voltages to all four DAC channels. Might have to change strategy
    depending on results next week. """

    # TODO: Next aproach would be to selectively probe each crystal
    # individually to see which one has the most "positive" effect towards the
    # target intensity
    pass
def error_function(I):

    """ Define target polarization state (modify as needed). """

    # Example: Correcting polarization to H as there could be a PBS in front of
    # the EPC

    I_target = np.array([1, 0])
    return np.sum((I - I_target)**2)

def compute_gradient(V):

    """ Compute numerical gradient for each voltage channel. """

    E0 = error_function(measure_intensities())
    grad = np.zeros(4)

    for i in range(4):
        V_test = V.copy()
        V_test[i] += delta_V
        set_voltage(V_test)
        time.sleep(0.5)
        E_new = error_function(measure_intensities())  # new error
        grad[i] = (E_new - E0) / delta_V  # gradient

    return grad

def update_voltages():

    """ gradient descent step. Hopefully. """

    global V # Can be returned by compute_gradient, but eh.
    grad = compute_gradient(V)
    print(f"Gradient = {grad}")
    V -= alpha * grad
    V = np.clip(V, 0, 130)
    print(f"Voltage = {V}")
    set_voltage(V)

# Gotta start somewhere
V = np.array([65, 65, 65, 65])
V = V.astype(float)  # Ensure V is a float array
alpha = 0.5  # "Learning rate"
delta_V = 0.5 # V_step for gradient
temperature = 50 #from 10 to 70degC

# Control loop
while True:
    update_voltages()
        # NOTE: Considering on how to make adaptive timing, based on drift amount.
        # Hopefully it's not needed as this would complicate things by an
        # unpleasant amount. This would likely require monitoring inside this loop,
        # possibly with an "if" statement to selectively go into the gradient
        # control loop. The "benefit" may be that changing the voltage often is not
        # good, so reducing the number of changes may increase the lifetime of the EPC.
        # To be determined.
    time.sleep(0.1)

