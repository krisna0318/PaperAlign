from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AiMode, JobStatus


class ArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)
    sha256: str | None = None


class AnalysisJob(BaseModel):
    """Metadata for one local processing job; manuscript text is stored elsewhere."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    status: JobStatus = JobStatus.CREATED
    ai_mode: AiMode = AiMode.OFF
    created_at: datetime
    updated_at: datetime
    input_filename: str = Field(min_length=1)
    input_sha256: str | None = None
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
