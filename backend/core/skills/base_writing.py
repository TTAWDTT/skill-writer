"""
BaseWritingSkill integration.

This module provides a lightweight composition wrapper that prepends a global
"meta writing skill" (BaseWritingSkill) to every concrete skill's guidelines and
evaluation rubric, without changing the underlying skill files.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.core.skills.base import BaseSkill, Section, RequirementField, SkillMetadata


class BaseWritingAugmentedSkill(BaseSkill):
    """
    Compose a concrete skill with a global BaseWritingSkill.

    - metadata/structure/fields come from the concrete skill
    - writing_guidelines/evaluation_criteria are merged (base first)
    - prompts/validation behavior are delegated to the concrete skill
    """

    def __init__(self, base_writing: BaseSkill, concrete: BaseSkill):
        super().__init__()
        self._base = base_writing
        self._concrete = concrete

    @property
    def metadata(self) -> SkillMetadata:
        return self._concrete.metadata

    @property
    def structure(self) -> List[Section]:
        return self._concrete.structure

    @property
    def requirement_fields(self) -> List[RequirementField]:
        return self._concrete.requirement_fields

    @property
    def writing_guidelines(self) -> str:
        base = (self._base.writing_guidelines or "").strip()
        concrete = (self._concrete.writing_guidelines or "").strip()
        if not base:
            return concrete
        if not concrete:
            return base
        return f"{base}\n\n---\n\n{concrete}\n"

    @property
    def evaluation_criteria(self) -> str:
        base = (self._base.evaluation_criteria or "").strip()
        concrete = (self._concrete.evaluation_criteria or "").strip()
        if not base:
            return concrete
        if not concrete:
            return base
        return f"{base}\n\n---\n\n{concrete}\n"

    def get_section_prompt(self, section: Section, context: Dict[str, Any]) -> str:
        return self._concrete.get_section_prompt(section, context)

    def validate_section(self, section: Section, content: str) -> Dict[str, Any]:
        return self._concrete.validate_section(section, content)

