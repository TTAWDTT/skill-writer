"""
数据库支持的会话存储
"""
from typing import Optional, List
from datetime import datetime
import json

from backend.models.database import Database, Session as SessionModel, get_database
from backend.core.workflow.state import SessionState


class DatabaseSessionStore:
    """数据库支持的会话存储"""

    def __init__(self, database: Optional[Database] = None):
        self.db = database or get_database()

    def get(self, session_id: str) -> Optional[SessionState]:
        """获取会话"""
        with self.db.get_session() as db_session:
            record = db_session.query(SessionModel).filter(SessionModel.id == session_id).first()
            if not record:
                return None

            return SessionState(
                session_id=record.id,
                skill_id=record.skill_id,
                phase=record.phase,
                requirement_state=json.loads(record.requirement_state) if record.requirement_state else None,
                requirements=json.loads(record.requirements) if record.requirements else None,
                writing_state=json.loads(record.writing_state) if record.writing_state else None,
                sections=json.loads(record.sections) if record.sections else {},
                review_results=json.loads(record.review_results) if record.review_results else {},
                final_document=record.final_document,
                messages=json.loads(record.messages) if record.messages else [],
                uploaded_files=json.loads(record.uploaded_files) if record.uploaded_files else [],
                external_information=record.external_information or "",
                created_at=record.created_at.isoformat() if record.created_at else datetime.now().isoformat(),
                updated_at=record.updated_at.isoformat() if record.updated_at else datetime.now().isoformat(),
                error=record.error,
            )

    def save(self, session: SessionState):
        """保存会话"""
        with self.db.get_session() as db_session:
            record = db_session.query(SessionModel).filter(SessionModel.id == session.session_id).first()

            if record:
                # 更新现有记录
                record.skill_id = session.skill_id
                record.phase = session.phase
                record.requirement_state = json.dumps(session.requirement_state) if session.requirement_state else None
                record.requirements = json.dumps(session.requirements) if session.requirements else None
                record.writing_state = json.dumps(session.writing_state) if session.writing_state else None
                record.sections = json.dumps(session.sections)
                record.review_results = json.dumps(session.review_results)
                record.messages = json.dumps(session.messages)
                record.uploaded_files = json.dumps(session.uploaded_files)
                record.external_information = session.external_information
                record.final_document = session.final_document
                record.error = session.error
                record.updated_at = datetime.utcnow()
            else:
                # 创建新记录
                record = SessionModel(
                    id=session.session_id,
                    skill_id=session.skill_id,
                    phase=session.phase,
                    requirement_state=json.dumps(session.requirement_state) if session.requirement_state else None,
                    requirements=json.dumps(session.requirements) if session.requirements else None,
                    writing_state=json.dumps(session.writing_state) if session.writing_state else None,
                    sections=json.dumps(session.sections),
                    review_results=json.dumps(session.review_results),
                    messages=json.dumps(session.messages),
                    uploaded_files=json.dumps(session.uploaded_files),
                    external_information=session.external_information,
                    final_document=session.final_document,
                    error=session.error,
                )
                db_session.add(record)

            db_session.commit()

    def delete(self, session_id: str):
        """删除会话"""
        with self.db.get_session() as db_session:
            record = db_session.query(SessionModel).filter(SessionModel.id == session_id).first()
            if record:
                db_session.delete(record)
                db_session.commit()

    def list_all(self, limit: int = 100) -> List[SessionState]:
        """列出所有会话"""
        with self.db.get_session() as db_session:
            records = db_session.query(SessionModel).order_by(SessionModel.updated_at.desc()).limit(limit).all()
            return [
                SessionState(
                    session_id=r.id,
                    skill_id=r.skill_id,
                    phase=r.phase,
                    requirement_state=json.loads(r.requirement_state) if r.requirement_state else None,
                    requirements=json.loads(r.requirements) if r.requirements else None,
                    writing_state=json.loads(r.writing_state) if r.writing_state else None,
                    sections=json.loads(r.sections) if r.sections else {},
                    review_results=json.loads(r.review_results) if r.review_results else {},
                    final_document=r.final_document,
                    messages=json.loads(r.messages) if r.messages else [],
                    uploaded_files=json.loads(r.uploaded_files) if r.uploaded_files else [],
                    external_information=r.external_information or "",
                    created_at=r.created_at.isoformat() if r.created_at else datetime.now().isoformat(),
                    updated_at=r.updated_at.isoformat() if r.updated_at else datetime.now().isoformat(),
                    error=r.error,
                )
                for r in records
            ]

    def list_by_skill(self, skill_id: str, limit: int = 100) -> List[SessionState]:
        """按 Skill 列出会话"""
        with self.db.get_session() as db_session:
            records = (
                db_session.query(SessionModel)
                .filter(SessionModel.skill_id == skill_id)
                .order_by(SessionModel.updated_at.desc())
                .limit(limit)
                .all()
            )
            return [
                SessionState(
                    session_id=r.id,
                    skill_id=r.skill_id,
                    phase=r.phase,
                    requirement_state=json.loads(r.requirement_state) if r.requirement_state else None,
                    requirements=json.loads(r.requirements) if r.requirements else None,
                    writing_state=json.loads(r.writing_state) if r.writing_state else None,
                    sections=json.loads(r.sections) if r.sections else {},
                    review_results=json.loads(r.review_results) if r.review_results else {},
                    final_document=r.final_document,
                    messages=json.loads(r.messages) if r.messages else [],
                    uploaded_files=json.loads(r.uploaded_files) if r.uploaded_files else [],
                    external_information=r.external_information or "",
                    created_at=r.created_at.isoformat() if r.created_at else datetime.now().isoformat(),
                    updated_at=r.updated_at.isoformat() if r.updated_at else datetime.now().isoformat(),
                    error=r.error,
                )
                for r in records
            ]
