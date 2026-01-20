"""
Sessions API 路由
管理会话历史记录
"""
from fastapi import APIRouter, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from backend.models.session_store import DatabaseSessionStore

router = APIRouter()
store = DatabaseSessionStore()


class SessionSummary(BaseModel):
    """会话摘要"""
    session_id: str
    skill_id: str
    phase: str
    message_count: int
    has_document: bool
    created_at: str
    updated_at: str


class SessionDetail(BaseModel):
    """会话详情"""
    session_id: str
    skill_id: str
    phase: str
    messages: List[dict]
    sections: dict
    final_document: Optional[str]
    created_at: str
    updated_at: str


@router.get("/", response_model=List[SessionSummary])
async def list_sessions(
    skill_id: Optional[str] = None,
    limit: int = 50
):
    """
    列出会话历史

    - 可选按 skill_id 筛选
    - 返回最近的会话列表
    """
    if skill_id:
        sessions = store.list_by_skill(skill_id, limit=limit)
    else:
        sessions = store.list_all(limit=limit)

    return [
        SessionSummary(
            session_id=s.session_id,
            skill_id=s.skill_id,
            phase=s.phase,
            message_count=len(s.messages) if s.messages else 0,
            has_document=s.final_document is not None,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str):
    """获取会话详情"""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return SessionDetail(
        session_id=session.session_id,
        skill_id=session.skill_id,
        phase=session.phase,
        messages=session.messages,
        sections=session.sections,
        final_document=session.final_document,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    store.delete(session_id)
    return {"message": f"Session {session_id} deleted"}


@router.get("/{session_id}/document")
async def get_session_document(session_id: str):
    """获取会话生成的文档"""
    session = store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not session.final_document:
        raise HTTPException(status_code=404, detail="Document not generated yet")

    return {
        "session_id": session_id,
        "skill_id": session.skill_id,
        "document": session.final_document,
        "sections": session.sections,
    }
