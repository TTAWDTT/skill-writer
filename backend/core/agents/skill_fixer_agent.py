"""
Skill Fixer Agent
Session-scoped skill augmentation based on uploaded materials.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
import json
import re

from .base import BaseAgent
from backend.core.skills.base import BaseSkill


@dataclass
class SkillFixResult:
    writing_guidelines_additions: str
    global_principles: list
    section_overrides: Dict[str, str]
    relax_requirements: bool
    material_context: str
    section_prompt_overrides: Dict[str, str]


class SkillFixerAgent(BaseAgent):
    """Generate session-scoped skill augmentations."""

    async def run(
        self,
        skill: BaseSkill,
        extracted_fields: Optional[Dict[str, Any]] = None,
        external_information: str = "",
        file_summaries: Optional[str] = None,
    ) -> SkillFixResult:
        sections = [
            {
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "writing_guide": s.writing_guide,
                "evaluation_points": s.evaluation_points,
            }
            for s in skill.get_flat_sections()
        ]

        external_excerpt = (external_information or "")[:4000]
        extracted_excerpt = json.dumps(extracted_fields or {}, ensure_ascii=False, indent=2)[:2000]
        summaries = (file_summaries or "").strip()

        prompt = f"""你是 skill-fixer。你的任务是基于上传材料，为当前 Skill 生成“补充版提示词”，仅用于本次会话。

要求：
1. 只给“增补”，不要重写原 Skill
2. 允许补充写作规范、全局写作准则、章节补充要求
3. material_context 必须是基于材料的事实与关键信息摘要，用于直接写作
4. section_prompt_overrides 如提供，必须是可直接用于写作的完整章节提示词
5. 不允许输出 JSON 之外的内容
6. 字符串必须是纯文本，不要在字符串里嵌套 JSON 或代码块

## 原 Skill 信息
名称：{skill.metadata.name}
描述：{skill.metadata.description}

### 写作规范
{skill.writing_guidelines[:2500]}

### 章节信息
{json.dumps(sections, ensure_ascii=False, indent=2)}

## 已提取字段
{extracted_excerpt if extracted_excerpt.strip() else "（无）"}

## 外部信息摘要
{external_excerpt if external_excerpt.strip() else "（无）"}

## 文件摘要
{summaries if summaries else "（无）"}

输出 JSON 格式：
{{
  "writing_guidelines_additions": "补充写作规范（可为空）",
  "global_principles": ["准则1", "准则2"],
  "section_overrides": {{
    "section_id": "该章节的补充要求"
  }},
  "material_context": "基于材料的事实摘要与关键信息（纯文本）",
  "section_prompt_overrides": {{
    "section_id": "完整章节提示词（纯文本，可为空；为空则使用原 Skill）"
  }},
  "relax_requirements": true
}}
"""

        messages = [
            {"role": "system", "content": "你是严谨的技能修正助手，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ]

        response = await self._chat(messages, temperature=0.3, max_tokens=2048)
        data = self._parse_json(response)

        return SkillFixResult(
            writing_guidelines_additions=(data.get("writing_guidelines_additions") or "").strip(),
            global_principles=data.get("global_principles") or [],
            section_overrides=data.get("section_overrides") or {},
            relax_requirements=bool(data.get("relax_requirements", True)),
            material_context=(data.get("material_context") or "").strip(),
            section_prompt_overrides=data.get("section_prompt_overrides") or {},
        )

    def _parse_json(self, response: str) -> Dict[str, Any]:
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        match = re.search(r"\{[\s\S]*\}", response)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return {
            "writing_guidelines_additions": "",
            "global_principles": [],
            "section_overrides": {},
            "relax_requirements": True,
            "material_context": "",
            "section_prompt_overrides": {},
        }
