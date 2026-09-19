from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Default Extension="bin" ContentType="application/octet-stream"/>
  <Default Extension="html" ContentType="text/html"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
  <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
  <Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
  {extra_overrides}
</Types>
"""

ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
  </w:style>
</w:styles>
"""

HEADER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p><w:r><w:t>华南农业大学本科毕业论文</w:t></w:r></w:p>
</w:hdr>
"""

FOOTER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>
    <w:r><w:fldChar w:fldCharType="begin"/></w:r>
    <w:r><w:instrText> PAGE </w:instrText></w:r>
    <w:r><w:fldChar w:fldCharType="separate"/></w:r>
    <w:r><w:t>1</w:t></w:r>
    <w:r><w:fldChar w:fldCharType="end"/></w:r>
  </w:p>
</w:ftr>
"""

FOOTNOTES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:footnote w:id="1"><w:p><w:r><w:t>合成脚注</w:t></w:r></w:p></w:footnote>
</w:footnotes>
"""

PNG_1X1 = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
)


def create_synthetic_docx(
    path: Path,
    *,
    heading_text: str = "1 绪论",
    body_text: str = "这是用于测试的论文正文。",
    font_name: str = "宋体",
    include_unsupported: bool = False,
    include_three_line_table: bool = False,
) -> Path:
    extra_body = ""
    extra_relationships = ""
    extra_overrides = ""
    extra_parts: dict[str, bytes | str] = {}

    if include_unsupported:
        extra_body = """
    <w:altChunk r:id="rIdChunk"/>
    <w:p><w:sdt><w:sdtContent><w:r><w:t>内容控件</w:t></w:r></w:sdtContent></w:sdt></w:p>
"""
        extra_relationships = """
  <Relationship Id="rIdExternal" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://example.com" TargetMode="External"/>
  <Relationship Id="rIdEmbed" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/package" Target="embeddings/object1.bin"/>
  <Relationship Id="rIdChunk" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/aFChunk" Target="afchunk1.html"/>
  <Relationship Id="rIdVba" Type="http://schemas.microsoft.com/office/2006/relationships/vbaProject" Target="vbaProject.bin"/>
"""
        extra_overrides = """
  <Override PartName="/word/vbaProject.bin" ContentType="application/vnd.ms-office.vbaProject"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.ms-word.document.macroEnabled.main+xml"/>
"""
        extra_parts = {
            "word/embeddings/object1.bin": b"synthetic embedded object",
            "word/afchunk1.html": "<p>Imported HTML</p>",
            "word/vbaProject.bin": b"synthetic macro bytes",
        }

    table_properties = ""
    first_row_cell_properties = ""
    second_row = ""
    if include_three_line_table:
        table_properties = """
      <w:tblPr>
        <w:tblStyle w:val="NormalTable"/>
        <w:jc w:val="center"/>
        <w:tblBorders>
          <w:top w:val="single" w:sz="12" w:color="auto"/>
          <w:left w:val="none" w:sz="0" w:color="auto"/>
          <w:bottom w:val="single" w:sz="12" w:color="auto"/>
          <w:right w:val="none" w:sz="0" w:color="auto"/>
          <w:insideH w:val="none" w:sz="0" w:color="auto"/>
          <w:insideV w:val="none" w:sz="0" w:color="auto"/>
        </w:tblBorders>
      </w:tblPr>
"""
        first_row_cell_properties = """
          <w:tcPr><w:tcBorders><w:top w:val="single" w:sz="12"/><w:bottom w:val="single" w:sz="8"/></w:tcBorders></w:tcPr>
"""
        second_row = """
      <w:tr>
        <w:tc><w:tcPr><w:tcBorders><w:top w:val="single" w:sz="8"/><w:bottom w:val="single" w:sz="12"/></w:tcBorders></w:tcPr><w:p><w:r><w:t>样本</w:t></w:r></w:p></w:tc>
        <w:tc><w:tcPr><w:tcBorders><w:top w:val="single" w:sz="8"/><w:bottom w:val="single" w:sz="12"/></w:tcBorders></w:tcPr><w:p><w:r><w:t>1</w:t></w:r></w:p></w:tc>
      </w:tr>
"""

    document = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
  <w:body>
    <w:p>
      <w:pPr><w:pStyle w:val="Heading1"/><w:jc w:val="left"/></w:pPr>
      <w:r><w:rPr><w:rFonts w:eastAsia="{escape(font_name)}" w:ascii="Times New Roman"/><w:sz w:val="24"/><w:b/></w:rPr><w:t>{escape(heading_text)}</w:t></w:r>
    </w:p>
    <w:p>
      <w:r><w:t>{escape(body_text)}</w:t></w:r>
      <w:fldSimple w:instr=" REF _Ref1 "><w:r><w:t>图1</w:t></w:r></w:fldSimple>
      <w:r><w:drawing><wp:inline><a:graphic><a:graphicData><pic:pic><pic:blipFill><a:blip r:embed="rIdImage"/></pic:blipFill></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>
    </w:p>
    <w:tbl>
      {table_properties}
      <w:tr>
        <w:tc>{first_row_cell_properties}<w:p><w:r><w:t>指标</w:t></w:r></w:p></w:tc>
        <w:tc>{first_row_cell_properties}<w:p><w:r><w:t>结果</w:t></w:r></w:p></w:tc>
      </w:tr>
      {second_row}
    </w:tbl>
    {extra_body}
    <w:sectPr>
      <w:headerReference w:type="default" r:id="rIdHeader"/>
      <w:footerReference w:type="default" r:id="rIdFooter"/>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/>
      <w:pgNumType w:fmt="decimal" w:start="1"/>
    </w:sectPr>
  </w:body>
</w:document>
"""

    document_rels = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rIdHeader" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
  <Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
  <Relationship Id="rIdImage" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image1.png"/>
  <Relationship Id="rIdFootnotes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>
  {extra_relationships}
</Relationships>
"""

    parts: dict[str, bytes | str] = {
        "[Content_Types].xml": CONTENT_TYPES.format(extra_overrides=extra_overrides),
        "_rels/.rels": ROOT_RELS,
        "word/document.xml": document,
        "word/_rels/document.xml.rels": document_rels,
        "word/styles.xml": STYLES,
        "word/header1.xml": HEADER,
        "word/footer1.xml": FOOTER,
        "word/footnotes.xml": FOOTNOTES,
        "word/media/image1.png": PNG_1X1,
        **extra_parts,
    }
    write_deterministic_zip(path, parts)
    return path


def write_deterministic_zip(path: Path, parts: dict[str, bytes | str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w") as archive:
        for name, content in sorted(parts.items()):
            info = ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            data = content.encode("utf-8") if isinstance(content, str) else content
            archive.writestr(info, data)
