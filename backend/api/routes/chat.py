"""
Chat API 路由
处理与工作流的交互对话，支持流式输出
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from pathlib import Path
import re
import json

from backend.core.workflow import get_workflow
from backend.core.skills.registry import get_registry
from backend.core.agents.file_extractor import (
    parse_uploaded_file,
    extract_info_from_multiple_files,
    generate_field_from_files,
)
from backend.core.agents.skill_fixer_agent import SkillFixerAgent
from backend.core.llm.config_store import has_llm_credentials

try:
    import multipart  # noqa: F401
    MULTIPART_AVAILABLE = True
except Exception:
    MULTIPART_AVAILABLE = False

router = APIRouter()


def _ensure_llm_configured():
    if not has_llm_credentials():
        raise HTTPException(status_code=400, detail="模型未配置")


class StartSessionRequest(BaseModel):
    """开始会话请求"""
    skill_id: str


class ChatRequest(BaseModel):
    """对话请求"""
    session_id: str
    message: str


class SessionResponse(BaseModel):
    """会话响应"""
    session_id: str
    phase: str
    message: str
    is_complete: bool
    document: Optional[str] = None


class UploadFilePayload(BaseModel):
    """JSON 上传文件"""
    filename: str
    content_base64: str
    content_type: Optional[str] = None


class UploadFilesRequest(BaseModel):
    """JSON 上传请求"""
    files: List[UploadFilePayload]


class GenerateFieldRequest(BaseModel):
    """生成单个字段请求"""
    field_id: str


@router.post("/start", response_model=SessionResponse)
async def start_session(request: StartSessionRequest):
    """
    开始新会话

    - 传入 skill_id，创建新会话
    - 返回初始问候语和 session_id
    """
    # 验证 skill 存在
    registry = get_registry()
    skill = registry.get(request.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {request.skill_id}")

    _ensure_llm_configured()

    # 开始会话
    workflow = get_workflow()
    result = await workflow.start_session(request.skill_id)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return SessionResponse(
        session_id=result["session_id"],
        phase=result["phase"],
        message=result["message"],
        is_complete=result["is_complete"],
    )


@router.post("/message", response_model=SessionResponse)
async def send_message(request: ChatRequest):
    """
    发送消息

    - 在需求收集阶段，发送用户回复
    - 如果需求收集完成，自动进入写作阶段
    """
    _ensure_llm_configured()
    workflow = get_workflow()
    result = await workflow.chat(request.session_id, request.message)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return SessionResponse(
        session_id=result["session_id"],
        phase=result["phase"],
        message=result["message"],
        is_complete=result.get("is_complete", False),
        document=result.get("document"),
    )


@router.post("/generate/{session_id}")
async def generate_document(session_id: str):
    """
    生成文档（非流式）

    - 在 writing 阶段调用
    - 返回生成的完整文档
    """
    _ensure_llm_configured()
    workflow = get_workflow()
    result = await workflow.generate_document(session_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return SessionResponse(
        session_id=result["session_id"],
        phase=result["phase"],
        message=result["message"],
        is_complete=result.get("is_complete", False),
        document=result.get("document"),
    )


@router.get("/generate/{session_id}/stream")
async def generate_document_stream(session_id: str):
    """
    流式生成文档（SSE）

    - 在 writing 阶段调用
    - 实时返回生成过程
    """
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if session.phase != "writing":
        raise HTTPException(
            status_code=400,
            detail=f"Session not in writing phase: {session.phase}"
        )

    _ensure_llm_configured()

    async def event_generator():
        try:
            async for event in workflow.generate_document_stream(session_id):
                # 格式化为 SSE
                data = json.dumps(event, ensure_ascii=False)
                yield f"data: {data}\n\n"
        except Exception as e:
            error_event = json.dumps({"type": "error", "error": str(e)})
            yield f"data: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """获取会话状态"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return {
        "session_id": session.session_id,
        "skill_id": session.skill_id,
        "phase": session.phase,
        "has_document": session.final_document is not None,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "message_count": len(session.messages),
    }


