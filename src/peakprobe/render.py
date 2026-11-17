"""Human-readable rendering and size parsing for peakprobe."""

from __future__ import annotations

from .api import Report

UNITS = ("B", "KiB", "MiB", "GiB", "TiB")
SUFFIXES = {
    "b": 1,
    "kb": 1000,
    "kib": 1024,
    "mb": 1000**2,
    "mib": 1024**2,
    "gb": 1000**3,
    "gib": 1024**3,
}


def human_size(size: int) -> str:
    value = float(size)
    for unit in UNITS:
        if abs(value) < 1024 or unit == UNITS[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{int(size)} B"


def parse_size(raw: str) -> int:
    """Parse `512`, `4KB`, `16MiB` into bytes."""

    text = raw.strip().lower().replace("_", "")
    if not text:
        raise ValueError("empty size")
    number = ""
    suffix = ""
    for char in text:
        if char.isdigit() or char in ".+-":
            if suffix:
                raise ValueError(f"invalid size: {raw}")
            number += char
        else:
            suffix += char
    if not number:
        raise ValueError(f"invalid size: {raw}")
    multiplier = SUFFIXES.get(suffix, None)
    if suffix and multiplier is None:
        raise ValueError(f"unknown size suffix '{suffix}' in {raw}")
    try:
        value = float(number)
    except ValueError:
        raise ValueError(f"invalid size: {raw}") from None
    if value < 0:
        raise ValueError("size must not be negative")
    return int(value * (multiplier or 1))


def render(report: Report) -> str:
    if not report.phases:
        return (
            f"peakprobe: {report.label}\n"
            f"no checkpoints recorded; whole-run peak {human_size(report.total_peak_bytes)}, "
            f"retained {human_size(report.total_retained_bytes)}.\n"
            "Call peakprobe.checkpoint('name') to attribute memory to phases."
        )

    width = max(5, max(len(phase.name) for phase in report.phases))
    lines = [
        f"peakprobe: {report.label} ({len(report.phases)} checkpoint(s))",
        f"total peak {human_size(report.total_peak_bytes)}, "
        f"retained {human_size(report.total_retained_bytes)}",
        "",
        f"{'phase':<{width}}  {'time':>9}  {'peak':>10}  {'retained':>10}  top site",
    ]
    for phase in report.phases:
        top = phase.top_sites[0] if phase.top_sites else None
        top_text = (
            f"{top.location} (+{human_size(top.size_diff)})" if top else ""
        )
        lines.append(
            f"{phase.name:<{width}}  {phase.duration_ms:>8.1f}ms  "
            f"{human_size(phase.peak_bytes):>10}  "
            f"{human_size(phase.retained_bytes):>10}  {top_text}".rstrip()
        )

    detailed = [phase for phase in report.phases if phase.top_sites]
    if detailed:
        lines.append("")
        lines.append("allocation sites by phase")
        for phase in detailed:
            lines.append(f"  {phase.name}")
            for site in phase.top_sites:
                lines.append(
                    f"    +{human_size(site.size_diff):>9}  "
                    f"{site.location:<40} {site.count} allocation(s)"
                )
    return "\n".join(lines)
