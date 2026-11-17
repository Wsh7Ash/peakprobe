# Changelog

## 0.1.0 — 2026-11-17
- Initial release
- `Probe` with checkpoint-based peak, retained and current measurement
- Allocation-site attribution by line, with filtering of probe and tracemalloc frames
- Optional include glob restricting attribution to a source tree
- Module-level default probe (`start`, `checkpoint`, `report`, `stop`, `reset`, `phase`)
- CLI `run` with `--label`, `--top`, `--json`, `--out`, `--fail-peak`, `--fail-retained`
- CLI `demo`
- Human size parsing and rendering (B/KB/KiB/MB/MiB/GB/GiB)
