"""
Chat API 路由
处理与工作流的交互对话，支持流式输出
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import json

from backend.core.workflow import get_workflow
from backend.core.skills.registry import get_registry

router = APIRouter()


class StartSessionRequest(BaseModel):
    """开始会话请求"""
    skill_id: str


class ChatRequest(BaseModel):
    """对话请求"""
    session_id: str
    message: str


class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str
    phase: str
    message: str
    is_complete: bool
    document: Optional[str] = None


@router.post("/start", response_model=SessionResponse)
async def start_session(request: StartSessionRequest):
    """
    开始新会话

    - 传入 skill_id，创建新会话
    - 返回初始问候语和 session_id
    """
    # 验证 skill 存在
    registry = get_registry()
    skill = registry.get(request.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {request.skill_id}")

    # 开始会话
    workflow = get_workflow()
    result = await workflow.start_session(request.skill_id)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return SessionResponse(
        session_id=result["session_id"],
        phase=result["phase"],
        message=result["message"],
        is_complete=result["is_complete"],
    )


@router.post("/message", response_model=SessionResponse)
async def send_message(request: ChatRequest):
    """
    发送消息

    - 在需求收集阶段，发送用户回复
    - 如果需求收集完成，自动进入写作阶段
    """
    workflow = get_workflow()
    result = await workflow.chat(request.session_id, request.message)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return SessionResponse(
        session_id=result["session_id"],
        phase=result["phase"],
        message=result["message"],
        is_complete=result.get("is_complete", False),
        document=result.get("document"),
    )


@router.post("/generate/{session_id}")
async def generate_document(session_id: str):
    """
    生成文档（非流式）

    - 在 writing 阶段调用
    - 返回生成的完整文档
    """
    workflow = get_workflow()
    result = await workflow.generate_document(session_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return SessionResponse(
        session_id=result["session_id"],
        phase=result["phase"],
        message=result["message"],
        is_complete=result.get("is_complete", False),
        document=result.get("document"),
    )


@router.get("/generate/{session_id}/stream")
async def generate_document_stream(session_id: str):
    """
    流式生成文档（SSE）

    - 在 writing 阶段调用
    - 实时返回生成过程
    """
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if session.phase != "writing":
        raise HTTPException(
            status_code=400,
            detail=f"Session not in writing phase: {session.phase}"
        )

    async def event_generator():
        try:
            async for event in workflow.generate_document_stream(session_id):
                # 格式化为 SSE
                data = json.dumps(event, ensure_ascii=False)
                yield f"data: {data}\n\n"
        except Exception as e:
            error_event = json.dumps({"type": "error", "error": str(e)})
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """获取会话状态"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return {
        "session_id": session.session_id,
        "skill_id": session.skill_id,
        "phase": session.phase,
        "has_document": session.final_document is not None,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "message_count": len(session.messages),
    }


@router.get("/session/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取会话消息历史"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return {
        "session_id": session.session_id,
        "messages": session.messages,
    }


@router.get("/session/{session_id}/document")
async def get_session_document(session_id: str):
    """获取会话生成的文档"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not session.final_document:
        raise HTTPException(status_code=404, detail="Document not generated yet")

    return {
        "session_id": session.session_id,
        "document": session.final_document,
        "sections": session.sections,
    }
