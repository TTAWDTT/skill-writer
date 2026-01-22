"""
写作 Agent
负责根据 Skill 模板和用户需求生成高质量内容
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field
import re

from .base import BaseAgent
from backend.core.skills.base import BaseSkill, Section


@dataclass
class WritingState:
    """写作状态"""
    skill_id: str
    requirements: Dict[str, Any]
    sections: Dict[str, str] = field(default_factory=dict)  # section_id -> content
    current_section: Optional[str] = None
    completed_sections: List[str] = field(default_factory=list)
    total_sections: int = 0
    external_information: str = ""  # 从上传文件提取的外部信息


class WriterAgent(BaseAgent):
    """
    写作 Agent
    负责撰写各章节内容
    """

    def _find_section_by_id(self, skill: BaseSkill, section_id: str) -> Optional[Section]:
        """根据 ID 查找章节"""
        for section in skill.get_flat_sections():
            if section.id == section_id:
                return section
        return None

    def _normalize_ordered_lists(self, content: str) -> str:
        """将每个有序列表重新编号为从 1 开始"""
        lines = content.splitlines()
        normalized = []
        in_list = False
        list_index = 1
        list_indent = None
        pattern = re.compile(r'^(\s*)(\d+)([.)、．])\s+(.*)$')

        for line in lines:
            match = pattern.match(line)
            if match:
                indent, _, delimiter, rest = match.groups()
                if not in_list or indent != list_indent:
                    list_index = 1
                    list_indent = indent
                    in_list = True
                normalized.append(f"{indent}{list_index}{delimiter} {rest}")
                list_index += 1
                continue

            if line.strip() == "":
                in_list = False
                list_index = 1
                list_indent = None
                normalized.append(line)
                continue

            in_list = False
            list_index = 1
            list_indent = None
            normalized.append(line)

        return "\n".join(normalized)

    def _strip_section_heading(self, section: Section, content: str) -> str:
        """移除章节内容里重复的标题行（移除开头连续匹配的标题）"""
        lines = content.splitlines()
        if not lines:
            return content

        def normalize_title(text: str) -> str:
            # 去掉括号内容与标点，便于匹配“标题+说明”场景
            text = re.sub(r'[\(\（\[\【<《].*?[\)\）\]\】>》]', '', text)
            return re.sub(r'[^0-9a-zA-Z\u4e00-\u9fff]+', '', text).lower()

        target = normalize_title(section.title)

        def extract_heading_text(line: str) -> str:
            md_match = re.match(r'^#{1,6}\s*(.+)$', line)
            if md_match:
                return md_match.group(1).strip()
            num_match = re.match(r'^([一二三四五六七八九十\\d]+)[、．.\\)]\\s*(.+)$', line)
            if num_match:
                return num_match.group(2).strip()
            bracket_match = re.match(r'^[【\\[](.+?)[】\\]]$', line)
            if bracket_match:
                return bracket_match.group(1).strip()
            return line.strip()

        cleaned = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            heading_text = extract_heading_text(stripped)
            normalized = normalize_title(heading_text)
            if normalized == target:
                # 跳过标题行以及紧随其后的空行
                i += 1
                while i < len(lines) and not lines[i].strip():
                    i += 1
                continue

            # 遇到首个正文行，保留其余全部内容
            cleaned.append(line)
            cleaned.extend(lines[i + 1:])
            break

        return "\n".join(cleaned)

    def _postprocess_section(self, section: Section, content: str) -> str:
        """章节后处理：去重标题 + 规范编号"""
        content = self._strip_section_heading(section, content)
        return self._normalize_ordered_lists(content)

    def _dedupe_adjacent_heading_lines(self, content: str) -> str:
        """移除标题行后紧跟的重复标题文本行"""
        lines = content.splitlines()

        def normalize_title(text: str) -> str:
            text = re.sub(r'[\(\（\[\【<《].*?[\)\）\]\】>》]', '', text)
            return re.sub(r'[^0-9a-zA-Z\u4e00-\u9fff]+', '', text).lower()

        cleaned = []
        i = 0
        while i < len(lines):
            line = lines[i]
            cleaned.append(line)

            md_match = re.match(r'^#{1,6}\s*(.+)$', line.strip())
            if not md_match:
                i += 1
                continue

            heading_text = md_match.group(1).strip()
            target = normalize_title(heading_text)

            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1

            if j < len(lines):
                next_line = lines[j].strip()
                if normalize_title(next_line) == target:
                    lines.pop(j)
                    continue

            i += 1

        return "\n".join(cleaned)

    async def run(
        self,
        skill: BaseSkill,
        requirements: Dict[str, Any],
        section_id: Optional[str] = None,
        state: Optional[WritingState] = None,
        external_information: str = "",
    ) -> Dict[str, Any]:
        """
        执行写作任务

        Args:
            skill: 使用的 Skill
            requirements: 用户需求
            section_id: 要写的章节 ID（如果为 None，则写全部）
            state: 写作状态
            external_information: 从上传文件提取的外部信息

        Returns:
            {
                "content": str,  # 生成的内容
                "state": WritingState,
                "section_id": str,
            }
        """
        if state is None:
            flat_sections = skill.get_flat_sections()
            state = WritingState(
                skill_id=skill.metadata.id,
                requirements=requirements,
                total_sections=len(flat_sections),
                external_information=external_information,
            )

        if section_id:
            # 写单个章节
            section = self._find_section_by_id(skill, section_id)
            if not section:
                return {
                    "content": f"[错误] 未找到章节: {section_id}",
                    "state": state,
                    "section_id": section_id,
                }
            content = await self._write_single_section(skill, section, requirements, state)
            state.sections[section_id] = content
            state.completed_sections.append(section_id)
            return {
                "content": content,
                "state": state,
                "section_id": section_id,
            }
        else:
            # 写全部章节（返回合并内容）
            all_content = await self.write_all_sections(skill, requirements, state)
            return {
                "content": all_content,
                "state": state,
                "section_id": None,
            }

    async def write_all_sections(
        self,
        skill: BaseSkill,
        requirements: Dict[str, Any],
        state: WritingState,
    ) -> str:
        """顺序写作所有章节"""
        flat_sections = skill.get_flat_sections()
        contents = []

        for section in flat_sections:
            state.current_section = section.id

            content = await self._write_single_section(skill, section, requirements, state)
            state.sections[section.id] = content
            state.completed_sections.append(section.id)

            # 格式化为 Markdown
            heading = "#" * section.level + " " + section.title
            contents.append(f"{heading}\n\n{content}")

        combined = "\n\n".join(contents)
        return self._dedupe_adjacent_heading_lines(combined)

    async def _write_single_section(
        self,
        skill: BaseSkill,
        section: Section,
        requirements: Dict[str, Any],
        state: WritingState,
    ) -> str:
        """写作单个章节"""
        # 构建上下文
        context = self._build_context(requirements, state)

        # 使用 skill 的 get_section_prompt 方法
        prompt = skill.get_section_prompt(section, context)

        messages = [
            {"role": "system", "content": self._get_system_prompt(skill)},
            {"role": "user", "content": prompt}
        ]

        content = await self._chat(messages, temperature=0.5)
        return self._postprocess_section(section, content)

    async def write_section_stream(
        self,
        skill: BaseSkill,
        section: Section,
        requirements: Dict[str, Any],
        state: WritingState,
    ) -> AsyncGenerator[str, None]:
        """流式写作单个章节"""
        # 构建上下文
        context = self._build_context(requirements, state)

        # 使用 skill 的 get_section_prompt 方法
        prompt = skill.get_section_prompt(section, context)

        messages = [
            {"role": "system", "content": self._get_system_prompt(skill)},
            {"role": "user", "content": prompt}
        ]

        # 流式输出
        full_content = ""
        async for chunk in self._chat_stream(messages, temperature=0.5):
            full_content += chunk
            yield chunk

        # 保存到状态
        state.sections[section.id] = self._postprocess_section(section, full_content)
        state.completed_sections.append(section.id)

    def _get_system_prompt(self, skill: BaseSkill) -> str:
        """获取系统提示词"""
        return f"""你是一个专业的{skill.metadata.name}写作专家。

