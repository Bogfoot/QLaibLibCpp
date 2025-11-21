# QLaibLib Usage (C++ Qt GUI)

## Run modes
- Live (default): `./cpp/build/apps/qlaib_gui` (tries quTAG, falls back to mock)
- BIN replay: `./cpp/build/apps/qlaib_gui --mode=replay --replay-bin /path/to/file.bin`
- Mock: `./cpp/build/apps/qlaib_gui --mode=mock`
- Headless: add `QLAIB_HEADLESS=1` (forces Qt offscreen if no display).
- Record BIN (quTAG): `./cpp/build/apps/qlaib_record_qudag out.bin 1000` or the “Record BIN” button.

## Controls
- **Start/Stop:** begin/stop acquisition.
- **Exposure (s):** sets quTAG exposure / mock cadence.
- **Coinc window (ps):** coincidence window used for all pairs.

### Pairs
- Table columns: Label, chA, chB, Delay (ps).
- Buttons: Add, Remove selected, Reset defaults, Calibrate selected/all.
- Edits apply immediately and persist to `~/.config/.../qlaib_gui.json`.

### Histogram
- Select a pair, set Window/Start/End/Step (ps), click “Histogram” (switches to tab).
- Uses coincfinder `computeCoincidencesForRange` on latest batch timestamps.

### Plots
- Tabs: Singles, Coincidences, Metrics, Histogram.
- Time axes grow from t=0; traces are not pruned.
- Legends update when pairs change; stale series are removed.

### Export
- “Export CSV” writes all visible time-series (singles, coincidences, metrics).
- Settings (pairs, coincidence window) persist between runs.

## Env vars
- `QLAIB_HEADLESS=1` – offscreen Qt platform (no X/Wayland).

## Windows notes
- Install Qt6 + Charts (e.g., vcpkg `qtbase qtcharts`) in your own vcpkg clone (not the embedded VS copy).
- Build coincfinder: `cmake -S coincfinder -B coincfinder/build && cmake --build coincfinder/build`.
- Configure with `-DCOINCFINDER_CORE=path\to\coincfinder_core.lib -DTDCBASE_LIB=path\to\tdcbase.lib`.
- QuTAG SDK: use `DLL_64bit/tdcbase.lib` for linking; copy `DLL_64bit/tdcbase.dll` and its deps (`libusb0.dll`, `libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll`) into the run folder or add that directory to `PATH` before launching the GUI.
- If vcpkg is manifest-only, create a manifest in repo root: `vcpkg new --application`, `vcpkg add port qtbase`, `vcpkg add port qtcharts`, then `vcpkg install --triplet x64-windows`. Otherwise run installs from your vcpkg clone after `bootstrap-vcpkg.bat`.
- PowerShell use with a vcpkg clone at `C:\Users\you\vcpkg`:
  ```powershell
  $env:VCPKG_ROOT = "C:\Users\you\vcpkg"
  & "$env:VCPKG_ROOT\vcpkg.exe" install qtbase qtcharts --triplet x64-windows
  ```
- vcpkg may pull ~20–30 dependencies for Qt. To speed up, enable binary caching (`set VCPKG_FEATURE_FLAGS=manifests,binarycaching`) or install Qt via the official Qt online installer (select Qt 6.x MSVC 64-bit + Charts) and set `-DCMAKE_PREFIX_PATH="C:/Qt/6.x/msvc2019_64/lib/cmake"` in CMake. With vcpkg, point CMake at `installed\x64-windows\share\Qt6` or set `Qt6_DIR=...\share\Qt6\cmake`; ensure a space between CMake args on Windows.
