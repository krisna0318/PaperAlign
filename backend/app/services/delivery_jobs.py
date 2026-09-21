from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from app.domain.delivery import DeliveryValidationResult
from app.domain.diagnostic_jobs import DiagnosticJobView
from app.domain.enums import JobStatus
from app.domain.formatting import FormattingReport
from app.domain.jobs import ArtifactReference
from app.parsers.docx_package import sha256_file
from app.services.delivery_validation import render_delivery_checklist, validate_delivery
from app.services.diagnostic_jobs import (
    DiagnosticJobError,
    get_diagnostic_job,
    save_diagnostic_job,
)
from app.services.template_inspector import _write_text

DOWNLOADABLE_KINDS = {
    "formatted_docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "delivery_checklist": "text/markdown; charset=utf-8",
    "delivery_validation": "application/json",
    "word_pdf": "application/pdf",
}


def validate_job(
    data_dir: Path, job_id: str, *, render_with_word: bool = False
) -> DeliveryValidationResult:
    root = data_dir.resolve()
    view = get_diagnostic_job(root, job_id)
    original = _artifact_path(root, view, "input_copy")
    formatted = _artifact_path(root, view, "formatted_docx")
    formatting_report_path = _artifact_path(root, view, "formatting_report")
    try:
        formatting_report = FormattingReport.model_validate_json(
            formatting_report_path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        raise DiagnosticJobError(
            "format_result_unreadable", "排版报告无法读取。", job_id=job_id
        ) from exc
    artifact_dir = root / "jobs" / job_id / "artifacts"
    pdf_path = artifact_dir / "PaperAlign-word-preview.pdf"
    report = validate_delivery(
        original,
        formatted,
        formatting_report,
        job_id=job_id,
        render_with_word=render_with_word,
        pdf_path=pdf_path if render_with_word else None,
    )
    report_path = artifact_dir / "delivery_validation.json"
    checklist_path = artifact_dir / "delivery_checklist.md"
    _write_text(report_path, report.model_dump_json(indent=2) + "\n")
    _write_text(checklist_path, render_delivery_checklist(report))
    new_artifacts = [
        _artifact(root, "delivery_validation", report_path),
        _artifact(root, "delivery_checklist", checklist_path),
    ]
    pdf_artifact = None
    if report.word_render.status == "passed" and pdf_path.is_file():
        new_artifacts.append(_artifact(root, "word_pdf", pdf_path))
        pdf_artifact = pdf_path.relative_to(root).as_posix()
    replaced_kinds = {item.kind for item in new_artifacts}
    artifacts = [item for item in view.job.artifacts if item.kind not in replaced_kinds]
    artifacts.extend(new_artifacts)
    updated = view.job.model_copy(
        update={
            "status": JobStatus.COMPLETED,
            "updated_at": datetime.now(UTC),
            "artifacts": artifacts,
        }
    )
    save_diagnostic_job(root, DiagnosticJobView(job=updated, summary=view.summary))
    return DeliveryValidationResult(
        job_id=job_id,
        report=report,
        checklist_artifact=checklist_path.relative_to(root).as_posix(),
        pdf_artifact=pdf_artifact,
    )


def resolve_downloadable_artifact(data_dir: Path, job_id: str, kind: str) -> tuple[Path, str]:
    if kind not in DOWNLOADABLE_KINDS:
        raise DiagnosticJobError("unknown_artifact", "不支持下载该产物。", job_id=job_id)
    root = data_dir.resolve()
    view = get_diagnostic_job(root, job_id)
    path = _artifact_path(root, view, kind)
    return path, DOWNLOADABLE_KINDS[kind]


def _artifact_path(root: Path, view: DiagnosticJobView, kind: str) -> Path:
    artifact = next((item for item in view.job.artifacts if item.kind == kind), None)
    if artifact is None:
        raise DiagnosticJobError(
            "artifact_not_found", f"任务产物不存在：{kind}", job_id=view.job.id
        )
    path = (root / artifact.relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise DiagnosticJobError(
            "artifact_not_found", f"任务产物不存在：{kind}", job_id=view.job.id
        )
    return path


def _artifact(root: Path, kind: str, path: Path) -> ArtifactReference:
    return ArtifactReference(
        kind=kind,
        relative_path=path.relative_to(root).as_posix(),
        sha256=sha256_file(path),
    )