{skill.writing_guidelines}

## 写作原则
1. 逻辑清晰，论述有力
2. 语言专业、准确
3. 结构层次分明
4. 数据和论据充分
5. 符合学术规范
"""

    def _build_context(
        self,
        requirements: Dict[str, Any],
        state: WritingState
    ) -> Dict[str, Any]:
        """构建写作上下文"""
        context = {
            "requirements": requirements,
            "external_information": state.external_information,
        }

        # 添加已写内容作为参考
        if state.sections:
            context["written_sections"] = state.sections

        return context

    def _format_requirements_for_prompt(
        self,
        skill: BaseSkill,
        requirements: Dict[str, Any],
    ) -> str:
        lines = []
        for field in skill.requirement_fields:
            value = requirements.get(field.id)
            if value:
                lines.append(f"- {field.name}({field.id}): {value}")
        return "\n".join(lines) if lines else "（暂无）"

    async def generate_outline(
        self,
        skill: BaseSkill,
        section: Section,
        requirements: Dict[str, Any],
        state: WritingState,
    ) -> str:
        """生成章节提纲"""
        requirements_text = self._format_requirements_for_prompt(skill, requirements)
        external_excerpt = (state.external_information or "")[:1200]
        external_block = f"\n\n## 参考材料\n{external_excerpt}" if external_excerpt else ""

        prompt = f"""请为章节「{section.title}」生成 3-6 条清晰的提纲要点。

