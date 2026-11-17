"""Checkpoint-based memory attribution on top of tracemalloc.

`Probe` records a snapshot at every checkpoint. Each phase reports:

* the peak traced memory reached during the phase (tracemalloc peak reset at the
  previous checkpoint);
* the retained growth at the end of the phase;
* the allocation sites that grew the most, sorted by byte difference.

A module-level default probe is provided so a script can call
`peakprobe.start()` / `peakprobe.checkpoint("name")` without threading an object
through its code. The CLI drives that default probe.
"""

from __future__ import annotations

import contextlib
import fnmatch
import os
import time
import tracemalloc
from dataclasses import dataclass, field
from typing import Iterator

SELF_PACKAGE = "peakprobe"
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")


@dataclass(frozen=True)
class Site:
    file: str
    line: int
    size_bytes: int
    size_diff: int
    count: int

    @property
    def location(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass(frozen=True)
class Phase:
    name: str
    index: int
    duration_ms: float
    peak_bytes: int
    retained_bytes: int
    current_bytes: int
    top_sites: tuple[Site, ...] = ()


@dataclass
class Report:
    label: str
    phases: tuple[Phase, ...] = ()
    total_peak_bytes: int = 0
    total_retained_bytes: int = 0

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "total_peak_bytes": self.total_peak_bytes,
            "total_retained_bytes": self.total_retained_bytes,
            "phases": [
                {
                    "name": phase.name,
                    "index": phase.index,
                    "duration_ms": round(phase.duration_ms, 3),
                    "peak_bytes": phase.peak_bytes,
                    "retained_bytes": phase.retained_bytes,
                    "current_bytes": phase.current_bytes,
                    "top_sites": [
                        {
                            "file": site.file,
                            "line": site.line,
                            "size_bytes": site.size_bytes,
                            "size_diff": site.size_diff,
                            "count": site.count,
                        }
                        for site in phase.top_sites
                    ],
                }
                for phase in self.phases
            ],
        }


