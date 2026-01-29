"""
Document Polisher Agent
LLM-based post-processing to improve document presentation after generation.
"""

import re
from typing import Any, Dict, Optional

from .base import BaseAgent


class DocumentPolisherAgent(BaseAgent):
    """
    Rewrite only presentation/formatting of an already-generated document.

    Key objectives:
    - Promote "文书标题：XXX" into a proper top-level title (H1), showing only "XXX".
    - Convert field-style lines ("字段：值") into natural prose where appropriate.
    - Remove exact duplicated content blocks (non-semantic dedupe) that may be introduced by
      upstream processing (not by the LLM itself).
    - Keep meaning, facts, numbers, names, and citations unchanged.
    """

    async def run(
        self,
        document_markdown: str,
        *,
        skill_name: str = "",
    ) -> Dict[str, Any]:
        raw0 = (document_markdown or "").strip()
        if not raw0:
            return {"content": document_markdown, "changed": False, "reason": "empty"}

        # Deterministic title normalization so the classic "文书标题：XXX" issue is fixed
        # even if the LLM postprocess is rate-limited or otherwise fails.
        raw0 = self._normalize_title_field(raw0).strip()

        # Deterministic, non-semantic cleanup first: remove exact duplicates so the LLM
        # doesn't waste tokens and the final document doesn't contain repeated blocks.
        baseline, pre_stats = self._dedupe_exact_blocks(raw0)
        baseline = baseline.strip()
        if not baseline:
            baseline = raw0

        system = (
            "你是 document-refiner（文档润色、格式整理与去重助手）。\n"
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
{baseline}
"""

        # Use a conservative temperature to avoid semantic drift.
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        last_error: Optional[str] = None
        polished = ""
        for attempt in range(1, 3):
            try:
                response = await self._chat(messages, temperature=0.2, max_tokens=4096)
                polished = self._strip_code_fences(response).strip()
                polished = self._cleanup_llm_artifacts(polished)
                polished = self._remove_title_labels_everywhere(polished)
                polished = self._normalize_title_field(polished).strip()
                if self._validate_refined_output(polished):
                    break

                # If output violates the contract (meta text, fences, title labels), ask once more
                # with an explicit "repair" instruction.
                last_error = "contract_violation"
                messages = [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": (
                            "你刚才的输出没有严格遵守约束（可能包含解释性文字、字段标签、或非正文内容）。\n"
                            "请只输出修复后的 Markdown 正文，且：\n"
                            "- 绝对不新增事实/内容；\n"
                            "- 删除任何“说明/提示/如果需要”等无关语句；\n"
                            "- 不要输出任何代码块围栏（```）；\n"
                            "- “文书标题：XXX/标题：XXX/项目名称：XXX”等必须变为首行 `# XXX`。\n\n"
                            "原始全文（去重后）：\n"
                            f"{baseline}\n\n"
                            "你上一版输出（有问题）：\n"
                            f"{polished}\n"
                        ),
                    },
                ]
            except Exception as e:
                last_error = type(e).__name__
                polished = ""
                break

        if not polished:
            # If LLM polishing fails (rate limit/network/etc), still apply deterministic dedupe.
            content = baseline.strip() + "\n"
            return {
                "content": content,
                "changed": content != (document_markdown or ""),
                "reason": f"dedupe_only:{last_error or 'llm_failed'}",
                "dedupe_pre": pre_stats,
                "dedupe_post": {"removed": 0, "kept": pre_stats.get("kept", 0)},
            }

        # Always do a deterministic cleanup pass (even after validation).
        polished = self._cleanup_llm_artifacts(polished)
        polished = self._remove_title_labels_everywhere(polished)
        polished = self._normalize_title_field(polished).strip()
        if not polished:
            content = baseline.strip() + "\n"
            return {
                "content": content,
                "changed": content != (document_markdown or ""),
                "reason": "dedupe_only:empty_output",
                "dedupe_pre": pre_stats,
                "dedupe_post": {"removed": 0, "kept": pre_stats.get("kept", 0)},
            }

        # Second deterministic pass after LLM: remove any exact duplicates that may remain.
        polished2, post_stats = self._dedupe_exact_blocks(polished)
        polished2 = polished2.strip()
        if not polished2:
            polished2 = polished

        # Safety checks: avoid destructive rewrites.
        # Compare against baseline (deduped input), because dedupe intentionally removes repeats.
        if len(polished2) < max(200, int(len(baseline) * 0.55)):
            content = baseline.strip() + "\n"
            return {
                "content": content,
                "changed": content != (document_markdown or ""),
                "reason": "dedupe_only:too_short",
                "dedupe_pre": pre_stats,
                "dedupe_post": {"removed": 0, "kept": pre_stats.get("kept", 0)},
            }

        if not self._preserve_number_tokens(baseline, polished2):
            content = baseline.strip() + "\n"
            return {
                "content": content,
                "changed": content != (document_markdown or ""),
                "reason": "dedupe_only:numbers_mismatch",
                "dedupe_pre": pre_stats,
                "dedupe_post": {"removed": 0, "kept": pre_stats.get("kept", 0)},
            }

        # Normalize trailing newline.
        final = polished2.strip() + "\n"
        return {
            "content": final,
            "changed": final != (document_markdown or ""),
            "reason": "ok",
            "dedupe_pre": pre_stats,
            "dedupe_post": post_stats,
        }

    def _strip_code_fences(self, text: str) -> str:
        if not text:
            return ""
        # Remove ```markdown ... ``` wrappers if present.
        fence = re.search(r"```(?:markdown|md)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
        if fence:
            return fence.group(1)
        return text

    def _normalize_title_field(self, markdown: str) -> str:
        """
        If the first non-empty line looks like a field-style title, convert it to H1.

        Examples:
        - "文书标题：XXX" -> "# XXX"
        - "# 文书标题：XXX" -> "# XXX"
        """
        if not markdown:
            return ""

        lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        out: list[str] = []
        done = False

        # Match both plain and H1-prefixed "标签：值"
        pat = re.compile(
            r"^\s*(?:#\s*)?(?:文书标题|标题|项目名称|项目题目|课题名称)\s*[:：]\s*(.+?)\s*$"
        )

        for ln in lines:
            if not done and ln.strip():
                m = pat.match(ln)
                if m:
                    title = m.group(1).strip()
                    out.append(f"# {title}")
                    done = True
                    continue
                done = True
            out.append(ln)

        return "\n".join(out)

    def _remove_title_labels_everywhere(self, markdown: str) -> str:
        """
        Remove stray occurrences of field-style title labels anywhere in the document.

        This avoids leaving behind lines like "文书标题：XXX" even if the LLM repeats them
        in later sections.
        """
        if not markdown:
            return ""

        pat = re.compile(r"^\s*(?:文书标题|标题|项目名称|项目题目|课题名称)\s*[:：]\s*(.+?)\s*$")
        out = []
        for ln in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            m = pat.match(ln)
            if m:
                out.append(m.group(1).strip())
            else:
                out.append(ln)
        return "\n".join(out)

    def _cleanup_llm_artifacts(self, markdown: str) -> str:
        """
        Remove assistant meta text that occasionally appears around the actual document.

        We only strip very typical "assistant chatter" patterns at the beginning/end to
        avoid deleting legitimate content.
        """
        if not markdown:
            return ""

        lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        def is_meta_line(s: str) -> bool:
            t = s.strip()
            if not t:
                return False
            # Common assistant chatter (Chinese).
            prefixes = ("下面是", "以下是", "这是", "我将", "我已", "我已经", "好的", "当然", "已为你", "根据你的")
            if t.startswith(prefixes):
                return True
            # Common assistant offer/CTA.
            if any(x in t for x in ("如需", "如果需要", "需要进一步", "希望对你有帮助")):
                return True
            # Explicit meta mentions.
            if any(x in t for x in ("润色", "格式调整说明", "说明：", "提示：")) and len(t) <= 40:
                return True
            return False

        # Remove all fenced-code markers (```xxx / ```) but keep the inner content.
        stripped: list[str] = []
        in_fence = False
        for ln in lines:
            if ln.strip().startswith("```"):
                in_fence = not in_fence
                continue
            stripped.append(ln)
        lines = stripped

        # Strip leading meta lines.
        start = 0
        while start < len(lines) and is_meta_line(lines[start]):
            start += 1
        # Strip trailing meta lines.
        end = len(lines)
        while end > start and is_meta_line(lines[end - 1]):
            end -= 1

        middle = lines[start:end]

        # Also remove short meta lines that appear in the middle (best-effort, conservative).
        cleaned_lines: list[str] = []
        for ln in middle:
            t = ln.strip()
            if t and not t.startswith("#") and len(t) <= 80 and is_meta_line(ln):
                continue
            cleaned_lines.append(ln)

        cleaned = "\n".join(cleaned_lines).strip()
        # Normalize excessive blank lines introduced by trimming.
        cleaned = re.sub(r"\n{4,}", "\n\n\n", cleaned).strip()
        return cleaned

    def _validate_refined_output(self, markdown: str) -> bool:
        """
        Validate that output looks like pure document markdown (no assistant meta).
        """
        if not markdown or not markdown.strip():
            return False

        t = markdown.strip()
        # No fences in final output.
        if "```" in t:
            return False
        # No leftover title labels.
        if re.search(r"(?m)^\s*(?:文书标题|标题|项目名称|项目题目|课题名称)\s*[:：]", t):
            return False

        # No obvious assistant meta on the edges.
        first = next((ln.strip() for ln in t.split("\n") if ln.strip()), "")
        last = next((ln.strip() for ln in reversed(t.split("\n")) if ln.strip()), "")
        edge_bad = ("下面是", "以下是", "我已", "我将", "好的", "当然", "如需", "如果需要")
        if first.startswith(edge_bad) or last.startswith(edge_bad):
            return False
        return True

    def _dedupe_exact_blocks(self, markdown: str) -> tuple[str, Dict[str, int]]:
        """
        Remove *exact* repeated content blocks (non-semantic).

        Strategy:
        - Preserve fenced code blocks as atomic blocks.
        - Split the rest into segments using heading boundaries and blank-line paragraphs.
        - Normalize whitespace lightly (line endings, trailing spaces, repeated blank lines).
        - Drop later blocks whose normalized content matches a previously seen block.
        """
        text = (markdown or "").replace("\r\n", "\n").replace("\r", "\n")
        blocks = self._split_markdown_blocks(text)

        seen = set()
        kept = []
        removed = 0
        for b in blocks:
            # Within a block, remove exact repeated lines/bullets (still non-semantic) to
            # handle copy/paste duplication artifacts without relying on the LLM.
            b2 = self._dedupe_in_block_lines(b)
            key = self._normalize_for_key(b2)
            if not key:
                continue
            if key in seen:
                removed += 1
                continue
            seen.add(key)
            kept.append(b2.rstrip())

        out = "\n\n".join(kept).strip()
        out = re.sub(r"\n{4,}", "\n\n\n", out)
        return out, {"removed": removed, "kept": len(kept)}

    def _dedupe_in_block_lines(self, block: str) -> str:
        """
        Non-semantic line-level dedupe inside a single markdown block.

        - Removes consecutive identical lines (ignoring surrounding whitespace).
        - Dedupes identical list-item lines within the same block (order-preserving).
        """
        if not block:
            return ""

        lines = block.split("\n")
        out: list[str] = []
        last_key: Optional[str] = None

        # Track duplicates only for explicit list-item lines.
        seen_list_items: set[str] = set()
        list_item_re = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)\S")

        for ln in lines:
            key = ln.strip()

            # Remove consecutive identical lines (common duplication artifact).
            if key and last_key == key:
                continue
            if key:
                last_key = key

            if list_item_re.match(ln):
                # Remove duplicate list item lines anywhere in the block.
                list_key = re.sub(r"\s+", " ", key)
                if list_key in seen_list_items:
                    continue
                seen_list_items.add(list_key)

            out.append(ln.rstrip())

        s = "\n".join(out)
        s = re.sub(r"\n{3,}", "\n\n", s).strip("\n")
        return s

    def _split_markdown_blocks(self, text: str) -> list[str]:
        blocks: list[str] = []
        i = 0
        lines = text.split("\n")
        n = len(lines)

        def flush(buf: list[str]):
            s = "\n".join(buf).strip("\n")
            if s.strip():
                blocks.append(s)

        buf: list[str] = []
        in_fence = False
        fence_buf: list[str] = []

        while i < n:
            line = lines[i]
            fence_start = bool(re.match(r"^\s*```", line))

            if in_fence:
                fence_buf.append(line)
                if fence_start:
                    # fence end (treat any ``` as closing)
                    in_fence = False
                    flush(buf)
                    buf = []
                    flush(fence_buf)
                    fence_buf = []
                i += 1
                continue

            if fence_start:
                # start fence
                flush(buf)
                buf = []
                in_fence = True
                fence_buf = [line]
                i += 1
                continue

            is_heading = bool(re.match(r"^\s*#{1,6}\s+\S", line))
            if is_heading:
                flush(buf)
                buf = [line]
                # absorb immediate following non-heading, non-fence content until blank-line paragraph breaks
                i += 1
                # Continue collecting until next heading or fence; paragraph breaks create new blocks.
                while i < n:
                    nxt = lines[i]
                    if re.match(r"^\s*```", nxt) or re.match(r"^\s*#{1,6}\s+\S", nxt):
                        break
                    if not nxt.strip():
                        # paragraph boundary inside a section: finalize current block and start new paragraph block
                        flush(buf)
                        buf = []
                        # skip consecutive blank lines
                        while i < n and not lines[i].strip():
                            i += 1
                        continue
                    buf.append(nxt)
                    i += 1
                flush(buf)
                buf = []
                continue

            # Non-heading normal text: group into paragraphs separated by blank lines
            if not line.strip():
                flush(buf)
                buf = []
                i += 1
                continue

            buf.append(line)
            i += 1

        if in_fence:
            # unclosed fence; keep as-is
            flush(buf)
            flush(fence_buf)
        else:
            flush(buf)

        return blocks

    def _normalize_for_key(self, block: str) -> str:
        b = (block or "").replace("\r\n", "\n").replace("\r", "\n")
        # Remove trailing spaces and normalize blank lines.
        b = "\n".join([ln.rstrip() for ln in b.split("\n")])
        b = re.sub(r"\n{3,}", "\n\n", b).strip()
        return b

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
        text = (text or "").replace("\u2013", "-").replace("\u2014", "-")
        tokens = re.findall(r"\d[\d\.,/%\-eE]*", text)
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
