import pytest

from peakprobe.api import Phase, Report, Site
from peakprobe.render import human_size, parse_size, render


def test_human_size_units():
    assert human_size(0) == "0 B"
    assert human_size(999) == "999 B"
    assert human_size(1024) == "1.0 KiB"
    assert human_size(1536) == "1.5 KiB"
    assert human_size(1024**2) == "1.0 MiB"


def test_parse_size_accepts_plain_and_suffixed_values():
    assert parse_size("512") == 512
    assert parse_size("4KB") == 4000
    assert parse_size("4KiB") == 4096
    assert parse_size("1.5MiB") == int(1.5 * 1024**2)
    assert parse_size("2_000") == 2000


def test_parse_size_rejects_bad_values():
    for raw in ("", "abc", "4XB", "-3"):
        with pytest.raises(ValueError):
            parse_size(raw)


def test_render_explains_missing_checkpoints():
    text = render(Report(label="app", total_peak_bytes=2048, total_retained_bytes=1024))
    assert "no checkpoints recorded" in text
    assert "2.0 KiB" in text
    assert "checkpoint" in text


def test_render_lists_phases_and_sites():
    report = Report(
        label="pipeline",
        total_peak_bytes=3 * 1024**2,
        total_retained_bytes=1024**2,
        phases=(
            Phase(
                name="build",
                index=0,
                duration_ms=12.5,
                peak_bytes=2 * 1024**2,
                retained_bytes=1024**2,
                current_bytes=1024**2,
                top_sites=(
                    Site(file="app.py", line=12, size_bytes=900_000, size_diff=800_000, count=4),
                ),
            ),
        ),
    )
    text = render(report)
    assert "pipeline" in text
    assert "build" in text
    assert "app.py:12" in text
    assert "allocation sites by phase" in text
    assert "4 allocation(s)" in text
