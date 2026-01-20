"""
审核 Agent
负责审核生成的内容质量
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
import json
import re

from .base import BaseAgent
from backend.core.skills.base import BaseSkill


@dataclass
class ReviewResult:
    """审核结果"""
    section_id: str
    score: int  # 0-100
    passed: bool
    issues: list
    suggestions: list
    revised_content: Optional[str] = None


class ReviewerAgent(BaseAgent):
    """
    审核 Agent
    负责检查内容质量，提出修改建议
    """

    async def run(
        self,
        skill: BaseSkill,
        section_id: str,
        content: str,
        requirements: Dict[str, Any],
    ) -> ReviewResult:
        """
        审核章节内容

        Args:
            skill: 使用的 Skill
            section_id: 章节 ID
            content: 待审核内容
            requirements: 用户需求

        Returns:
            ReviewResult
        """
        # 获取审核提示词
        prompt = skill.get_review_prompt(section_id, content, requirements)

        messages = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": prompt}
        ]

        response = await self._chat(messages, temperature=0.2)

        # 解析结果
        return self._parse_result(section_id, response)

    async def batch_review(
        self,
        skill: BaseSkill,
        sections: Dict[str, str],
        requirements: Dict[str, Any],
    ) -> Dict[str, ReviewResult]:
        """批量审核多个章节"""
        results = {}
        for section_id, content in sections.items():
            result = await self.run(skill, section_id, content, requirements)
            results[section_id] = result
        return results

    def _get_system_prompt(self) -> str:
        return """你是一个专业的学术文档审核专家。

你的任务是：
1. 检查内容是否符合要求
2. 评估内容质量（逻辑性、专业性、完整性）
3. 找出问题和不足
4. 提出具体的修改建议
5. 如有必要，提供修改后的内容

评分标准：
- 90-100：优秀，基本无需修改
- 80-89：良好，有小问题需要修改
- 70-79：及格，有明显问题需要修改
- 60-69：较差，需要大幅修改
- 60以下：不合格，需要重写

请以 JSON 格式输出审核结果。
"""

    def _parse_result(self, section_id: str, response: str) -> ReviewResult:
        """解析 LLM 返回的审核结果"""
        try:
            # 尝试提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                data = json.loads(json_match.group())
                return ReviewResult(
                    section_id=section_id,
                    score=data.get("score", 70),
                    passed=data.get("passed", False),
                    issues=data.get("issues", []),
                    suggestions=data.get("suggestions", []),
                    revised_content=data.get("revised_content"),
                )
        except (json.JSONDecodeError, KeyError):
            pass

        # 解析失败，返回默认结果
        return ReviewResult(
            section_id=section_id,
            score=70,
            passed=False,
            issues=["无法解析审核结果"],
            suggestions=["请重新审核"],
        )
