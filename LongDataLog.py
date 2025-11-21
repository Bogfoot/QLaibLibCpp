# Record timestamps
"""
Created on Wed Nov 19 12:31:58 2025

@author: Adrian
"""
import QuTAG_MC as qt
import datetime, os, time

tt = qt.QuTAG()
os.makedirs("Data/RAW/", exist_ok=True)

def record_raw_BIN(tt, exposure_sec):
    t = time.localtime()
    filename = f"Data/RAW/{str(datetime.date.today())}_{time.strftime('%H_%M_%S', t)}_MDP_UVTP_exp_time_s_{exposure_sec}.bin"

    try:
        # Start recording timestamps to BIN file
        tt.writeTimestamps(filename, tt.FILEFORMAT_BINARY)

        # Integration / exposure
        time.sleep(exposure_sec)

        # Stop recording
        tt.writeTimestamps("", tt.FILEFORMAT_NONE)
        print(f"Saved new BIN file: {filename}")
        time.sleep(0.001)
    except Exception as e:
        print(f"Caught {e}")
    return os.path.exists(filename)

# record_raw_BIN(tt, 1) # Test if it works.

for i in range(50):
    record_raw_BIN(tt, 10 * 60)