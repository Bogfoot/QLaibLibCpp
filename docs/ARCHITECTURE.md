# QLaibLib Architecture (C++/Qt)

This snapshot focuses on the native C++/Qt GUI driven by coincfinder and the quTAG SDK. The Python package is intentionally omitted/ignored.

## Layout (cpp/)

```
cpp/
 ├── include/qlaib/
 │     ├── acquisition/      # IBackend + Mock, BinReplay, QuTAG backends
 │     ├── data/             # SampleBatch, coincidence structs
 │     ├── metrics/          # Metric interfaces and registry
 │     └── ui/               # Qt MainWindow
 ├── src/                    # backend + UI implementations
 ├── apps/
 │     ├── qlaib_gui.cpp          # Qt GUI entry (modes: live/replay/mock)
 │     └── qlaib_record_qudag.cpp # headless BIN recorder
 └── CMakeLists.txt               # Qt6, coincfinder, optional quTAG
```

## Dataflow

- **Backends**
  - `MockBackend` — synthetic 8-channel singles/timestamps.
  - `BinReplayBackend` — reads BIN → per-second singles/timestamps.
  - `QuTAGBackend` — polls `TDC_getLastTimestamps`, optional BIN recording via `TDC_writeTimestamps`.
- **Coincidences**: computed in UI with coincfinder (`countCoincidencesWithDelay`, `findBestDelayPicoseconds`).
- **GUI**: Qt Charts tabs (Singles, Coincidences, Metrics, Histogram); configurable pair table; auto-delay calibration; CSV export; BIN record (quTAG only); settings persisted to JSON config.

## Build dependencies
- Qt6 Core/Widgets/Charts
- C++20 compiler
- coincfinder sources (compiled directly if static lib absent)
- quTAG SDK: `libtdcbase` (Linux) or `tdcbase.dll/.lib` plus deps (Windows), gated by `QQL_ENABLE_QUTAG`.

## Runtime
- Headless/offscreen via `QLAIB_HEADLESS=1` (sets `QT_QPA_PLATFORM=offscreen`).
- Backend selection via CLI: `--mode=live|replay|mock` (live default), `--replay-bin <file>` for replay.
