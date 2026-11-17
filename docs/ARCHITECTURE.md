# Architecture — peakprobe

## Overview

```text
script / Probe
   │  start()      tracemalloc start (3 frames), baseline snapshot, reset_peak
   │  checkpoint() current + peak, new snapshot, compare_to(previous, "lineno")
   │  stop()       freeze totals, stop tracing if this probe started it
   ▼
Report(label, phases[Phase], total_peak_bytes, total_retained_bytes)
   │
render.py / cli.py ──► table, JSON, budget exit codes
```

## Measurement model

| Field | Definition |
|---|---|
| `peak_bytes` | `tracemalloc.get_traced_memory()[1]` at the checkpoint minus the current traced size at the previous checkpoint. The peak is reset at every checkpoint, so it covers exactly one phase. |
| `retained_bytes` | current traced size minus current traced size at the previous checkpoint. Negative when a phase frees more than it allocates. |
| `current_bytes` | absolute traced size at the checkpoint. |
| `duration_ms` | wall-clock time since the previous checkpoint. |
| `top_sites` | allocation lines whose `size_diff` versus the previous snapshot is positive, sorted by `size_diff`, limited to `top`. |

`compare_to(previous, "lineno")` groups by the allocation's immediate source line, which is why a list comprehension appears as one site regardless of how many objects it created.

## Filtering

Frames that exist only because the probe is running are removed:

- files inside the installed `peakprobe` package directory;
- `tracemalloc.py`;
- `<string>`, `<stdin>` and `<frozen ...>`.

The package-directory check is exact (`os.path.dirname(__file__)`) rather than a name match: a user's checkout is often called `peakprobe`, and their allocations must not be hidden.

`Probe.include` restricts attribution to a glob. The CLI sets it to `<script directory>/*` so running a script inside a large host process attributes memory to the script, not the host. Peak and retained totals remain process-wide.

The glob is applied to the grouped statistics rather than to snapshots via `Snapshot.filter_traces()`, which walks every trace and measured ~8 s on a 500k-block heap here versus milliseconds for the grouped form. `take_snapshot()` itself is cheap; `compare_to(..., "lineno")` is the remaining cost (~2 s per checkpoint on that heap).

## Lifecycle details

- `start()` is idempotent: calling it twice does not reset the baseline.
- `checkpoint()` auto-starts an unstarted probe.
- `Probe` records whether it started tracemalloc, and only stops it in that case, so embedding it in an application that already traces does not disable tracing.
- `top == 0` skips snapshots entirely: peak and retained are still measured, which is the fast path for budget-only runs.
- `phase(name)` is a context manager that checkpoints on exit even when the body raises.

## CLI

`run` starts the default probe, executes the script with `runpy.run_path(..., "__main__")`, stops the probe, prints the report, and applies budgets. Script failures are reported after the measurement, with exit code 1. `--label` overrides a label the script passed to `start()`.

`demo` executes a fixed pipeline string with the same measurement path.

Sizes accept `B`, `KB`/`KiB`, `MB`/`MiB`, `GB`/`GiB` (decimal vs binary).

## Design decisions

- **Checkpoint API over sampling.** Sampling threads add noise and complexity; explicit phases map to how people reason about pipelines.
- **Line attribution, not object graphs.** `compare_to(..., "lineno")` is cheap and answers "which line grew".
- **Three-frame traces.** Deep traces multiply snapshot cost; the allocation line is what matters.
- **Filtered attribution.** Without `include`, a host process's heap dominates the top list and hides the script.
