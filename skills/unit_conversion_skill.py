"""Unit conversion skill, via pint's unit registry (handles aliases like
"kg"/"kilograms", offset units like temperature, etc. without a hand-rolled
conversion table)."""

import re
from .base import Skill
from loguru import logger

try:
    from pint import UnitRegistry
    _ureg = UnitRegistry()
except ImportError:
    _ureg = None

_CONVERT_RE = re.compile(
    r"(?:convert\s+)?(\d+(?:\.\d+)?)\s*([a-zA-Z°]+)\s+(?:to|in|into)\s+([a-zA-Z°]+)"
)


class UnitConversionSkill(Skill):
    name = "unit_conversion"

    def matches(self, text: str) -> bool:
        if _ureg is None:
            return False
        match = _CONVERT_RE.search(text.lower())
        if not match:
            return False
        _, from_unit, to_unit = match.groups()
        # The regex alone is too permissive - "remind me in 5 minutes to check
        # the oven" also has the "<number> <word> to <word>" shape. Requiring
        # both sides to actually be units pint recognizes rules that out
        # without needing to hardcode "check"/"oven"/etc as exclusions.
        return self._is_valid_unit(from_unit) and self._is_valid_unit(to_unit)

    def _is_valid_unit(self, unit_str: str) -> bool:
        try:
            _ureg.Unit(unit_str)
            return True
        except Exception:
            return False

    def handle(self, text: str) -> str:
        match = _CONVERT_RE.search(text.lower())
        if not match:
            return "I couldn't understand that conversion, sir."
        amount, from_unit, to_unit = match.groups()
        try:
            quantity = _ureg.Quantity(float(amount), from_unit)
            converted = quantity.to(to_unit)
        except Exception as e:
            logger.info(f"unit conversion failed for {from_unit!r} -> {to_unit!r}: {e}")
            return f"I don't know how to convert {from_unit} to {to_unit}, sir."

        value = round(converted.magnitude, 2)
        if value == int(value):
            value = int(value)
        return f"That's about {value} {to_unit}, sir."
