"""
Generated skill definition validator.

Used to sanity-check template-derived skill configs before writing them to disk.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Set

import jinja2
from jinja2 import meta


_SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_FIELD_ID_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]*$")

_ALLOWED_TEMPLATE_VARS = {
    "section_title",
    "section_id",
    "section_description",
    "section_writing_guide",
    "section_word_limit",
    "section_evaluation_points",
    "written_sections",
    "external_information",
    "requirements",
}


class SkillDefinitionValidationError(ValueError):
    """Raised when a generated skill definition is structurally invalid."""

    def __init__(self, errors: List[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _collect_section_ids(sections: List[Dict[str, Any]], seen: Set[str], errors: List[str], *, path: str = "sections"):
    for index, section in enumerate(sections or []):
        current_path = f"{path}[{index}]"
        section_id = str(section.get("id") or "").strip()
        title = str(section.get("title") or "").strip()

        if not section_id:
            errors.append(f"{current_path}.id 不能为空")
        elif section_id in seen:
            errors.append(f"章节 id 重复：{section_id}")
        else:
            seen.add(section_id)

        if not title:
            errors.append(f"{current_path}.title 不能为空")

        level = section.get("level", 1)
        if not isinstance(level, int) or level < 1:
            errors.append(f"{current_path}.level 必须是 >= 1 的整数")

        word_limit = section.get("word_limit")
        if word_limit is not None:
            if not isinstance(word_limit, list) or len(word_limit) != 2:
                errors.append(f"{current_path}.word_limit 必须是 [min, max]")
            else:
                low, high = word_limit
                if not isinstance(low, int) or not isinstance(high, int) or low < 0 or high < low:
                    errors.append(f"{current_path}.word_limit 数值不合法")

        children = section.get("children") or []
        if children and not isinstance(children, list):
            errors.append(f"{current_path}.children 必须是列表")
        else:
            _collect_section_ids(children, seen, errors, path=f"{current_path}.children")


def _validate_fields(fields: List[Dict[str, Any]], errors: List[str]):
    seen: Set[str] = set()
    for index, field in enumerate(fields or []):
        current_path = f"fields[{index}]"
        field_id = str(field.get("id") or "").strip()
        if not field_id:
            errors.append(f"{current_path}.id 不能为空")
        elif not _FIELD_ID_RE.match(field_id):
            errors.append(f"{current_path}.id 格式不合法：{field_id}")
        elif field_id in seen:
            errors.append(f"字段 id 重复：{field_id}")
        else:
            seen.add(field_id)

        if not str(field.get("name") or "").strip():
            errors.append(f"{current_path}.name 不能为空")

        collection = str(field.get("collection") or "required").strip()
        if collection not in {"required", "optional", "infer"}:
            errors.append(f"{current_path}.collection 不合法：{collection}")

        priority = field.get("priority", 3)
        if not isinstance(priority, int) or priority not in {1, 2, 3}:
            errors.append(f"{current_path}.priority 必须是 1/2/3")


def _validate_section_template(template_text: str, field_ids: Set[str], errors: List[str]):
    if not template_text.strip():
        return

    env = jinja2.Environment()
    try:
        ast = env.parse(template_text)
    except Exception as exc:
        errors.append(f"section_prompt 模板无法解析：{exc}")
        return

    undeclared = meta.find_undeclared_variables(ast)
    allowed = _ALLOWED_TEMPLATE_VARS | field_ids
    unknown = sorted(name for name in undeclared if name not in allowed)
    if unknown:
        errors.append("section_prompt 使用了未声明变量：" + ", ".join(unknown))


def validate_generated_skill_config(config: Dict[str, Any]) -> List[str]:
    """
    Validate generated skill config.

    Returns warnings list when validation passes.
    Raises SkillDefinitionValidationError on hard failures.
    """
    errors: List[str] = []
    warnings: List[str] = []

    skill_id = str(config.get("skill_id") or "").strip()
    if not skill_id:
        errors.append("skill_id 不能为空")
    elif not _SKILL_ID_RE.match(skill_id):
        errors.append(f"skill_id 格式不合法：{skill_id}")

    if not str(config.get("name") or "").strip():
        errors.append("name 不能为空")

    sections = config.get("sections") or []
    if not isinstance(sections, list) or not sections:
        errors.append("sections 不能为空，且必须是列表")
    else:
        _collect_section_ids(sections, set(), errors)

    fields = config.get("fields") or []
    if not isinstance(fields, list):
        errors.append("fields 必须是列表")
        field_ids: Set[str] = set()
    else:
        _validate_fields(fields, errors)
        field_ids = {str(field.get("id") or "").strip() for field in fields if str(field.get("id") or "").strip()}

    section_prompt = str(config.get("section_prompt") or "").strip()
    _validate_section_template(section_prompt, field_ids, errors)

    if not str(config.get("guidelines") or "").strip():
        warnings.append("guidelines 为空，将依赖默认写作规范。")
    if not str(config.get("system_prompt") or "").strip():
        warnings.append("system_prompt 为空，将回退到默认系统提示词。")

    if errors:
        raise SkillDefinitionValidationError(errors)
    return warnings
