"""
基于文件的 Skill 加载器
从文件夹中加载 Skill 配置
支持官方 SKILL.md 格式和传统 skill.yaml 格式
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml
import jinja2

from .base import BaseSkill, Section, SectionType, RequirementField, SkillMetadata


def parse_skill_md(content: str) -> Dict[str, Any]:
    """
    解析 SKILL.md 文件的 YAML frontmatter

    Args:
        content: SKILL.md 文件内容

    Returns:
        解析后的元数据字典
    """
    # 匹配 YAML frontmatter (---\n...\n---)
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)

    if match:
        frontmatter = match.group(1)
        body = match.group(2)
        try:
            metadata = yaml.safe_load(frontmatter)
            metadata['_body'] = body  # 保存 markdown 正文
            return metadata
        except yaml.YAMLError:
            return {'_body': content}

    return {'_body': content}


class FileBasedSkill(BaseSkill):
    """
    基于文件的 Skill 实现
    支持两种格式：
    1. 官方格式：SKILL.md (YAML frontmatter + Markdown)
    2. 传统格式：skill.yaml
    """

    def __init__(self, skill_path: Path):
        """
        初始化文件基础 Skill

        Args:
            skill_path: Skill 文件夹路径
        """
        super().__init__()
        self.skill_path = Path(skill_path)
        self._config = {}
        self._skill_content = ""  # SKILL.md 的 markdown 正文
        self._load_skill()

    def _load_skill(self):
        """加载 Skill 配置"""
        skill_md = self.skill_path / "SKILL.md"
        skill_yaml = self.skill_path / "skill.yaml"

        # 优先加载 SKILL.md（官方格式）
        if skill_md.exists():
            self._load_from_skill_md(skill_md)
        elif skill_yaml.exists():
            self._load_from_skill_yaml(skill_yaml)
        else:
            raise FileNotFoundError(f"Neither SKILL.md nor skill.yaml found in {self.skill_path}")

        # 加载辅助配置文件
        self._load_auxiliary_files()

        # 初始化 Jinja2 模板引擎
        self._jinja_env = jinja2.Environment(
            undefined=jinja2.Undefined
        )

    def _load_from_skill_md(self, skill_md: Path):
        """从 SKILL.md 加载配置"""
        with open(skill_md, 'r', encoding='utf-8') as f:
            content = f.read()

        parsed = parse_skill_md(content)
        self._skill_content = parsed.pop('_body', '')

        # 将 SKILL.md 的 frontmatter 转换为内部配置格式
        self._config = {
            'id': parsed.get('name', self.skill_path.name),
            'name': parsed.get('name', self.skill_path.name),
            'description': parsed.get('description', ''),
            'version': parsed.get('version', '1.0.0'),
            'category': parsed.get('category', ''),
            'tags': parsed.get('tags', []),
            'author': parsed.get('author', ''),
            'created_at': parsed.get('created_at', ''),
            'updated_at': parsed.get('updated_at', ''),
            # 官方格式的额外字段
            'allowed_tools': parsed.get('allowed-tools', []),
            'model': parsed.get('model', ''),
            'context': parsed.get('context', ''),
            'user_invocable': parsed.get('user-invocable', True),
        }

    def _load_from_skill_yaml(self, skill_yaml: Path):
        """从 skill.yaml 加载配置（传统格式）"""
        with open(skill_yaml, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

    def _load_auxiliary_files(self):
        """加载辅助配置文件"""
        # 加载结构定义
        structure_file = self.skill_path / "structure.yaml"
        if structure_file.exists():
            with open(structure_file, 'r', encoding='utf-8') as f:
                self._structure_config = yaml.safe_load(f) or {'sections': []}
        else:
            self._structure_config = {'sections': []}

        # 加载需求字段
        requirements_file = self.skill_path / "requirements.yaml"
        if requirements_file.exists():
            with open(requirements_file, 'r', encoding='utf-8') as f:
                self._requirements_config = yaml.safe_load(f) or {'fields': []}
        else:
            self._requirements_config = {'fields': []}

        # 加载写作规范（从 guidelines.md 或 SKILL.md 正文）
        guidelines_file = self.skill_path / "guidelines.md"
        if guidelines_file.exists():
            with open(guidelines_file, 'r', encoding='utf-8') as f:
                self._guidelines_content = f.read()
        else:
            # 如果没有单独的 guidelines.md，使用 SKILL.md 正文
            self._guidelines_content = self._skill_content

        # 加载评审标准
        evaluation_file = self.skill_path / "evaluation.md"
        if evaluation_file.exists():
            with open(evaluation_file, 'r', encoding='utf-8') as f:
                self._evaluation_content = f.read()
        else:
            self._evaluation_content = ""

        # 加载 prompts
        system_prompt_file = self.skill_path / "prompts" / "system.md"
        if system_prompt_file.exists():
            with open(system_prompt_file, 'r', encoding='utf-8') as f:
                self._system_prompt = f.read()
        else:
            self._system_prompt = ""

        section_prompt_file = self.skill_path / "prompts" / "section.md"
        if section_prompt_file.exists():
            with open(section_prompt_file, 'r', encoding='utf-8') as f:
                self._section_prompt_template = f.read()
        else:
            self._section_prompt_template = ""

    @property
    def metadata(self) -> SkillMetadata:
        """返回 Skill 元数据"""
        return SkillMetadata(
            id=self._config.get('id', ''),
            name=self._config.get('name', ''),
            description=self._config.get('description', ''),
            version=self._config.get('version', '1.0.0'),
            category=self._config.get('category', ''),
            tags=self._config.get('tags', []),
            author=self._config.get('author', ''),
            created_at=self._config.get('created_at', ''),
            updated_at=self._config.get('updated_at', ''),
        )

    @property
    def skill_content(self) -> str:
        """返回 SKILL.md 的 markdown 正文"""
        return self._skill_content

    @property
    def structure(self) -> List[Section]:
        """返回文书结构模板"""
        return self._parse_sections(self._structure_config.get('sections', []))

    def _parse_sections(self, sections_data: List[Dict]) -> List[Section]:
        """解析章节配置"""
        result = []
        for s in sections_data:
            section = Section(
                id=s.get('id', ''),
                title=s.get('title', ''),
                level=s.get('level', 1),
                type=SectionType(s.get('type', 'required')),
                description=s.get('description', ''),
                word_limit=tuple(s['word_limit']) if s.get('word_limit') else None,
                writing_guide=s.get('writing_guide', ''),
                evaluation_points=s.get('evaluation_points', []),
                examples=s.get('examples', []),
                children=self._parse_sections(s.get('children', [])),
            )
            result.append(section)
        return result

    @property
    def requirement_fields(self) -> List[RequirementField]:
        """返回需求收集字段"""
        result = []
        for f in self._requirements_config.get('fields', []):
            field = RequirementField(
                id=f.get('id', ''),
                name=f.get('name', ''),
                description=f.get('description', ''),
                field_type=f.get('type', 'text'),
                required=f.get('required', True),
                options=f.get('options'),
                placeholder=f.get('placeholder', ''),
                validation_prompt=f.get('validation_prompt', ''),
            )
            result.append(field)
        return result

    @property
    def writing_guidelines(self) -> str:
        """返回整体写作规范"""
        return self._guidelines_content

    @property
    def evaluation_criteria(self) -> str:
        """返回评审标准说明"""
        return self._evaluation_content

    @property
    def system_prompt(self) -> str:
        """返回系统提示词"""
        return self._system_prompt

    @property
    def collection_strategy(self) -> Dict:
        """返回需求收集策略"""
        return self._requirements_config.get('collection_strategy', {})

    def get_section_prompt(self, section: Section, context: Dict[str, Any]) -> str:
        """
        获取特定章节的写作 prompt

        Args:
            section: 章节定义
            context: 上下文信息（包含用户需求、已写内容等）

        Returns:
            用于 LLM 的写作 prompt
        """
        requirements = context.get('requirements', {})
        written_sections = context.get('written_sections', {})

        # 构建模板变量
        template_vars = {
            'section_title': section.title,
            'section_id': section.id,
            'section_description': section.description,
            'section_writing_guide': section.writing_guide,
            'section_word_limit': f"{section.word_limit[0]}-{section.word_limit[1]}字" if section.word_limit and len(section.word_limit) >= 2 else "无限制",
            'section_evaluation_points': '\n'.join(f"- {p}" for p in section.evaluation_points) if section.evaluation_points else "无",
            'written_sections': written_sections,
            **requirements,  # 展开所有用户需求字段
        }

        # 渲染模板
        try:
            template = self._jinja_env.from_string(self._section_prompt_template)
            return template.render(**template_vars)
        except Exception as e:
            # 如果模板渲染失败，返回简化的 prompt
            return self._get_fallback_prompt(section, context)

    def _get_fallback_prompt(self, section: Section, context: Dict[str, Any]) -> str:
        """备用 prompt 生成"""
        requirements = context.get('requirements', {})

        return f"""请撰写"{section.title}"部分。

