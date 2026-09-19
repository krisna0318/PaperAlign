from lxml import etree

from app.parsers.errors import DocxAnalysisError


def parse_xml(data: bytes, part_name: str) -> etree._Element:
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        recover=False,
        huge_tree=False,
        remove_blank_text=False,
    )
    try:
        return etree.fromstring(data, parser=parser)
    except (etree.XMLSyntaxError, ValueError) as exc:
        raise DocxAnalysisError(
            "invalid_xml",
            f"OOXML part is not valid XML: {part_name}",
        ) from exc
