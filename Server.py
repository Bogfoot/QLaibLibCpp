# Hello world for sockets
import socket

HOST = '100.97.8.91'   # Listen on all interfaces
PORT = 5000        # Choose any free port

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.bind((HOST, PORT))
    s.listen(1)
    print(f"Server listening on {HOST}:{PORT}")
    conn, addr = s.accept()
    with conn:
        print(f"Connected by {addr}")
        data = conn.recv(1024)
        if data:
            print("Received from client:", data.decode())
            conn.sendall(b"Hello from server!")


#%%
# Client code for the temperature scans
import socket, os, time
dirname = os.path.dirname(__file__)
os.chdir(dirname)

import QuTAG_MC as qt



tt = qt.QuTAG()
integration_time = 1
# tt.startCalibration()
time.sleep(1)

channels = [1, 2, 3, 4, 5, 6, 7, 8]
voltages = 1
# voltages = [-0.350,-0.350,-0.350,-0.350]
# voltages = [-0.400,-0.380,-0.370,-0.400]

for ch, volt in zip(channels,voltages):
    print(f"Channel {ch} voltage: {volt}")
    tt.setSignalConditioning(ch, tt.SCOND_MISC, 0, volt)
# timebase = tt.getTimebase()
CoincCounter_names = ['0(Start)','1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16','17','18','19','20','21','22','23','24','25','26','27','28','29','30','31','32','1/2','1/3','2/3','1/4','2/4','3/4','1/5','2/5','3/5','4/5','1/2/3','1/2/4','1/3/4','2/3/4','1/2/5','1/3/5','2/3/5','1/4/5','2/4/5','3/4/5','1/2/3/4','1/2/3/5','1/2/4/5','1/3/4/5','2/3/4/5','1/2/3/4/5']


# print(f"Device timebase is {timebase} s.")
tt.setExposureTime(integration_time * 1000)
start_time = time.perf_counter()
time.sleep(integration_time)
data, _ = tt.getCoincCounters()

print(f"End time 1 = {time.perf_counter() - start_time}.")

# print(f"Lenght of data = {len(data)}.\nLength of names = {len(CoincCounter_names)}.\n")

# Array for 
print("Channel/Coincidence : Counts ")
for i in range(len(CoincCounter_names)):
        print(f"{CoincCounter_names[i]} : {data[i]}")
        if i%8==0:
            print()
tt.deInitialize()
#%% Updated Server code

#Scan configuration
exposure_time_timetagger = 5.0  

def time_tagger_data(tt):
    
    # timebase = tt.getTimebase()
    # print("Device timebase:", timebase, "s")
    expT = int(exposure_time_timetagger * 1000)
    tt.setExposureTime(expT)  # ms Counting

    channel_1 = 1
    channel_2 = 2
    channel_3 = 3
    channel_4 = 4
    
    channels = [channel_1, channel_2, channel_3, channel_4]
            
    coincidences_12 = 33
    coincidences_13 = 34
    coincidences_23 = 35
    coincidences_14 = 36
    coincidences_24 = 37
    coincidences_34 = 38        

    tt.enableChannels(channels)
    time.sleep(exposure_time_timetagger)  # Wait for the exposure time

    data, _ = tt.getCoincCounters()

    result = {
        "Channel_1": data[channel_1],
        "Channel_2": data[channel_2],
        "Channel_3": data[channel_3],
        "Channel_4": data[channel_4],
        "Coincidences_12": data[coincidences_12],
        "Coincidences_13": data[coincidences_13],
        "Coincidences_23": data[coincidences_23],
        "Coincidences_14": data[coincidences_14],
        "Coincidences_24": data[coincidences_24],
        "Coincidences_34": data[coincidences_34],
    }
    
    return result

