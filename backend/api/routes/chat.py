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
import logging
import time
import datetime
import base64
import uuid

import httpx

from backend.core.workflow import get_workflow
from backend.core.skills.registry import get_registry
from backend.config import settings
from backend.core.diagrams.smart_generator import SmartDiagramGenerator
from backend.core.diagrams.schematics import SchematicsGenerator
from backend.core.agents.file_extractor import (
    parse_uploaded_file,
    extract_info_from_multiple_files,
    generate_field_from_files,
)
from backend.core.agents.skill_fixer_agent import SkillFixerAgent
from backend.core.llm.config_store import has_llm_credentials, get_llm_config

try:
    import multipart  # noqa: F401
    MULTIPART_AVAILABLE = True
except Exception:
    MULTIPART_AVAILABLE = False

router = APIRouter()

logger = logging.getLogger(__name__)


def _redact_secrets(message: str) -> str:
    if not message:
        return message
    # Redact common token formats (best-effort)
    patterns = [
        (re.compile(r"(sk-[A-Za-z0-9]{8,})"), "sk-***"),
        (re.compile(r"(gho_[A-Za-z0-9]{8,})"), "gho_***"),
        (re.compile(r"(Bearer\\s+)[A-Za-z0-9._\\-]{10,}"), r"\\1***"),
        (re.compile(r"(api[-_ ]?key\\s*[:=]\\s*)([^\\s,;]+)", re.IGNORECASE), r"\\1***"),
        (re.compile(r"(\*{2,}[A-Za-z0-9]{2,})"), "***"),
    ]
    sanitized = message
    for pattern, replacement in patterns:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


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


class WebSearchRequest(BaseModel):
    """Web 搜索请求"""
    query: str
    top_k: int = 5


class DiagramRequest(BaseModel):
    """生成图示请求"""
    title: Optional[str] = None
    diagram_type: str = "technical_route"  # technical_route | research_framework | freestyle
    mode: str = "infographic"  # infographic | image_model | auto
    # New fields for selection-based diagramming
    selected_text: Optional[str] = None
    context_text: Optional[str] = None


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
    # 上传材料应尽量“可用优先”：即使模型未配置/暂时不可用，也先保存解析出的文本，
    # 只是跳过自动信息提取与 Skill Fixer（依赖 LLM）。
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
    warning: Optional[str] = None
    extraction_ms: Optional[int] = None
    llm_used: Optional[dict] = None

    if has_llm_credentials():
        try:
            cfg = get_llm_config()
            llm_used = {
                "provider_name": getattr(cfg, "provider_name", ""),
                "provider": getattr(cfg, "provider", ""),
                "base_url": getattr(cfg, "base_url", ""),
                "model": getattr(cfg, "model", ""),
            }
            logger.info(
                "[upload] start llm extraction session=%s files=%s provider=%s model=%s base_url=%s",
                session.session_id,
                len(parsed_files),
                getattr(cfg, "provider_name", ""),
                getattr(cfg, "model", ""),
                getattr(cfg, "base_url", ""),
            )
            start_ts = time.time()
            extraction_result = await extract_info_from_multiple_files(
                files=parsed_files,
                skill_fields=skill_fields,
                skill_name=skill.metadata.name,
                existing_requirements=session.requirements,
            )
            extraction_ms = int((time.time() - start_ts) * 1000)
        except Exception as e:
            # 不阻断上传：允许用户继续生成/手工补充，只是失去自动提取能力
            warning = f"文件已解析并保存，但自动信息提取失败：{_redact_secrets(str(e))}"
            extraction_result = {
                "extracted_fields": {},
                "external_information": "",
                "summaries": "",
            }
    else:
        warning = "模型未配置：文件已解析并保存，但不会自动提取信息。"

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
    if warning is None:
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
        "warning": warning,
        "llm_used": llm_used,
        "extraction_ms": extraction_ms,
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


