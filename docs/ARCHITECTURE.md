# QLaibLib Architecture

QLaibLib now has two layers:
- **Python package**: CLI, metrics, plotting, Tk dashboard.
- **C++/Qt GUI**: native live dashboard with quTAG/BIN backends and coincfinder-based processing.

## Python package layout

```
qlaiblib/
├── __init__.py
├── acquisition/
│   ├── __init__.py
│   ├── base.py             # Abstract interfaces for time-tagger controllers
│   ├── qutag.py            # High-level QuTAG implementation using QuTAG_MC
│   └── mock.py             # Offline/simulated acquisition source for testing
├── coincidence/
│   ├── __init__.py
│   ├── delays.py           # Delay calibration helpers (auto-scan, caching)
│   └── pipeline.py         # Orchestrates singles → coincidences computations
├── data/
│   ├── __init__.py
│   └── models.py           # Dataclasses for singles, coincidences, metrics
├── io/
│   ├── __init__.py
│   └── coincfinder_backend.py   # Thin wrapper over the compiled coincfinder module
├── live/
│   ├── __init__.py
│   ├── controller.py       # Measurement loop with configurable exposure time
│   └── tk_dashboard.py     # Tkinter GUI that consumes the live controller
├── metrics/
│   ├── __init__.py
│   ├── core.py             # Metric base classes / registry
│   ├── qber.py             # QBER metrics (HV, DA, aggregate)
│   └── visibility.py       # Visibility/SNR style observables
├── plotting/
│   ├── __init__.py
│   └── static.py           # Matplotlib helpers for singles/coincidences
├── utils/
│   ├── __init__.py
│   └── timing.py           # Convenience wrappers for timestamps/durations
└── cli.py                  # Typer-based entry points (count, coincide, live)

## C++ layer (cpp/)

```
cpp/
 ├── include/qlaib/
 │     ├── acquisition/      # IBackend + Mock, BinReplay, QuTAG backends
 │     ├── data/             # SampleBatch, coincidence structs
 │     ├── metrics/          # Metric interfaces and registry
 │     └── ui/               # Qt MainWindow
 ├── src/                    # backend + UI implementations
 ├── apps/
 │     ├── qlaib_gui.cpp     # Qt GUI entry
 │     └── qlaib_record_qudag.cpp # headless BIN recorder
 └── CMakeLists.txt          # CMake build (Qt6, coincfinder, optional quTAG)
```

### C++ dataflow

- **Backends**: `MockBackend` (synthetic 8ch), `BinReplayBackend` (BIN → singles/timestamps), `QuTAGBackend` (polls `TDC_getLastTimestamps`, can record BIN via `TDC_writeTimestamps`).
- **Coincidences**: computed in UI using coincfinder (`countCoincidencesWithDelay`, `findBestDelayPicoseconds`).
- **GUI**: Qt Charts tabs for Singles, Coincidences, Metrics, Histogram; configurable pairs table; auto-delay calibration; CSV export; BIN record (quTAG only). Settings persisted to JSON config.

### Notes
- Build depends on Qt6 Core/Widgets/Charts and `coincfinder` static lib. QuTAG support links `libtdcbase` and is toggled with `QQL_ENABLE_QUTAG`.
- Offscreen/headless supported via `QLAIB_HEADLESS=1` (sets `QT_QPA_PLATFORM=offscreen`).
```

## Design goals

1. **Hardware agnostic acquisition:** The `AcquisitionBackend` protocol defines
   the interaction with a time-tagger. The QuTAG backend wraps the provided
   `QuTAG_MC` library, while `MockBackend` can replay BIN/CSV files for tests.
2. **Deterministic coincidence pipeline:** `coincidence.pipeline` centralizes
   flattening, delay matching, and coincidence counting via `coincfinder`.
3. **Extensible metrics:** `metrics.core.Metric` exposes a common interface;
   QBER, visibility, and SNR plug into a registry to drive reports and live plots.
4. **Plot-first UX:** `plotting.static` gives thin wrappers returning Matplotlib
   axes so notebooks/scripts can compose figures without boilerplate; the Tkinter
   dashboard uses the same primitives for consistency.
5. **Live loop separation:** `live.controller.LiveAcquisition` handles the async
   measurement loop, while `live.tk_dashboard.DashboardApp` focuses purely on UI.
6. **Packaging:** `pyproject.toml` + CLI commands surface the functionality as
   `qlaib count`, `qlaib coincide`, `qlaib live`, etc., making it pip-installable.

This file should be kept up to date as the library evolves.
