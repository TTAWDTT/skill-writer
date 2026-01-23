"""
Document Polisher Agent
LLM-based post-processing to improve document presentation after generation.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, Optional

from .base import BaseAgent


@dataclass
class DocumentPolishResult:
    content: str
    changed: bool
    reason: str = ""


class DocumentPolisherAgent(BaseAgent):
    """
    Rewrite only presentation/formatting of an already-generated document.

    Key objectives:
    - Promote "文书标题：XXX" into a proper top-level title (H1), showing only "XXX".
    - Convert field-style lines ("字段：值") into natural prose where appropriate.
    - Keep meaning, facts, numbers, names, and citations unchanged.
    """

    async def run(
        self,
        document_markdown: str,
        *,
        skill_name: str = "",
    ) -> Dict[str, Any]:
        raw = (document_markdown or "").strip()
        if not raw:
            return {"content": document_markdown, "changed": False, "reason": "empty"}

        system = (
            "你是 document-polisher（文档润色与格式整理助手）。\n"
            "你的任务：仅对用户提供的 Markdown 文档做“展示层”的润色与格式整理。\n"
            "硬性约束：\n"
            "1) 绝对不新增事实，不删减事实，不编造；\n"
            "2) 数字、金额、日期、人名、机构名、专有名词必须保持原样；\n"
            "3) 引用、结论、数据口径保持一致；\n"
            "4) 仅输出 Markdown 正文，不要输出解释、不要代码块包裹。\n"
        )

        prompt = f"""请对下面的文档进行润色与格式调整（仅展示层），文书类型：{skill_name or "未指定"}。

具体目标：
- 如果出现“文书标题：XXX / 标题：XXX / 项目名称：XXX”等字段式标题，转换为文档第一行的 Markdown 一级标题：`# XXX`，不要保留“文书标题：”等标签。
- 对明显的“字段：值”条目（如 背景/目标/方法/创新点/预期成果/实施计划 等）进行自然语言重排，让它更像一篇正式文书，而不是表单；必要时可使用小标题与列表，但避免机械模板。
- 保持章节层级清晰；尽量去除重复标题、重复空行；段落之间留一行空行。

下面是原文（Markdown）：
{raw}
"""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        # Use a conservative temperature to avoid semantic drift.
        response = await self._chat(messages, temperature=0.2, max_tokens=4096)
        polished = self._strip_code_fences(response).strip()

        if not polished:
            return {"content": document_markdown, "changed": False, "reason": "empty_output"}

        # Safety checks: avoid destructive rewrites.
        if len(polished) < max(200, int(len(raw) * 0.55)):
            return {"content": document_markdown, "changed": False, "reason": "too_short"}

        if not self._preserve_number_tokens(raw, polished):
            return {"content": document_markdown, "changed": False, "reason": "numbers_mismatch"}

        # Normalize trailing newline.
        polished = polished.strip() + "\n"
        return {"content": polished, "changed": polished != (document_markdown or ""), "reason": "ok"}

    def _strip_code_fences(self, text: str) -> str:
        if not text:
            return ""
        # Remove ```markdown ... ``` wrappers if present.
        fence = re.search(r"```(?:markdown|md)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
        if fence:
            return fence.group(1)
        return text

    def _preserve_number_tokens(self, before: str, after: str) -> bool:
        """
        Heuristic guardrail: ensure most number-like tokens are preserved.
        """
        before_tokens = self._extract_number_tokens(before)
        if not before_tokens:
            return True
        after_set = set(self._extract_number_tokens(after))
        missing = [t for t in before_tokens if t not in after_set]
        # Allow a small miss rate due to formatting differences.
        return (len(missing) / len(before_tokens)) <= 0.05

    def _extract_number_tokens(self, text: str) -> list[str]:
        # Extract tokens like 2026, 3.14, 10%, 1-2, 1/2, 1.2e3 (basic).
        tokens = re.findall(r"\d[\d\.,/%\-–—]*", text)
        cleaned = []
        for tok in tokens:
            t = tok.strip(".,")
            if len(t) >= 2:
                cleaned.append(t)
        # Deduplicate but keep stable-ish order.
        seen = set()
        out = []
        for t in cleaned:
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
        return out

