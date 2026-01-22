"""
简化的工作流管理
不使用复杂的 LangGraph 状态机，采用更直接的方式
"""
from typing import Dict, Any, Optional, AsyncGenerator
from dataclasses import asdict
from datetime import datetime
import uuid

from backend.core.skills.registry import get_registry
from backend.core.skills.base import BaseSkill
from backend.core.skills.overlay import apply_skill_overlay
from backend.core.agents.requirement_agent import RequirementAgent, RequirementState
from backend.core.agents.writer_agent import WriterAgent, WritingState
from backend.core.agents.reviewer_agent import ReviewerAgent

# 从独立模块导入 SessionState 避免循环依赖
from backend.core.workflow.state import SessionState


class SessionStore:
    """会话存储（内存版，后续可替换为数据库）"""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}

    def get(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    def save(self, session: SessionState):
        session.update_timestamp()
        self._sessions[session.session_id] = session

    def delete(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]

    def list_all(self) -> list:
        return list(self._sessions.values())


# 延迟导入 DatabaseSessionStore 避免循环依赖
def _get_database_store():
    from backend.models.session_store import DatabaseSessionStore
    return DatabaseSessionStore()


class SimpleWorkflow:
    """
    简化的文书生成工作流
    """

    def __init__(self, store=None):
        self.registry = get_registry()
        self.requirement_agent = RequirementAgent()
        self.writer_agent = WriterAgent()
        self.reviewer_agent = ReviewerAgent()
        self.store = store or _get_database_store()

    def create_session(self, skill_id: str) -> SessionState:
        """创建新会话"""
        session = SessionState(
            session_id=str(uuid.uuid4()),
            skill_id=skill_id,
        )
        self.store.save(session)
        return session

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """获取会话"""
        return self.store.get(session_id)

    def save_session(self, session: SessionState):
        """保存会话"""
        self.store.save(session)

    async def start_session(self, skill_id: str) -> Dict[str, Any]:
        """
        开始新会话，返回初始问候语
        """
        skill = self.registry.get(skill_id)
        if not skill:
            return {
                "error": f"未找到 Skill: {skill_id}",
                "session_id": None,
            }

        # 创建会话
        session = self.create_session(skill_id)

        # 获取初始问候
        result = await self.requirement_agent.run(skill, "", None)

        # 更新会话状态
        session.phase = "requirement"
        session.requirement_state = asdict(result["state"])
        session.messages.append({
            "role": "assistant",
            "content": result["response"],
            "timestamp": datetime.now().isoformat(),
        })
        self.store.save(session)

        return {
            "session_id": session.session_id,
            "phase": session.phase,
            "message": result["response"],
            "is_complete": False,
        }

    async def chat(self, session_id: str, user_message: str) -> Dict[str, Any]:
        """
        处理用户消息
        """
        session = self.get_session(session_id)
        if not session:
            return {"error": f"会话不存在: {session_id}"}

        skill = self.registry.get(session.skill_id)
        if not skill:
            return {"error": f"Skill 不存在: {session.skill_id}"}
        skill = apply_skill_overlay(skill, session.skill_overlay)

        # 记录用户消息
        session.messages.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat(),
        })

        # 根据当前阶段处理
        if session.phase == "requirement":
            return await self._handle_requirement_phase(session, skill, user_message)
        elif session.phase == "writing":
            # 写作阶段不需要用户输入，直接返回状态
            return {
                "session_id": session_id,
                "phase": session.phase,
                "message": "正在生成文档，请稍候...",
                "is_complete": False,
            }
        elif session.phase == "complete":
            return {
                "session_id": session_id,
                "phase": session.phase,
                "message": "文档已生成完成。",
                "is_complete": True,
                "document": session.final_document,
            }
        else:
            return {"error": f"未知阶段: {session.phase}"}

    async def _handle_requirement_phase(
        self,
        session: SessionState,
        skill: BaseSkill,
        user_message: str
    ) -> Dict[str, Any]:
        """处理需求收集阶段"""
        # 重建需求状态
        req_state = None
        if session.requirement_state:
            req_state = RequirementState(**session.requirement_state)

        # 调用需求 Agent
        result = await self.requirement_agent.run(skill, user_message, req_state)

        # 更新会话
        session.requirement_state = asdict(result["state"])
        session.messages.append({
            "role": "assistant",
            "content": result["response"],
            "timestamp": datetime.now().isoformat(),
        })

        response = {
            "session_id": session.session_id,
            "phase": "requirement",
            "message": result["response"],
            "is_complete": False,
        }

        # 如果需求收集完成，进入写作阶段
        if result["is_complete"]:
            session.requirements = result["requirements"]
            session.phase = "writing"
            response["phase"] = "writing"
            response["message"] += "\n\n需求收集完成，开始生成文档..."

        self.store.save(session)
        return response

    async def generate_document(self, session_id: str) -> Dict[str, Any]:
        """
        生成文档（非流式）
        """
        session = self.get_session(session_id)
        if not session:
            return {"error": f"���话不存在: {session_id}"}

        if session.phase != "writing":
            return {"error": f"当前阶段不支持生成文档: {session.phase}"}

        skill = self.registry.get(session.skill_id)
        if not skill:
            return {"error": f"Skill 不存在: {session.skill_id}"}

        try:
            flat_sections = skill.get_flat_sections()
            state = WritingState(
                skill_id=skill.metadata.id,
                requirements=session.requirements or {},
                total_sections=len(flat_sections),
                external_information=session.external_information,
            )
            session.sections = {}
            session.review_results = {}

            contents = []
            for section in flat_sections:
                state.current_section = section.id
                section_result = await self.writer_agent.write_section_with_review(
                    skill=skill,
                    section=section,
                    requirements=session.requirements or {},
                    state=state,
                    reviewer_agent=self.reviewer_agent,
                )

                content = section_result["content"]
                review = section_result["review"]
                state.sections[section.id] = content
                state.completed_sections.append(section.id)
                session.sections[section.id] = content
                session.review_results[section.id] = {
                    "section_id": section.id,
                    "outline": section_result["outline"],
                    "draft": section_result["draft"],
                    "score": review.score,
                    "passed": review.passed,
                    "issues": review.issues,
                    "suggestions": review.suggestions,
                    "revised_content": review.revised_content,
                    "revised": section_result["revised"],
                }

                heading = "#" * section.level + " " + section.title
                contents.append(f"{heading}\n\n{content}")

            combined = "\n\n".join(contents)
            session.writing_state = asdict(state)
            session.final_document = self.writer_agent._dedupe_adjacent_heading_lines(combined)
            session.phase = "complete"
            self.store.save(session)

            return {
                "session_id": session_id,
                "phase": "complete",
                "message": "文档生成完成！",
                "is_complete": True,
                "document": session.final_document,
            }

        except Exception as e:
            session.phase = "error"
            session.error = str(e)
            self.store.save(session)
            return {"error": str(e)}

    async def generate_document_stream(
        self,
        session_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式生成文档
        """
        session = self.get_session(session_id)
        if not session:
            yield {"type": "error", "error": f"会话不存在: {session_id}"}
            return

        if session.phase != "writing":
            yield {"type": "error", "error": f"当前阶段不支持生成文档: {session.phase}"}
            return

        skill = self.registry.get(session.skill_id)
        if not skill:
            yield {"type": "error", "error": f"Skill 不存在: {session.skill_id}"}
            return
        skill = apply_skill_overlay(skill, session.skill_overlay)

        # 发送开始事件
        yield {
            "type": "start",
            "session_id": session_id,
            "total_sections": len(skill.get_flat_sections()),
        }

        try:
            flat_sections = skill.get_flat_sections()
            state = WritingState(
                skill_id=skill.metadata.id,
                requirements=session.requirements or {},
                total_sections=len(flat_sections),
                external_information=session.external_information,
            )
            session.sections = {}
            session.review_results = {}
            all_content = []

            for i, section in enumerate(flat_sections):
                # 发送章节开始事件
                yield {
                    "type": "section_start",
                    "section_id": section.id,
                    "section_title": section.title,
                    "section_level": section.level,
                    "section_index": i + 1,
                    "total_sections": len(flat_sections),
                }

                yield {
                    "type": "stage_start",
                    "stage": "outline",
                    "section_id": section.id,
                    "section_title": section.title,
                }
                outline = await self.writer_agent.generate_outline(
                    skill=skill,
                    section=section,
                    requirements=session.requirements or {},
                    state=state,
                )
                yield {
                    "type": "stage_complete",
                    "stage": "outline",
                    "section_id": section.id,
                    "section_title": section.title,
                }

                yield {
                    "type": "stage_start",
                    "stage": "draft",
                    "section_id": section.id,
                    "section_title": section.title,
                }
                draft = await self.writer_agent.generate_draft(
                    skill=skill,
                    section=section,
                    requirements=session.requirements or {},
                    state=state,
                    outline=outline,
                )
                yield {
                    "type": "stage_complete",
                    "stage": "draft",
                    "section_id": section.id,
                    "section_title": section.title,
                }

                yield {
                    "type": "stage_start",
                    "stage": "review",
                    "section_id": section.id,
                    "section_title": section.title,
                }
                review = await self.reviewer_agent.run(
                    skill=skill,
                    section_id=section.id,
                    content=draft,
                    requirements=session.requirements or {},
                )
                should_revise = not review.revised_content and (not review.passed or review.score < 80)
                yield {
                    "type": "stage_complete",
                    "stage": "review",
                    "section_id": section.id,
                    "section_title": section.title,
                    "score": review.score,
                    "passed": review.passed,
                    "will_revise": should_revise,
                }

                final_content = draft
                revised = False
                if review.revised_content:
                    final_content = review.revised_content
                    revised = True
                elif should_revise:
                    yield {
                        "type": "stage_start",
                        "stage": "revise",
                        "section_id": section.id,
                        "section_title": section.title,
                    }
                    final_content = await self.writer_agent.revise_section(
                        skill=skill,
                        section=section,
                        requirements=session.requirements or {},
                        state=state,
                        draft=draft,
                        issues=review.issues,
                        suggestions=review.suggestions,
                    )
                    yield {
                        "type": "stage_complete",
                        "stage": "revise",
                        "section_id": section.id,
                        "section_title": section.title,
                    }
                    revised = True

                final_content = self.writer_agent._postprocess_section(section, final_content)

                # 保存章节内容
                state.sections[section.id] = final_content
                state.completed_sections.append(section.id)
                session.sections[section.id] = final_content
                session.review_results[section.id] = {
                    "section_id": section.id,
                    "outline": outline,
                    "draft": draft,
                    "score": review.score,
                    "passed": review.passed,
                    "issues": review.issues,
                    "suggestions": review.suggestions,
                    "revised_content": review.revised_content,
                    "revised": revised,
                }
                session.writing_state = asdict(state)
                self.store.save(session)

                yield {
                    "type": "chunk",
                    "section_id": section.id,
                    "content": final_content,
                }

                # 格式化为 Markdown
                heading = "#" * section.level + " " + section.title
                all_content.append(f"{heading}\n\n{final_content}")

                # 发送章节完成事件
                yield {
                    "type": "section_complete",
                    "section_id": section.id,
                    "section_title": section.title,
                }

            # 组装最终文档
            combined = "\n\n".join(all_content)
            session.final_document = self.writer_agent._dedupe_adjacent_heading_lines(combined)
            session.phase = "complete"
            self.store.save(session)

            # 发送完成事件
            yield {
                "type": "complete",
                "session_id": session_id,
                "document": session.final_document,
            }

        except Exception as e:
            session.phase = "error"
            session.error = str(e)
            self.store.save(session)
            yield {"type": "error", "error": str(e)}

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


# 全局工作流实例
_workflow: Optional[SimpleWorkflow] = None
_store = None


def get_store():
    """获取全局会话存储（默认使用数据库存储）"""
    global _store
    if _store is None:
        # 使用数据库存储实现持久化
        _store = _get_database_store()
    return _store


def get_workflow() -> SimpleWorkflow:
    """获取全局工作流实例"""
    global _workflow
    if _workflow is None:
        _workflow = SimpleWorkflow(store=get_store())
    return _workflow
