# Contributing

## Setup

```shell
pip install -e ".[dev]"
```

## Running tests

```shell
PYTHONPATH=src python -m pytest tests/ -v
```

The suite takes about 50 seconds because each measured checkpoint takes a real `tracemalloc` snapshot. Do not "fix" that by mocking tracemalloc: the point of the tests is that the numbers react to real allocations.

## Adding a measurement

1. Extend `Phase` (and `Report.to_dict`) in `src/peakprobe/api.py`.
2. Keep `checkpoint()` single-pass: it already pays for one snapshot and one compare.
3. Update `render.py` for text output and the JSON shape in `docs/USAGE.md`.
4. Add an API test with a lower-bound assertion, never an exact byte count.

## Testing rules

- Assert `>=` thresholds, never equality: allocator behaviour differs between interpreters and platforms.
- Always release large fixtures and call `probe.stop()` so tracemalloc is not left running for other tests.
- Prefer `--top 0` in CLI tests that only exercise budgets, labels or files.

## Design rules

- Runtime stays stdlib-only.
- Never attribute `tracemalloc`'s own frames to user code.
- Peak and retained totals are process-wide; only attribution may be filtered.
