from typing import Literal

from pydantic import Field

from app.domain.rules import ContractModel


class ManualReviewStep(ContractModel):
    order: int = Field(ge=1)
    instruction: str = Field(min_length=1)
    expected_result: str = Field(min_length=1)


class ManualReviewItem(ContractModel):
    id: str = Field(min_length=1)
    category: Literal[
        "final_layout",
        "toc_and_fields",
        "figure_pagination",
        "table_pagination",
        "section_page_numbering",
        "unsupported_objects",
    ]
    title: str = Field(min_length=1)
    customer_notice: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    required: bool = True
    related_block_ids: list[str] = Field(default_factory=list)
    steps: list[ManualReviewStep] = Field(min_length=1)
    acceptance_checks: list[str] = Field(min_length=1)


class ManualReviewGuide(ContractModel):
    schema_version: Literal["1.0"] = "1.0"
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope_statement: str = Field(min_length=1)
    generated_automatically: Literal[True] = True
    word_desktop_required: bool
    items: list[ManualReviewItem] = Field(min_length=1)
