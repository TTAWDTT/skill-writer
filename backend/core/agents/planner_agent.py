"""
Planner / Outline Manager Agent

Generates a document-level writing blueprint before section-by-section generation.
The blueprint is used to:
- enforce global consistency (terminology, claims, structure)
- provide per-section objectives and key points
- reduce contradictions across sections
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import json
import re

from .base import BaseAgent
from backend.core.skills.base import BaseSkill


@dataclass
class PlannerResult:
    """Document-level plan returned by PlannerAgent."""

    global_thesis: str
    global_outline: str
    section_guidance: Dict[str, Dict[str, Any]]
    terminology: List[Dict[str, str]]
    risks: List[str]


class PlannerAgent(BaseAgent):
    """
    Create a document-level blueprint.

    Notes:
    - Output is strictly JSON for robustness.
    - The plan should not invent facts; it should only reorganize known requirements
      and uploaded material excerpts.
    """

    async def run(
        self,
        *,
        skill: BaseSkill,
        requirements: Dict[str, Any],
        external_information: str = "",
    ) -> PlannerResult:
        sections = [
            {
                "id": s.id,
                "title": s.title,
                "level": s.level,
                "description": s.description,
                "word_limit": s.word_limit,
                "writing_guide": s.writing_guide,
                "evaluation_points": s.evaluation_points,
            }
            for s in skill.get_flat_sections()
        ]

        req_lines = []
        for f in skill.requirement_fields:
            value = requirements.get(f.id)
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            req_lines.append(f"- {f.name}({f.id}): {value}")
        requirements_text = "\n".join(req_lines) if req_lines else "（暂无）"

        external_excerpt = (external_information or "").strip()
        if len(external_excerpt) > 5000:
            external_excerpt = external_excerpt[:5000]

        prompt = f"""你是文书写作的 Planner / Outline Manager。你的任务是在写作前生成“全文蓝图”，用于指导后续分章节写作与一致性控制。

硬性约束：
1) 不能编造事实：只能基于“已知需求”和“材料摘要”做组织与规划；
2) 输出必须是严格 JSON，禁止输出解释、markdown 围栏、或额外文本；
3) section_guidance 必须覆盖所有 section_id；
4) global_outline 用 Markdown 列表（可包含层级缩进），但它必须作为 JSON 字符串值返回。

## 文书类型
{skill.metadata.name}

## 全部章节（按顺序）
{json.dumps(sections, ensure_ascii=False, indent=2)[:6000]}

## 已知需求（用户输入/已抽取）
{requirements_text}

## 材料摘要（可为空）
{external_excerpt if external_excerpt else "（无）"}

请输出 JSON，格式如下：
{{
  "global_thesis": "一句话概括全文主线/核心论点（不新增事实）",
  "global_outline": "Markdown 列表：全篇结构与论证链（可含二级缩进）",
  "terminology": [{{"term":"术语","definition":"简明定义/约定"}}],
  "risks": ["可能的风险/缺口（如缺关键数据/口径不清）"],
  "section_guidance": {{
    "section_id": {{
      "objective": "本节写作目的（1-2句）",
      "key_points": ["要点1","要点2","要点3"],
      "must_mention": ["必须提及的要素/字段（如有）"],
      "avoid": ["避免的表述/常见坑"],
      "cross_refs": ["与哪些章节形成承接/引用（用 section_id）"]
    }}
  }}
}}
"""

        messages = [
            {"role": "system", "content": "你是严谨的 Planner，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ]

        response = await self._chat(messages, temperature=0.2, max_tokens=3072)
        data = self._parse_json(response)

        section_guidance = data.get("section_guidance") or {}
        if not isinstance(section_guidance, dict):
            section_guidance = {}

        # Ensure all sections exist (best-effort defaults)
        for s in skill.get_flat_sections():
            if s.id not in section_guidance:
                section_guidance[s.id] = {
                    "objective": f"撰写 {s.title}，确保与全文主线一致。",
                    "key_points": [],
                    "must_mention": [],
                    "avoid": [],
                    "cross_refs": [],
                }

        terminology = data.get("terminology") or []
        if not isinstance(terminology, list):
            terminology = []

        risks = data.get("risks") or []
        if not isinstance(risks, list):
            risks = []

        return PlannerResult(
            global_thesis=str(data.get("global_thesis") or "").strip(),
            global_outline=str(data.get("global_outline") or "").strip(),
            section_guidance=section_guidance,
            terminology=[t for t in terminology if isinstance(t, dict)],
            risks=[str(r).strip() for r in risks if str(r).strip()],
        )

    def _parse_json(self, text: str) -> Dict[str, Any]:
        if not text:
            return {}
        text = text.strip()

        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # fenced code block
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # First JSON object
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return {}

