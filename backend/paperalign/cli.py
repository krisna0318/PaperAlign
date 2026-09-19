from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app import __version__
from app.parsers.errors import DocxAnalysisError
from app.services.analyzer import analyze_docx, write_artifacts
from app.services.template_inspector import inspect_template, write_template_artifacts


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

    inspect = subparsers.add_parser(
        "inspect-template",
        help="extract formatting evidence from a DOCX template without requiring comments",
    )
    inspect.add_argument("input", type=Path, help="path to the template .docx")
    inspect.add_argument(
        "--out",
        type=Path,
        required=True,
        help="directory for the M2 template evidence artifacts",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "analyze":
            artifacts = analyze_docx(args.input)
            write_artifacts(args.out, artifacts)
            print(f"Analysis completed: {args.out.resolve()}")
            print(f"Content fingerprint: {artifacts.content_fingerprint.aggregate_sha256}")
            if artifacts.unsupported_objects.safe_for_future_formatting:
                print("Safety result: no blocking unsupported object detected")
            else:
                print("Safety result: blocking unsupported objects require manual review")
            return 0
        if args.command == "inspect-template":
            template_artifacts = inspect_template(args.input)
            write_template_artifacts(args.out, template_artifacts)
            print(f"Template evidence completed: {args.out.resolve()}")
            print(f"Comments found: {template_artifacts.report.comment_count}")
            print(f"Tables found: {len(template_artifacts.report.tables)}")
            return 0
        return 2
    except DocxAnalysisError as exc:
        print(f"PaperAlign analysis failed [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"PaperAlign could not access input or write artifacts: {exc}", file=sys.stderr)
        return 3
