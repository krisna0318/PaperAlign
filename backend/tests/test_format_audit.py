import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from lxml import etree

from app.parsers.effective_format import EffectiveFormatResolver
from app.parsers.errors import DocxAnalysisError
from app.parsers.namespaces import W
from app.services.format_audit import write_format_audit
from tests.support.docx_factory import create_synthetic_docx


def resolve(styles: str, run: str = "", ppr: str = ""):
    resolver = EffectiveFormatResolver(
        etree.fromstring(f'<w:styles xmlns:w="{W}">{styles}</w:styles>'.encode())
    )
    document = etree.fromstring(
        f'<w:document xmlns:w="{W}"><w:body><w:p><w:pPr>{ppr}</w:pPr>'
        f"<w:r><w:rPr>{run}</w:rPr><w:t>Sample</w:t></w:r>"
        "</w:p></w:body></w:document>".encode()
    )
    return resolver.resolve(document)[0]


def test_high_ansi_does_not_override_inherited_ascii() -> None:
    item = resolve(
        "<w:docDefaults><w:rPrDefault><w:rPr>"
        '<w:rFonts w:ascii="Times New Roman"/>'
        "</w:rPr></w:rPrDefault></w:docDefaults>",
        '<w:rFonts w:hAnsi="宋体"/>',
    )
    props = item.runs[0].properties
    assert props.font_latin == "Times New Roman"
    assert props.font_high_ansi == "宋体"
    assert props.sources["font_latin"] == "doc_defaults"


@pytest.mark.parametrize(
    "direct,expected", [("", False), ("<w:b/>", True), ('<w:b w:val="0"/>', False)]
)
def test_style_toggles_and_direct_boolean_override(direct: str, expected: bool) -> None:
    item = resolve(
        '<w:style w:type="paragraph" w:styleId="Base"><w:rPr><w:b/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Child"><w:basedOn w:val="Base"/>'
        "<w:rPr><w:b/></w:rPr></w:style>",
        direct,
        '<w:pStyle w:val="Child"/>',
    )
    assert item.runs[0].properties.bold is expected


def test_theme_font_and_line_based_spacing_are_not_guessed() -> None:
    item = resolve(
        "",
        '<w:rFonts w:ascii="Arial" w:asciiTheme="minorHAnsi"/>',
        '<w:spacing w:after="120" w:afterLines="50"/>',
    )
    assert item.runs[0].properties.font_latin is None
    assert item.runs[0].properties.unresolved["font_latin"] == "theme_font_not_resolved"
    assert item.paragraph.space_after_twips is None
    assert "space_after_twips" in item.paragraph.unresolved


def test_cycle_is_reported_on_affected_paragraph() -> None:
    item = resolve(
        '<w:style w:type="paragraph" w:styleId="A"><w:basedOn w:val="A"/></w:style>',
        ppr='<w:pStyle w:val="A"/>',
    )
    assert any("cycle" in w for w in item.resolution_warnings)


def test_local_audit_preview_is_opt_in_escaped_and_deterministic(tmp_path: Path) -> None:
    source = create_synthetic_docx(
        tmp_path / "audit.docx", heading_text="<script>alert(1)</script>"
    )
    local_root = Path(__file__).resolve().parents[2] / ".paperalign"
    local_root.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=local_root) as temporary:
        output = Path(temporary)
        html_path = write_format_audit(source, output)
        assert all(
            not row["preview"]
            for row in json.loads((output / "format_audit.json").read_text(encoding="utf-8"))
        )
        write_format_audit(source, output, include_preview=True)
        first = html_path.read_bytes()
        assert b"<script>" not in first
        assert b"&lt;script&gt;" in first
        write_format_audit(source, output, include_preview=True)
        assert first == html_path.read_bytes()


def test_audit_rejects_public_output(tmp_path: Path) -> None:
    source = create_synthetic_docx(tmp_path / "audit.docx")
    public_output = Path(__file__).resolve().parents[2] / "public-audit-output"
    with pytest.raises(DocxAnalysisError, match=".paperalign"):
        write_format_audit(source, public_output, include_preview=True)
