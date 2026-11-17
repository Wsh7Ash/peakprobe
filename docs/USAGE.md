# Usage — peakprobe

## Instrument a script

```python
import peakprobe

peakprobe.start("pipeline")      # optional under `peakprobe run`

rows = build_rows(source)
peakprobe.checkpoint("build rows")

index = build_index(rows)
peakprobe.checkpoint("index")

peakprobe.checkpoint("done")
```

The CLI starts and stops the default probe, so `start()` and `stop()` are only needed when running the script directly with `python`.

## Use the API

```python
from peakprobe import Probe

with Probe("load", top=3, include="src/*") as probe:
    with probe.phase("parse"):
        rows = parse(path)
    with probe.phase("index"):
        index = build_index(rows)

report = probe.report()
for phase in report.phases:
    print(phase.name, phase.peak_bytes, phase.retained_bytes)
```

`Probe` parameters:

| Parameter | Meaning |
|---|---|
| `label` | report title |
| `top` | allocation sites per phase; `0` skips snapshots (totals only) |
| `include` | glob of files whose allocations are attributed |

## CLI

### `run`

```shell
peakprobe run examples/report_pipeline.py
peakprobe run examples/report_pipeline.py --json
peakprobe run examples/report_pipeline.py --out results/report.txt
peakprobe run examples/report_pipeline.py --fail-retained 64MiB
peakprobe run examples/report_pipeline.py --top 0 --fail-peak 512MB
peakprobe run examples/report_pipeline.py --label nightly-import
```

| Flag | Effect |
|---|---|
| `--label NAME` | report title; overrides a label passed to `start()` |
| `--top N` | allocation sites per phase (default 5) |
| `--json` | machine-readable report |
| `--out FILE` | also write the report to a file |
| `--fail-peak SIZE` | exit 1 when the run's peak exceeds SIZE |
| `--fail-retained SIZE` | exit 1 when memory retained at the end exceeds SIZE |

### `demo`

```shell
peakprobe demo
peakprobe demo --json
```

Runs the built-in three-phase pipeline.

## Size syntax

| Input | Bytes |
|---|---|
| `512` | 512 |
| `4KB` | 4 000 |
| `4KiB` | 4 096 |
| `1.5MiB` | 1 572 864 |
| `2_000` | 2 000 |

Unknown suffixes (for example `4XB`) are rejected with exit code `2`.

## Reading the report

```text
phase               time        peak    retained  top site
build rows        995.0ms    29.3 MiB    29.3 MiB  <demo>:6 (+29.3 MiB)
```

- **peak** is the highest traced size reached during the phase.
- **retained** is how much more memory was live at the end of the phase than at its start; a negative value means the phase freed memory.
- **top site** is the allocation line with the largest positive difference in that phase.

The detailed section lists up to `--top` sites per phase with byte deltas and allocation counts.

## JSON shape

```json
{
  "label": "pipeline",
  "total_peak_bytes": 38580224,
  "total_retained_bytes": 36282368,
  "phases": [
    {
      "name": "build rows",
      "index": 0,
      "duration_ms": 995.0,
      "peak_bytes": 30720000,
      "retained_bytes": 30720000,
      "current_bytes": 30720000,
      "top_sites": [
        {"file": "app.py", "line": 6, "size_bytes": 30720000, "size_diff": 30720000, "count": 479473}
      ]
    }
  ]
}
```

## CI integration

```yaml
- name: Memory budget
  run: |
    pip install ./tools/peakprobe
    peakprobe run scripts/nightly_import.py --top 0 --fail-retained 64MiB
```

Use `--top 0` in CI when you only need the budget: it skips snapshots and is much faster and more stable than attribution output.

## Troubleshooting

- **No sites listed:** everything was allocated outside the include glob, or `--top 0` was used. The totals are still valid.
- **Numbers differ from `/usr/bin/time`:** tracemalloc measures CPython allocator memory, not RSS. Native buffers and the interpreter's arenas are not comparable.
- **The script stops early:** a script that calls `peakprobe.stop()` itself ends tracing before the CLI's stop; remove that call and let the CLI finish the measurement.
