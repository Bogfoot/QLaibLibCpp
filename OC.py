from collections import namedtuple
from datetime import datetime
from time import sleep

import serial
import serial.tools.list_ports


class OC:
    version = 1.0

    def __init__(self, port) -> None:
        self.port_params = namedtuple(
            "port_params",
            ["baud", "data_bits", "stop_bits", "parity", "timeout", "write_timeout"],
        )
        self.OC_description = []
        self.OC_selected = ""
        self.OC = serial.Serial()  # Connection to the OC
        self.port = port
        self.port_params.baud = 19200
        self.port_params.data_bits = serial.EIGHTBITS
        self.port_params.stop_bits = serial.STOPBITS_ONE
        self.port_params.parity = serial.PARITY_EVEN
        self.port_params.timeout = 1
        self.port_params.write_timeout = 1
        self.fault_code = (0, "")
        self.fault_queue = []
        self.buff_length = 1024
        self.local_buffer = bytearray(self.buff_length)
        self.buff_end = 0  # The index of the last useful part of the local_buffer
        self.delimiter = b";"
        self.message_available = False
        self.message = []
        self.message_time = []
        self.requested_temperature = []  # temperatrure [C]
        self.ramp_rate = 50  # Temperature ramp rate in degrees/s. Units ship with a default of 100 C/s
        self.setpoint = (0, "")
        self.temperature = (0, "")
        self.enable_state = []
        self.setup_port()
        success = self.OC_open()
        if success:
            print("OC controller initialised successfully.")
        else:
            print("Error initialising OC controller.")

    def setup_port(self):
        self.OC = serial.Serial()
        self.OC.baudrate = self.port_params.baud
        self.OC.port = self.port
        self.OC.bytesize = self.port_params.data_bits
        self.OC.stopbits = self.port_params.stop_bits
        self.OC.timeout = self.port_params.timeout
        self.OC.write_timeout = self.port_params.write_timeout

    def OC_open(self):
        self.OC.open()

        success = self.get_status()

        return success

    def OC_close(self):
        print("Oven is closing")
        self.OC.close()


    ############## Simple setters and getters

    def set_continuous_output(self):
        cmd = bytes(b"!nxx1;1;\r")  # Set continuous update to oven 1 at 1Hz
        success = self.send_command(cmd)
        return success

    def stop_continuous_output(self):
        cmd = bytes(b"!nxx0;1;\r")  # Stop continuous update to oven 1
        success = self.send_command(cmd)
        return success

    def enable(self):
        # Enables output of the OC to heat the oven.
        cmd = bytes(b"!mxx1;1;\r")
        success = self.send_command(cmd)
        return success

    def disable(self):
        # Enables output of the OC to heat the oven.
        cmd = bytes(b"!mxx0;1;\r")
        success = self.send_command(cmd)
        return success

    def set_temperature(self, temp):
        self.requested_temperature = temp
        str = "!ixx1;%3.3f;100;0;%3.3f;1;0;\r" % (
            self.requested_temperature,
            self.ramp_rate,
        )
        cmd = bytes(str, "utf-8")
        success = self.send_command(cmd)
        return success

    def get_temperature(self):
        self.get_status()
        return self.temperature[0]

    def set_ramp_rate(self, rate):
        # Set the ramp rate, coercing to within 0.01 and 100 C/s
        if rate < 0.01:
            rate = 0.01
            print("Requested rate too low. Value set to 0.01 C/s")
        if rate > 100:
            rate = 100
            print("Requested rate too high. Value set to 100 C/s")

        self.ramp_rate = rate

        controls = (self.requested_temperature, rate)
        str = "!ixx1;%3.3f;100;0;%3.3f;1;0;\r" % controls
        # str = (
        #     f"!ixx1;{round(self.requested_temperature,3)};100;0;{round(rate,3)};1;0;\r"
        # )
        cmd = bytes(str, "utf-8")
        success = self.send_command(cmd)
        return success

    def get_ramp_rate(self):
        return self.ramp_rate

    def get_faults(self):
        self.get_status()
        return self.fault_code[0]

    def get_status(self):
        cmd = bytes(b"!jxx;1;\r")  # Request status of oven 1
        success = self.send_command(cmd)

        # clear the message type for now
        self.msg_type = ""
        t_start = datetime.now()
        timeout = 3
        if success:
            while not self.msg_type == "status":
                # read back response
                while not self.message_available:
                    self.read_available_bytes()

                self.read_message()
                self.parse_message()

                dt = datetime.now() - t_start
                if dt.seconds > timeout:
                    success = False
                    return success

        return success

    def reset_defaults(self):
        # Disable the output
        self.disable()

        # Stop continuous output
        self.stop_continuous_output()

        # Set ramp rate to 100 degrees C/s
        self.set_ramp_rate(100)

        # Set the temperature to 40 C
        self.set_temperature(40)

    ########## Utility functions

    def send_command(self, cmd):
        # Send the message to the OC. In case of error during the write, the
        # method will make three attempts, if needed.
        trying = 0
        while trying < 4:
            try:
                bytes_written = self.OC.write(cmd)

                # The OC requires at least 200 ms between writes. To ensure this always happens
                # a pause is added here
                sleep(0.3)

                if bytes_written == len(cmd):
                    trying = 100  # exit the loop as we do not need to try again
                    return True

            except Exception as e:
                if trying < 3:
                    # ignore for now and allow the loop to try again
                    pass
                else:
                    print("Error writing to the serial port\n")
                    print(e)  # print the exception

        return False

    def bytes_available(self):
        # This is, possibly, redunant, but gives a place to add additional code for checking
        bytes_available = self.OC.in_waiting

        return bytes_available

    def read_available_bytes(self):
        # Check for buffer overrun, clear and shift if needed
        bytes_available = self.bytes_available()

        if bytes_available > 0:
            if bytes_available >= len(self.local_buffer):
                # clear out the old and read in part of the new
                self.local_buffer[:] = self.OC.read(len(self.local_buffer))
                self.buff_end = len(self.local_buffer)

            elif bytes_available > len(self.local_buffer) - self.buff_end:
                # clear enough to grab all the new data
                dif = len(self.local_buffer) - self.buff_end
                self.shift_buffer(dif)
                self.local_buffer[
                    self.buff_end : self.buff_end + bytes_available
                ] = self.OC.read(bytes_available)
                self.buff_end += bytes_available

            else:
                self.local_buffer[
                    self.buff_end : self.buff_end + bytes_available
                ] = self.OC.read(bytes_available)
                self.buff_end += bytes_available

            self.parse_buffer()

    def parse_buffer(self):
        # look for starting with SOH
        # if not, discard start
        if not self.local_buffer.startswith(b"\x01"):
            # look for a SOH character
            pos = self.local_buffer.find(b"\x01")
            if pos < 0:
                # if no SOH, shift out 1 byte
                pos = 1

            self.shift_buffer(pos)

        # Look for a crlf
        n_crlf = self.local_buffer.find(b"\r\n")
        if n_crlf > 0:
            self.message_available = True
            self.message_time = datetime.now()
            # if found, say raise Message_available
        else:
            self.message_available = False

    def shift_buffer(self, shift):
        # clear and shift
        self.local_buffer[:-shift] = self.local_buffer[shift:]
        self.local_buffer[-shift:] = bytearray(shift)
        self.buff_end = self.buff_end - shift
        if self.buff_end < 0:
            self.buff_end = 0

    def read_message(self):
        # Search buffer for the first \r\n
        pos = self.local_buffer.find(b"\r\n")
        self.message = self.local_buffer[: pos + 2]
        # Shift the buffer to remove the message
        self.shift_buffer(pos + 2)

        # reset message_available since we have removed it
        self.message_available = False

        # Clean up the message
        self.message = self.message.removeprefix(b"\x01")
        self.message = self.message.removesuffix(b"\r\n")

        # re-parse the buffer to check it is all ok and set/reset the message available flag
        self.parse_buffer()

    def parse_message(self):
        # Determine the message type
        type_code = self.message.decode("utf-8")[0]

        match type_code:
            case "+":
                self.msg_type = "ack"  # replace all these strings with codes? put ascii back with a getter for when requested?
                matched = True

            case "j":
                self.msg_type = "status"
                self.parse_status_message()
                matched = True

            case other:
                self.msg_type = ""
                matched = False

        return matched

    def parse_status_message(self, msg=""):
        if len(msg) > 0:
            message = msg
        else:
            message = self.message

        # split the message using the delimiter

        parts = message.split(self.delimiter)

        # Check if OC is enabled
        if parts[2] == b"0":
            self.enable_state = False
        elif parts[2] == b"1":
            self.enable_state = True

        # Get setpoint
        self.setpoint = (float(parts[0][3:]), self.message_time)
        # Get actual temperature
        self.temperature = (float(parts[1]), self.message_time)
        # Get state
        self.enable_state = float(parts[2])

        # Check fault status
        self.fault_code = (float(parts[5]), self.message_time)
        if int(parts[5]) != 0:
            self.parse_fault(int(parts[5]))

    def parse_fault(self, fault):
        # Append any faults present to the fault queue

        if fault & 0b1:
            self.fault_queue.append(
                "ADC fault present at "
                + self.message_time.strftime("%b %d %Y %H:%M:%S")
            )
        if fault & 0b01:
            self.fault_queue.append(
                "ADCR fault present at "
                + self.message_time.strftime("%b %d %Y %H:%M:%S")
            )
        if fault & 0b001:
            self.fault_queue.append(
                "VDC limit fault present at "
                + self.message_time.strftime("%b %d %Y %H:%M:%S")
            )
        if fault & 0b0001:
            self.fault_queue.append(
                "Temp fault present at "
                + self.message_time.strftime("%b %d %Y %H:%M:%S")
            )
        if fault & 0b00001:
            self.fault_queue.append(
                "Inhibited fault present at "
                + self.message_time.strftime("%b %d %Y %H:%M:%S")
            )
