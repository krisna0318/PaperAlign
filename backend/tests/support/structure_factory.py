from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZipFile

from tests.support.docx_factory import create_synthetic_docx, write_deterministic_zip


def paragraph(text: str, *, style: str | None = None, properties: str = "", runs: str = "") -> str:
    style_xml = f'<w:pStyle w:val="{escape(style)}"/>' if style else ""
    return (
        f"<w:p><w:pPr>{style_xml}{properties}</w:pPr>"
        f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r>{runs}</w:p>'
    )


def structured_docx(path: Path, parts: list[str]) -> Path:
    create_synthetic_docx(path)
    with ZipFile(path) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    entries["word/document.xml"] = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
        "<w:body>"
        + "".join(parts)
        + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/></w:sectPr></w:body></w:document>'
    ).encode()
    extra_styles = "".join(
        f'<w:style w:type="paragraph" w:styleId="{name}"><w:name w:val="{name}"/>'
        '<w:basedOn w:val="Normal"/></w:style>'
        for name in ("Heading2", "Heading3", "Heading4", "TOC1", "Caption", "英文摘要标题")
    )
    entries["word/styles.xml"] = entries["word/styles.xml"].replace(
        b"</w:styles>", (extra_styles + "</w:styles>").encode()
    )
    write_deterministic_zip(path, entries)
    return path
