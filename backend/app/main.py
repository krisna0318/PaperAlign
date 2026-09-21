from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import __version__
from app.api.jobs import router as jobs_router
from app.settings import get_settings


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    stage: str


settings = get_settings()
app = FastAPI(
    title="PaperAlign API",
    description="Explainable thesis analysis and safe formatting API",
    version=__version__,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(jobs_router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="paperalign-api",
        version=__version__,
        stage="M6",
    )
