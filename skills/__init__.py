"""Skill manager for loading and routing skills"""

import importlib
import pkgutil
from typing import Any, Dict, List, Optional
from loguru import logger

from .base import Skill


class SkillManager:
    def __init__(self, enabled_skills: Optional[List[str]] = None, context: Optional[Dict[str, Any]] = None):
        """
        :param enabled_skills: names of skills to load; if None, all discovered skills are loaded
        :param context: shared objects skills may need (e.g. a `speak` callback for the timer skill)
        """
        self.context = context or {}
        self.skills: Dict[str, Skill] = {}
        self._load_skills(enabled_skills)

    def _load_skills(self, enabled_skills: Optional[List[str]]):
        for _, module_name, is_pkg in pkgutil.iter_modules(__path__):
            if is_pkg or module_name == "base":
                continue
            if enabled_skills is not None and module_name.replace("_skill", "") not in enabled_skills:
                continue
            try:
                module = importlib.import_module(f".{module_name}", package=__name__)
                class_name = "".join(part.capitalize() for part in module_name.split("_"))
                skill_class = getattr(module, class_name, None)
                if skill_class is None or not issubclass(skill_class, Skill):
                    continue
                instance = skill_class(context=self.context)
                self.skills[instance.name] = instance
                logger.info(f"Loaded skill: {instance.name}")
            except Exception as e:
                logger.error(f"Failed to load skill module {module_name}: {e}")

    def route(self, text: str) -> Optional[str]:
        """Try each loaded skill against the utterance; return the first match's response,
        or None if no skill claims it (caller should fall back to the LLM)."""
        for skill in self.skills.values():
            try:
                if skill.matches(text):
                    return skill.handle(text)
            except Exception:
                logger.exception(f"Error running skill {skill.name}")
                return f"Sorry, I hit an error with the {skill.name} skill."
        return None

    def list_skills(self) -> List[str]:
        return list(self.skills.keys())
