"""Command-line interface for peakprobe."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import sys

from . import __version__
from .api import default_probe
from .render import human_size, parse_size, render

DEMO = '''
import peakprobe

peakprobe.start("demo-pipeline")

rows = [{"id": index, "amount": index * 3} for index in range(120_000)]
peakprobe.checkpoint("build rows")

by_id = {row["id"]: row for row in rows}
peakprobe.checkpoint("index rows")

blob = " ".join(str(row["id"]) for row in rows[:40_000])
peakprobe.checkpoint("render export")
'''


def _emit(report, as_json: bool, out: str | None) -> None:
    if as_json:
        text = json.dumps(report.to_dict(), indent=2)
    else:
        text = render(report)
    print(text)
    if out:
        with open(out, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")


def _check_budgets(report, peak_budget: int | None, retained_budget: int | None) -> int:
    failed = False
    if peak_budget is not None and report.total_peak_bytes > peak_budget:
        print(
            f"peakprobe: peak {human_size(report.total_peak_bytes)} exceeds "
            f"budget {human_size(peak_budget)}",
            file=sys.stderr,
        )
        failed = True
    if retained_budget is not None and report.total_retained_bytes > retained_budget:
        print(
            f"peakprobe: retained {human_size(report.total_retained_bytes)} exceeds "
            f"budget {human_size(retained_budget)}",
            file=sys.stderr,
        )
        failed = True
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="peakprobe",
        description=(
            "Attribute Python peak and retained memory to named checkpoints, "
            "with the allocation sites that grew in each phase."
        ),
    )
    parser.add_argument("--version", action="version", version=f"peakprobe {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a script under the default probe")
    run.add_argument("script")
    run.add_argument("--label", help="report label (default: script file name)")
    run.add_argument("--top", type=int, default=5, help="allocation sites per phase")
    run.add_argument("--json", action="store_true")
    run.add_argument("--out", help="also write the report to this file")
    run.add_argument(
        "--fail-peak",
        metavar="SIZE",
        help="exit 1 when the whole-run peak exceeds SIZE (e.g. 64MiB)",
    )
    run.add_argument(
        "--fail-retained",
        metavar="SIZE",
        help="exit 1 when memory retained at the end exceeds SIZE",
    )

    demo = sub.add_parser("demo", help="run the built-in memory pipeline")
    demo.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    peak_budget = retained_budget = None
    try:
        if getattr(args, "fail_peak", None):
            peak_budget = parse_size(args.fail_peak)
        if getattr(args, "fail_retained", None):
            retained_budget = parse_size(args.fail_retained)
    except ValueError as exc:
        print(f"peakprobe: {exc}", file=sys.stderr)
        return 2

    if args.command == "demo":
        probe = default_probe()
        probe.reset()
        probe.label = "demo-pipeline"
        probe.top = 5
        probe.start()
        namespace = {"__name__": "__main__", "__file__": "<demo>"}
        try:
            exec(compile(DEMO, "<demo>", "exec"), namespace)  # noqa: S102 - fixed string
        finally:
            report = probe.stop()
        _emit(report, args.json, None)
        return _check_budgets(report, peak_budget, retained_budget)

    if args.command == "run":
        script = args.script
        if not os.path.isfile(script):
            print(f"peakprobe: no such file: {script}", file=sys.stderr)
            return 2
        probe = default_probe()
        probe.reset()
        probe.label = args.label or os.path.basename(script)
        probe.top = max(0, args.top)
        probe.include = os.path.dirname(os.path.abspath(script)) + "/*"
        probe.start()
        failure: str | None = None
        try:
            runpy.run_path(script, run_name="__main__")
        except SystemExit as exc:
            code = exc.code
            if code not in (0, None):
                failure = f"script exited with status {code}"
        except BaseException as exc:  # surface, then still print the measurement
            failure = f"{type(exc).__name__}: {exc}"
        finally:
            if args.label:
                # An explicit --label wins over a label the script passed to start().
                probe.label = args.label
            report = probe.stop()

        _emit(report, args.json, args.out)
        if failure:
            print(f"peakprobe: {failure}", file=sys.stderr)
            return 1
        return _check_budgets(report, peak_budget, retained_budget)

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
