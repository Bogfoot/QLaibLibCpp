# QLaibLib
## Quantum Laibach Library (C++/Qt GUI)

A modular toolkit for quTAG-based photon counting with a native C++/Qt GUI: live singles/coincidence plots, configurable pairs, delay histograms, quTAG recording, and BIN replay.

## Features (C++/Qt GUI)

- **Live acquisition**: quTAG backend (polls `TDC_getLastTimestamps`) or BIN replay; mock for offline dev.
- **Configurable pairs**: editable table (labels, chA/chB, delay ps), auto-delay calibration (coincfinder).
- **Histograms**: delay scans per pair with configurable window/range/step.
- **Recording**: start/stop BIN recording from GUI (quTAG) or via `qlaib_record_qudag` CLI.
- **Export**: CSV of all time-series; settings persisted to config.
- **Headless-friendly**: `QLAIB_HEADLESS=1` forces offscreen Qt.

## Installation

Installation requirements:

- CMake ≥3.22, Ninja or your chosen generator
- C++20 compiler (MSVC 2022, clang, or gcc)
- Qt6 (Core, Widgets, Charts)
- coincfinder sources (bundled in `coincfinder/` and built as part of GUI)



### C++/Qt GUI build

#### Linux (Qt from distro)
Dependencies: Qt6 (Qt6Core/Widgets/Charts), CMake ≥3.22, C++20 compiler.

```bash
# build coincfinder core
cmake -S coincfinder -B coincfinder/build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build coincfinder/build

# build GUI
cmake -S cpp -B cpp/build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DQQL_BUILD_GUI=ON -DQQL_ENABLE_CHARTS=ON -DQQL_ENABLE_QUTAG=ON \
  -DCMAKE_PREFIX_PATH=/usr/lib/x86_64-linux-gnu/cmake/Qt6 \
  -DCOINCFINDER_CORE=$(pwd)/coincfinder/build/libcoincfinder_core.a
cmake --build cpp/build

# run
./cpp/build/apps/qlaib_gui --mode=mock
```

#### Windows (MSVC, no vcpkg)
Prereqs: Qt official install (MSVC 64-bit + Qt Charts), Visual Studio 2022 (or Build Tools), CMake ≥3.22, coincfinder built with MSVC, quTAG SDK DLLs (`DLL_64bit/`).

1) Install Qt (e.g., `C:/Qt/6.10.1/msvc2022_64`) with MSVC 64-bit and Qt Charts.
2) Build coincfinder (Release):
```cmd
cmake -S coincfinder -B coincfinder/build -G "Ninja" -DCMAKE_BUILD_TYPE=Release
cmake --build coincfinder/build
```
3) Build GUI (Release):
```cmd
cmake -S cpp -B cpp/build -G "Ninja" -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_PREFIX_PATH="C:/Qt/6.10.1/msvc2022_64/lib/cmake" ^
  -DQQL_BUILD_GUI=ON -DQQL_ENABLE_CHARTS=ON -DQQL_ENABLE_QUTAG=ON ^
  -DCOINCFINDER_CORE="C:/Users/LjubljanaLab/Desktop/QLaibLibCpp/coincfinder/build/coincfinder_core.lib" ^
  -DTDCBASE_LIB="C:/Users/LjubljanaLab/Desktop/QLaibLibCpp/DLL_64bit/tdcbase.lib"
cmake --build cpp/build
```
4) Deploy Qt next to the exe:
```cmd
"C:/Qt/6.10.1/msvc2022_64/bin/windeployqt.exe" --release --compiler-runtime ^
  C:/Users/LjubljanaLab/Desktop/QLaibLibCpp/cpp/build/apps/qlaib_gui.exe
copy /Y C:/Users/LjubljanaLab/Desktop/QLaibLibCpp/DLL_64bit/*.dll ^
  C:/Users/LjubljanaLab/Desktop/QLaibLibCpp/cpp/build/apps/
```
5) Run:
```cmd
set QT_QPA_PLATFORM=windows
set QT_QPA_PLATFORM_PLUGIN_PATH=C:/Users/LjubljanaLab/Desktop/QLaibLibCpp/cpp/build/apps/platforms
C:/Users/LjubljanaLab/Desktop/QLaibLibCpp/cpp/build/apps/qlaib_gui.exe --mode=mock
```

#### quTAG SDK on Windows
- Use the vendor DLLs in `DLL_64bit/` (`tdcbase.dll`, `tdcbase.lib`, plus `libusb0.dll`, `libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll`).
- Point CMake to the import lib: `-DTDCBASE_LIB=.../DLL_64bit/tdcbase.lib`.
- Ensure `tdcbase.dll` and deps are beside the exe (copy `DLL_64bit/*.dll` into `cpp/build/apps/`).

## License
MIT — see `LICENSE` for details. Copyright (c) 2025 Adrian Udovičić, PhD student in physics at University of Ljubljana, Faculty of Mathematics and Physics.
