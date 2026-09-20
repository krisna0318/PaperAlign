from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app import __version__
from app.ai.deepseek_responses import DeepSeekResponsesProvider
from app.ai.openai_responses import OpenAIResponsesProvider
from app.domain.enums import AiMode
from app.parsers.errors import DocxAnalysisError
from app.profiles.loader import ProfileLoadError, check_applicability, load_profile
from app.services.ai_review import write_ai_review_plan
from app.services.ai_runner import load_ai_review_plan, write_ai_review_run
from app.services.analyzer import analyze_docx, write_artifacts
from app.services.evaluation import write_evaluation_report, write_gold_set_template
from app.services.format_audit import write_format_audit
from app.services.profile_service import export_profile, verify_template_samples
from app.services.structure_service import write_structure_review
from app.services.template_inspector import inspect_template, write_template_artifacts
from app.settings import get_settings


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
    ai_review = subparsers.add_parser(
        "prepare-ai-review",
        help="prepare private M4 prompt packets without contacting a model",
    )
    ai_review.add_argument("input", type=Path)
    ai_review.add_argument("--out", type=Path, required=True, help="directory under .paperalign")
    ai_review.add_argument("--mode", choices=("hybrid", "prompt_only"), default="hybrid")
    ai_review.add_argument("--context-radius", type=int, choices=(0, 1, 2), default=2)
    ai_review.add_argument("--max-characters", type=int, default=240)
    run_ai = subparsers.add_parser(
        "run-ai-review",
        help="send an inspected private review plan to the configured cloud model",
    )
    run_ai.add_argument("plan", type=Path, help="ai_review_plan.json under .paperalign")
    run_ai.add_argument("--out", type=Path, required=True, help="directory under .paperalign")
    run_ai.add_argument(
        "--confirm-send-cloud",
        action="store_true",
        help="confirm that bounded thesis snippets may be sent to the configured provider",
    )
    gold_set = subparsers.add_parser(
        "prepare-gold-set",
        help="create a hash-bound human annotation template from an AI review plan",
    )
    gold_set.add_argument("plan", type=Path, help="ai_review_plan.json under .paperalign")
    gold_set.add_argument("--out", type=Path, required=True, help="directory under .paperalign")
    evaluate = subparsers.add_parser(
        "evaluate-ai-review",
        help="compare rules and model proposals against confirmed human labels",
    )
    evaluate.add_argument("plan", type=Path)
    evaluate.add_argument("gold_set", type=Path)
    evaluate.add_argument("run", type=Path)
    evaluate.add_argument("--out", type=Path, required=True, help="directory under .paperalign")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "evaluate-ai-review":
            report = write_evaluation_report(
                args.plan,
                args.gold_set,
                args.run,
                args.out,
            )
            print(
                f"Evaluation {report.status}: {report.evaluated_count}/{report.target_count} "
                "human-confirmed targets"
            )
            print(f"Summary: {args.out.resolve() / 'evaluation_summary.md'}")
            return 0
        if args.command == "prepare-gold-set":
            gold_set = write_gold_set_template(args.plan, args.out)
            print(f"Gold Set template prepared: {gold_set.target_count} targets")
            print("No labels were inferred; human annotation is required")
            print(f"Template: {args.out.resolve() / 'gold_set.template.json'}")
            return 0
        if args.command == "run-ai-review":
            settings = get_settings()
            if settings.ai_mode == AiMode.OFF:
                raise DocxAnalysisError("ai_disabled", "Set PAPERALIGN_AI_MODE before cloud review")
            plan = load_ai_review_plan(args.plan)
            expected_mode = "hybrid" if settings.ai_mode == AiMode.AMBIGUOUS_ONLY else "prompt_only"
            if plan.mode != expected_mode:
                raise DocxAnalysisError(
                    "ai_mode_mismatch",
                    f"Configured AI mode requires a {expected_mode} review plan",
                )
            if settings.ai_api_key is None or settings.ai_model is None:
                raise DocxAnalysisError(
                    "missing_ai_configuration", "AI API key and model are required"
                )
            provider: OpenAIResponsesProvider
            if settings.ai_provider == "deepseek_responses":
                provider = DeepSeekResponsesProvider(
                    api_key=settings.ai_api_key.get_secret_value(),
                    model=settings.ai_model,
                    base_url=settings.ai_base_url or "https://api.deepseek.com",
                    timeout_seconds=settings.ai_timeout_seconds,
                    max_output_tokens=settings.ai_max_output_tokens,
                    input_cost_per_million=settings.ai_input_cost_per_million,
                    output_cost_per_million=settings.ai_output_cost_per_million,
                )
            else:
                provider = OpenAIResponsesProvider(
                    api_key=settings.ai_api_key.get_secret_value(),
                    model=settings.ai_model,
                    base_url=settings.ai_base_url or "https://api.openai.com/v1",
                    timeout_seconds=settings.ai_timeout_seconds,
                    max_output_tokens=settings.ai_max_output_tokens,
                    input_cost_per_million=settings.ai_input_cost_per_million,
                    output_cost_per_million=settings.ai_output_cost_per_million,
                )
            run = write_ai_review_run(
                args.plan,
                args.out,
                provider,
                confirmed_cloud_send=args.confirm_send_cloud,
                max_retries=settings.ai_max_retries,
            )
            print(
                f"Cloud review {run.status}: {run.completed_count} completed, "
                f"{run.failed_count} failed, {run.total_tokens} tokens"
            )
            print("Model proposals only; formatting_allowed=false; rules-only fallback remains")
            print(f"Result: {args.out.resolve() / 'ai_review_run.json'}")
            return 0 if run.status != "failed" else 4
        if args.command == "prepare-ai-review":
            plan = write_ai_review_plan(
                args.input,
                args.out,
                mode=args.mode,
                context_radius=args.context_radius,
                max_characters=args.max_characters,
            )
            print(
                f"AI review prepared: {plan.packet_count} packets, "
                f"{plan.skipped_count} manual-only targets, "
                f"{plan.total_context_characters} private context characters"
            )
            print("No model was contacted; ai_used=false; formatting_allowed=false")
            print(f"Plan: {args.out.resolve() / 'ai_review_plan.json'}")
            return 0
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