@router.get("/session/{session_id}/messages")
async def get_session_messages(session_id: str):
    """获取会话消息历史"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return {
        "session_id": session.session_id,
        "messages": session.messages,
    }


@router.get("/session/{session_id}/document")
async def get_session_document(session_id: str):
    """获取会话生成的文档"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not session.final_document:
        raise HTTPException(status_code=404, detail="Document not generated yet")

    return {
        "session_id": session.session_id,
        "document": session.final_document,
        "sections": session.sections,
    }

def _build_skill_fields(skill) -> List[dict]:
    target_fields = list(skill.requirement_fields)

    collection_rank = {"required": 0, "infer": 1, "optional": 2}
    target_fields.sort(
        key=lambda f: (
            collection_rank.get(f.collection, 2),
            f.priority,
            f.name,
        )
    )
    return [
        {
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "type": f.field_type,
            "required": f.required,
            "collection": f.collection,
            "priority": f.priority,
            "example": f.example,
        }
        for f in target_fields
    ]


def _try_parse_json_value(value: Any):
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value

    candidates = []
    if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
        candidates.append(stripped)

    fence_matches = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", stripped)
    candidates.extend(fence_matches)

    for pattern in (r"\{[\s\S]*?\}", r"\[[\s\S]*?\]"):
        match = re.search(pattern, stripped)
        if match:
            candidates.append(match.group())

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    return value


def _flatten_list_value(values: list, field_type: str, field_id: str) -> str:
    separator = "\n" if field_type == "textarea" else "、"
    parts = []
    for item in values:
        normalized = _normalize_extracted_value(item, field_type, "", field_id)
        if normalized is None:
            continue
        parts.append(str(normalized))
    return separator.join(parts).strip()


def _normalize_key(text: str) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", str(text)).lower()


def _find_partial_key(tokens: list, key_lookup_normalized: dict) -> Optional[str]:
    for token in tokens:
        normalized_token = _normalize_key(token)
        if not normalized_token:
            continue
        for normalized_key, original in key_lookup_normalized.items():
            if normalized_token in normalized_key:
                return original
    return None


