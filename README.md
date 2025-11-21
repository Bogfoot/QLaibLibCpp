# QLaibLib
## Quantum Laibach Library

A modular toolkit for quTAG-based photon counting. It now has two faces:
- **Python package** (`qlaiblib/`): CLI (`qlaib`) plus plotting/metrics and legacy scripts.
- **Native C++/Qt GUI** (`cpp/`): live singles/coincidence/metrics plots, configurable pairs, delay histograms, quTAG recording, and BIN replay.

## Features (Python)

- **Singles & coincidences** via quTAG or mock backends.
- **Metrics**: visibility, QBER, CHSH (Python side), export-ready.
- **Plotting**: Matplotlib helpers and Tk dashboard.
- **CLI**: `qlaib count|coincide|live|replay`.

## Features (C++/Qt GUI)

- **Live acquisition**: quTAG backend (polls `TDC_getLastTimestamps`) or BIN replay; mock for offline dev.
- **Configurable pairs**: editable table (labels, chA/chB, delay ps), auto-delay calibration (coincfinder).
- **Histograms**: delay scans per pair with configurable window/range/step.
- **Recording**: start/stop BIN recording from GUI (quTAG) or via `qlaib_record_qudag` CLI.
- **Export**: CSV of all time-series; settings persisted to config.
- **Headless-friendly**: `QLAIB_HEADLESS=1` forces offscreen Qt.

## Installation

Installation requirements:

- `cmake>=3.18` and `ninja` (installed automatically by pip if missing, or install
  system packages such as `sudo apt install cmake ninja-build` / Homebrew)
- A C++20 compiler (Visual Studio Build Tools on Windows, `build-essential`/`clang`
  on Linux/macOS)

### C++/Qt GUI build

#### Linux (Ubuntu/Debian example)
Dependencies: Qt6 (`qt6-base-dev`, `qt6-charts-dev`), CMake ≥3.22, C++20 compiler, coincfinder static lib.

```bash
# build coincfinder core
cmake -S coincfinder -B coincfinder/build -G Ninja
cmake --build coincfinder/build

# build GUI
cmake -S cpp -B cpp/build -DQQL_BUILD_GUI=ON -DQQL_ENABLE_CHARTS=ON -DQQL_ENABLE_QUTAG=ON \
      -DCMAKE_PREFIX_PATH=/usr/lib/x86_64-linux-gnu/cmake/Qt6 \
      -DCOINCFINDER_CORE=$(pwd)/coincfinder/build/libcoincfinder_core.a
cmake --build cpp/build

# run
QLAIB_USE_QUTAG=1 ./cpp/build/apps/qlaib_gui           # live hardware
QLAIB_REPLAY_BIN=./capture.bin ./cpp/build/apps/qlaib_gui  # replay BIN
```

#### Windows (MSVC + vcpkg example)
Prereqs: Visual Studio 2022 (or Build Tools), CMake ≥3.22, vcpkg, Qt6 base + charts, coincfinder built with MSVC, quTAG SDK DLLs (`DLL_64bit/`).

```powershell
# Option A: manifest mode (recommended, run in repo root)
vcpkg new --application
vcpkg add port qtbase
vcpkg add port qtcharts
vcpkg install --triplet x64-windows

# Option B: classic install from vcpkg clone
# cd C:\path\to\vcpkg
# .\bootstrap-vcpkg.bat
# .\vcpkg install qtbase qtcharts --triplet x64-windows

# build coincfinder
cmake -S coincfinder -B coincfinder/build -G "Ninja"
cmake --build coincfinder/build

# build GUI
cmake -S cpp -B cpp/build -G "Ninja" `
  -DCMAKE_TOOLCHAIN_FILE=$env:VCPKG_ROOT\scripts\buildsystems\vcpkg.cmake `
  -DQQL_BUILD_GUI=ON -DQQL_ENABLE_CHARTS=ON -DQQL_ENABLE_QUTAG=ON `
  -DCOINCFINDER_CORE=$PWD/coincfinder/build/coincfinder_core.lib `
  -DTDCBASE_LIB=$PWD/DLL_64bit/tdcbase.lib
cmake --build cpp/build

# runtime: ensure DLLs are found
copy DLL_64bit\*.dll cpp\build\apps\
cpp\build\apps\qlaib_gui.exe
```

#### quTAG SDK on Windows
- Use the vendor DLLs in `DLL_64bit/` (or `DLL_32bit/` if you target 32-bit): `tdcbase.dll`, `tdcbase.lib`, plus the dependent `libusb0.dll`, `libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll`.
- Point CMake to the import lib: `-DTDCBASE_LIB=C:/path/to/DLL_64bit/tdcbase.lib`.
- Ensure `tdcbase.dll` and its dependencies are on `PATH` or next to the executable (copy the contents of `DLL_64bit/` into `cpp/build/apps/` after building).

## Usage (C++ GUI)

- **Live (default):** `./cpp/build/apps/qlaib_gui` (tries quTAG; falls back to mock if init fails)
- **Replay BIN:** `./cpp/build/apps/qlaib_gui --mode=replay --replay-bin path/to/file.bin`
- **Mock:** `./cpp/build/apps/qlaib_gui --mode=mock`
- **Headless/offscreen:** add `QLAIB_HEADLESS=1` (useful on SSH/CI).
- **Record BIN (quTAG):** click “Record BIN” in the GUI or run `./cpp/build/apps/qlaib_record_qudag out.bin 1000`.

### GUI controls

- **Pairs table:** edit label/chA/chB/delay; Add/Remove/Reset defaults; “Calibrate selected/all” runs coincfinder delay scan using the Histogram range/step.
- **Histogram tab:** choose pair, set window/start/end/step (ps); click “Histogram” or the toolbar button (auto-switches to the tab).
- **Plots:** tabs for Singles, Coincidences, Metrics; axes auto-extend in time; legend updates when pairs change.
- **Spins:** Exposure (seconds); Coincidence window (ps).
- **Export:** “Export CSV” writes all time-series; settings persist to `~/.config/.../qlaib_gui.json`.

## Hardware requirements

- QuTAG hardware with the `QuTAG_MC` Python bindings installed.
- The C++ `coincfinder` extension (built automatically during `pip install` or
  bundled in prebuilt wheels once published).
- For live plotting, Tkinter must be available (ships with standard Python on
  Windows/macOS/Linux).
