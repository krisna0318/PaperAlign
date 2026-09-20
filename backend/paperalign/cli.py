from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app import __version__
from app.parsers.errors import DocxAnalysisError
from app.profiles.loader import ProfileLoadError, check_applicability, load_profile
from app.services.analyzer import analyze_docx, write_artifacts
from app.services.format_audit import write_format_audit
from app.services.profile_service import export_profile, verify_template_samples
from app.services.structure_service import write_structure_review
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
    audit = subparsers.add_parser("audit-template", help="create a private local format audit")
    audit.add_argument("input", type=Path)
    audit.add_argument("--out", type=Path, required=True, help="directory under .paperalign")
    audit.add_argument(
        "--include-preview", action="store_true", help="include 20-character previews"
    )
    profile = subparsers.add_parser("inspect-profile", help="validate and export the SCAU Profile")
    profile.add_argument("--out", type=Path, required=True)
    profile.add_argument("--school")
    profile.add_argument("--education-level")
    profile.add_argument("--college")
    profile.add_argument("--cohort")
    verify = subparsers.add_parser(
        "verify-template", help="check hash-bound official template samples"
    )
    verify.add_argument("input", type=Path)
    verify.add_argument("--out", type=Path, required=True)
    classify = subparsers.add_parser(
        "classify", help="classify manuscript structure and review ambiguity locally"
    )
    classify.add_argument("input", type=Path)
    classify.add_argument("--out", type=Path, required=True, help="directory under .paperalign")
    classify.add_argument(
        "--include-preview", action="store_true", help="include at most 20 characters per block"
    )
    classify.add_argument("--overrides", type=Path, help="hash-bound manual role corrections")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "classify":
            structure = write_structure_review(
                args.input,
                args.out,
                overrides_path=args.overrides,
                include_preview=args.include_preview,
            )
            print(
                f"Structure classified: {len(structure.decisions)} blocks, "
                f"{structure.review_count} need review"
            )
            print(f"Located rule checks: {structure.validation_counts}")
            print(f"Review: {args.out.resolve() / 'structure_review.html'}")
            print("Rules-only; no formatting or whole-document compliance conclusion")
            return 0
        if args.command == "inspect-profile":
            bundle = load_profile()
            scope_result = None
            if any((args.school, args.education_level, args.college, args.cohort)):
                scope_result = check_applicability(
                    bundle.manifest,
                    school=args.school,
                    education_level=args.education_level,
                    college=args.college,
                    cohort=args.cohort,
                )
            export_profile(bundle, args.out, scope_result)
            print(
                f"Profile validated: {len(bundle.rules)} rules, "
                f"{len(bundle.coverage)} inventory entries"
            )
            if scope_result:
                print(f"Applicability: {scope_result.status} ({scope_result.reason})")
            return 0
        if args.command == "verify-template":
            payload = verify_template_samples(load_profile(), args.input, args.out)
            print(f"Template sample checks: {payload['counts']}")
            print("Scope: fixed template samples only; not whole-document compliance")
            return 0
        if args.command == "audit-template":
            output = write_format_audit(args.input, args.out, include_preview=args.include_preview)
            print(f"Local audit completed: {output}")
            return 0
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
    except ProfileLoadError as exc:
        print(f"PaperAlign profile error: {exc}", file=sys.stderr)
        return 2
    except DocxAnalysisError as exc:
        print(f"PaperAlign analysis failed [{exc.code}]: {exc.message}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"PaperAlign could not access input or write artifacts: {exc}", file=sys.stderr)
        return 3
