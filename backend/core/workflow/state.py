"""
会话状态定义
独立文件以避免循环导入
"""
from typing import Dict, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class SessionState:
    """会话状态"""
    session_id: str
    skill_id: str
    phase: str = "init"  # init, requirement, writing, review, complete, error

    # 需求收集状态
    requirement_state: Optional[Dict] = None
    requirements: Optional[Dict] = None

    # 写作状态
    writing_state: Optional[Dict] = None
    sections: Dict[str, str] = field(default_factory=dict)

    # 审核结果
    review_results: Dict[str, Dict] = field(default_factory=dict)

    # 最终文档
    final_document: Optional[str] = None

    # 对话历史
    messages: list = field(default_factory=list)

    # 时间戳
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # 错误信息
    error: Optional[str] = None

    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "SessionState":
        """从字典创建"""
        return cls(**data)

    def update_timestamp(self):
        """更新时间戳"""
        self.updated_at = datetime.now().isoformat()
