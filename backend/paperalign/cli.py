from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app import __version__
from app.parsers.errors import DocxAnalysisError
from app.services.analyzer import analyze_docx, write_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paperalign",
        description="PaperAlign explainable thesis document tooling",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze",
        help="read a DOCX package and create deterministic analysis artifacts",
    )
    analyze.add_argument("input", type=Path, help="path to the input .docx")
    analyze.add_argument(
        "--out",
        type=Path,
        required=True,
        help="directory for the four M1 analysis artifacts",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "analyze":
        return 2

    try:
        artifacts = analyze_docx(args.input)
        write_artifacts(args.out, artifacts)
    except DocxAnalysisError as exc:
        print(f"PaperAlign analysis failed [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"PaperAlign could not access input or write artifacts: {exc}", file=sys.stderr)
        return 3

    print(f"Analysis completed: {args.out.resolve()}")
    print(f"Content fingerprint: {artifacts.content_fingerprint.aggregate_sha256}")
    if artifacts.unsupported_objects.safe_for_future_formatting:
        print("Safety result: no blocking unsupported object detected")
    else:
        print("Safety result: blocking unsupported objects require manual review")
    return 0
