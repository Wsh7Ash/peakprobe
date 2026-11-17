"""Example script for `peakprobe run examples/report_pipeline.py`.

The checkpoints split a small report pipeline into phases so the report shows
which phase owns the memory, not just the process total.
"""

import peakprobe

peakprobe.start("report-pipeline")


def build_rows(count: int) -> list[dict]:
    return [{"id": index, "amount": index * 3} for index in range(count)]


rows = build_rows(80_000)
peakprobe.checkpoint("build rows")

by_id = {row["id"]: row for row in rows}
peakprobe.checkpoint("index rows")

blob = " ".join(str(row["id"]) for row in rows[:30_000])
peakprobe.checkpoint("render export")

summary = {"rows": len(rows), "bytes": len(blob)}
peakprobe.checkpoint("summarise")
print(summary)
