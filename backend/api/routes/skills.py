"""
Skills API 路由
"""
import re
import shutil
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import List
import yaml

from backend.core.skills.registry import get_registry, init_skills_from_directory
from backend.core.skills.template_parser import parse_template_file
from backend.core.skills.skill_generator import generate_skill_with_llm
from backend.core.llm.config_store import has_llm_credentials
from backend.config import SKILLS_DIR

router = APIRouter()


@router.get("/", response_model=List[dict])
async def list_skills():
    """获取所有可用的 Skill 列表"""
    registry = get_registry()
    skills = registry.get_all()

    return [
        {
            "id": skill.metadata.id,
            "name": skill.metadata.name,
            "description": skill.metadata.description,
            "category": skill.metadata.category,
            "tags": skill.metadata.tags,
        }
        for skill in skills
    ]


@router.post("/create-from-template")
async def create_skill_from_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    category: str = Form(""),
    tags: str = Form("")
):
    """
    从模板文件创建新的 Skill（使用 LLM 分析模板）

    Args:
        file: 模板文件 (md, doc, docx, pdf, txt)
        name: Skill 名称
        description: Skill 描述
        category: 分类
        tags: 标签（逗号分隔）
    """
    # 验证文件类型
    allowed_extensions = {'.md', '.doc', '.docx', '.pdf', '.txt', '.pptx'}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Allowed: {', '.join(allowed_extensions)}"
        )

    if not has_llm_credentials():
        raise HTTPException(status_code=400, detail="模型未配置")

    skill_dir = None
    try:
        # 读取文件内容
        content = await file.read()

        # 解析模板文件为文本
        template_content = parse_template_file(content, file_ext, file.filename)

        # 解析标签
        tag_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []

        # 使用 LLM 分析模板并生成 Skill 配置
        skill_config = await generate_skill_with_llm(
            template_content=template_content,
            skill_name=name,
            description=description,
            category=category,
            tags=tag_list
        )

        skill_id = skill_config.get("skill_id")
        if not skill_id:
            skill_id = re.sub(r'[^a-z0-9-]', '-', name.lower())
            skill_id = re.sub(r'-+', '-', skill_id).strip('-')

        # 检查是否已存在
        skill_dir = SKILLS_DIR / skill_id
        if skill_dir.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Skill '{skill_id}' already exists"
            )

        # 创建 Skill 目录和文件
        skill_dir.mkdir(parents=True, exist_ok=True)

        # 写入 SKILL.md
        skill_md_content = f"""---
name: {skill_id}
description: {skill_config.get('description', f'Writing skill for {name}')}
version: "1.0.0"
category: {skill_config.get('category', 'custom')}
tags: {skill_config.get('tags', [])}
author: user
user-invocable: true
---

# {skill_config.get('name', name)}

{skill_config.get('instructions', f'This skill helps write documents based on the {name} template.')}
"""
        with open(skill_dir / "SKILL.md", 'w', encoding='utf-8') as f:
            f.write(skill_md_content)

        # 写入 structure.yaml
        with open(skill_dir / "structure.yaml", 'w', encoding='utf-8') as f:
            yaml.dump({'sections': skill_config.get('sections', [])}, f, allow_unicode=True, default_flow_style=False)

        # 写入 requirements.yaml
        with open(skill_dir / "requirements.yaml", 'w', encoding='utf-8') as f:
            yaml.dump({
                'fields': skill_config.get('fields', []),
                'collection_strategy': {
                    'mode': 'conversational',
                    'max_questions_per_turn': 2
                }
            }, f, allow_unicode=True, default_flow_style=False)

        # 写入 guidelines.md
        with open(skill_dir / "guidelines.md", 'w', encoding='utf-8') as f:
            f.write(skill_config.get('guidelines', f'# Writing Guidelines for {name}\n\nFollow the template structure when generating content.'))

        # 创建 prompts 目录
        prompts_dir = skill_dir / "prompts"
        prompts_dir.mkdir(exist_ok=True)

        # 写入 system.md
        with open(prompts_dir / "system.md", 'w', encoding='utf-8') as f:
            f.write(skill_config.get('system_prompt', f'You are an expert writer helping to create {name} documents.'))

        # 写入 section.md
        with open(prompts_dir / "section.md", 'w', encoding='utf-8') as f:
            f.write(skill_config.get('section_prompt', ''))

        # 保存原始模板文件
        templates_dir = skill_dir / "templates"
        templates_dir.mkdir(exist_ok=True)
        with open(templates_dir / f"original{file_ext}", 'wb') as f:
            await file.seek(0)
            f.write(await file.read())

        # 重新加载 Skills
        init_skills_from_directory()

        return {
            "success": True,
            "skill_id": skill_id,
            "message": f"Skill '{name}' created successfully using LLM analysis"
        }

    except HTTPException:
        raise
    except Exception as e:
        # 清理失败的目录
        if skill_dir and skill_dir.exists():
            shutil.rmtree(skill_dir)
        raise HTTPException(status_code=500, detail=f"Failed to create skill: {str(e)}")


