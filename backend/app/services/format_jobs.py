from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from app.domain.diagnostic_jobs import DiagnosticJobView
from app.domain.enums import JobStatus
from app.domain.formatting import FormatJobResult, FormattingReport
from app.domain.jobs import ArtifactReference
from app.formatting.safe_formatter import format_docx
from app.parsers.docx_package import sha256_file
from app.parsers.errors import DocxAnalysisError
from app.services.diagnostic_jobs import (
    DiagnosticJobError,
    get_diagnostic_job,
    save_diagnostic_job,
)
from app.services.template_inspector import _write_text


def format_job(data_dir: Path, job_id: str, approved_rule_ids: list[str]) -> FormatJobResult:
    root = data_dir.resolve()
    view = get_diagnostic_job(root, job_id)
    if view.job.status not in {JobStatus.AWAITING_CONFIRMATION, JobStatus.COMPLETED}:
        raise DiagnosticJobError("job_not_ready", "任务尚未完成只读诊断。", job_id=job_id)
    input_artifact = next(
        (item for item in view.job.artifacts if item.kind == "input_copy"), None
    )
    if input_artifact is None:
        raise DiagnosticJobError("job_input_missing", "任务输入副本不存在。", job_id=job_id)
    input_path = (root / input_artifact.relative_path).resolve()
    if not input_path.is_relative_to(root) or not input_path.is_file():
        raise DiagnosticJobError("job_input_missing", "任务输入副本不存在。", job_id=job_id)
    artifact_dir = root / "jobs" / job_id / "artifacts"
    output_path = artifact_dir / "PaperAlign-formatted.docx"
    report_path = artifact_dir / "formatting_report.json"
    plan_path = artifact_dir / "formatting_plan.json"

    if output_path.is_file() and report_path.is_file():
        try:
            report = FormattingReport.model_validate_json(report_path.read_text(encoding="utf-8"))
            if set(report.applied_rule_ids) != set(approved_rule_ids):
                raise DiagnosticJobError(
                    "format_approval_changed",
                    "该任务已有使用另一组规则生成的排版副本。",
                    job_id=job_id,
                )
            return FormatJobResult(
                job_id=job_id,
                output_artifact=output_path.relative_to(root).as_posix(),
                report=report,
            )
        except (OSError, ValidationError) as exc:
            raise DiagnosticJobError(
                "format_result_unreadable", "已有排版结果无法读取。", job_id=job_id
            ) from exc

    try:
        plan, report = format_docx(input_path, output_path, approved_rule_ids)
    except DocxAnalysisError as exc:
        raise DiagnosticJobError(exc.code, exc.message, job_id=job_id) from exc
    _write_text(plan_path, plan.model_dump_json(indent=2) + "\n")
    _write_text(report_path, report.model_dump_json(indent=2) + "\n")
    artifacts = [
        *view.job.artifacts,
        _artifact(root, "formatting_plan", plan_path),
        _artifact(root, "formatting_report", report_path),
        _artifact(root, "formatted_docx", output_path),
    ]
    updated_job = view.job.model_copy(
        update={
            "status": JobStatus.COMPLETED,
            "updated_at": datetime.now(UTC),
            "artifacts": artifacts,
        }
    )
    save_diagnostic_job(root, DiagnosticJobView(job=updated_job, summary=view.summary))
    return FormatJobResult(
        job_id=job_id,
        output_artifact=output_path.relative_to(root).as_posix(),
        report=report,
    )


def resolve_formatted_output(data_dir: Path, job_id: str) -> Path:
    root = data_dir.resolve()
    view = get_diagnostic_job(root, job_id)
    artifact = next(
        (item for item in view.job.artifacts if item.kind == "formatted_docx"), None
    )
    if artifact is None:
        raise DiagnosticJobError("format_result_not_found", "尚未生成排版副本。", job_id=job_id)
    path = (root / artifact.relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise DiagnosticJobError("format_result_not_found", "排版副本不存在。", job_id=job_id)
    return path


def _artifact(root: Path, kind: str, path: Path) -> ArtifactReference:
    return ArtifactReference(
        kind=kind,
        relative_path=path.relative_to(root).as_posix(),
        sha256=sha256_file(path),
    )