class Probe:
    """Measures allocation growth between explicit checkpoints."""

    def __init__(self, label: str = "run", top: int = 5, include: str | None = None):
        self.label = label
        self.top = top
        # Optional glob restricting allocation sites to one source tree. Peak
        # and retained totals stay process-wide; only attribution is filtered.
        self.include = include
        # Three frames name an allocation site without paying for a deep trace
        # of a large process.
        self._steps = 3
        self._owns_tracing = False
        self._started = False
        self._phases: list[Phase] = []
        self._previous = None
        self._previous_current = 0
        self._initial_current = 0
        self._phase_start = 0.0
        self._peak_bytes = 0
        self._current_bytes = 0
        self._stopped = False

    def _snapshot(self):
        return tracemalloc.take_snapshot()

    def _included(self, filename: str) -> bool:
        """Cheap attribution filter.

        `Snapshot.filter_traces()` walks every trace and cost ~8 s on a modest
        500k-block heap in this environment, so the include glob is applied to
        the handful of grouped statistics instead.
        """

        if not self.include:
            return True
        normalized = os.path.abspath(filename).replace("\\", "/")
        pattern = self.include.replace("\\", "/")
        if pattern.endswith("*"):
            return normalized.startswith(pattern[:-1])
        return fnmatch.fnmatch(normalized, pattern)

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> "Probe":
        if self._started:
            return self
        if not tracemalloc.is_tracing():
            tracemalloc.start(self._steps)
            self._owns_tracing = True
        tracemalloc.reset_peak()
        self._initial_current = tracemalloc.get_traced_memory()[0]
        self._previous_current = self._initial_current
        self._previous = self._snapshot() if self.top > 0 else None
        self._phase_start = time.perf_counter()
        self._started = True
        self._stopped = False
        return self

    def checkpoint(self, name: str) -> Phase:
        if not self._started:
            self.start()
        if not tracemalloc.is_tracing():
            raise RuntimeError("tracemalloc is not running; call start() first")

        current, peak = tracemalloc.get_traced_memory()
        elapsed_ms = (time.perf_counter() - self._phase_start) * 1000
        snapshot = self._snapshot() if self.top > 0 else None

        top_sites: list[Site] = []
        if snapshot is not None and self._previous is not None:
            stats = snapshot.compare_to(self._previous, "lineno")
            grown = []
            for stat in stats:
                if stat.size_diff <= 0 or not stat.traceback:
                    continue
                frame = stat.traceback[0]
                if _is_own_frame(frame.filename):
                    continue
                if not self._included(frame.filename):
                    continue
                grown.append(stat)
            grown.sort(key=lambda stat: stat.size_diff, reverse=True)
            for stat in grown[: self.top]:
                frame = stat.traceback[0]
                top_sites.append(
                    Site(
                        file=_display_path(frame.filename),
                        line=frame.lineno,
                        size_bytes=max(0, stat.size),
                        size_diff=max(0, stat.size_diff),
                        count=max(0, stat.count),
                    )
                )

        phase = Phase(
            name=name,
            index=len(self._phases),
            duration_ms=elapsed_ms,
            peak_bytes=max(0, peak - self._previous_current),
            retained_bytes=current - self._previous_current,
            current_bytes=current,
            top_sites=tuple(top_sites),
        )
        self._phases.append(phase)
        self._peak_bytes = max(self._peak_bytes, peak)
        self._current_bytes = current
        if snapshot is not None:
            self._previous = snapshot
        self._previous_current = current
        self._phase_start = time.perf_counter()
        tracemalloc.reset_peak()
        return phase

    def stop(self) -> Report:
        if self._started and not self._stopped:
            current, peak = tracemalloc.get_traced_memory()
            self._peak_bytes = max(self._peak_bytes, peak)
            self._current_bytes = current
            self._stopped = True
        if self._owns_tracing and tracemalloc.is_tracing():
            tracemalloc.stop()
            self._owns_tracing = False
        return self.report()

    def reset(self) -> None:
        self.include = None
        if self._owns_tracing and tracemalloc.is_tracing():
            tracemalloc.stop()
        self._steps = 3
        self._owns_tracing = False
        self._started = False
        self._phases = []
        self._previous = None
        self._previous_current = 0
        self._initial_current = 0
        self._phase_start = 0.0
        self._peak_bytes = 0
        self._current_bytes = 0
        self._stopped = False

    # -- context managers --------------------------------------------------
    def __enter__(self) -> "Probe":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.stop()
        return False

    @contextlib.contextmanager
    def phase(self, name: str) -> Iterator[Phase]:
        if not self._started:
            self.start()
        try:
            yield self
        finally:
            self.checkpoint(name)

    # -- results -----------------------------------------------------------
    def report(self) -> Report:
        return Report(
            label=self.label,
            phases=tuple(self._phases),
            total_peak_bytes=self._peak_bytes,
            total_retained_bytes=max(0, self._current_bytes - self._initial_current),
        )


def _is_own_frame(filename: str) -> bool:
    """True for frames that only exist because the probe is running.

    Matching on the directory name alone is wrong: a user's checkout can be
    called `peakprobe` (this repository is), and their own allocations must not
    be filtered out. Tracemalloc's own bookkeeping and synthetic `<...>` frames
    are also excluded because they are measurement noise.
    """

    if filename in {"<string>", "<stdin>"} or filename.startswith("<frozen"):
        return True
    if filename.endswith("/tracemalloc.py"):
        return True
    normalized = os.path.abspath(filename).replace("\\", "/")
    return normalized.startswith(_PACKAGE_DIR + "/")


def _display_path(filename: str) -> str:
    return filename


_default = Probe(label="default")


def default_probe() -> Probe:
    return _default


def start(label: str = "default") -> Probe:
    _default.label = label
    return _default.start()


def checkpoint(name: str) -> Phase:
    return _default.checkpoint(name)


def report() -> Report:
    return _default.report()


def stop() -> Report:
    return _default.stop()


def reset() -> None:
    _default.reset()


def phase(name: str):
    return _default.phase(name)
