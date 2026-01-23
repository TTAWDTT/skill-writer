"""
Format Refiner Agent
Post-process the final document to improve presentation without changing meaning.
"""

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class FormatRefineResult:
    content: str
    changed: bool = False
    reason: str = ""


class FormatRefinerAgent:
    """
    Deterministic, low-risk formatting refinements.

    Goals:
    - Remove "Field: Value" title patterns like "文书标题：XXX" at the very top.
    - Convert them into a clean Markdown title heading.
    - Avoid rewriting substantive content.
    """

    _TITLE_KEYS = (
        "文书标题",
        "标题",
        "项目标题",
        "课题名称",
        "项目名称",
        "Title",
    )

    def run(self, markdown: str, *, skill_name: Optional[str] = None) -> FormatRefineResult:
        if not markdown or not markdown.strip():
            return FormatRefineResult(content=markdown, changed=False)

        original = markdown
        lines = markdown.splitlines()

        # Find the first non-empty line.
        first_idx = None
        for idx, line in enumerate(lines):
            if line.strip():
                first_idx = idx
                break
        if first_idx is None:
            return FormatRefineResult(content=markdown, changed=False)

        first_line = lines[first_idx].strip()
        title = self._extract_title(first_line)

        # Also handle a two-line title form:
        #   文书标题：
        #   XXX
        if title is None and self._is_title_key_only(first_line) and first_idx + 1 < len(lines):
            next_line = lines[first_idx + 1].strip()
            if next_line and not next_line.startswith("#"):
                title = next_line
                # Remove the key-only line; we'll replace with a heading below.
                lines[first_idx] = ""
                lines[first_idx + 1] = ""

        if title:
            # Always promote the extracted title into a Markdown H1 heading.
            # This keeps the title visible even when the document begins with a section heading.
            lines[first_idx] = f"# {title}"

        # Remove a redundant "标题：xxx" line if the first heading equals the same title.
        lines = self._dedupe_title_label(lines)

        refined = self._normalize_spacing("\n".join(lines))
        changed = refined != original
        reason = "refined_title_format" if changed else ""
        return FormatRefineResult(content=refined, changed=changed, reason=reason)

    def _extract_title(self, line: str) -> Optional[str]:
        # Only treat as a title if it's near the top and matches known keys.
        key_pattern = "|".join(re.escape(k) for k in self._TITLE_KEYS)
        match = re.match(rf"^(?:{key_pattern})\s*[:：]\s*(.+?)\s*$", line)
        if not match:
            return None
        candidate = match.group(1).strip()
        # Avoid capturing obviously non-title values.
        if not candidate:
            return None
        if len(candidate) > 200:
            return None
        return candidate

    def _is_title_key_only(self, line: str) -> bool:
        # "文书标题：" or "标题：" etc.
        stripped = line.strip()
        for key in self._TITLE_KEYS:
            if stripped == key or stripped == f"{key}:" or stripped == f"{key}：":
                return True
        return False

    def _dedupe_title_label(self, lines: list[str]) -> list[str]:
        # If we have both a "# Title" and a later immediate "标题：Title" at top, remove the label line.
        non_empty = [(i, l.strip()) for i, l in enumerate(lines) if l.strip()]
        if not non_empty:
            return lines

        first_heading_idx = None
        first_heading_text = None
        for i, l in non_empty[:10]:
            if l.startswith("#"):
                first_heading_idx = i
                first_heading_text = re.sub(r"^#+\s*", "", l).strip()
                break
        if not first_heading_text:
            return lines

        # Remove a "标题：<same>" line within the first few lines (excluding heading line itself).
        for i, l in non_empty[:12]:
            if i == first_heading_idx:
                continue
            extracted = self._extract_title(l)
            if extracted and extracted == first_heading_text:
                lines[i] = ""
                break
        return lines

    def _normalize_spacing(self, text: str) -> str:
        # Collapse excessive blank lines but preserve paragraphs.
        text = text.replace("\r\n", "\n")
        text = re.sub(r"\n{4,}", "\n\n\n", text)
        return text.strip() + "\n"
