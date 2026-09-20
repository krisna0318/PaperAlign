"""Explicit OOXML conversions; unknown line modes stay unknown."""

from app.domain.rules import FixedSpacing, LineSpacing, MultipleSpacing


def twips_to_pt(value: int) -> float:
    return value / 20


def twips_to_mm(value: int) -> float:
    return value * 25.4 / 1440


def hundredths_to_chars(value: int) -> float:
    return value / 100


def ooxml_line_spacing(value: int | None, mode: str | None) -> LineSpacing | None:
    if value is None or value <= 0:
        return None
    if mode == "auto":
        return MultipleSpacing(value=value / 240)
    if mode in {"exact", "atLeast"}:
        return FixedSpacing(
            mode="exact" if mode == "exact" else "at_least", value=twips_to_pt(value)
        )
    return None
