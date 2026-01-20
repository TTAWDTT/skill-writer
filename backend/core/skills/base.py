"""
Skill 基类定义
每个文书类型对应一个 Skill，包含结构模板、写作规范、评审要点等
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class SectionType(str, Enum):
    """章节类型"""
    REQUIRED = "required"      # 必填
    OPTIONAL = "optional"      # 选填
    CONDITIONAL = "conditional"  # 条件性必填


class Section(BaseModel):
    """章节定义"""
    id: str
    title: str
    level: int = 1  # 1, 2, 3 级标题
    type: SectionType = SectionType.REQUIRED
    description: str = ""  # 章节说明
    word_limit: Optional[tuple[int, int]] = None  # (最小, 最大) 字数
    children: List["Section"] = Field(default_factory=list)
    writing_guide: str = ""  # 写作指导
    evaluation_points: List[str] = Field(default_factory=list)  # 评审要点
    examples: List[str] = Field(default_factory=list)  # 写作示例


class RequirementField(BaseModel):
    """需求字段定义"""
    id: str
    name: str
    description: str
    field_type: str = "text"  # text, textarea, select, multiselect
    required: bool = True
    options: Optional[List[str]] = None  # 用于 select 类型
    placeholder: str = ""
    validation_prompt: str = ""  # 用于 AI 验证输入质量


class SkillMetadata(BaseModel):
    """Skill 元数据"""
    id: str
    name: str
    description: str
    version: str = "1.0.0"
    category: str = ""  # 如：科研基金、专利、企业项目
    tags: List[str] = Field(default_factory=list)
    author: str = ""
    created_at: str = ""
    updated_at: str = ""


class BaseSkill(ABC):
    """
    Skill 基类
    每个具体的文书类型继承此类实现
    """

    def __init__(self):
        self._metadata: Optional[SkillMetadata] = None
        self._structure: Optional[List[Section]] = None
        self._requirements: Optional[List[RequirementField]] = None

    @property
    @abstractmethod
    def metadata(self) -> SkillMetadata:
        """返回 Skill 元数据"""
        pass

    @property
    @abstractmethod
    def structure(self) -> List[Section]:
        """返回文书结构模板"""
        pass

    @property
    @abstractmethod
    def requirement_fields(self) -> List[RequirementField]:
        """返回需求收集字段"""
        pass

    @property
    @abstractmethod
    def writing_guidelines(self) -> str:
        """返回整体写作规范"""
        pass

    @property
    @abstractmethod
    def evaluation_criteria(self) -> str:
        """返回评审标准说明"""
        pass

    @abstractmethod
    def get_section_prompt(self, section: Section, context: Dict[str, Any]) -> str:
        """
        获取特定章节的写作 prompt

        Args:
            section: 章节定义
            context: 上下文信息（包含用户需求、已写内容等）

        Returns:
            用于 LLM 的写作 prompt
        """
        pass

    @abstractmethod
    def validate_section(self, section: Section, content: str) -> Dict[str, Any]:
        """
        验证章节内容质量

        Args:
            section: 章节定义
            content: 生成的内容

        Returns:
            验证结果，包含 is_valid, issues, suggestions
        """
        pass

    def get_flat_sections(self) -> List[Section]:
        """获取扁平化的章节列表"""
        result = []

        def flatten(sections: List[Section]):
            for section in sections:
                result.append(section)
                if section.children:
                    flatten(section.children)

        flatten(self.structure)
        return result

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "metadata": self.metadata.model_dump(),
            "structure": [s.model_dump() for s in self.structure],
            "requirement_fields": [r.model_dump() for r in self.requirement_fields],
            "writing_guidelines": self.writing_guidelines,
            "evaluation_criteria": self.evaluation_criteria,
        }
