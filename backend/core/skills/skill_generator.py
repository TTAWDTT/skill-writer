"""
Skill Generator - 使用 LLM 和 writer_skill_creator 来生成新的 Skill
"""
import json
import re
from typing import Dict, Any, Optional
from pathlib import Path

from backend.core.llm.providers import get_llm_client
from backend.core.skills.registry import get_registry


# 默认的 section prompt Jinja2 模板
DEFAULT_SECTION_PROMPT_TEMPLATE = """请撰写"{{ section_title }}"部分。

## 章节要求
{{ section_description }}

## 写作指导
{{ section_writing_guide }}

## 字数要求
{{ section_word_limit }}

## 评审要点
{{ section_evaluation_points }}

{% if written_sections %}
## 已完成的章节
{% for sec_id, sec_content in written_sections.items() %}
### {{ sec_id }}
{{ sec_content[:500] }}...
{% endfor %}
{% endif %}

请直接输出该章节的内容，不要包含章节标题。
"""


# writer_skill_creator 的系统提示词
SKILL_CREATOR_SYSTEM_PROMPT = """你是一个专门分析文书模板并创建相应写作 Skill 的专家。你的任务是根据用户提供的文书模板，生成完整的 Skill 配置。

## 工作流程

### 分析模板结构

从模板中提取以下信息：
- 章节标题层级（一级、二级、三级）
- 每个章节的描述/说明
- 字数要求或限制
- 必填/选填属性
- 需要用户提供的输入字段

### 识别章节结构

从模板中查找以下模式：
- 数字编号：`一、` `1.` `1.1`
- 标题标记：`【】` `《》` 粗体
- Markdown 标题：`#` `##` `###`
- 缩进层级
- 分隔线或空行

### 推断字数要求

- 如果模板明确标注，使用标注值
- 如果没有标注，根据章节重要性推断：
  - 核心章节：1000-3000 字
  - 说明性章节：300-800 字
  - 简短章节：100-300 字

### 推断需求字段

分析模板中的占位符和变量：
- `[项目名称]`、`____` 等填空位置
- 需要用户提供的核心信息
- 可以从其他字段推导的信息（不作为字段）

## 输出格式

你必须严格按照以下 JSON 格式输出，不要输出任何其他内容：

```json
{
  "skill_id": "skill-id-here",
  "name": "Skill 显示名称",
  "description": "Skill 的描述，说明何时使用",
  "category": "分类",
  "tags": ["标签1", "标签2"],
  "instructions": "Skill 的详细使用说明...",
  "sections": [
    {
      "id": "section_1",
      "title": "章节标题",
      "level": 1,
      "type": "required",
      "description": "章节描述",
      "word_limit": [100, 500],
      "writing_guide": "写作指导...",
      "evaluation_points": ["评审要点1", "评审要点2"]
    }
  ],
  "fields": [
    {
      "id": "field_id",
      "name": "字段名称",
      "description": "字段描述",
      "type": "text",
      "required": true,
      "placeholder": "输入提示"
    }
  ],
  "guidelines": "写作指南的 Markdown 内容...",
  "system_prompt": "用于生成内容的系统提示词..."
}
```

字段类型说明：
- type: "text" - 单行文本
- type: "textarea" - 多行文本
- type: "select" - 下拉选择（需要添加 options 数组）

章节类型说明：
- type: "required" - 必需章节
- type: "optional" - 可选章节
"""


async def generate_skill_with_llm(
    template_content: str,
    skill_name: str,
    description: str = "",
    category: str = "",
    tags: list = None,
) -> Dict[str, Any]:
    """
    使用 LLM 分析模板并生成 Skill 配置

    Args:
        template_content: 模板文件的文本内容
        skill_name: Skill 名称
        description: Skill 描述
        category: 分类
        tags: 标签列表

    Returns:
        生成的 Skill 配置字典
    """
    tags = tags or []

    # 构建用户提示词
    user_prompt = f"""请分析以下文书模板，并生成完整的 Skill 配置。

## 基本信息
- Skill 名称: {skill_name}
- 描述: {description or '请根据模板内容生成描述'}
- 分类: {category or '请根据模板内容推断分类'}
- 标签: {', '.join(tags) if tags else '请根据模板内容生成标签'}

## 模板内容

{template_content}

---

请严格按照 JSON 格式输出 Skill 配置，不要输出任何其他内容。确保：
1. skill_id 使用小写字母、数字和连字符
2. 所有章节都有合理的 word_limit
3. 所有必需的用户输入字段都被识别
4. 写作指导具体可操作
"""

    messages = [
        {"role": "system", "content": SKILL_CREATOR_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    # 调用 LLM
    llm_client = get_llm_client()
    response = await llm_client.chat(messages, temperature=0.3, max_tokens=8192)

    # 解析 JSON 响应
    skill_config = _parse_llm_response(response)

    # 补充默认值
    skill_config = _fill_defaults(skill_config, skill_name, description, category, tags)

    return skill_config


def _parse_llm_response(response: str) -> Dict[str, Any]:
    """解析 LLM 响应中的 JSON"""
    # 尝试直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 代码块
    json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    matches = re.findall(json_pattern, response)

    for match in matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue

    # 尝试找到 JSON 对象
    json_start = response.find('{')
    json_end = response.rfind('}')

    if json_start != -1 and json_end != -1:
        try:
            return json.loads(response[json_start:json_end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 LLM 响应中解析 JSON: {response[:500]}...")


def _fill_defaults(
    config: Dict[str, Any],
    skill_name: str,
    description: str,
    category: str,
    tags: list
) -> Dict[str, Any]:
    """填充默认值"""
    # 生成 skill_id
    if not config.get("skill_id"):
        skill_id = re.sub(r'[^a-z0-9-]', '-', skill_name.lower())
        skill_id = re.sub(r'-+', '-', skill_id).strip('-')
        config["skill_id"] = skill_id

    # 使用提供的值覆盖（如果有）
    if skill_name and not config.get("name"):
        config["name"] = skill_name
    if description:
        config["description"] = description
    if category:
        config["category"] = category
    if tags:
        config["tags"] = tags

    # 确保必需字段存在
    config.setdefault("name", skill_name)
    config.setdefault("description", f"{skill_name}文书写作")
    config.setdefault("category", "custom")
    config.setdefault("tags", [])
    config.setdefault("sections", [])
    config.setdefault("fields", [])
    config.setdefault("instructions", f"这是一个用于生成{skill_name}的写作技能。")
    config.setdefault("guidelines", f"# {skill_name}写作指南\n\n请按照模板结构进行写作。")
    config.setdefault("system_prompt", f"你是一个专业的{skill_name}写作专家。请根据用户提供的信息，生成高质量的文书内容。")

    # 使用正确的 Jinja2 模板格式
    config.setdefault("section_prompt", DEFAULT_SECTION_PROMPT_TEMPLATE)

    # 确保每个章节有必需字段
    for section in config.get("sections", []):
        section.setdefault("type", "required")
        section.setdefault("description", "")
        section.setdefault("word_limit", [100, 500])
        section.setdefault("writing_guide", "")
        section.setdefault("evaluation_points", [])

    # 确保每个字段有必需字段
    for field in config.get("fields", []):
        field.setdefault("type", "text")
        field.setdefault("required", True)
        field.setdefault("description", "")
        field.setdefault("placeholder", "")

    return config