## 项目信息
- 项目名称：{requirements.get('project_title', '未提供')}
- 研究领域：{requirements.get('research_field', '未提供')}
- 研究问题：{requirements.get('research_problem', '未提供')}
- 研究方法：{requirements.get('research_method', '未提供')}
- 创新点：{requirements.get('innovation_points', '未提供')}

## 章节要求
{section.description}

## 写作指导
{section.writing_guide}

## 字数要求
{f"{section.word_limit[0]}-{section.word_limit[1]}字" if section.word_limit and len(section.word_limit) >= 2 else "适当篇幅"}

请直接输出该章节的内容。
"""

    def validate_section(self, section: Section, content: str) -> Dict[str, Any]:
        """
        验证章节内容质量

        Args:
            section: 章节定义
            content: 生成的内容

        Returns:
            验证结果，包含 is_valid, issues, suggestions
        """
        issues = []
        suggestions = []

        # 字数检查
        word_count = len(content)
        if section.word_limit and len(section.word_limit) >= 2:
            min_words, max_words = section.word_limit[0], section.word_limit[1]
            if word_count < min_words:
                issues.append(f"字数不足：当前 {word_count} 字，要求至少 {min_words} 字")
                suggestions.append("请扩充内容，增加更多细节和论述")
            elif word_count > max_words:
                issues.append(f"字数超出：当前 {word_count} 字，要求最多 {max_words} 字")
                suggestions.append("请精简内容，删除冗余表述")

        # 内容为空检查
        if not content.strip():
            issues.append("内容为空")

        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'suggestions': suggestions,
            'word_count': word_count,
        }

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "metadata": self.metadata.model_dump(),
            "structure": [s.model_dump() for s in self.structure],
            "requirement_fields": [r.model_dump() for r in self.requirement_fields],
            "writing_guidelines": self.writing_guidelines,
            "evaluation_criteria": self.evaluation_criteria,
            "system_prompt": self.system_prompt,
            "collection_strategy": self.collection_strategy,
        }


class SkillLoader:
    """
    Skill 加载器
    负责扫描和加载所有 Skill
    支持 SKILL.md（官方格式）和 skill.yaml（传统格式）
    """

    def __init__(self, skills_dir: Path):
        """
        初始化加载器

        Args:
            skills_dir: Skills 文件夹路径
        """
        self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, FileBasedSkill] = {}

    def _is_valid_skill_dir(self, path: Path) -> bool:
        """检查是否是有效的 Skill 目录"""
        if not path.is_dir():
            return False
        # 检查是否有 SKILL.md 或 skill.yaml
        return (path / "SKILL.md").exists() or (path / "skill.yaml").exists()

    def load_all(self) -> Dict[str, FileBasedSkill]:
        """加载所有 Skill"""
        if not self.skills_dir.exists():
            return {}

        for item in self.skills_dir.iterdir():
            if self._is_valid_skill_dir(item):
                try:
                    skill = FileBasedSkill(item)
                    self._skills[skill.metadata.id] = skill
                except Exception as e:
                    print(f"Warning: Failed to load skill from {item}: {e}")

        return self._skills

    def load_skill(self, skill_id: str) -> Optional[FileBasedSkill]:
        """加载单个 Skill"""
        skill_path = self.skills_dir / skill_id
        if self._is_valid_skill_dir(skill_path):
            try:
                skill = FileBasedSkill(skill_path)
                self._skills[skill.metadata.id] = skill
                return skill
            except Exception as e:
                print(f"Warning: Failed to load skill {skill_id}: {e}")
        return None

    def get_skill(self, skill_id: str) -> Optional[FileBasedSkill]:
        """获取 Skill"""
        if skill_id not in self._skills:
            return self.load_skill(skill_id)
        return self._skills.get(skill_id)

    def list_skills(self) -> List[Dict[str, Any]]:
        """列出所有 Skill 的元信息"""
        return [
            skill.metadata.model_dump()
            for skill in self._skills.values()
        ]
