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

Clone the repository and install (the build now auto-compiles the C++
`coincfinder` module via [scikit-build-core](https://github.com/scikit-build/scikit-build-core)):

```bash
git clone https://github.com/Bogfoot/QLaibLib.git
cd QLaibLib
python -m venv .venv && source .venv/bin/activate  # optional but recommended
pip install .
```

Installation requirements:

- Python ≥ 3.10
- `cmake>=3.18` and `ninja` (installed automatically by pip if missing, or install
  system packages such as `sudo apt install cmake ninja-build` / Homebrew)
- A C++20 compiler (Visual Studio Build Tools on Windows, `build-essential`/`clang`
  on Linux/macOS)

Once published to PyPI you can simply run `pip install qlaiblib` on any machine
with those prerequisites. For developer builds, `python -m build` produces wheels
in `dist/` that already include the compiled `coincfinder` extension.

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
# assumes $env:VCPKG_ROOT is set
vcpkg install qtbase qtcharts --triplet x64-windows

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

- **Mock mode (default):** `./cpp/build/apps/qlaib_gui`
- **BIN replay:** `QLAIB_REPLAY_BIN=/path/to/file.bin ./cpp/build/apps/qlaib_gui`
- **Live quTAG:** `QLAIB_USE_QUTAG=1 ./cpp/build/apps/qlaib_gui`
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

## CLI usage
### Experimental

```bash
# Count singles for one exposure chunk and plot the bar chart
qlaib count --exposure 1.5 --plot

# Capture coincidences after automatically calibrating delays
qlaib coincide --exposure 0.5 --window-ps 200

# Launch the Tkinter dashboard with 2-second integration
qlaib live --exposure 2.0

# Process an existing BIN file (≈5 s capture) without hardware
qlaib replay Data/sample_capture.bin --window-ps 200 --plot

# Plot singles/coincidences + metric time series from a BIN file (default 1 s chunks)
qlaib replay Data/sample_capture.bin --plot --timeseries

# Skip auto-delay calibration and use DEFAULT_SPECS (lab defaults)
qlaib replay Data/sample_capture.bin --use-default-specs --plot

# Ingest BIN file using the actual exposure time per bucket (e.g., 0.4 s)
qlaib replay Data/sample_capture.bin --bucket-seconds 0.4 --plot --timeseries

# Run the live dashboard in demo mode, replaying a BIN capture instead of hardware
# (press keys 1–6 to switch between singles/coincidences/metrics/CHSH views)
qlaib live --demo-file Data/sample_capture.bin --bucket-seconds 0.4 --history-points 800

# Develop without hardware using the synthetic backend
qlaib live --mock --exposure 0.5
```

To script the same workflows, see:

	- `examples/process_bin_file.py` – load a recorded BIN file, auto-calibrate
	  delays, and print coincidences/metrics.
- `examples/live_qutag.py` – initialize the QuTAG backend, calibrate once, and
  launch the Tk dashboard with all live controls.
- `examples/mock_quickstart.py` – Simulated plotter.
- `examples/bin_custom_specs.py` – calibrate using the first N seconds of a BIN
  file, apply custom coincidence specs (including N-fold), and plot coincidences +
  metrics such as visibility/QBER.
- `examples/bin_default_timeseries.py` – use `DEFAULT_SPECS`, auto-calibrate on
  the first N seconds of a BIN file, and visualize both aggregate metrics and
  per-chunk time series.
- `examples/bin_timeseries_only.py` – plot singles and coincidences as time series
  without extra metrics (useful for quick sanity checks).

## Custom coincidence layouts

Coincidence logic is fully described by `CoincidenceSpec`, so you can define any
channel combinations (2-fold or higher) and plug them into the pipeline:

```python
from qlaiblib import CoincidencePipeline, CoincidenceSpec, DEFAULT_SPECS

specs = DEFAULT_SPECS  # ready-to-use H/V/D/A pairs + GHZ-style triplets
pipeline = CoincidencePipeline(specs)

# or build your own specs ad-hoc
custom_specs = (
    CoincidenceSpec(label="AB", channels=(1, 3), window_ps=250.0, delay_ps=12.5),
    CoincidenceSpec(label="CD", channels=(2, 4), window_ps=250.0, delay_ps=-8.0),
    CoincidenceSpec(label="ABC", channels=(1, 3, 5), window_ps=300.0),
)
custom_pipeline = CoincidencePipeline(custom_specs)
```

- `window_ps` **and** `delay_ps` are specified in **picoseconds**.
- If you still want auto-delay calibration, pass your own `like_pairs` /
  `cross_pairs` into `specs_from_delays(window_ps=..., like_pairs=..., cross_pairs=...)`
  so the generated specs match your detector wiring.
- The CLI and Tk dashboard reflect whatever specs you supply, so custom labels
  automatically appear in plots, filters, and metrics.

- **New installs/lab defaults**: set `DEFAULT_SPECS` in code and wire it directly
  into `CoincidencePipeline` so everyone sees the same definitions.

### Using specs across the APIs

- **CLI**: tweak `qlaiblib/cli.py` where `CoincidencePipeline(specs)` is created
  (e.g., replace `specs = specs_from_delays(...)` with `specs = DEFAULT_SPECS`)
  to hard-code lab defaults when you don’t need auto-delay scans.
- **Live dashboard**:
  ```python
  from qlaiblib import LiveAcquisition, MockBackend, CoincidencePipeline, DEFAULT_SPECS, run_dashboard
  backend = MockBackend(exposure_sec=1.0)
  pipeline = CoincidencePipeline(DEFAULT_SPECS)
  controller = LiveAcquisition(backend, pipeline)
  run_dashboard(controller)
  ```
- **Offline scripts** (BIN replay, notebooks): pass `DEFAULT_SPECS` into the
  pipeline exactly as shown above, or mix in your own N-fold coincidences.

## Python API glimpse

```python
from qlaiblib import (
    QuTAGBackend,
    CoincidencePipeline,
    auto_calibrate_delays,
    specs_from_delays,
    LiveAcquisition,
    run_dashboard,
)

backend = QuTAGBackend(exposure_sec=1.0)
batch = backend.capture()
cal_delays = auto_calibrate_delays(batch, window_ps=200, delay_start_ps=-8000,
                                  delay_end_ps=8000, delay_step_ps=50)
specs = specs_from_delays(window_ps=200, delays_ps=cal_delays)
pipeline = CoincidencePipeline(specs)
controller = LiveAcquisition(backend, pipeline)
run_dashboard(controller)
```

## Legacy scripts

The original helper scripts remain untouched for reference (`Print_Counts_and_Stats.py`,
`Stability_Check_and_Record.py`, etc.), but new development should happen
through the packaged interfaces above. They can be distributed upon reasonable request.
