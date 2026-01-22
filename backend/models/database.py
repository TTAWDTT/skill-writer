"""
数据库模型
使用 SQLAlchemy 定义数据模型
"""
from datetime import datetime
from typing import Optional
import json
import os

from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

Base = declarative_base()


class Session(Base):
    """会话模型"""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    skill_id = Column(String(100), nullable=False, index=True)
    phase = Column(String(50), default="init")

    # JSON 存储的字段
    requirement_state = Column(Text, nullable=True)  # JSON
    requirements = Column(Text, nullable=True)  # JSON
    writing_state = Column(Text, nullable=True)  # JSON
    sections = Column(Text, default="{}")  # JSON
    review_results = Column(Text, default="{}")  # JSON
    messages = Column(Text, default="[]")  # JSON

    # 上传的文件信息
    uploaded_files = Column(Text, default="[]")  # JSON

    # 外部信息 - 从文件中提取的额外有价值信息
    external_information = Column(Text, default="")

    # 会话级 Skill 覆盖
    skill_overlay = Column(Text, nullable=True)  # JSON

    # 文档
    final_document = Column(Text, nullable=True)

    # 错误
    error = Column(Text, nullable=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "session_id": self.id,
            "skill_id": self.skill_id,
            "phase": self.phase,
            "requirement_state": json.loads(self.requirement_state) if self.requirement_state else None,
            "requirements": json.loads(self.requirements) if self.requirements else None,
            "writing_state": json.loads(self.writing_state) if self.writing_state else None,
            "sections": json.loads(self.sections) if self.sections else {},
            "review_results": json.loads(self.review_results) if self.review_results else {},
            "messages": json.loads(self.messages) if self.messages else [],
            "uploaded_files": json.loads(self.uploaded_files) if self.uploaded_files else [],
            "external_information": self.external_information or "",
            "skill_overlay": json.loads(self.skill_overlay) if self.skill_overlay else None,
            "final_document": self.final_document,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Document(Base):
    """文档模型"""
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), nullable=True, index=True)
    skill_id = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)

    # 元数据
    sections = Column(Text, default="{}")  # JSON

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "skill_id": self.skill_id,
            "title": self.title,
            "content": self.content,
            "sections": json.loads(self.sections) if self.sections else {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Database:
    """数据库管理类"""

    def __init__(self, database_url: str = "sqlite:///./data/skillwriter.db"):
        # 对于 SQLite，使用特殊配置以支持多线程
        if database_url.startswith("sqlite"):
            self.engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            self.engine = create_engine(database_url)

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        """创建所有表"""
        Base.metadata.create_all(bind=self.engine)
        self._ensure_session_columns()

    def _ensure_session_columns(self):
        """为已有数据库补齐新列"""
        if not self.engine.url.get_backend_name().startswith("sqlite"):
            return

        inspector = inspect(self.engine)
        if "sessions" not in inspector.get_table_names():
            return

        existing_columns = {col["name"] for col in inspector.get_columns("sessions")}
        if "skill_overlay" not in existing_columns:
            with self.engine.begin() as connection:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN skill_overlay TEXT"))

    def get_session(self):
        """获取数据库会话"""
        return self.SessionLocal()


# 全局数据库实例
_database: Optional[Database] = None


def get_database() -> Database:
    """获取全局数据库实例"""
    global _database
    if _database is None:
        from backend.config import settings, DATA_DIR
        # 确保数据目录存在
        os.makedirs(DATA_DIR, exist_ok=True)
        _database = Database(settings.DATABASE_URL)
        _database.create_tables()
    return _database
