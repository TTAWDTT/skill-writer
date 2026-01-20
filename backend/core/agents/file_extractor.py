"""
File Content Extractor - 使用 LLM 从上传的文件中提取信息
"""
from typing import Dict, Any, List, Optional
from pathlib import Path

from backend.core.llm.providers import get_llm_client
from backend.core.skills.template_parser import parse_template_file


# 信息提取系统提示词
EXTRACTION_SYSTEM_PROMPT = """你是一个专业的文档分析助手。你的任务是从用户上传的材料中提取有价值的信息。

## 工作流程

1. **理解文档类型**：首先判断文档的类型（论文、报告、简历、项目材料等）
2. **提取关键信息**：根据用户需要填写的字段，从文档中提取相关信息
3. **记录额外发现**：记录文档中其他可能对写作有帮助的重要信息

## 输出格式

你必须严格按照以下 JSON 格式输出，不要输出任何其他内容：

```json
{
  "document_type": "文档类型描述",
  "extracted_fields": {
    "字段ID": "提取的内容",
    "字段ID2": "提取的内容2"
  },
  "external_information": "这里记录文档中发现的其他有价值信息，包括但不限于：关键数据、重要发现、背景知识、可引用的内容等。这些信息可能对后续写作有帮助。",
  "summary": "文档的简要摘要"
}
```

注意：
- extracted_fields 中的键应该匹配用户提供的字段 ID
- 如果某个字段在文档中找不到相关信息，不要包含该字段
- external_information 应该包含所有可能有用但不直接对应字段的信息
- 保持客观准确，不要编造信息
"""


async def extract_info_from_file(
    file_content: str,
    filename: str,
    skill_fields: List[Dict],
    skill_name: str = "",
    existing_requirements: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    从文件内容中提取信息

    Args:
        file_content: 文件的文本内容
        filename: 文件名
        skill_fields: Skill 定义的字段列表
        skill_name: Skill 名称
        existing_requirements: 已收集的需求

    Returns:
        提取的信息字典
    """
    # 构建字段说明
    fields_description = "\n".join([
        f"- **{f.get('name', f.get('id'))}** (ID: {f.get('id')}): {f.get('description', '无描述')}"
        for f in skill_fields
    ])

    # 构建用户提示词
    user_prompt = f"""请分析以下文档并提取相关信息。

## 文档信息
- 文件名：{filename}
- 目标文书类型：{skill_name}

## 需要填写的字段
{fields_description}

## 已收集的信息
{_format_existing_requirements(existing_requirements)}

## 文档内容

{file_content[:15000]}
{f'... (文档过长，已截断，共 {len(file_content)} 字符)' if len(file_content) > 15000 else ''}

---

请从上述文档中提取与字段相关的信息，并记录其他有价值的外部信息。
严格按照 JSON 格式输出。
"""

    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

    # 调用 LLM
    llm_client = get_llm_client()
    response = await llm_client.chat(messages, temperature=0.2, max_tokens=4096)

    # 解析响应
    return _parse_extraction_response(response, filename)


def _format_existing_requirements(requirements: Optional[Dict]) -> str:
    """格式化已有的需求信息"""
    if not requirements:
        return "（暂无）"

    lines = []
    for key, value in requirements.items():
        if value:
            lines.append(f"- {key}: {str(value)[:200]}...")
    return "\n".join(lines) if lines else "（暂无）"


def _parse_extraction_response(response: str, filename: str) -> Dict[str, Any]:
    """解析 LLM 提取响应"""
    import json
    import re

    result = {
        "filename": filename,
        "document_type": "unknown",
        "extracted_fields": {},
        "external_information": "",
        "summary": "",
        "raw_response": response,
    }

    # 尝试直接解析
    try:
        data = json.loads(response)
        result.update({
            "document_type": data.get("document_type", "unknown"),
            "extracted_fields": data.get("extracted_fields", {}),
            "external_information": data.get("external_information", ""),
            "summary": data.get("summary", ""),
        })
        return result
    except json.JSONDecodeError:
        pass

    # 尝试提取 JSON 代码块
    json_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    matches = re.findall(json_pattern, response)

    for match in matches:
        try:
            data = json.loads(match)
            result.update({
                "document_type": data.get("document_type", "unknown"),
                "extracted_fields": data.get("extracted_fields", {}),
                "external_information": data.get("external_information", ""),
                "summary": data.get("summary", ""),
            })
            return result
        except json.JSONDecodeError:
            continue

    # 尝试找到 JSON 对象
    json_start = response.find('{')
    json_end = response.rfind('}')

    if json_start != -1 and json_end != -1:
        try:
            data = json.loads(response[json_start:json_end + 1])
            result.update({
                "document_type": data.get("document_type", "unknown"),
                "extracted_fields": data.get("extracted_fields", {}),
                "external_information": data.get("external_information", ""),
                "summary": data.get("summary", ""),
            })
            return result
        except json.JSONDecodeError:
            pass

    # 如果都失败了，将整个响应作为 external_information
    result["external_information"] = response
    return result


async def extract_info_from_multiple_files(
    files: List[Dict[str, Any]],
    skill_fields: List[Dict],
    skill_name: str = "",
    existing_requirements: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    从多个文件中提取信息并合并

    Args:
        files: 文件列表，每个包含 filename 和 content
        skill_fields: Skill 定义的字段列表
        skill_name: Skill 名称
        existing_requirements: 已收集的需求

    Returns:
        合并后的提取信息
    """
    all_extracted_fields = {}
    all_external_info = []
    all_summaries = []

    for file_info in files:
        filename = file_info.get("filename", "unknown")
        content = file_info.get("content", "")

        if not content:
            continue

        result = await extract_info_from_file(
            file_content=content,
            filename=filename,
            skill_fields=skill_fields,
            skill_name=skill_name,
            existing_requirements=existing_requirements,
        )

        # 合并提取的字段（后面的文件会覆盖前面的）
        all_extracted_fields.update(result.get("extracted_fields", {}))

        # 收集外部信息
        ext_info = result.get("external_information", "")
        if ext_info:
            all_external_info.append(f"### 来自 {filename}\n{ext_info}")

        # 收集摘要
        summary = result.get("summary", "")
        if summary:
            all_summaries.append(f"- **{filename}**: {summary}")

    return {
        "extracted_fields": all_extracted_fields,
        "external_information": "\n\n".join(all_external_info),
        "summaries": "\n".join(all_summaries),
        "file_count": len(files),
    }


def parse_uploaded_file(content: bytes, file_ext: str, filename: str) -> str:
    """
    解析上传的文件为文本

    Args:
        content: 文件二进制内容
        file_ext: 文件扩展名
        filename: 文件名

    Returns:
        解析后的文本内容
    """
    return parse_template_file(content, file_ext, filename)
