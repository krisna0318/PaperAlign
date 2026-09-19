W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
OFFICE = "urn:schemas-microsoft-com:office:office"
V = "urn:schemas-microsoft-com:vml"

NS = {
    "w": W,
    "r": R,
    "pr": PKG_REL,
    "ct": CONTENT_TYPES,
    "mc": MC,
    "m": M,
    "o": OFFICE,
    "v": V,
}


def qn(namespace: str, local_name: str) -> str:
    return f"{{{namespace}}}{local_name}"
