"""
Job store

Lightweight helper around the Job ORM model for creating and
updating background tasks.
"""
from __future__ import annotations

from typing import Optional, Dict, Any, List
from datetime import datetime
import json
import uuid

from backend.models.database import Database, Job, get_database


class JobStore:
    """后台任务存储封装."""

    def __init__(self, database: Optional[Database] = None):
        self.db = database or get_database()

    def create_job(self, *, owner_token: str, job_type: str, payload: Optional[Dict[str, Any]] = None) -> Job:
        now = datetime.utcnow()
        job_id = str(uuid.uuid4())
        with self.db.get_session() as db_session:
            record = Job(
                id=job_id,
                owner_token=owner_token or "",
                type=job_type,
                status="pending",
                payload=json.dumps(payload or {}, ensure_ascii=False),
                result=None,
                error=None,
                created_at=now,
                updated_at=now,
            )
            db_session.add(record)
            db_session.commit()
            db_session.refresh(record)
            return record

    def get_job(self, job_id: str) -> Optional[Job]:
        with self.db.get_session() as db_session:
            return db_session.query(Job).filter(Job.id == job_id).first()

    def update_job(
        self,
        job_id: str,
        *,
        status: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Optional[Job]:
        with self.db.get_session() as db_session:
            record = db_session.query(Job).filter(Job.id == job_id).first()
            if not record:
                return None

            if status is not None:
                record.status = status
            if result is not None:
                record.result = json.dumps(result, ensure_ascii=False)
            if error is not None:
                record.error = error
            record.updated_at = datetime.utcnow()
            db_session.commit()
            db_session.refresh(record)
            return record

    def list_jobs_for_owner(self, owner_token: str, limit: int = 50) -> List[Job]:
        with self.db.get_session() as db_session:
            return (
                db_session.query(Job)
                .filter(Job.owner_token == owner_token)
                .order_by(Job.created_at.desc())
                .limit(limit)
                .all()
            )

