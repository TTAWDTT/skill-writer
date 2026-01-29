"""
Skill 注册表
管理所有可用的 Skill，支持动态注册和发现
"""
from typing import Dict, List, Optional, Type
from pathlib import Path

from .base import BaseSkill, SkillMetadata
from .base_writing import BaseWritingAugmentedSkill


class SkillRegistry:
    """
    Skill 注册表
    单例模式，管理所有已注册的 Skill
    支持代码定义和文件定义两种方式
    """

    _instance: Optional["SkillRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._skills: Dict[str, BaseSkill] = {}
            cls._instance._skill_classes: Dict[str, Type[BaseSkill]] = {}
            cls._instance._file_loader = None
        return cls._instance

    def register(self, skill_class: Type[BaseSkill]) -> None:
        """
        注册一个 Skill 类

        Args:
            skill_class: Skill 类（非实例）
        """
        instance = skill_class()
        skill_id = instance.metadata.id
        self._skills[skill_id] = instance
        self._skill_classes[skill_id] = skill_class

    def register_instance(self, skill: BaseSkill) -> None:
        """
        直接注册一个 Skill 实例

        Args:
            skill: Skill 实例
        """
        skill_id = skill.metadata.id
        self._skills[skill_id] = skill

    def get(self, skill_id: str) -> Optional[BaseSkill]:
        """获取 Skill 实例"""
        # 先从已注册的 Skill 中查找
        if skill_id in self._skills:
            return self._skills[skill_id]

        # 尝试从文件加载
        if self._file_loader:
            skill = self._file_loader.get_skill(skill_id)
            if skill:
                self._skills[skill_id] = skill
                return skill

        return None

    def get_all(self) -> List[BaseSkill]:
        """获取所有已注册的 Skill"""
        return list(self._skills.values())

    def get_metadata_list(self) -> List[SkillMetadata]:
        """获取所有 Skill 的元数据"""
        return [skill.metadata for skill in self._skills.values()]

    def list_by_category(self, category: str) -> List[BaseSkill]:
        """按类别筛选 Skill"""
        return [
            skill for skill in self._skills.values()
            if skill.metadata.category == category
        ]

    def search(self, query: str) -> List[BaseSkill]:
        """搜索 Skill（按名称、描述、标签）"""
        query = query.lower()
        results = []
        for skill in self._skills.values():
            meta = skill.metadata
            if (query in meta.name.lower() or
                query in meta.description.lower() or
                any(query in tag.lower() for tag in meta.tags)):
                results.append(skill)
        return results

    def unregister(self, skill_id: str) -> bool:
        """注销 Skill"""
        if skill_id in self._skills:
            del self._skills[skill_id]
            if skill_id in self._skill_classes:
                del self._skill_classes[skill_id]
            return True
        return False

    def load_from_directory(self, directory: Path) -> int:
        """
        从目录加载所有文件定义的 Skill

        Args:
            directory: Skills 文件夹路径

        Returns:
            加载的 Skill 数量
        """
        from .loader import SkillLoader

        directory = Path(directory)
        if not directory.exists():
            return 0

        self._file_loader = SkillLoader(directory)
        loaded_skills = self._file_loader.load_all()

        # Apply global BaseWritingSkill (meta skill) if present.
        base_writing = loaded_skills.get("base_writing")
        if base_writing:
            for skill_id, skill in list(loaded_skills.items()):
                if skill_id == "base_writing":
                    continue
                loaded_skills[skill_id] = BaseWritingAugmentedSkill(base_writing, skill)

        # 注册到主注册表
        for skill_id, skill in loaded_skills.items():
            self._skills[skill_id] = skill

        return len(loaded_skills)

    def reload_skill(self, skill_id: str) -> Optional[BaseSkill]:
        """
        重新加载指定的 Skill（用于热更新）

        Args:
            skill_id: Skill ID

        Returns:
            重新加载的 Skill 实例
        """
        if self._file_loader:
            # 从文件重新加载
            skill = self._file_loader.load_skill(skill_id)
            if skill:
                self._skills[skill_id] = skill
                return skill
        return None


# 全局注册表实例
_registry: Optional[SkillRegistry] = None


def get_registry() -> SkillRegistry:
    """获取全局 Skill 注册表"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry


def register_skill(skill_class: Type[BaseSkill]):
    """
    装饰器：注册 Skill 类

    Usage:
        @register_skill
        class MySkill(BaseSkill):
            ...
    """
    get_registry().register(skill_class)
    return skill_class


def init_skills_from_directory(directory: Optional[Path] = None) -> int:
    """
    从目录初始化所有 Skill

    Args:
        directory: Skills 目录，默认为 backend/data/skills

    Returns:
        加载的 Skill 数量
    """
    if directory is None:
        from backend.config import SKILLS_DIR
        directory = SKILLS_DIR

    return get_registry().load_from_directory(directory)