def _format_search_sources(query: str, results: List[dict]) -> str:
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    lines = [f"## Web Search（{ts}）", f"查询：{query}", ""]
    for idx, r in enumerate(results, start=1):
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        snippet = (r.get("snippet") or "").strip()
        lines.append(f"{idx}. {title}")
        if url:
            lines.append(f"   - URL: {url}")
        if snippet:
            lines.append(f"   - 摘要: {snippet}")
    return "\n".join(lines).strip()


async def _duckduckgo_search(query: str, top_k: int = 5) -> List[dict]:
    q = (query or "").strip()
    if not q:
        return []
    top_k = max(1, min(int(top_k or 5), 10))

    url = "https://duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }
    async with httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True) as client:
        resp = await client.post(url, data={"q": q})
        resp.raise_for_status()
        html = resp.text

    results: List[dict] = []
    for m in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>', html):
        href = m.group(1)
        raw_title = m.group(2)
        title = re.sub(r"<[^>]+>", "", raw_title)
        title = re.sub(r"\s+", " ", title).strip()

        snippet = ""
        tail = html[m.end(): m.end() + 2500]
        sm = re.search(r'class="result__snippet"[^>]*>([\s\S]*?)</a>|class="result__snippet"[^>]*>([\s\S]*?)</div>', tail)
        if sm:
            raw = sm.group(1) or sm.group(2) or ""
            snippet = re.sub(r"<[^>]+>", "", raw)
            snippet = re.sub(r"\s+", " ", snippet).strip()

        if href and title:
            results.append({"title": title, "url": href, "snippet": snippet})
        if len(results) >= top_k:
            break
    return results


