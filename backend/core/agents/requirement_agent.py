"""
需求理解 Agent
通过多轮对话收集和澄清用户需求
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .base import BaseAgent
from backend.core.skills.base import BaseSkill, RequirementField


@dataclass
class RequirementState:
    """需求收集状态"""
    skill_id: str
    collected: Dict[str, Any] = field(default_factory=dict)  # 已收集的需求
    pending_questions: List[str] = field(default_factory=list)  # 待询问的问题
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    is_complete: bool = False


class RequirementAgent(BaseAgent):
    """
    需求理解 Agent
    负责收集用户需求，确保信息完整且准确
    """

    SYSTEM_PROMPT = """你是一个专业的科研项目申报顾问，正在帮助用户准备申报材料。
你的任务是通过对话收集撰写申报书所需的信息。

要求：
1. 每次只问1-2个相关问题，不要一次问太多
2. 根据用户回答进行追问，挖掘更深入的信息
3. 注意信息的完整性和准确性
4. 用专业但友好的语气交流
5. 如果用户的回答不够详细，要引导用户补充
6. 优先收集必填字段，按优先级从高到低提问
7. 标记为“infer”的字段不要向用户提问

当你认为信息已经足够完整时，输出 [REQUIREMENTS_COMPLETE] 标记。
"""

    async def run(
        self,
        skill: BaseSkill,
        user_message: str,
        state: Optional[RequirementState] = None,
    ) -> Dict[str, Any]:
        """
        处理用户消息，收集需求

        Returns:
            {
                "response": str,  # 给用户的回复
                "state": RequirementState,  # 更新后的状态
                "is_complete": bool,  # 需求是否完整
                "requirements": Dict,  # 收集到的需求（如果完整）
            }
        """
        # 初始化状态
        if state is None:
            state = RequirementState(skill_id=skill.metadata.id)
            # 构建初始问题
            initial_prompt = self._build_initial_prompt(skill)
            return {
                "response": initial_prompt,
                "state": state,
                "is_complete": False,
                "requirements": None,
            }

        # 记录用户消息
        state.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # 构建消息列表
        messages = self._build_messages(skill, state)

        # 调用 LLM
        response = await self._chat(messages, temperature=0.7)

        # 检查是否完成
        is_complete = "[REQUIREMENTS_COMPLETE]" in response
        if is_complete:
            response = response.replace("[REQUIREMENTS_COMPLETE]", "").strip()
            # 提取结构化需求
            requirements = await self._extract_requirements(skill, state)
            state.is_complete = True
        else:
            requirements = None

        # 记录助手回复
        state.conversation_history.append({
            "role": "assistant",
            "content": response
        })

        return {
            "response": response,
            "state": state,
            "is_complete": is_complete,
            "requirements": requirements,
        }

    def _build_initial_prompt(self, skill: BaseSkill) -> str:
        """构建初始引导语"""
        fields = skill.requirement_fields
        required_fields = [f for f in fields if f.collection == "required"]
        optional_fields = [f for f in fields if f.collection == "optional"]

        required_fields.sort(key=lambda f: (f.priority, f.name))
        optional_fields.sort(key=lambda f: (f.priority, f.name))

        prompt = f"""您好！我是您的申报书写作助手，将帮助您撰写「{skill.metadata.name}」。

为了更好地为您服务，我需要了解一些基本信息。

"""
        # Handle case when there are required fields
        if required_fields:
            prompt += "首先，请告诉我：\n"
            prompt += f"1. **{required_fields[0].name}**：{required_fields[0].description or ''}"
            if required_fields[0].example:
                prompt += f"（示例：{required_fields[0].example}）"
            prompt += "\n"
            if len(required_fields) > 1:
                prompt += f"2. **{required_fields[1].name}**：{required_fields[1].description or ''}"
                if required_fields[1].example:
                    prompt += f"（示例：{required_fields[1].example}）"
                prompt += "\n"
        elif optional_fields:
            # If no required fields but there are optional fields
            prompt += "首先，请告诉我：\n"
            prompt += f"1. **{optional_fields[0].name}**：{optional_fields[0].description or ''}"
            if optional_fields[0].example:
                prompt += f"（示例：{optional_fields[0].example}）"
            prompt += "\n"
            if len(optional_fields) > 1:
                prompt += f"2. **{optional_fields[1].name}**：{optional_fields[1].description or ''}"
                if optional_fields[1].example:
                    prompt += f"（示例：{optional_fields[1].example}）"
                prompt += "\n"
        else:
            # No fields at all - ask for general project info
            prompt += "首先，请简单介绍一下您的项目：\n"
            prompt += "1. **项目名称**：您的项目叫什么？\n"
            prompt += "2. **研究内容**：主要研究什么？\n"

        prompt += "\n请随时告诉我，我们开始吧！"
        return prompt

    def _build_messages(self, skill: BaseSkill, state: RequirementState) -> List[Dict]:
        """构建 LLM 消息列表"""
        # 系统提示
        system_content = self.SYSTEM_PROMPT + "\n\n"
        system_content += f"## 当前任务\n撰写「{skill.metadata.name}」\n\n"
        system_content += "## 需要收集的信息\n"
        for field in skill.requirement_fields:
            status = "✓ 已收集" if field.id in state.collected else "○ 待收集"
            if field.collection == "infer":
                status = "※ 材料推断"
            required_mark = "*" if field.collection == "required" else ""
            example = f" 示例: {field.example}" if field.example else ""
            system_content += (
                f"- {field.name}{required_mark} "
                f"(优先级: P{field.priority}, 层级: {field.collection}): "
                f"{field.description}{example} [{status}]\n"
            )

        system_content += "\n## 已收集的信息\n"
        if state.collected:
            for key, value in state.collected.items():
                system_content += f"- {key}: {value}\n"
        else:
            system_content += "（暂无）\n"

        messages = [{"role": "system", "content": system_content}]

        # 添加对话历史
        for msg in state.conversation_history:
            messages.append(msg)

        return messages

    async def _extract_requirements(
        self,
        skill: BaseSkill,
        state: RequirementState
    ) -> Dict[str, Any]:
        """从对话历史中提取结构化需求"""
        conversation_text = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in state.conversation_history
        ])

        fields_desc = "\n".join([
            f"- {f.id}: {f.name} ({f.description})"
            for f in skill.requirement_fields
        ])

        prompt = f"""请从以下对话中提取结构化的项目需求信息。

## 对话记录
{conversation_text}

## 需要提取的字段
{fields_desc}

请以 JSON 格式输出提取的信息，字段名使用上述定义的 id。
如果某个字段在对话中未提及，设为 null。

输出格式：
```json
{{
    "field_id_1": "value1",
    "field_id_2": "value2",
    ...
}}
```
"""

        messages = [
            {"role": "system", "content": "你是一个信息提取助手，负责从对话中提取结构化数据。"},
            {"role": "user", "content": prompt}
        ]

        response = await self._chat(messages, temperature=0)

        # 解析 JSON
        import json
        import re

        # 提取 JSON 块
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return state.collected
