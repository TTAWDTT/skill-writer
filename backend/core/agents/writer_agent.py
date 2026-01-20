"""
写作 Agent
负责根据 Skill 模板和用户需求生成高质量内容
"""
from typing import Dict, Any, List, Optional, AsyncGenerator
from dataclasses import dataclass, field

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

        return "\n\n".join(contents)

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
        return content

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
        state.sections[section.id] = full_content
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
