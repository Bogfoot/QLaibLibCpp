# Repository Guidelines

## Project Structure & Module Organization
- Core package lives in `qlaiblib/` with submodules: `acquisition/` (hardware + mock backends), `coincidence/` (delay scan + pipeline), `metrics/`, `plotting/`, `live/` (Tk dashboard), `io/` (compiled `coincfinder` bridge), and `utils/`.
- CLI entry point `qlaiblib/cli.py` backs the `qlaib` command (`count`, `coincide`, `live`).
- Examples for scripting are under `examples/`; high-level design notes sit in `docs/ARCHITECTURE.md`.
- C++ artifacts (`coincfinder` shared lib) are built automatically during Python builds; legacy lab scripts remain at the repo root for reference only.

## Build, Test, and Development Commands
- `python -m pip install -e .[dev]` — editable install with dev tools (ruff, pytest).
- `python -m build` — produce wheels/sdist in `dist/` (auto-compiles `coincfinder` via scikit-build-core).
- `pytest` — run the test suite (add tests in `tests/`).
- `qlaib count --help` / `qlaib live --mock` — quick sanity checks without hardware.

## Coding Style & Naming Conventions
- Prefer PEP 8: 4-space indent, snake_case for modules/functions, PascalCase for classes.
- Use type hints; keep functions small and side-effect free where possible.
- Run `ruff check .` before publishing; adopt its autofixes for imports/formatting.
- Keep public APIs documented with concise docstrings; surface new flags through `cli.py` with descriptive `--long-option` names.

## Testing Guidelines
- Use `pytest` with readable names like `test_calibrate_delays_handles_negative_offsets`.
- When touching acquisition or pipeline code, add deterministic tests that exercise mock backends (no hardware dependency).
- For visualization helpers, assert on data arrays/metadata rather than figure pixels.
- Aim for coverage on new logic; record flaky-hardware tests with `@pytest.mark.slow` and keep default runs hardware-free.

## Commit & Pull Request Guidelines
- Commits: short, imperative mood (e.g., `add mock backend delay jitter test`); bundle logically related changes.
- PRs: include scope/intent, test evidence (`pytest` logs or screenshots for UI changes), and note hardware requirements or data files used.
- Link issues when applicable; flag breaking changes in the description and update README/ARCHITECTURE when APIs move.

## Security & Configuration Tips
- QuTAG drivers and `libtdcbase.so` must be present on lab machines; avoid committing vendor binaries beyond what is already tracked.
- Keep BIN/CSV captures with participant data out of the repo; use `Data/sample_capture.bin`-style sanitized files for demos.
- If adding new hardware backends, isolate credentials/addresses via environment variables rather than hard-coding paths.