@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    """获取单个 Skill 详情"""
    registry = get_registry()
    skill = registry.get(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    # 返回详细信息，包括结构模板和需求字段
    return {
        "id": skill.metadata.id,
        "name": skill.metadata.name,
        "description": skill.metadata.description,
        "category": skill.metadata.category,
        "tags": skill.metadata.tags,
        "requirement_fields": [
            {
                "id": f.id,
                "name": f.name,
                "field_type": f.field_type,
                "required": f.required,
                "description": f.description,
                "options": f.options,
            }
            for f in skill.requirement_fields
        ],
        "structure": skill.get_flat_sections(),
    }


@router.get("/{skill_id}/structure")
async def get_skill_structure(skill_id: str):
    """获取 Skill 的文档结构模板"""
    registry = get_registry()
    skill = registry.get(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    return {
        "skill_id": skill_id,
        "sections": skill.get_flat_sections(),
    }


@router.get("/{skill_id}/requirements")
async def get_skill_requirements(skill_id: str):
    """获取 Skill 的需求字段定义"""
    registry = get_registry()
    skill = registry.get(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    return {
        "skill_id": skill_id,
        "fields": [
            {
                "id": f.id,
                "name": f.name,
                "field_type": f.field_type,
                "required": f.required,
                "description": f.description,
                "placeholder": f.placeholder,
                "options": f.options,
            }
            for f in skill.requirement_fields
        ],
    }


@router.get("/{skill_id}/content")
async def get_skill_content(skill_id: str):
    """获取 Skill 的完整内容（包括写作指南、评审标准等）"""
    registry = get_registry()
    skill = registry.get(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    return {
        "skill_id": skill_id,
        "guidelines": skill.writing_guidelines,
        "evaluation_criteria": skill.evaluation_criteria,
        "structure_detail": [
            {
                "id": s.id,
                "title": s.title,
                "level": s.level,
                "type": s.type,
                "description": s.description,
                "word_limit": s.word_limit,
                "writing_guide": s.writing_guide,
                "evaluation_points": s.evaluation_points,
                "examples": s.examples,
            }
            for s in skill.get_flat_sections()
        ],
    }


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    """
    删除指定的 Skill

    注意：此操作不可逆，会删除 Skill 的所有文件
    """
    # 防止删除系统内置 Skill
    protected_skills = {'writer-skill-creator', 'writer_skill_creator'}
    if skill_id in protected_skills:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delete system skill: {skill_id}"
        )

    registry = get_registry()
    skill = registry.get(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    # 获取 Skill 目录路径
    skill_dir = SKILLS_DIR / skill_id

    try:
        # 从注册表中移除
        registry.unregister(skill_id)

        # 删除文件系统中的 Skill 目录
        if skill_dir.exists():
            shutil.rmtree(skill_dir)

        return {
            "success": True,
            "message": f"Skill '{skill_id}' deleted successfully"
        }
    except Exception as e:
        # 如果删除失败，尝试重新注册 Skill
        try:
            init_skills_from_directory()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to delete skill: {str(e)}")
