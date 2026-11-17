# peakprobe

## Attribute Python peak and retained memory to named checkpoints

`tracemalloc` can tell you the total peak of a process, and a profiler can tell you where time went, but neither answers "which phase of my pipeline is holding 300 MB". **peakprobe** records a snapshot at every explicit checkpoint and reports, per phase, the peak reached, the memory retained at the end of the phase, and the allocation sites that grew.

- **Problem:** memory debugging is either a whole-process number or a heap dump you have to read by hand.
- **Solution:** four lines of instrumentation and a phase table built on `tracemalloc`.
- **Audience:** Python developers investigating a batch job, ETL step, API warm-up or report generator.

## Quick start

```shell
pip install -e .

# run a script that calls peakprobe.start() / checkpoint()
peakprobe run examples/report_pipeline.py

# gate a pipeline: fail if the run retains more than 64 MiB
peakprobe run examples/report_pipeline.py --fail-retained 64MiB

# see the bundled demonstration
peakprobe demo
```

Instrumentation is optional:

```python
from peakprobe import Probe

with Probe("load") as probe:
    with probe.phase("parse"):
        rows = parse(path)
    with probe.phase("index"):
        index = build_index(rows)
print(probe.report().phases)
```

## Observed output

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

Measurements vary by interpreter and platform; the phase shape and the largest site are stable.

## How it works

1. `start()` starts `tracemalloc` with a three-frame trace and records a baseline snapshot.
2. Each `checkpoint(name)` takes the current traced memory and a snapshot, diffs it against the previous snapshot by allocation line, and resets the tracemalloc peak.
3. `peak_bytes` for a phase is the peak since the previous checkpoint; `retained_bytes` is the change in current traced memory.
4. `stop()` stops tracemalloc if peakprobe started it, and freezes the report.

Measurement frames (peakprobe itself and `tracemalloc`'s own bookkeeping) are filtered out of the site list. With `run`, attribution is further restricted to the script's directory so a large host process does not pollute the report.

## Features

- per-phase peak, retained growth, current total and duration;
- top allocation sites per phase, with byte delta and allocation count;
- API (`Probe`, `peakprobe.start/checkpoint/report`) and CLI (`run`, `demo`);
- `--json`, `--out` and human size budgets (`--fail-peak 64MiB`, `--fail-retained 512MB`);
- `--top 0` for totals-only runs, which skips snapshots entirely;
- no third-party dependencies.

## Requirements

- Python 3.12+
- Anything `tracemalloc` can see: pure-Python allocations and CPython object memory. NumPy buffers are visible only if allocated through tracked Python allocators.

## Installation

```shell
git clone https://github.com/Wsh7Ash/peakprobe
cd peakprobe
pip install -e ".[dev]"
```

## Usage

```shell
peakprobe run SCRIPT [--label NAME] [--top N] [--json] [--out FILE]
                     [--fail-peak SIZE] [--fail-retained SIZE]
peakprobe demo [--json]
```

Inside the script:

```python
import peakprobe

peakprobe.start("pipeline")       # optional: the CLI starts the probe for you
rows = build_rows()
peakprobe.checkpoint("build rows")
peakprobe.checkpoint("index")
report = peakprobe.report()       # Report(phases=..., total_peak_bytes=...)
```

Sizes can be written as plain bytes or with `KB/KiB/MB/MiB/GB/GiB` suffixes. `MB` is decimal, `MiB` is binary.

Exit codes: `0` within budget, `1` budget exceeded or the script raised, `2` bad argument or missing file.

## Configuration

No config file. `Probe(label, top, include)` is the API surface:

- `label` names the report;
- `top` is the number of allocation sites per phase (`0` disables snapshots);
- `include` is an optional glob restricting which files are attributed.

## Testing

```shell
PYTHONPATH=src python -m pytest tests/ -v
```

26 tests cover phase measurement, retained growth, site attribution, context managers, totals-only mode, size parsing/rendering, JSON output, budgets and script failures. `results/validation.log` holds the captured run. The suite takes ~40 s because every measured checkpoint takes a real `tracemalloc` snapshot of the pytest process.

## Project structure

```text
peakprobe/
├─ src/peakprobe/{api,render,cli}.py
├─ tests/{test_api,test_render,test_cli}.py
├─ examples/report_pipeline.py
├─ docs/{ARCHITECTURE,USAGE,PROJECT_SPEC}.md
├─ results/{demo.txt,validation.log}
├─ RESULTS.md
└─ .github/workflows/ci.yml
```

## Limitations

- `tracemalloc` sees CPython allocations, not native extensions that bypass the Python allocator (some NumPy/pandas buffers, C libraries, mmap).
- Snapshots are process-wide; `include` filters attribution only, not the peak/retained totals.
- Taking a snapshot is expensive: keep checkpoints coarse (phases, not loops).
- Peak is measured since the previous checkpoint, so code that frees and reallocates within a phase reports the peak, not the sum.
- Attribution uses up to three frames; deeply wrapped allocations may point at the wrapper.
- Not thread-aware: allocations from other threads during a phase are included.

## Roadmap

- A `peakprobe compare` command that diffs two JSON reports by phase.
- Optional RSS sampling for native memory beside the traced numbers.
- A `pytest` fixture that fails a test when a phase exceeds a byte budget.

## Security note

The tool runs the script you name, in-process, exactly as `python script.py` would. Only point it at code you would run anyway.

## License

MIT — see `LICENSE`.
