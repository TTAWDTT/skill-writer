"""
Skill overlay wrapper for session-scoped prompt augmentation.
"""
from typing import Dict, Any, List, Optional

from backend.core.skills.base import BaseSkill, Section, RequirementField, SkillMetadata


class OverlaySkill(BaseSkill):
    """Session-scoped overlay that augments an existing skill without persisting."""

    def __init__(self, base_skill: BaseSkill, overlay: Optional[Dict[str, Any]] = None):
        super().__init__()
        self._base = base_skill
        self._overlay = overlay or {}

    @property
    def metadata(self) -> SkillMetadata:
        return self._base.metadata

    @property
    def structure(self) -> List[Section]:
        return self._base.structure

    @property
    def requirement_fields(self) -> List[RequirementField]:
        return self._base.requirement_fields

    @property
    def writing_guidelines(self) -> str:
        additions = (self._overlay.get("writing_guidelines_additions") or "").strip()
        principles = self._overlay.get("global_principles") or []
        material_context = (self._overlay.get("material_context") or "").strip()
        if not additions and not principles and not material_context:
            return self._base.writing_guidelines

        parts = [self._base.writing_guidelines.rstrip()]
        if additions:
            parts.append("\n\n## 补充写作规范\n" + additions)
        if principles:
            bullets = "\n".join(f"- {p}" for p in principles if str(p).strip())
            if bullets:
                parts.append("\n\n## 额外写作准则\n" + bullets)
        if material_context:
            parts.append("\n\n## 材料事实摘要\n" + material_context)
        return "".join(parts).strip()

    @property
    def evaluation_criteria(self) -> str:
        return self._base.evaluation_criteria

    def get_section_prompt(self, section: Section, context: Dict[str, Any]) -> str:
        section_prompts = self._overlay.get("section_prompt_overrides") or {}
        if isinstance(section_prompts, list):
            section_prompts = {item.get("id"): item.get("prompt") for item in section_prompts if isinstance(item, dict)}

        base_prompt = section_prompts.get(section.id) or self._base.get_section_prompt(section, context)
        section_overrides = self._overlay.get("section_overrides") or {}
        if isinstance(section_overrides, list):
            section_overrides = {item.get("id"): item.get("extra") for item in section_overrides if isinstance(item, dict)}

        extra = section_overrides.get(section.id) if isinstance(section_overrides, dict) else None
        extra_text = (extra or "").strip()
        principles = self._overlay.get("global_principles") or []
        principle_text = "\n".join(f"- {p}" for p in principles if str(p).strip())
        material_context = (self._overlay.get("material_context") or "").strip()

        if not extra_text and not principle_text and not material_context:
            return base_prompt

        additions = []
        if extra_text:
            additions.append("## 本节补充要求\n" + extra_text)
        if principle_text:
            additions.append("## 写作准则\n" + principle_text)
        if material_context:
            additions.append("## 材料事实摘要\n" + material_context)

        return base_prompt.rstrip() + "\n\n" + "\n\n".join(additions)

    def validate_section(self, section: Section, content: str) -> Dict[str, Any]:
        return self._base.validate_section(section, content)


def apply_skill_overlay(skill: BaseSkill, overlay: Optional[Dict[str, Any]]) -> BaseSkill:
    if not overlay:
        return skill
    return OverlaySkill(skill, overlay)
