import tracemalloc

import peakprobe
from peakprobe.api import Probe


def rows(count):
    return [{"id": index, "amount": index * 3} for index in range(count)]


def test_checkpoint_records_peak_and_retained_growth():
    probe = Probe("test").start()
    data = rows(20_000)
    phase = probe.checkpoint("build rows")
    report = probe.stop()

    assert phase.name == "build rows"
    assert phase.retained_bytes > 500_000
    assert phase.peak_bytes > 500_000
    assert report.phases == (phase,)
    assert report.total_peak_bytes >= phase.peak_bytes
    assert report.total_retained_bytes > 500_000
    del data
    assert not tracemalloc.is_tracing()


def test_two_phases_attribute_growth_separately():
    probe = Probe("test").start()
    first = rows(12_000)
    phase_one = probe.checkpoint("first")
    second = rows(12_000)
    phase_two = probe.checkpoint("second")
    report = probe.stop()

    assert phase_one.retained_bytes > 0
    assert phase_two.retained_bytes > 0
    assert [phase.name for phase in report.phases] == ["first", "second"]
    del first, second


def test_top_sites_point_at_the_allocating_line():
    probe = Probe("test", top=3).start()
    data = [str(index) * 4 for index in range(20_000)]
    phase = probe.checkpoint("strings")
    probe.stop()

    assert phase.top_sites
    assert any("test_api" in site.file for site in phase.top_sites)
    assert any(site.size_diff > 0 for site in phase.top_sites)
    del data


def test_phase_context_manager_records_a_checkpoint():
    probe = Probe("test")
    with probe:
        with probe.phase("inside"):
            payload = bytearray(1_000_000)
    report = probe.report()
    assert [phase.name for phase in report.phases] == ["inside"]
    assert report.phases[0].peak_bytes > 500_000
    del payload


def test_checkpoint_starts_the_probe_automatically():
    probe = Probe("test")
    probe.checkpoint("auto")
    assert len(probe.report().phases) == 1
    probe.stop()


def test_stop_without_checkpoints_records_whole_run_totals():
    probe = Probe("whole").start()
    payload = bytearray(2_000_000)
    report = probe.stop()
    assert report.phases == ()
    assert report.total_peak_bytes > 1_000_000
    del payload


def test_reset_clears_phases_and_tracing():
    probe = Probe("test").start()
    probe.checkpoint("one")
    probe.reset()
    assert probe.report().phases == ()
    assert not tracemalloc.is_tracing()


def test_report_to_dict_shape():
    probe = Probe("shape").start()
    data = rows(5_000)
    probe.checkpoint("rows")
    report = probe.stop()
    payload = report.to_dict()
    assert payload["label"] == "shape"
    assert payload["phases"][0]["name"] == "rows"
    assert set(payload["phases"][0]) >= {
        "duration_ms",
        "peak_bytes",
        "retained_bytes",
        "current_bytes",
        "top_sites",
    }
    del data


def test_default_probe_module_functions():
    peakprobe.reset()
    peakprobe.start("module")
    data = rows(10_000)
    peakprobe.checkpoint("module phase")
    report = peakprobe.stop()
    assert report.label == "module"
    assert report.phases[0].name == "module phase"
    assert peakprobe.default_probe() is not None
    del data
    peakprobe.reset()
