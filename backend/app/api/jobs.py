from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.domain.delivery import DeliveryValidationRequest, DeliveryValidationResult
from app.domain.diagnostic_jobs import DiagnosticJobView
from app.domain.formatting import FormatJobRequest, FormatJobResult
from app.services.delivery_jobs import resolve_downloadable_artifact, validate_job
from app.services.diagnostic_jobs import (
    MAX_UPLOAD_BYTES,
    DiagnosticJobError,
    create_diagnostic_job,
    get_diagnostic_job,
)
from app.services.format_jobs import format_job, resolve_formatted_output
from app.settings import Settings, get_settings

router = APIRouter(prefix="/api/jobs", tags=["diagnostic jobs"])


@router.post("", response_model=DiagnosticJobView, status_code=status.HTTP_201_CREATED)
async def create_job(
    request: Request,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiagnosticJobView:
    declared_size = request.headers.get("content-length")
    if declared_size and declared_size.isdigit() and int(declared_size) > MAX_UPLOAD_BYTES:
        _raise_http(DiagnosticJobError("upload_too_large", "文件超过 50 MB 限制。"))
    payload = bytearray()
    async for chunk in request.stream():
        payload.extend(chunk)
        if len(payload) > MAX_UPLOAD_BYTES:
            _raise_http(DiagnosticJobError("upload_too_large", "文件超过 50 MB 限制。"))
    try:
        return await run_in_threadpool(
            create_diagnostic_job, settings.data_dir, filename, bytes(payload)
        )
    except DiagnosticJobError as exc:
        _raise_http(exc)


@router.get("/{job_id}", response_model=DiagnosticJobView)
def read_job(
    job_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DiagnosticJobView:
    try:
        return get_diagnostic_job(settings.data_dir, job_id)
    except DiagnosticJobError as exc:
        _raise_http(exc)


@router.post("/{job_id}/format", response_model=FormatJobResult)
async def create_formatted_copy(
    job_id: str,
    body: FormatJobRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FormatJobResult:
    try:
        return await run_in_threadpool(
            format_job, settings.data_dir, job_id, body.approved_rule_ids
        )
    except DiagnosticJobError as exc:
        _raise_http(exc)


@router.get("/{job_id}/download")
def download_formatted_copy(
    job_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    try:
        path = resolve_formatted_output(settings.data_dir, job_id)
        return FileResponse(
            path,
            media_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            filename="PaperAlign-formatted.docx",
        )
    except DiagnosticJobError as exc:
        _raise_http(exc)


@router.post("/{job_id}/validate", response_model=DeliveryValidationResult)
async def validate_formatted_copy(
    job_id: str,
    body: DeliveryValidationRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DeliveryValidationResult:
    try:
        return await run_in_threadpool(
            validate_job,
            settings.data_dir,
            job_id,
            render_with_word=body.render_with_word,
        )
    except DiagnosticJobError as exc:
        _raise_http(exc)


@router.get("/{job_id}/artifacts/{kind}")
def download_job_artifact(
    job_id: str,
    kind: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    try:
        path, media_type = resolve_downloadable_artifact(settings.data_dir, job_id, kind)
        return FileResponse(path, media_type=media_type, filename=path.name)
    except DiagnosticJobError as exc:
        _raise_http(exc)


def _raise_http(exc: DiagnosticJobError) -> NoReturn:
    code_to_status = {
        "invalid_filename": status.HTTP_400_BAD_REQUEST,
        "unsupported_file_type": status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        "empty_upload": status.HTTP_400_BAD_REQUEST,
        "upload_too_large": status.HTTP_413_CONTENT_TOO_LARGE,
        "invalid_job_id": status.HTTP_400_BAD_REQUEST,
        "job_not_found": status.HTTP_404_NOT_FOUND,
        "job_unreadable": status.HTTP_500_INTERNAL_SERVER_ERROR,
    }
    raise HTTPException(
        status_code=code_to_status.get(exc.code, status.HTTP_422_UNPROCESSABLE_CONTENT),
        detail={"code": exc.code, "message": exc.message, "job_id": exc.job_id},
    ) from exc