## 章节说明
{section.description or "无"}

## 写作指导
{section.writing_guide or "无"}

## 评审要点
{chr(10).join(f"- {p}" for p in section.evaluation_points) if section.evaluation_points else "无"}

## 已知需求
{requirements_text}
{external_block}

请只输出提纲列表，不要输出正文。
"""

        messages = [
            {"role": "system", "content": self._get_system_prompt(skill)},
            {"role": "user", "content": prompt},
        ]
        outline = await self._chat(messages, temperature=0.3)
        return outline.strip()

    async def generate_draft(
        self,
        skill: BaseSkill,
        section: Section,
        requirements: Dict[str, Any],
        state: WritingState,
        outline: str,
    ) -> str:
        """根据提纲生成章节草稿"""
        context = self._build_context(requirements, state)
        prompt = skill.get_section_prompt(section, context)
        draft_prompt = f"""{prompt}

## 章节提纲
{outline}

请按照提纲撰写章节正文，不要输出章节标题。
"""

        messages = [
            {"role": "system", "content": self._get_system_prompt(skill)},
            {"role": "user", "content": draft_prompt},
        ]
        draft = await self._chat(messages, temperature=0.5)
        return draft

    async def revise_section(
        self,
        skill: BaseSkill,
        section: Section,
        requirements: Dict[str, Any],
        state: WritingState,
        draft: str,
        issues: List[str],
        suggestions: List[str],
    ) -> str:
        """根据自检建议修订章节内容"""
        requirements_text = self._format_requirements_for_prompt(skill, requirements)
        external_excerpt = (state.external_information or "")[:1200]
        external_block = f"\n\n## 参考材料\n{external_excerpt}" if external_excerpt else ""
        issues_text = "\n".join(f"- {i}" for i in issues) if issues else "无"
        suggestions_text = "\n".join(f"- {s}" for s in suggestions) if suggestions else "无"

        prompt = f"""请根据审核问题修订以下内容。

## 章节
{section.title}

## 已知需求
{requirements_text}
{external_block}

## 原始内容
{draft}

## 发现的问题
{issues_text}

## 修改建议
{suggestions_text}

请输出修订后的章节正文，不要输出章节标题。
"""

        messages = [
            {"role": "system", "content": self._get_system_prompt(skill)},
            {"role": "user", "content": prompt},
        ]
        revised = await self._chat(messages, temperature=0.4)
        return revised

    async def write_section_with_review(
        self,
        skill: BaseSkill,
        section: Section,
        requirements: Dict[str, Any],
        state: WritingState,
        reviewer_agent,
    ) -> Dict[str, Any]:
        """多轮生成：提纲 → 草稿 → 自检 → 修订"""
        outline = await self.generate_outline(skill, section, requirements, state)
        draft = await self.generate_draft(skill, section, requirements, state, outline)
        review = await reviewer_agent.run(skill, section.id, draft, requirements)

        final_content = draft
        revised = False
        if review.revised_content:
            final_content = review.revised_content
            revised = True
        elif not review.passed or review.score < 80:
            final_content = await self.revise_section(
                skill,
                section,
                requirements,
                state,
                draft,
                review.issues,
                review.suggestions,
            )
            revised = True

        final_content = self._postprocess_section(section, final_content)

        return {
            "outline": outline,
            "draft": draft,
            "review": review,
            "content": final_content,
            "revised": revised,
        }
