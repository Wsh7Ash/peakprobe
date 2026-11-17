import json

from peakprobe.cli import main

SCRIPT = """
import peakprobe

peakprobe.start("script")

payload = [str(index) * 2 for index in range(40_000)]
peakprobe.checkpoint("build payload")

extra = {index: str(index) for index in range(20_000)}
peakprobe.checkpoint("index payload")
"""

FAILING = """
raise RuntimeError("boom")
"""


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_demo_runs_three_checkpoints(capsys):
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "demo-pipeline" in out
    assert "build rows" in out
    assert "index rows" in out
    assert "render export" in out


def test_demo_json_shape(capsys):
    assert main(["demo", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["label"] == "demo-pipeline"
    assert len(payload["phases"]) == 3
    assert payload["total_peak_bytes"] > 0
    assert payload["phases"][0]["name"] == "build rows"


def test_run_script_reports_checkpoints(tmp_path, capsys):
    path = write(tmp_path, "mem.py", SCRIPT)
    assert main(["run", path]) == 0
    out = capsys.readouterr().out
    assert "build payload" in out
    assert "index payload" in out
    assert "script" in out


def test_run_script_json(tmp_path, capsys):
    path = write(tmp_path, "mem.py", SCRIPT)
    assert main(["run", path, "--json", "--top", "2"]) == 0
    payload = json.loads(capsys.readouterr().out)
    # The script names its own run through peakprobe.start("script").
    assert payload["label"] == "script"
    assert [phase["name"] for phase in payload["phases"]] == [
        "build payload",
        "index payload",
    ]
    assert all(len(phase["top_sites"]) <= 2 for phase in payload["phases"])


def test_explicit_label_overrides_the_script_label(tmp_path, capsys):
    path = write(tmp_path, "mem.py", SCRIPT)
    assert main(["run", path, "--json", "--label", "checkout", "--top", "0"]) == 0
    assert json.loads(capsys.readouterr().out)["label"] == "checkout"


def test_peak_budget_failure(tmp_path, capsys):
    path = write(tmp_path, "mem.py", SCRIPT)
    assert main(["run", path, "--fail-peak", "1B", "--top", "0"]) == 1
    assert "exceeds budget" in capsys.readouterr().err


def test_peak_budget_passes_with_a_generous_limit(tmp_path):
    path = write(tmp_path, "mem.py", SCRIPT)
    assert main(["run", path, "--fail-peak", "1GiB", "--top", "0"]) == 0


def test_retained_budget_failure(tmp_path, capsys):
    path = write(tmp_path, "mem.py", SCRIPT)
    assert main(["run", path, "--fail-retained", "1B", "--top", "0"]) == 1
    assert "retained" in capsys.readouterr().err


def test_bad_size_is_an_error(tmp_path, capsys):
    path = write(tmp_path, "mem.py", SCRIPT)
    assert main(["run", path, "--fail-peak", "12XB"]) == 2
    assert "unknown size suffix" in capsys.readouterr().err


def test_missing_script_is_an_error(capsys):
    assert main(["run", "nope.py"]) == 2
    assert "no such file" in capsys.readouterr().err


def test_out_file_is_written(tmp_path, capsys):
    path = write(tmp_path, "mem.py", SCRIPT)
    out_path = tmp_path / "report.txt"
    assert main(["run", path, "--out", str(out_path), "--top", "0"]) == 0
    assert "build payload" in out_path.read_text(encoding="utf-8")
    assert "build payload" in capsys.readouterr().out


def test_script_failure_still_reports_and_exits_nonzero(tmp_path, capsys):
    path = write(tmp_path, "boom.py", FAILING)
    assert main(["run", path, "--top", "0"]) == 1
    captured = capsys.readouterr()
    assert "whole-run peak" in captured.out
    assert "RuntimeError: boom" in captured.err