def _extract_value_from_unparsed_json(text: str, keys: list) -> Optional[str]:
    if not isinstance(text, str):
        return None
    if not keys:
        return None

    for key in keys:
        if not key:
            continue
        escaped = re.escape(str(key))
        patterns = [
            rf'"{escaped}"\s*:\s*"([\s\S]*?)"',
            rf"'{escaped}'\s*:\s*'([\s\S]*?)'",
            rf'“{escaped}”\s*:\s*“([\s\S]*?)”',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

    return None


def _flatten_dict_value(value_map: dict, field_type: str, field_name: str, field_id: str) -> str:
    if not value_map:
        return ""

    name_hint = (field_name or "").lower()
    prefer_title = field_type != "textarea" and any(k in name_hint for k in ["name", "title", "名称", "标题", "题目"])
    content_keys = ["content", "正文", "内容", "text", "body", "detail", "details", "description", "summary", "简介", "说明", "背景"]
    title_keys = ["title", "标题", "name", "名称", "topic", "subject", "项目名称", "课题名称"]

    key_order = title_keys + content_keys if prefer_title else content_keys + title_keys
    key_lookup = {str(k).lower(): k for k in value_map.keys()}
    key_lookup_normalized = {_normalize_key(k): k for k in value_map.keys()}
    field_id_key = _normalize_key(field_id)
    field_name_key = _normalize_key(field_name)

    if field_id_key in key_lookup_normalized:
        raw_value = value_map.get(key_lookup_normalized[field_id_key])
        normalized = _normalize_extracted_value(raw_value, field_type, field_name, field_id)
        return str(normalized).strip() if normalized is not None else ""

    if field_name_key and field_name_key in key_lookup_normalized:
        raw_value = value_map.get(key_lookup_normalized[field_name_key])
        normalized = _normalize_extracted_value(raw_value, field_type, field_name, field_id)
        return str(normalized).strip() if normalized is not None else ""

    partial_key = _find_partial_key([field_id, field_name], key_lookup_normalized)
    if partial_key:
        raw_value = value_map.get(partial_key)
        normalized = _normalize_extracted_value(raw_value, field_type, field_name, field_id)
        return str(normalized).strip() if normalized is not None else ""

    for key in key_order:
        if key in key_lookup:
            raw_value = value_map.get(key_lookup[key])
            normalized = _normalize_extracted_value(raw_value, field_type, field_name, field_id)
            if normalized is None:
                continue
            return str(normalized).strip()

    partial_key = _find_partial_key(key_order, key_lookup_normalized)
    if partial_key:
        raw_value = value_map.get(partial_key)
        normalized = _normalize_extracted_value(raw_value, field_type, field_name, field_id)
        return str(normalized).strip() if normalized is not None else ""

    if len(value_map) == 1:
        only_value = next(iter(value_map.values()))
        normalized = _normalize_extracted_value(only_value, field_type, field_name, field_id)
        return str(normalized).strip() if normalized is not None else ""

    separator = "\n" if field_type == "textarea" else "，"
    parts = []
    for key, raw_value in value_map.items():
        normalized = _normalize_extracted_value(raw_value, field_type, field_name, field_id)
        if normalized is None:
            continue
        parts.append(f"{key}: {normalized}")
    return separator.join(parts).strip()


def _normalize_extracted_value(value: Any, field_type: str, field_name: str, field_id: str) -> Any:
    if value is None:
        return None

    parsed = _try_parse_json_value(value)

    if isinstance(parsed, dict):
        return _flatten_dict_value(parsed, field_type, field_name, field_id)
    if isinstance(parsed, list):
        return _flatten_list_value(parsed, field_type, field_id)
    if isinstance(parsed, str):
        stripped = parsed.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            title_keys = ["title", "name", "标题", "名称", "topic", "subject", "项目名称", "课题名称", "project_title"]
            content_keys = ["content", "正文", "内容", "text", "body", "detail", "details", "description", "summary", "简介", "说明", "背景"]
            key_candidates = [field_id, field_name] + title_keys + content_keys
            extracted = _extract_value_from_unparsed_json(stripped, key_candidates)
            if extracted:
                return extracted

    return parsed


def _normalize_extracted_fields(extracted_fields: Dict[str, Any], skill) -> Dict[str, Any]:
    if not extracted_fields:
        return {}

    field_map = {f.id: f for f in skill.requirement_fields}
    normalized = {}
    for field_id, value in extracted_fields.items():
        field = field_map.get(field_id)
        field_type = field.field_type if field else "text"
        field_name = field.name if field else field_id
        normalized_value = _normalize_extracted_value(value, field_type, field_name, field_id)
        if normalized_value is None:
            continue
        if isinstance(normalized_value, str) and not normalized_value.strip():
            continue
        normalized[field_id] = normalized_value
    return normalized


def _trim_file_content(content: str, max_chars: int = 20000) -> str:
    """限制存储的文件内容长度，避免数据库过大"""
    if not content:
        return ""
    content = content.strip()
    if len(content) <= max_chars:
        return content
    return content[:max_chars]


async def _handle_parsed_upload(
    session,
    skill,
    workflow,
    parsed_files: List[dict],
    file_summaries: List[str],
):
    _ensure_llm_configured()
    if not parsed_files:
        return {
            "success": False,
            "session_id": session.session_id,
            "message": "没有成功解析任何文件",
            "file_results": file_summaries,
            "extracted_fields": {},
            "external_information": "",
        }

    skill_fields = _build_skill_fields(skill)
    extraction_result = {
        "extracted_fields": {},
        "external_information": "",
        "summaries": "",
    }

    try:
        extraction_result = await extract_info_from_multiple_files(
            files=parsed_files,
            skill_fields=skill_fields,
            skill_name=skill.metadata.name,
            existing_requirements=session.requirements,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件信息提取失败: {str(e)}") from e

    extraction_result["extracted_fields"] = _normalize_extracted_fields(
        extraction_result.get("extracted_fields", {}),
        skill,
    )

    # 更新会话状态
    for pf in parsed_files:
        session.add_uploaded_file({
            "filename": pf["filename"],
            "content_type": pf.get("content_type", ""),
            "size": pf.get("size", 0),
            "content": _trim_file_content(pf.get("content", "")),
            "extracted_fields": extraction_result.get("extracted_fields", {}),
        })

    # 追加外部信息
    external_info = extraction_result.get("external_information", "")
    if external_info:
        session.append_external_info(external_info)

    # 基于上传材料修补 Skill（仅当前会话）
    try:
        fixer = SkillFixerAgent()
        fixer_result = await fixer.run(
            skill=skill,
            extracted_fields=extraction_result.get("extracted_fields", {}),
            external_information=session.external_information,
            file_summaries=extraction_result.get("summaries", ""),
        )
        session.skill_overlay = {
            "writing_guidelines_additions": fixer_result.writing_guidelines_additions,
            "global_principles": fixer_result.global_principles,
            "section_overrides": fixer_result.section_overrides,
            "relax_requirements": fixer_result.relax_requirements,
            "material_context": fixer_result.material_context,
            "section_prompt_overrides": fixer_result.section_prompt_overrides,
        }
    except Exception as e:
        print(f"[Skill Fixer Warning] {e}")

    # 将提取的字段合并到需求中
    extracted_fields = extraction_result.get("extracted_fields", {})
    if extracted_fields:
        if session.requirements is None:
            session.requirements = {}
        for field_id, value in extracted_fields.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            existing_value = session.requirements.get(field_id)
            if existing_value is None or (isinstance(existing_value, str) and not existing_value.strip()):
                session.requirements[field_id] = value

    # 保存会话
    workflow.save_session(session)

    # 添加系统消息到对话历史
    upload_message = f"📎 已上传 {len(parsed_files)} 个文件并提取信息：\n" + "\n".join(file_summaries)
    session.messages.append({
        "role": "system",
        "content": upload_message,
    })
    workflow.save_session(session)

    return {
        "success": True,
        "session_id": session.session_id,
        "message": f"成功处理 {len(parsed_files)} 个文件",
        "file_results": file_summaries,
        "extracted_fields": extracted_fields,
        "external_information": external_info[:500] + "..." if len(external_info) > 500 else external_info,
        "summaries": extraction_result.get("summaries", ""),
    }


@router.post("/session/{session_id}/upload-json")
async def upload_files_json(
    session_id: str,
    payload: UploadFilesRequest,
):
    """
    上传文件到会话

    - 支持上传多个文件
    - 自动解析文件内容并使用 LLM 提取相关信息
    - 返回提取的信息摘要
    """
    # 验证会话存在
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if session.phase not in ["init", "requirement"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot upload files in phase: {session.phase}. Only allowed during requirement collection."
        )

    # 获取 Skill 信息
    registry = get_registry()
    skill = registry.get(session.skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {session.skill_id}")

    _ensure_llm_configured()

    # 支持的文件类型
    allowed_extensions = {'.md', '.txt', '.doc', '.docx', '.pdf', '.pptx'}

    # 解析所有上传的文件
    parsed_files = []
    file_summaries = []

    for file in payload.files:
        file_ext = Path(file.filename).suffix.lower()

        if file_ext not in allowed_extensions:
            file_summaries.append(f"❌ {file.filename}: 不支持的文件类型 ({file_ext})")
            continue

        try:
            import base64
            content = base64.b64decode(file.content_base64)
            text_content = parse_uploaded_file(content, file_ext, file.filename)

            if text_content:
                parsed_files.append({
                    "filename": file.filename,
                    "content": text_content,
                    "content_type": file.content_type or "",
                    "size": len(content),
                })
                file_summaries.append(f"✅ {file.filename}: 解析成功 ({len(text_content)} 字符)")
            else:
                file_summaries.append(f"⚠️ {file.filename}: 文件为空或无法解析")

        except Exception as e:
            file_summaries.append(f"❌ {file.filename}: 解析失败 - {str(e)}")

    try:
        return await _handle_parsed_upload(session, skill, workflow, parsed_files, file_summaries)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"[File Upload Error] {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


if MULTIPART_AVAILABLE:
    @router.post("/session/{session_id}/upload")
    async def upload_files(
        session_id: str,
        files: List[UploadFile] = File(...),
    ):
        """
        上传文件到会话

        - 支持上传多个文件
        - 自动解析文件内容并使用 LLM 提取相关信息
        - 返回提取的信息摘要
        """
        # 验证会话存在
        workflow = get_workflow()
        session = workflow.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        if session.phase not in ["init", "requirement"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot upload files in phase: {session.phase}. Only allowed during requirement collection."
            )

        # 获取 Skill 信息
        registry = get_registry()
        skill = registry.get(session.skill_id)

        if not skill:
            raise HTTPException(status_code=404, detail=f"Skill not found: {session.skill_id}")

        _ensure_llm_configured()

        # 支持的文件类型
        allowed_extensions = {'.md', '.txt', '.doc', '.docx', '.pdf', '.pptx'}

        # 解析所有上传的文件
        parsed_files = []
        file_summaries = []

        for file in files:
            file_ext = Path(file.filename).suffix.lower()

            if file_ext not in allowed_extensions:
                file_summaries.append(f"❌ {file.filename}: 不支持的文件类型 ({file_ext})")
                continue

            try:
                content = await file.read()
                text_content = parse_uploaded_file(content, file_ext, file.filename)

                if text_content:
                    parsed_files.append({
                        "filename": file.filename,
                        "content": text_content,
                        "content_type": file.content_type,
                        "size": len(content),
                    })
                    file_summaries.append(f"✅ {file.filename}: 解析成功 ({len(text_content)} 字符)")
                else:
                    file_summaries.append(f"⚠️ {file.filename}: 文件为空或无法解析")

            except Exception as e:
                file_summaries.append(f"❌ {file.filename}: 解析失败 - {str(e)}")

        try:
            return await _handle_parsed_upload(session, skill, workflow, parsed_files, file_summaries)
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            print(f"[File Upload Error] {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )


@router.get("/session/{session_id}/files")
async def get_session_files(session_id: str):
    """获取会话上传的文件列表"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    files = [
        {k: v for k, v in file_info.items() if k != "content"}
        for file_info in session.uploaded_files
    ]

    return {
        "session_id": session.session_id,
        "files": files,
        "external_information": session.external_information,
    }


@router.post("/session/{session_id}/generate-field")
async def generate_field(session_id: str, request: GenerateFieldRequest):
    """基于已上传材料生成单个字段内容"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not session.uploaded_files:
        raise HTTPException(status_code=400, detail="No uploaded files found for this session")

    if not has_llm_credentials():
        raise HTTPException(status_code=400, detail="模型未配置")

    registry = get_registry()
    skill = registry.get(session.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {session.skill_id}")

    field = next((f for f in skill.requirement_fields if f.id == request.field_id), None)
    if not field:
        raise HTTPException(status_code=404, detail=f"Field not found: {request.field_id}")

    files = [
        {
            "filename": f.get("filename", "unknown"),
            "content": f.get("content", ""),
        }
        for f in session.uploaded_files
    ]

    if not any(f.get("content") for f in files):
        raise HTTPException(status_code=400, detail="No file content available; please re-upload files")

    result = await generate_field_from_files(
        files=files,
        field={
            "id": field.id,
            "name": field.name,
            "description": field.description,
            "type": field.field_type,
        },
        skill_name=skill.metadata.name,
        existing_requirements=session.requirements,
        external_information=session.external_information,
    )

    value = result.get("value")
    value = _normalize_extracted_value(value, field.field_type, field.name, field.id)
    if value is None or (isinstance(value, str) and not value.strip()):
        return {
            "success": False,
            "session_id": session_id,
            "field_id": field.id,
            "message": "未在材料中找到相关信息",
            "value": None,
        }

    if session.requirements is None:
        session.requirements = {}
    session.requirements[field.id] = value
    workflow.save_session(session)

    return {
        "success": True,
        "session_id": session_id,
        "field_id": field.id,
        "value": value,
    }


class UpdateRequirementsRequest(BaseModel):
    """更新需求请求"""
    requirements: dict


@router.put("/session/{session_id}/requirements")
async def update_requirements(session_id: str, request: UpdateRequirementsRequest):
    """
    直接更新会话的需求字段

    - 用于表单直接编辑需求
    - 不需要通过对话收集
    """
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # 更新需求
    if session.requirements is None:
        session.requirements = {}

    # 合并新的需求（保留已有值，除非明确覆盖）
    for key, value in request.requirements.items():
        if value is None:
            session.requirements.pop(key, None)
            continue
        if isinstance(value, str) and not value.strip():
            session.requirements.pop(key, None)
            continue
        session.requirements[key] = value

    # 保存会话
    workflow.save_session(session)

    return {
        "success": True,
        "session_id": session_id,
        "requirements": session.requirements,
    }


@router.get("/session/{session_id}/requirements")
async def get_requirements(session_id: str):
    """获取会话的需求字段"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # 获取 Skill 的字段定义
    registry = get_registry()
    skill = registry.get(session.skill_id)

    fields = []
    if skill:
        if session.requirements:
            normalized_requirements = _normalize_extracted_fields(session.requirements, skill)
            if normalized_requirements != session.requirements:
                session.requirements = normalized_requirements
                workflow.save_session(session)

        fields = [
            {
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "type": f.field_type,
                "required": f.required,
                "collection": f.collection,
                "priority": f.priority,
                "example": f.example,
                "placeholder": f.placeholder,
            }
            for f in skill.requirement_fields
        ]
        if session.skill_overlay and session.skill_overlay.get("relax_requirements"):
            for field in fields:
                field["required"] = False
                if field.get("collection") == "required":
                    field["collection"] = "optional"

    return {
        "session_id": session_id,
        "requirements": session.requirements or {},
        "fields": fields,
        "external_information": session.external_information,
        "skill_overlay": session.skill_overlay,
    }


@router.post("/session/{session_id}/start-generation")
async def start_generation(session_id: str):
    """
    开始文档生成

    - 检查必填字段是否已填写
    - 将阶段切换到 writing
    """
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # 获取 Skill 的字段定义
    registry = get_registry()
    skill = registry.get(session.skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {session.skill_id}")

    _ensure_llm_configured()

    # 检查必填字段
    missing_fields = []
    requirements = session.requirements or {}

    if not (session.skill_overlay and session.skill_overlay.get("relax_requirements")):
        for field in skill.requirement_fields:
            if field.required:
                value = requirements.get(field.id)
                if not value or (isinstance(value, str) and not value.strip()):
                    missing_fields.append(field.name)

    if missing_fields:
        return {
            "success": False,
            "session_id": session_id,
            "message": f"请填写以下必填字段: {', '.join(missing_fields)}",
            "missing_fields": missing_fields,
        }

    # 切换到写作阶段
    session.phase = "writing"
    workflow.save_session(session)

    return {
        "success": True,
        "session_id": session_id,
        "phase": "writing",
        "message": "开始生成文档...",
    }
