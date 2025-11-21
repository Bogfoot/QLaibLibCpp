import sys
from time import sleep

from OC import OC

oven = OC("COM4")

# temp = 42.95    # 23.01.2025 Lens 300 mm, big coupler
# temp = 42.85    # 24.01.2025
# temp = 42.92    # 21.02.2025
# temp = 43.715     # 05.04.2025 Playing with Sagnac
# temp = 43.98        # 07.04.2025
# temp = 44.724        # 22.05.2025
# temp = 44.3585      # 06.06.2025
# temp = 44.086       # 01.07.2025
temp = 44        # 23.07.2025

oven.enable()
sleep(1)
print(oven.get_temperature())

oven.set_temperature(temp)
while (abs(oven.get_temperature() - temp)) > 0.01:
      try:
          print(oven.get_temperature())
          sleep(5)
      except Exception as e:
          print(f"Something wierd has happened: {e} Aborting and closing the ports.")
          oven.OC_close()

oven.OC_close()