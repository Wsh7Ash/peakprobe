# Results — peakprobe

## Environment
- OS: Windows (MSYS2/Git Bash)
- Runtime: Python 3.14.3
- Dependency manager: pip (stdlib-only runtime)
- Test runner: pytest 9.1.1

## Validation performed
- install: PASS (`PYTHONPATH=src python -c "import peakprobe, peakprobe.cli"`)
- build: PASS (no build step; CLI runs from source)
- unit tests: PASS (26 passed)
- integration tests: PASS (`demo` and `run` execute scripts and emit phase reports)
- lint: N/A (no linter configured for this stdlib-only project)
- type check: N/A (no type checker in scope for this run)
- demo run: PASS (3 checkpoints, 36.8 MiB peak, 34.6 MiB retained on this interpreter)
- budget gate: PASS (`--fail-peak 1B` and `--fail-retained 1B` exit 1; generous limits exit 0)

## Commands executed
```shell
cd projects/2026-11-17/peakprobe
PYTHONPATH=src python -m pytest tests/ -v
PYTHONPATH=src python -m peakprobe demo
PYTHONPATH=src python -m peakprobe run examples/report_pipeline.py
```

## Observed result

`peakprobe demo` (`results/demo.txt`):

```text
peakprobe: demo-pipeline (3 checkpoint(s))
total peak 36.8 MiB, retained 34.6 MiB

phase               time        peak    retained  top site
build rows        697.7ms    29.3 MiB    29.3 MiB  <demo>:6 (+29.3 MiB)
index rows         11.7ms     7.5 MiB     5.0 MiB  <demo>:9 (+5.0 MiB)
render export     190.6ms     2.4 MiB   226.7 KiB  <demo>:12 (+223.6 KiB)

allocation sites by phase
  build rows
    + 29.3 MiB  <demo>:6                                 479473 allocation(s)
  index rows
    +  5.0 MiB  <demo>:9                                 3 allocation(s)
  render export
    +223.6 KiB  <demo>:12                                1 allocation(s)
```

The largest phase (`build rows`) is correctly attributed to the list comprehension on the script's line 6, and the index phase to the dict comprehension on line 9. Exact byte values and timings vary between runs; the phase ordering and the dominant site do not.

Budget behaviour observed in the test suite: `--fail-peak 1B` and `--fail-retained 1B` return exit code 1 with a stderr message, while `--fail-peak 1GiB` returns 0.

## Generated artifacts
- `results/demo.txt`
- `results/validation.log` (captured pytest run)

## Known limitations
- Only allocations visible to CPython's tracemalloc allocator are measured; native buffers may be invisible.
- Snapshots are process-wide; `include` filters attribution, not totals.
- Snapshotting is expensive, so the test suite takes about 40 seconds.
- Attribution uses three frames and is not thread-aware.
