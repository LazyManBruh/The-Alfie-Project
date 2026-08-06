"""Base class for skills"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class Skill(ABC):
    """Base class for all skills"""
    name: str = "base"

    def __init__(self, context: Optional[Dict[str, Any]] = None):
        self.context = context or {}

    def matches(self, text: str) -> bool:
        """Return True if this skill should handle the given utterance."""
        return False

    @abstractmethod
    def handle(self, text: str) -> str:
        """Handle the utterance and return a response to be spoken back."""
        ...
