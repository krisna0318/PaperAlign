from pathlib import Path

import pytest

from app.parsers.docx_package import DocxPackage
from app.parsers.errors import DocxAnalysisError
from tests.support.docx_factory import create_synthetic_docx, write_deterministic_zip


def test_opens_valid_docx_read_only(tmp_path: Path) -> None:
    input_path = create_synthetic_docx(tmp_path / "synthetic.docx")

    with DocxPackage(input_path) as package:
        assert package.has_part("word/document.xml")
        assert "word/media/image1.png" in package.part_names()
        assert package.inspection is not None
        assert package.inspection.part_count == 9


def test_rejects_non_docx_extension(tmp_path: Path) -> None:
    input_path = tmp_path / "synthetic.zip"
    write_deterministic_zip(input_path, {})

    with pytest.raises(DocxAnalysisError, match=".docx") as error, DocxPackage(input_path):
        pass
    assert error.value.code == "unsupported_extension"


def test_rejects_path_traversal_part(tmp_path: Path) -> None:
    input_path = tmp_path / "unsafe.docx"
    write_deterministic_zip(
        input_path,
        {
            "[Content_Types].xml": "<Types/>",
            "_rels/.rels": "<Relationships/>",
            "word/document.xml": "<document/>",
            "../escape.xml": "<unsafe/>",
        },
    )

    with (
        pytest.raises(DocxAnalysisError, match="Unsafe package part") as error,
        DocxPackage(input_path),
    ):
        pass
    assert error.value.code == "unsafe_part_name"


def test_rejects_missing_required_part(tmp_path: Path) -> None:
    input_path = tmp_path / "missing.docx"
    write_deterministic_zip(
        input_path,
        {
            "[Content_Types].xml": "<Types/>",
            "_rels/.rels": "<Relationships/>",
        },
    )

    with pytest.raises(DocxAnalysisError) as error, DocxPackage(input_path):
        pass
    assert error.value.code == "missing_required_part"