@router.post("/session/{session_id}/search-web")
async def search_web(session_id: str, request: WebSearchRequest):
    """Web 搜索并把来源追加到会话 external_information（用于后续写作引用/背景补充）"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    query = (request.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")

    results = await _duckduckgo_search(query, request.top_k)
    if not results:
        return {"success": True, "session_id": session_id, "query": query, "results": [], "message": "未检索到结果"}

    block = _format_search_sources(query, results)
    session.append_external_info(block)
    workflow.save_session(session)

    return {
        "success": True,
        "session_id": session_id,
        "query": query,
        "results": results,
        "message": f"已写入外部信息（{len(results)} 条来源）",
    }


def _extract_json_obj(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        return {}
    raw = re.sub(r"^```(?:json)?\\s*", "", raw).strip()
    raw = re.sub(r"\\s*```$", "", raw).strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass

    # Best-effort: grab the largest {...} block
    m = re.search(r"\\{[\\s\\S]*\\}", raw)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _diagram_storage_dir(session_id: str) -> Path:
    from backend.config import DATA_DIR
    p = Path(DATA_DIR) / "diagrams" / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def _diagram_paths(session_id: str, diagram_id: str) -> tuple[Path, Path]:
    d = _diagram_storage_dir(session_id)
    return d / f"{diagram_id}.png", d / f"{diagram_id}.svg"


def _safe_filename(title: str, ext: str) -> str:
    name = (title or "diagram").strip() or "diagram"
    safe = re.sub(r"[^\\u4e00-\\u9fff0-9a-zA-Z._-]+", "_", name).strip("_") or "diagram"
    return f"{safe}.{ext}"


def _diagram_asset_flags(session_id: str, diagram: dict) -> tuple[bool, bool]:
    did = diagram.get("id")
    if not did:
        return False, False
    png_path, svg_path = _diagram_paths(session_id, did)
    has_png = png_path.exists()
    has_svg = svg_path.exists() or bool(diagram.get("has_svg")) or bool(diagram.get("svg"))
    return has_png, has_svg


@router.post("/session/{session_id}/generate-diagram")
async def generate_diagram(session_id: str, request: DiagramRequest):
    """生成图示（两种模式：infographic 本地渲染 / image_model 成图模型）并返回可插入 Markdown 的图片片段"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    _ensure_llm_configured()

    registry = get_registry()
    skill = registry.get(session.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {session.skill_id}")

    diagram_type = (request.diagram_type or "technical_route").strip() or "technical_route"
    # Allow freestyle type
    if diagram_type not in {"technical_route", "research_framework", "freestyle"}:
        raise HTTPException(status_code=400, detail=f"Unsupported diagram_type: {diagram_type}")

    mode = (request.mode or "infographic").strip().lower() or "infographic"
    if mode not in {"infographic", "image_model", "auto"}:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")

    cfg = get_llm_config()
    image_model = (getattr(cfg, "image_model", None) or "").strip()
    if mode == "auto":
        mode = "image_model" if image_model else "infographic"

    title = (request.title or ("研究框架图" if diagram_type == "research_framework" else "图示")).strip()

    # Context preparation
    if request.selected_text:
        # User selected specific text -> Focus on that
        requirements_text = request.selected_text
        external_excerpt = (request.context_text or "")[:1000] # Optional surrounding context
    else:
        # Default: use global requirements
        requirements = session.requirements or {}
        req_lines = []
        for f in skill.requirement_fields:
            v = requirements.get(f.id)
            if v is None:
                continue
            if isinstance(v, str) and not v.strip():
                continue
            req_lines.append(f"- {f.name}({f.id}): {v}")
        requirements_text = "\n".join(req_lines) if req_lines else "（暂无）"
        external_excerpt = (session.external_information or "").strip()
        if len(external_excerpt) > 2500:
            external_excerpt = external_excerpt[:2500]

    # Handle Freestyle (Text -> SVG/Image)
    if diagram_type == "freestyle":
        # 1. Try Gemini (Fastest, SVG output)
        if settings.GEMINI_API_KEY:
            try:
                smart_gen = SmartDiagramGenerator(gemini_key=settings.GEMINI_API_KEY)
                svg_text = await smart_gen.generate_freestyle_svg(requirements_text, title)

                # Save SVG
                diagram_id = str(uuid.uuid4())
                _png_path, svg_path = _diagram_paths(session_id, diagram_id)
                svg_path.write_text(svg_text, encoding="utf-8")

                data_uri = f"data:image/svg+xml;base64,{base64.b64encode(svg_text.encode('utf-8')).decode('ascii')}"
                snippet = f"![{title}]({data_uri})"

                diagram_record = {
                    "id": diagram_id,
                    "title": title,
                    "diagram_type": "freestyle",
                    "mode": "svg_code",
                    "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                    "has_png": False,
                    "has_svg": True,
                    "meta": {"provider": "google_gemini", "model": "gemini-1.5-pro"},
                }
                session.diagrams = (session.diagrams or []) + [diagram_record]
                workflow.save_session(session)

                return {
                    "success": True,
                    "session_id": session_id,
                    "diagram_id": diagram_id,
                    "title": title,
                    "diagram_type": "freestyle",
                    "mode": "svg_code",
                    "image_data_uri": data_uri,
                    "markdown_snippet": snippet,
                    "has_svg": True,
                    "png_url": None,
                    "svg_url": f"/api/chat/session/{session_id}/diagrams/{diagram_id}.svg",
                }
            except Exception as e:
                logger.warning(f"Gemini freestyle generation failed, falling back to Schematics: {e}")

        # 2. Fallback: Schematics Generator (Python Code -> Image)
        # Uses the configured LLM to write Python code (Schemdraw, Matplotlib, etc.)
        try:
            logger.info("Using SchematicsGenerator for freestyle diagram...")
            schematic_gen = SchematicsGenerator()
            # Combine context
            full_context = f"需求：{requirements_text}\n\n背景：{external_excerpt}"

            png_bytes, svg_text, code_used = await schematic_gen.generate(full_context, diagram_type, title)

            if not png_bytes and not svg_text:
                raise Exception("Generated code did not produce any image output")

            diagram_id = str(uuid.uuid4())
            png_path, svg_path = _diagram_paths(session_id, diagram_id)

            if png_bytes:
                png_path.write_bytes(png_bytes)
            if svg_text:
                svg_path.write_text(svg_text, encoding="utf-8")

            # Prefer PNG for markdown compatibility, or SVG data URI if no PNG
            if png_bytes:
                b64_img = base64.b64encode(png_bytes).decode("ascii")
                data_uri = f"data:image/png;base64,{b64_img}"
            else:
                b64_img = base64.b64encode(svg_text.encode('utf-8')).decode('ascii')
                data_uri = f"data:image/svg+xml;base64,{b64_img}"

            snippet = f"![{title}]({data_uri})"

            diagram_record = {
                "id": diagram_id,
                "title": title,
                "diagram_type": "freestyle",
                "mode": "schematic_code",
                "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "has_png": bool(png_bytes),
                "has_svg": bool(svg_text),
                "meta": {"provider": "schematics_generator", "generator": "python_code"},
            }
            session.diagrams = (session.diagrams or []) + [diagram_record]
            workflow.save_session(session)

            return {
                "success": True,
                "session_id": session_id,
                "diagram_id": diagram_id,
                "title": title,
                "diagram_type": "freestyle",
                "mode": "schematic_code",
                "image_data_uri": data_uri,
                "markdown_snippet": snippet,
                "has_svg": bool(svg_text),
                "png_url": f"/api/chat/session/{session_id}/diagrams/{diagram_id}.png" if png_bytes else None,
                "svg_url": f"/api/chat/session/{session_id}/diagrams/{diagram_id}.svg" if svg_text else None,
            }

        except Exception as e:
            logger.error(f"Freestyle generation failed: {e}")
            raise HTTPException(status_code=500, detail=f"绘图失败: {str(e)}")


    # Step 1) Ask chat model (or Gemini) for a compact JSON spec
    raw_spec = {}

    # 1.1 Try Gemini if configured (Smarter & Faster)
    if settings.GEMINI_API_KEY:
        try:
            logger.info(f"Using Gemini to generate diagram spec for {diagram_type}...")
            smart_gen = SmartDiagramGenerator(gemini_key=settings.GEMINI_API_KEY)
            context_text = f"需求与背景：\n{requirements_text}\n\n材料摘要：\n{external_excerpt}"

            if diagram_type == "technical_route":
                raw_spec = await smart_gen._generate_technical_route_spec(context_text, title)
            elif diagram_type == "research_framework":
                raw_spec = await smart_gen._generate_research_framework_spec(context_text, title)
        except Exception as e:
            logger.error(f"Gemini diagram generation failed: {e}")
            raw_spec = {}

    # 1.2 Fallback to default LLM (Writer Agent)
    if not raw_spec:
        if diagram_type == "technical_route":
            json_schema_hint = """{
  "stages": [
    {"title": "阶段标题", "bullets": ["要点1", "要点2", "要点3"]},
    {"title": "阶段标题", "bullets": ["要点1", "要点2", "要点3"]},
    {"title": "阶段标题", "bullets": ["要点1", "要点2", "要点3"]},
    {"title": "阶段标题", "bullets": ["要点1", "要点2", "要点3"]}
  ]
}"""
            content_rule = "技术路线图：建议 4 个阶段，体现“目标/问题 → 方法 → 实验验证 → 产出评估”的闭环。"
        else:
            json_schema_hint = """{
  "goal": {"title": "研究目标", "bullets": ["要点1", "要点2", "要点3"]},
  "hypotheses": {"title": "科学问题/假设", "bullets": ["要点1", "要点2", "要点3"]},
  "support": {"title": "支撑条件", "bullets": ["要点1", "要点2", "要点3"]},
  "work_packages": [
    {"title": "WP1 研究内容", "bullets": ["要点1", "要点2", "要点3"]},
    {"title": "WP2 研究内容", "bullets": ["要点1", "要点2", "要点3"]},
    {"title": "WP3 研究内容", "bullets": ["要点1", "要点2", "要点3"]}
  ],
  "outcomes": {"title": "预期成果", "bullets": ["要点1", "要点2", "要点3"]}
}"""
            content_rule = "研究框架图：强调“目标/假设 → 任务包(WP) → 预期成果”，并标出支撑条件。"

        prompt = f"""你是科研申报书的信息图内容策划助手。请根据“已知需求”和“材料摘要”，生成可用于绘制“{title}”的信息图内容 JSON。

只输出 JSON（不要解释、不要 Markdown 代码块）。

硬性约束：
1) 结构必须严格匹配下面的 JSON 结构示例（字段名保持一致）；
2) 标题/要点要专业、准确、可直接用于申报书；避免虚构具体结论、数值、实验结果；
3) 不要出现“待定/未知/自行补充”等字样；信息不足时用抽象但规范的表述补全；
4) 每个 title <= 14 字；每条 bullets <= 22 字，尽量使用“方法/数据/产出/指标”等结构；
5) 只基于已知信息组织内容。

内容规则：{content_rule}
文书类型：{skill.metadata.name}

已知需求：
{requirements_text}

材料摘要（可为空）：
{external_excerpt if external_excerpt else "（无）"}

JSON 结构示例：
{json_schema_hint}
"""

        messages = [
            {"role": "system", "content": "你只输出 JSON。"},
            {"role": "user", "content": prompt},
        ]

        try:
            spec_text = await workflow.writer_agent._chat(messages, temperature=0.2, max_tokens=900)
            raw_spec = _extract_json_obj(spec_text)
        except Exception as e:
            logger.warning("diagram spec generation failed: %s", _redact_secrets(str(e))[:240])
            raw_spec = {}

    diagram_id = str(uuid.uuid4())
    png_path, svg_path = _diagram_paths(session_id, diagram_id)

    svg_text = ""
    normalized_spec = {}

    if mode == "infographic":
        try:
            from backend.core.diagrams.infographic import render_infographic_png_svg
            png_bytes, svg_text, normalized_spec = render_infographic_png_svg(diagram_type, raw_spec, title=title)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"本地信息图渲染失败：{_redact_secrets(str(e))}")
    else:
        if not image_model:
            raise HTTPException(status_code=400, detail="未配置成图模型：请先在设置中填写“成图模型（Image Model）”或改用 infographic 模式")

        # Build a concise, text-friendly prompt from the spec (best-effort).
        def _lines_from_spec() -> str:
            if diagram_type == "technical_route":
                stages = (raw_spec.get("stages") if isinstance(raw_spec, dict) else None) or []
                out = []
                for i, st in enumerate(stages[:6] if isinstance(stages, list) else []):
                    if not isinstance(st, dict):
                        continue
                    t = str(st.get("title") or f"阶段{i+1}").strip()
                    bs = st.get("bullets") or []
                    btxt = "；".join([str(x).strip() for x in (bs[:4] if isinstance(bs, list) else []) if str(x).strip()])
                    if t or btxt:
                        out.append(f"{i+1}. {t}：{btxt}".strip("："))
                return "\n".join(out) if out else requirements_text

            # research_framework
            parts = []
            for key in ("goal", "hypotheses", "support", "outcomes"):
                box = raw_spec.get(key) if isinstance(raw_spec, dict) else None
                if not isinstance(box, dict):
                    continue
                t = str(box.get("title") or "").strip()
                bs = box.get("bullets") or []
                btxt = "；".join([str(x).strip() for x in (bs[:4] if isinstance(bs, list) else []) if str(x).strip()])
                if t or btxt:
                    parts.append(f"{t}：{btxt}".strip("："))
            wps = raw_spec.get("work_packages") if isinstance(raw_spec, dict) else None
            if isinstance(wps, list):
                for i, wp in enumerate(wps[:3]):
                    if not isinstance(wp, dict):
                        continue
                    t = str(wp.get("title") or f"WP{i+1}").strip()
                    bs = wp.get("bullets") or []
                    btxt = "；".join([str(x).strip() for x in (bs[:4] if isinstance(bs, list) else []) if str(x).strip()])
                    if t or btxt:
                        parts.append(f"{t}：{btxt}".strip("："))
            return "\n".join(parts) if parts else requirements_text

        diagram_kind_cn = "技术路线图" if diagram_type == "technical_route" else "研究框架图"
        image_prompt = f"""请生成一张可直接用于科研申报书的中文信息图（{diagram_kind_cn}）。

风格要求：
- 专业、干净、矢量信息图风格（flat design），白色或浅色背景
- 结构清晰：圆角矩形卡片 + 箭头流程，适合 A4/16:9
- 中文文字务必清晰可读，不要艺术字，不要水印/Logo

标题：{title}
内容（请保持含义，不要虚构数据/结论）：
{_lines_from_spec()}
"""

        try:
            from backend.core.diagrams.openai_images import generate_image_png_via_openai_compatible
            last_err = None
            for size in ("1792x1024", "1024x1024"):
                try:
                    png_bytes, _raw = await generate_image_png_via_openai_compatible(
                        base_url=cfg.base_url,
                        api_key=cfg.api_key,
                        model=image_model,
                        prompt=image_prompt,
                        size=size,
                    )
                    last_err = None
                    break
                except Exception as e:
                    last_err = e
                    continue
            if last_err is not None:
                raise last_err
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"成图模型生成失败：{_redact_secrets(str(e))}")

    # Save assets
    try:
        png_path.write_bytes(png_bytes)
        if svg_text and mode == "infographic":
            svg_path.write_text(svg_text, encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存图示失败：{_redact_secrets(str(e))}")

    # Build markdown snippet (data URI) for direct insertion/export.
    b64_png = base64.b64encode(png_bytes).decode("ascii")
    data_uri = f"data:image/png;base64,{b64_png}"
    snippet = f"![{title}]({data_uri})"

    diagram_record = {
        "id": diagram_id,
        "title": title,
        "diagram_type": diagram_type,
        "mode": mode,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "has_png": True,
        "has_svg": bool(svg_text) and mode == "infographic",
        "spec": normalized_spec or raw_spec or None,
        "meta": {
            "provider": getattr(cfg, "provider_name", None),
            "chat_model": getattr(cfg, "model", None),
            "image_model": image_model or None,
        },
    }
    session.diagrams = (session.diagrams or []) + [diagram_record]
    workflow.save_session(session)

    return {
        "success": True,
        "session_id": session_id,
        "diagram_id": diagram_id,
        "title": title,
        "diagram_type": diagram_type,
        "mode": mode,
        "image_data_uri": data_uri,
        "markdown_snippet": snippet,
        "has_svg": diagram_record["has_svg"],
        "png_url": f"/api/chat/session/{session_id}/diagrams/{diagram_id}.png",
        "svg_url": f"/api/chat/session/{session_id}/diagrams/{diagram_id}.svg" if diagram_record["has_svg"] else None,
    }


@router.get("/session/{session_id}/diagrams")
async def list_diagrams(session_id: str):
    """List session diagrams (metadata only)."""
    workflow = get_workflow()
    session = workflow.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    diagrams = session.diagrams or []
    return {
        "session_id": session_id,
        "diagrams": [
            {
                "id": d.get("id"),
                "title": d.get("title"),
                "diagram_type": d.get("diagram_type"),
                "mode": d.get("mode") or ("infographic" if d.get("svg") else "unknown"),
                "created_at": d.get("created_at"),
                "has_png": (flags := _diagram_asset_flags(session_id, d))[0],
                "has_svg": flags[1],
                "png_url": f"/api/chat/session/{session_id}/diagrams/{d.get('id')}.png" if flags[0] else None,
                "svg_url": f"/api/chat/session/{session_id}/diagrams/{d.get('id')}.svg" if flags[1] else None,
            }
            for d in diagrams
            if isinstance(d, dict)
        ],
    }


@router.get("/session/{session_id}/diagrams/{diagram_id}.svg")
async def get_diagram_svg(session_id: str, diagram_id: str):
    """Download a stored diagram SVG (infographic mode)."""
    workflow = get_workflow()
    session = workflow.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    diagram = next((d for d in (session.diagrams or []) if isinstance(d, dict) and d.get("id") == diagram_id), None)
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")

    # New format: file-based SVG
    _png_path, svg_path = _diagram_paths(session_id, diagram_id)
    if svg_path.exists():
        svg = svg_path.read_text(encoding="utf-8", errors="ignore")
        filename = _safe_filename(diagram.get("title") or "diagram", "svg")
        return StreamingResponse(
            iter([svg.encode("utf-8")]),
            media_type="image/svg+xml",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Backward compatibility: stored inline SVG string (older mermaid-based diagrams)
    svg_inline = (diagram.get("svg") or "").strip()
    if svg_inline:
        filename = _safe_filename(diagram.get("title") or "diagram", "svg")
        return StreamingResponse(
            iter([svg_inline.encode("utf-8")]),
            media_type="image/svg+xml",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    raise HTTPException(status_code=404, detail="SVG 不存在（该图示可能由成图模型生成）")


@router.get("/session/{session_id}/diagrams/{diagram_id}.png")
async def get_diagram_png(session_id: str, diagram_id: str):
    """Download a stored diagram PNG."""
    workflow = get_workflow()
    session = workflow.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    diagram = next((d for d in (session.diagrams or []) if isinstance(d, dict) and d.get("id") == diagram_id), None)
    if not diagram:
        raise HTTPException(status_code=404, detail="Diagram not found")

    png_path, _svg_path = _diagram_paths(session_id, diagram_id)
    if not png_path.exists():
        raise HTTPException(status_code=404, detail="PNG 不存在")

    raw = png_path.read_bytes()
    filename = _safe_filename(diagram.get("title") or "diagram", "png")
    return StreamingResponse(
        iter([raw]),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
        "planner_plan": session.planner_plan,
        "diagrams": [
            {
                "id": d.get("id"),
                "title": d.get("title"),
                "diagram_type": d.get("diagram_type"),
                "mode": d.get("mode") or ("infographic" if d.get("svg") else "unknown"),
                "created_at": d.get("created_at"),
                "has_png": (flags := _diagram_asset_flags(session_id, d))[0],
                "has_svg": flags[1],
                "png_url": f"/api/chat/session/{session_id}/diagrams/{d.get('id')}.png" if flags[0] else None,
                "svg_url": f"/api/chat/session/{session_id}/diagrams/{d.get('id')}.svg" if flags[1] else None,
            }
            for d in (session.diagrams or [])
            if isinstance(d, dict)
        ],
    }


@router.get("/session/{session_id}/plan")
async def get_planner_plan(session_id: str):
    """获取会话的 Planner 蓝图"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    if not session.planner_plan:
        raise HTTPException(status_code=404, detail="Planner 蓝图尚未生成")
    return {"session_id": session_id, "planner_plan": session.planner_plan}


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
        # 前端已去除“必填字段”表单展示，因此这里改为“软校验”：
        # - 有材料：允许继续生成，后续在写作过程中让模型基于材料补全/自洽
        # - 无材料：仍提示用户补充关键信息
        if session.uploaded_files:
            session.phase = "writing"
            workflow.save_session(session)
            return {
                "success": True,
                "session_id": session_id,
                "phase": "writing",
                "message": "将基于已上传材料继续生成（部分字段缺失将自动补全/弱化）。",
                "missing_fields": missing_fields,
                "warning": f"以下字段在材料中未明确提取到：{', '.join(missing_fields)}",
            }
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