def time_tagger_data_sleep(tt):
    
    time.sleep(2)
    # timebase = tt.getTimebase()
    # print("Device timebase:", timebase, "s")
    tt.setExposureTime(exposure_time_timetagger * 1000)  # ms Counting

    channel_1 = 1
    channel_2 = 2
    channel_3 = 3
    channel_4 = 4
    
    channels = [channel_1, channel_2, channel_3, channel_4]
            
    coincidences_12 = 33
    coincidences_13 = 34
    coincidences_23 = 35
    coincidences_14 = 36
    coincidences_24 = 37
    coincidences_34 = 38        

    tt.enableChannels(channels)
    time.sleep(exposure_time_timetagger)  # Wait for the exposure time

    data, _ = tt.getCoincCounters()

    result = {
        "Channel_1": data[channel_1],
        "Channel_2": data[channel_2],
        "Channel_3": data[channel_3],
        "Channel_4": data[channel_4],
        "Coincidences_12": data[coincidences_12],
        "Coincidences_13": data[coincidences_13],
        "Coincidences_23": data[coincidences_23],
        "Coincidences_14": data[coincidences_14],
        "Coincidences_24": data[coincidences_24],
        "Coincidences_34": data[coincidences_34],
    }
    
    return result

def gather_data(tt):
    try:
        return time_tagger_data(tt)
    except RuntimeError:
        try:
            return time_tagger_data_sleep(tt)
        except Exception as e:
            print(f"Error during data gathering: {e}")
            return {"Error": str(e)}
    except Exception as e:
        print(f"Error during initial data gathering: {e}")
        return {"Error": str(e)}


def server(tt):
    host = '141.255.216.170'  # Localhost
    port = 65432        # Port to listen on

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        RUN = True
        print('Server is listening...')
        while RUN:
            conn, addr = s.accept()
            with conn:
                print('Connected by', addr)
                conn.settimeout(5)  # Set timeout for the connection (5 seconds)
                
                while True:
                    try:
                        data = conn.recv(1024)
                        if not data:
                            break
                        
                        command = data.decode('utf-8')
                        if command == 'GATHER DATA':
                            result = gather_data(tt)
                            if "Error" in result:
                                response = f"Error: {result['Error']}\nCLOSE OVEN"
                            else:
                                response = (
                                    f"Channel1: {result.get('Channel_1', 'N/A')}, "
                                    f"Channel2: {result.get('Channel_2', 'N/A')}, "
                                    f"Channel3: {result.get('Channel_3', 'N/A')}, "
                                    f"Channel4: {result.get('Channel_4', 'N/A')}, "
                                    f"Coincidences_12: {result.get('Coincidences_12', 'N/A')}, "
                                    f"Coincidences_13: {result.get('Coincidences_13', 'N/A')}, "
                                    f"Coincidences_23: {result.get('Coincidences_23', 'N/A')}, "
                                    f"Coincidences_14: {result.get('Coincidences_14', 'N/A')}, "
                                    f"Coincidences_24: {result.get('Coincidences_24', 'N/A')}, "
                                    f"Coincidences_34: {result.get('Coincidences_34', 'N/A')}"
                                )
                            conn.sendall(response.encode('utf-8'))
                        elif command == 'STOP':
                            RUN = False
                            print("Ending the recording.")
                            response = "Ending recording now."
                            conn.sendall(response.encode('utf-8'))
                            break
                        elif command.startswith("EXPOSURE"):
                            global exposure_time_timetagger
                            exposure_str = command[8:].strip()
                            try:
                                exposure_time_timetagger = float(exposure_str)
                                response = f"Exposure time is {exposure_time_timetagger} s."
                            except ValueError:
                                response("Invalid exposure time value")
                            conn.sendall(response.encode('utf-8'))
                        else:
                            conn.sendall(b'Unknown command')
                    except socket.timeout:
                        print("Timeout occurred, no data received.")
                        break
                    except socket.error as e:
                        print(f"Socket error: {e}")
                        break
                    except KeyboardInterrupt:
                        print("Interrupted")
                        RUN = False
                        print("Ending the recording.")
                        response = "Ending recording now."
                        conn.sendall(response.encode('utf-8'))
                        break
if __name__ == '__main__':
    tt = qt.QuTAG()
    server(tt)
    time.sleep(1)
    tt.deInitialize()
    
