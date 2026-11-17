"""peakprobe — attribute Python memory to named checkpoints.

    import peakprobe

    peakprobe.start("pipeline")
    rows = build_rows()
    peakprobe.checkpoint("build rows")

    index = build_index(rows)
    peakprobe.checkpoint("index")

    summary = peakprobe.report()   # or run under `peakprobe run script.py`

`Probe` is the same API without the module-level singleton:

    from peakprobe import Probe

    with Probe("pipeline") as probe:
        with probe.phase("build"):
            rows = build_rows()
    print(probe.report())
"""

from .api import (
    Phase,
    Probe,
    Report,
    Site,
    checkpoint,
    default_probe,
    phase,
    report,
    reset,
    start,
    stop,
)

__version__ = "0.1.0"

__all__ = [
    "Phase",
    "Probe",
    "Report",
    "Site",
    "checkpoint",
    "default_probe",
    "phase",
    "report",
    "reset",
    "start",
    "stop",
    "__version__",
]
