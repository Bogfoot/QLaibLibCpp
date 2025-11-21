import os, math, time

class PolarizationDevice:
    """Explicit-address EPC control — using either serial number or index."""

    def __init__(self, device_ref):
        if isinstance(device_ref, str) and len(device_ref) > 1:
            self.connection_arg = f"-connectS={device_ref}"  # Serial number
        elif device_ref in [0, 1]:
            self.connection_arg = f"-connectI={device_ref}"  # Index
        else:
            raise ValueError("Invalid device reference. Provide serial number or index 0/1.")

    def _spi(self, payload: str):
        cmd = (
            f"MCP2210CLI.exe {self.connection_arg} "
            f"-spitxfer={payload} -bd=100000 -cs=gp4 -md=1"
        )
    
        # Mute all command-line output
        if os.name == "nt":
            cmd += " >NUL 2>&1"
        else:
            cmd += " >/dev/null 2>&1"
    
        os.system(cmd)
        time.sleep(0.001)

    def set_voltage(self, channel: str, V_out: float):
        V_out = float(V_out)
        dac_code = round(V_out * 4095 / (5.088 * 25.877))
        dac_code_hex = f"{dac_code:03x}"
        dac_num = f"{8 + int(channel[3]):x}"
        payload = f"{dac_num}{dac_code_hex[0]},{dac_code_hex[1:]}"
        self._spi(payload)

    def set_temperature(self, T_th: float):
        R_th0 = 10e3
        Beta = 3950.0
        TempK = 273.0 + float(T_th)
        T0 = 298.0
        V_th = 5.088 * (R_th0 * math.exp(Beta * (1/TempK - 1/T0))) / (
            10e3 + R_th0 * math.exp(Beta * (1/TempK - 1/T0))
        )
        V_dac = (V_th - 0.632) / 0.584
        dac_code = round(V_dac * 4095 / 5.088)
        dac_code_hex = f"{dac_code:03x}"
        payload = f"E{dac_code_hex[0]},{dac_code_hex[1:]}"
        self._spi(payload)
