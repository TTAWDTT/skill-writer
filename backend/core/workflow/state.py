"""
会话状态定义
独立文件以避免循环导入
"""
from typing import Dict, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class UploadedFile:
    """上传的文件信息"""
    filename: str
    content_type: str
    content: str  # 解析后的文本内容
    extracted_info: Dict = field(default_factory=dict)  # LLM 提取的信息
    uploaded_at: str = field(default_factory=lambda: datetime.now().isoformat())


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

    # 上传的文件列表
    uploaded_files: List[Dict] = field(default_factory=list)

    # 外部信息 - 从文件中提取的额外有价值信息
    external_information: str = ""

    # 会话级 Skill 覆盖（仅对当前会话生效）
    skill_overlay: Optional[Dict] = None

    # Planner 输出的全文蓝图（可用于前端展示/复用）
    planner_plan: Optional[Dict] = None

    # 会话内生成的图示（SVG 等，可下载/可复用）
    diagrams: List[Dict] = field(default_factory=list)

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

    def add_uploaded_file(self, file_info: Dict):
        """添加上传的文件"""
        self.uploaded_files.append(file_info)
        self.update_timestamp()

    def append_external_info(self, info: str):
        """追加外部信息"""
        if self.external_information:
            self.external_information += "\n\n---\n\n" + info
        else:
            self.external_information = info
        self.update_timestamp()
