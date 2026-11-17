# Project spec — peakprobe

## Name

peakprobe

## Category

dynamic-instrumentation

## Target user

A Python developer investigating memory growth in a batch job, ETL pipeline, report generator or service warm-up, who needs to know which phase owns the memory.

## Problem

`tracemalloc` reports a single process peak. A profiler reports time. Neither answers "which phase is retaining 300 MB, and on which line". Heap dumps answer it but are heavy to read and compare.

## Solution

Explicit checkpoints. Each checkpoint records peak-since-last, retained growth, current total and the top allocation sites by line. A CLI runs a script under the default probe, a small API allows embedding, and byte budgets gate CI.

## Core workflow

1. Add `peakprobe.checkpoint("phase name")` after each pipeline step.
2. `peakprobe run script.py`.
3. Read the phase table, then the allocation sites of the largest phase.
4. Fix the code, re-run, add `--fail-retained` to CI.

## Must-have features

- peak and retained measurement per phase;
- allocation sites per phase (line, byte delta, count);
- API and CLI;
- process-wide totals even when attribution is filtered to a script;
- JSON output and byte budgets;
- no dependencies;
- fast totals-only mode.

## Nice-to-have features

- compare two reports;
- RSS sampling;
- pytest fixture budget assertions.

## Stack

Python 3.12+, `tracemalloc` + `time` from the standard library, pytest.

## Test strategy

API tests allocate known-larger-than-threshold structures and assert lower bounds (never exact bytes): peak/retained growth, attribution to the allocating line, two-phase separation, context manager, auto-start, totals-only mode, reset. Render tests cover unit formatting, size parsing and both report shapes. CLI tests cover text/JSON, label precedence, out files, budget failure/pass, invalid sizes, missing scripts and script exceptions.

## Demo/result strategy

`peakprobe demo` runs a 120k-row build, an index build and an export render, producing three phases with a clear dominant site. `examples/report_pipeline.py` is the same shape with a printable summary. Observed output is stored in `results/demo.txt` and quoted in the README.

## Safety considerations

The tool executes the script the user names, in-process. That is its purpose and is documented; no network, no subprocess, no privilege changes. Budget failures are reported on stderr with exit 1.

## Definition of done

- 26 tests green;
- demo produces three phases with attribution to the script lines;
- budgets verified in both directions;
- docs match observed output;
- committed and published.
