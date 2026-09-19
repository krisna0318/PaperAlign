from dataclasses import dataclass
from pathlib import PurePosixPath

from app.parsers.docx_package import DocxPackage
from app.parsers.namespaces import NS
from app.parsers.xml_utils import parse_xml


@dataclass(frozen=True)
class ContentTypeMap:
    defaults: dict[str, str]
    overrides: dict[str, str]

    def for_part(self, part_name: str) -> str | None:
        override = self.overrides.get(part_name)
        if override is not None:
            return override
        return self.defaults.get(PurePosixPath(part_name).suffix.lstrip(".").casefold())

    @property
    def macro_enabled(self) -> bool:
        return any("macroenabled" in value.casefold() for value in self.overrides.values())


def parse_content_types(package: DocxPackage) -> ContentTypeMap:
    root = parse_xml(package.read_part("[Content_Types].xml"), "[Content_Types].xml")
    defaults: dict[str, str] = {
        element.get("Extension", "").casefold(): element.get("ContentType", "")
        for element in root.findall("./ct:Default", namespaces=NS)
        if element.get("Extension")
    }
    overrides: dict[str, str] = {
        element.get("PartName", "").lstrip("/"): element.get("ContentType", "")
        for element in root.findall("./ct:Override", namespaces=NS)
        if element.get("PartName")
    }
    return ContentTypeMap(defaults=defaults, overrides=overrides)
