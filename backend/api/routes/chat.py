"""
Chat API 路由
处理与工作流的交互对话，支持流式输出
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from pathlib import Path
import asyncio
import re
import json
import logging
import time
import datetime
import base64
import uuid
import os

import httpx

from backend.core.workflow import get_workflow
from backend.core.skills.registry import get_registry
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

_UPLOAD_PARSE_CONCURRENCY = max(1, min(int(os.getenv("UPLOAD_PARSE_CONCURRENCY", "4")), 12))
_UPLOAD_SESSION_LOCKS: Dict[str, asyncio.Lock] = {}
_UPLOAD_SESSION_LOCKS_GUARD = asyncio.Lock()


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


def _resolve_skill_system_prompt(skill: Any) -> str:
    """Best-effort extraction of system prompt from wrapped skills."""
    if skill is None:
        return ""

    queue: List[Any] = [skill]
    seen: set[int] = set()
    fallback_guidelines = ""

    while queue:
        cur = queue.pop(0)
        if cur is None:
            continue
        cur_id = id(cur)
        if cur_id in seen:
            continue
        seen.add(cur_id)

        for attr in ("system_prompt", "_system_prompt"):
            try:
                value = getattr(cur, attr, "")
            except Exception:
                value = ""
            if isinstance(value, str) and value.strip():
                return value.strip()

        try:
            guidelines = getattr(cur, "writing_guidelines", "")
        except Exception:
            guidelines = ""
        if isinstance(guidelines, str) and guidelines.strip() and not fallback_guidelines:
            fallback_guidelines = guidelines.strip()

        for attr in ("_concrete", "_base", "base_skill", "wrapped_skill", "_wrapped", "inner_skill"):
            try:
                nested = getattr(cur, attr, None)
            except Exception:
                nested = None
            if nested is not None:
                queue.append(nested)

    return fallback_guidelines


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
    diagram_type: str = "technical_route"  # technical_route | research_framework | freestyle | infographic
    mode: str = "infographic"  # infographic | image_model | auto
    # 选区生成：selected_text 为核心，context_text 为全文上下文
    selected_text: Optional[str] = None
    context_text: Optional[str] = None


class GenerateIllustrationsRequest(BaseModel):
    """自动生成配图请求（输入为整篇文章）"""
    document_content: str
    mode: str = "infographic"  # infographic | image_model | auto
    max_images: int = 2


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


async def _get_upload_session_lock(session_id: str) -> asyncio.Lock:
    """Per-session lock for merge/save to avoid concurrent upload write conflicts."""
    async with _UPLOAD_SESSION_LOCKS_GUARD:
        lock = _UPLOAD_SESSION_LOCKS.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            _UPLOAD_SESSION_LOCKS[session_id] = lock
        return lock


async def _parse_json_upload_file(
    idx: int,
    file: UploadFilePayload,
    allowed_extensions: set[str],
) -> tuple[int, Optional[dict], str]:
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        return idx, None, f"❌ {file.filename}: 不支持的文件类型 ({file_ext})"

    try:
        content = base64.b64decode(file.content_base64)
        text_content = await asyncio.to_thread(parse_uploaded_file, content, file_ext, file.filename)
        if text_content:
            parsed = {
                "filename": file.filename,
                "content": text_content,
                "content_type": file.content_type or "",
                "size": len(content),
            }
            return idx, parsed, f"✅ {file.filename}: 解析成功 ({len(text_content)} 字符)"
        return idx, None, f"⚠️ {file.filename}: 文件为空或无法解析"
    except Exception as e:
        return idx, None, f"❌ {file.filename}: 解析失败 - {str(e)}"


async def _parse_multipart_upload_file(
    idx: int,
    file: UploadFile,
    allowed_extensions: set[str],
) -> tuple[int, Optional[dict], str]:
    filename = file.filename or f"uploaded_{idx}"
    file_ext = Path(filename).suffix.lower()
    if file_ext not in allowed_extensions:
        return idx, None, f"❌ {filename}: 不支持的文件类型 ({file_ext})"

    try:
        content = await file.read()
        text_content = await asyncio.to_thread(parse_uploaded_file, content, file_ext, filename)
        if text_content:
            parsed = {
                "filename": filename,
                "content": text_content,
                "content_type": file.content_type or "",
                "size": len(content),
            }
            return idx, parsed, f"✅ {filename}: 解析成功 ({len(text_content)} 字符)"
        return idx, None, f"⚠️ {filename}: 文件为空或无法解析"
    except Exception as e:
        return idx, None, f"❌ {filename}: 解析失败 - {str(e)}"


async def _parse_json_files_parallel(files: List[UploadFilePayload], allowed_extensions: set[str]) -> tuple[List[dict], List[str]]:
    sem = asyncio.Semaphore(_UPLOAD_PARSE_CONCURRENCY)

    async def _worker(idx: int, file: UploadFilePayload):
        async with sem:
            return await _parse_json_upload_file(idx, file, allowed_extensions)

    tasks = [asyncio.create_task(_worker(i, f)) for i, f in enumerate(files)]
    results = await asyncio.gather(*tasks)
    results.sort(key=lambda item: item[0])

    parsed_files: List[dict] = []
    file_summaries: List[str] = []
    for _, parsed, summary in results:
        file_summaries.append(summary)
        if parsed:
            parsed_files.append(parsed)
    return parsed_files, file_summaries


async def _parse_multipart_files_parallel(files: List[UploadFile], allowed_extensions: set[str]) -> tuple[List[dict], List[str]]:
    sem = asyncio.Semaphore(_UPLOAD_PARSE_CONCURRENCY)

    async def _worker(idx: int, file: UploadFile):
        async with sem:
            return await _parse_multipart_upload_file(idx, file, allowed_extensions)

    tasks = [asyncio.create_task(_worker(i, f)) for i, f in enumerate(files)]
    results = await asyncio.gather(*tasks)
    results.sort(key=lambda item: item[0])

    parsed_files: List[dict] = []
    file_summaries: List[str] = []
    for _, parsed, summary in results:
        file_summaries.append(summary)
        if parsed:
            parsed_files.append(parsed)
    return parsed_files, file_summaries


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

    external_info = extraction_result.get("external_information", "")
    extracted_fields = extraction_result.get("extracted_fields", {})
    upload_message = f"📎 已上传 {len(parsed_files)} 个文件并提取信息：\n" + "\n".join(file_summaries)
    merged_external_information = session.external_information or ""

    # Merge/save must be serialized per session; uploads may arrive concurrently.
    session_lock = await _get_upload_session_lock(session.session_id)
    async with session_lock:
        latest_session = workflow.get_session(session.session_id)
        if not latest_session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session.session_id}")

        for pf in parsed_files:
            latest_session.add_uploaded_file({
                "filename": pf["filename"],
                "content_type": pf.get("content_type", ""),
                "size": pf.get("size", 0),
                "content": _trim_file_content(pf.get("content", "")),
                "extracted_fields": extracted_fields,
            })

        if external_info:
            latest_session.append_external_info(external_info)

        if extracted_fields:
            if latest_session.requirements is None:
                latest_session.requirements = {}
            for field_id, value in extracted_fields.items():
                if value is None:
                    continue
                if isinstance(value, str) and not value.strip():
                    continue
                existing_value = latest_session.requirements.get(field_id)
                if existing_value is None or (isinstance(existing_value, str) and not existing_value.strip()):
                    latest_session.requirements[field_id] = value

        latest_session.messages.append({
            "role": "system",
            "content": upload_message,
        })
        workflow.save_session(latest_session)
        merged_external_information = latest_session.external_information or ""

    # Skill-Fixer 调用较重，不持锁执行；执行后再短暂持锁落库。
    if warning is None:
        try:
            fixer = SkillFixerAgent()
            fixer_result = await fixer.run(
                skill=skill,
                extracted_fields=extracted_fields,
                external_information=merged_external_information,
                file_summaries=extraction_result.get("summaries", ""),
            )
            overlay = {
                "writing_guidelines_additions": fixer_result.writing_guidelines_additions,
                "global_principles": fixer_result.global_principles,
                "section_overrides": fixer_result.section_overrides,
                "relax_requirements": fixer_result.relax_requirements,
                "material_context": fixer_result.material_context,
                "section_prompt_overrides": fixer_result.section_prompt_overrides,
            }
            async with session_lock:
                latest_session = workflow.get_session(session.session_id)
                if latest_session:
                    latest_session.skill_overlay = overlay
                    workflow.save_session(latest_session)
        except Exception as e:
            print(f"[Skill Fixer Warning] {e}")

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

    parsed_files, file_summaries = await _parse_json_files_parallel(payload.files, allowed_extensions)

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

        parsed_files, file_summaries = await _parse_multipart_files_parallel(files, allowed_extensions)

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


def _normalize_markdown_text(markdown: str) -> str:
    text = (markdown or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    out: List[str] = []
    blank = 0
    for ln in lines:
        if ln.strip():
            blank = 0
            out.append(ln.rstrip())
            continue
        blank += 1
        if blank <= 2:
            out.append("")
    return "\n".join(out).strip() + "\n"


def _build_figure_markdown(title: str, data_uri: str) -> str:
    t = (title or "图示").strip() or "图示"
    return f"![{t}]({data_uri})\n\n*图：{t}*"


def _split_infographic_points(lines_text: str) -> List[str]:
    source = (lines_text or "").strip()
    if not source:
        return []
    pieces = []
    for line in source.split("\n"):
        s = str(line or "").strip()
        if not s:
            continue
        s = re.sub(r"^\d+[.)、]\s*", "", s)
        s = re.sub(r"^[•\-]\s*", "", s)
        s = s.strip("；; ")
        if s:
            pieces.append(s)
    return pieces[:12]


def _build_local_infographic_spec(
    *,
    diagram_type: str,
    raw_spec: dict,
    lines_text: str,
    title: str,
) -> tuple[str, dict]:
    pieces = _split_infographic_points(lines_text)
    if not pieces:
        pieces = ["研究目标与问题定义", "方法与技术路径", "实验验证与成果输出"]

    if diagram_type == "research_framework":
        spec = raw_spec if isinstance(raw_spec, dict) else {}
        if not spec.get("goal"):
            spec["goal"] = {"title": "研究目标", "bullets": pieces[:3]}
        if not spec.get("hypotheses"):
            spec["hypotheses"] = {"title": "科学问题/假设", "bullets": pieces[1:4] or pieces[:3]}
        if not spec.get("support"):
            spec["support"] = {"title": "支撑条件", "bullets": pieces[2:5] or pieces[:3]}
        if not spec.get("work_packages"):
            spec["work_packages"] = [
                {"title": "WP1 研究内容", "bullets": pieces[:3]},
                {"title": "WP2 研究内容", "bullets": pieces[1:4] or pieces[:3]},
                {"title": "WP3 研究内容", "bullets": pieces[2:5] or pieces[:3]},
            ]
        if not spec.get("outcomes"):
            spec["outcomes"] = {"title": "预期成果", "bullets": pieces[-3:] or pieces[:3]}
        return "research_framework", spec

    # technical_route / infographic / freestyle -> technical route renderer
    spec = raw_spec if isinstance(raw_spec, dict) else {}
    stages = spec.get("stages")
    if not isinstance(stages, list) or not stages:
        chunk_size = max(2, min(3, len(pieces)))
        split_stages = []
        cursor = 0
        while cursor < len(pieces) and len(split_stages) < 5:
            split_stages.append({
                "title": f"阶段{len(split_stages) + 1}",
                "bullets": pieces[cursor:cursor + chunk_size],
            })
            cursor += chunk_size
        if len(split_stages) < 3:
            split_stages = [
                {"title": "阶段1", "bullets": pieces[:3]},
                {"title": "阶段2", "bullets": pieces[1:4] or pieces[:3]},
                {"title": "阶段3", "bullets": pieces[-3:] or pieces[:3]},
            ]
        spec["stages"] = split_stages
    spec["title"] = title
    return "technical_route", spec


def _render_local_infographic_assets(
    *,
    diagram_type: str,
    raw_spec: dict,
    lines_text: str,
    title: str,
) -> tuple[bytes, str, dict, str]:
    from backend.core.diagrams.infographic import render_infographic_png_svg

    render_type, render_spec = _build_local_infographic_spec(
        diagram_type=diagram_type,
        raw_spec=raw_spec,
        lines_text=lines_text,
        title=title,
    )
    png_bytes, svg_text, normalized_spec = render_infographic_png_svg(
        render_type,
        render_spec,
        title=title,
    )
    return png_bytes, svg_text, normalized_spec, render_type


def _build_codegen_schema_hint(diagram_type: str) -> str:
    dt = (diagram_type or "").strip().lower()
    if dt == "research_framework":
        return """{
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
    return """{
  "stages": [
    {"title": "阶段标题", "bullets": ["要点1", "要点2", "要点3"]},
    {"title": "阶段标题", "bullets": ["要点1", "要点2", "要点3"]},
    {"title": "阶段标题", "bullets": ["要点1", "要点2", "要点3"]},
    {"title": "阶段标题", "bullets": ["要点1", "要点2", "要点3"]}
  ]
}"""


def _dedupe_text_list(items: Any, *, max_items: int = 4, max_len: int = 24) -> List[str]:
    if not isinstance(items, list):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for raw in items:
        text = str(raw or "").strip()
        if not text:
            continue
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > max_len:
            text = text[:max_len].rstrip()
        key = _normalized_heading_text(text)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= max_items:
            break
    return out


def _extract_codegen_summary_points(payload: dict) -> List[str]:
    if not isinstance(payload, dict):
        return []
    candidates = [
        payload.get("concise_summary"),
        payload.get("summary_points"),
        payload.get("summary"),
        payload.get("outline"),
    ]
    for value in candidates:
        if isinstance(value, list):
            return _dedupe_text_list(value, max_items=8, max_len=22)
        if isinstance(value, str) and value.strip():
            parts = re.split(r"[；;。\n]+", value.strip())
            return _dedupe_text_list(parts, max_items=8, max_len=22)
    return []


def _extract_codegen_spec_block(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {}
    for key in ("diagram_spec", "spec", "structure", "output", "diagram"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def _sanitize_codegen_spec(spec: dict, diagram_type: str) -> dict:
    dt = (diagram_type or "").strip().lower()
    if not isinstance(spec, dict):
        return {}

    payload = _extract_codegen_spec_block(spec)
    summary_points = _extract_codegen_summary_points(spec)
    global_seen: set[str] = set()
    summary_cursor = 0

    def _borrow_summary(max_items: int = 2) -> List[str]:
        nonlocal summary_cursor
        out: List[str] = []
        if not summary_points:
            return out
        attempts = 0
        while len(out) < max_items and attempts < len(summary_points) * 2:
            candidate = summary_points[summary_cursor % len(summary_points)]
            summary_cursor += 1
            attempts += 1
            key = _normalized_heading_text(candidate)
            if not key or key in global_seen:
                continue
            global_seen.add(key)
            out.append(candidate)
        return out

    def _dedupe_with_global(items: Any, *, max_items: int = 4, max_len: int = 20) -> List[str]:
        local = _dedupe_text_list(items, max_items=max_items * 2, max_len=max_len)
        out: List[str] = []
        for item in local:
            key = _normalized_heading_text(item)
            if not key or key in global_seen:
                continue
            global_seen.add(key)
            out.append(item)
            if len(out) >= max_items:
                break
        return out

    if dt == "research_framework":
        out: Dict[str, Any] = {}
        for key in ("goal", "hypotheses", "support", "outcomes"):
            box = payload.get(key)
            if not isinstance(box, dict):
                continue
            title = str(box.get("title") or "").strip()[:20]
            bullets = _dedupe_with_global(box.get("bullets"), max_items=4, max_len=20)
            if not bullets:
                bullets = _borrow_summary(max_items=2)
            if title or bullets:
                out[key] = {"title": title or key, "bullets": bullets}

        wps = payload.get("work_packages")
        if isinstance(wps, list):
            wp_out = []
            seen_titles: set[str] = set()
            for wp in wps:
                if not isinstance(wp, dict):
                    continue
                title = str(wp.get("title") or "").strip()[:24]
                bullets = _dedupe_with_global(wp.get("bullets"), max_items=4, max_len=20)
                if not bullets:
                    bullets = _borrow_summary(max_items=2)
                key = _normalized_heading_text(title) or _normalized_heading_text(" ".join(bullets))
                if not key or key in seen_titles:
                    continue
                seen_titles.add(key)
                wp_out.append({"title": title or f"WP{len(wp_out) + 1}", "bullets": bullets})
                if len(wp_out) >= 4:
                    break
            if wp_out:
                out["work_packages"] = wp_out

        if not out and summary_points:
            out = {
                "goal": {"title": "研究目标", "bullets": summary_points[:3]},
                "hypotheses": {"title": "科学问题/假设", "bullets": summary_points[1:4] or summary_points[:3]},
                "support": {"title": "支撑条件", "bullets": summary_points[2:5] or summary_points[:3]},
                "work_packages": [
                    {"title": "WP1 研究内容", "bullets": summary_points[:3]},
                    {"title": "WP2 研究内容", "bullets": summary_points[1:4] or summary_points[:3]},
                    {"title": "WP3 研究内容", "bullets": summary_points[2:5] or summary_points[:3]},
                ],
                "outcomes": {"title": "预期成果", "bullets": summary_points[-3:] or summary_points[:3]},
            }
        return out

    stages = payload.get("stages")
    if not isinstance(stages, list):
        if summary_points:
            return {
                "stages": [
                    {"title": "问题定义", "bullets": summary_points[:3]},
                    {"title": "方法设计", "bullets": summary_points[1:4] or summary_points[:3]},
                    {"title": "验证与产出", "bullets": summary_points[-3:] or summary_points[:3]},
                ]
            }
        return {}
    stage_out = []
    seen_titles: set[str] = set()
    for stage in stages:
        if not isinstance(stage, dict):
            continue
        title = str(stage.get("title") or "").strip()[:20]
        bullets = _dedupe_with_global(stage.get("bullets"), max_items=4, max_len=20)
        if not bullets:
            bullets = _borrow_summary(max_items=2)
        key = _normalized_heading_text(title) or _normalized_heading_text(" ".join(bullets))
        if not key or key in seen_titles:
            continue
        seen_titles.add(key)
        stage_out.append({"title": title or f"阶段{len(stage_out) + 1}", "bullets": bullets})
        if len(stage_out) >= 6:
            break

    if not stage_out and summary_points:
        stage_out = [
            {"title": "问题定义", "bullets": summary_points[:3]},
            {"title": "方法设计", "bullets": summary_points[1:4] or summary_points[:3]},
            {"title": "验证与产出", "bullets": summary_points[-3:] or summary_points[:3]},
        ]
    return {"stages": stage_out} if stage_out else {}


async def _generate_local_infographic_spec_via_skill(
    *,
    workflow,
    diagram_type: str,
    title: str,
    full_context: str,
    focus_context: str,
) -> dict:
    registry = get_registry()
    codegen_skill = registry.get("scientific-infographic-codegen")

    full_text = (full_context or "").strip()
    focus_text = (focus_context or "").strip()
    if len(full_text) > 12000:
        full_text = full_text[:12000]
    if len(focus_text) > 3000:
        focus_text = focus_text[:3000]

    schema_hint = _build_codegen_schema_hint(diagram_type)
    fallback_user_prompt = f"""请为科研文稿生成“{title}”的结构化图示规格（用于本地代码渲染，不是成图模型）。

只输出 JSON，不要解释、不要代码块。
请按“两步法”：
步骤1）先做信息压缩：从输入中提炼 3-6 条 `concise_summary`；
步骤2）基于该摘要输出 `diagram_spec`（必须符合 schema）。

强约束：
1) 重点片段优先，同时与全文上下文保持一致；
2) 严禁复制长段落，必须改写为短语要点；
3) 每个 bullets 条目建议 8-20 字，避免同义重复；
4) 技术路线建议体现：问题定义 → 方法实现 → 验证评估 → 产出；
5) 不得编造数据、实验结果或结论。

图类型：{diagram_type}

目标 schema（用于 diagram_spec）：
{schema_hint}

输出 JSON 目标格式：
{{
  "concise_summary": ["摘要要点1", "摘要要点2", "摘要要点3"],
  "diagram_spec": "按上方 schema 输出对象"
}}

输入A（全文上下文，背景参考）：
{full_text or "（无）"}

输入B（重点片段，核心优先）：
{focus_text or "（无）"}
"""

    system_prompt = "你是科研图示结构规划器。只输出 JSON。"
    user_prompt = fallback_user_prompt

    if codegen_skill:
        try:
            system_prompt = _resolve_skill_system_prompt(codegen_skill) or system_prompt
            sections = codegen_skill.get_flat_sections()
            section = sections[0] if sections else None
            if section:
                context = {
                    "requirements": {
                        "diagram_type": diagram_type,
                        "diagram_title": title,
                        "schema_hint": schema_hint,
                        "full_context": full_text,
                        "focus_context": focus_text,
                    },
                    "external_information": full_text,
                }
                rendered = codegen_skill.get_section_prompt(section, context)
                if isinstance(rendered, str) and rendered.strip():
                    user_prompt = rendered.strip()
            if user_prompt == fallback_user_prompt:
                guidelines = (getattr(codegen_skill, "writing_guidelines", "") or "").strip()
                if guidelines:
                    user_prompt = f"{guidelines}\n\n{fallback_user_prompt}"
        except Exception as e:
            logger.warning("codegen skill prompt render failed, fallback prompt used: %s", _redact_secrets(str(e))[:240])

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        raw = await workflow.writer_agent._chat(messages, temperature=0.2, max_tokens=900)
        parsed = _extract_json_obj(raw)
        return _sanitize_codegen_spec(parsed, diagram_type)
    except Exception as e:
        logger.warning("local infographic spec generation failed: %s", _redact_secrets(str(e))[:280])
        return {}


def _heading_keywords_for_type(diagram_type: str) -> List[str]:
    dt = (diagram_type or "").strip().lower()
    if dt == "technical_route":
        return ["技术路线", "研究内容", "研究方案", "研究方法", "方法", "路线", "实施方案"]
    if dt == "research_framework":
        return ["研究框架", "总体框架", "总体思路", "研究目标", "立项依据", "框架"]
    if dt == "infographic":
        return ["摘要", "概述", "引言", "项目简介", "研究思路"]
    return ["研究内容", "方法", "框架", "结论"]


def _normalized_heading_text(text: str) -> str:
    s = re.sub(r"^[#\s]+", "", (text or "").strip())
    s = re.sub(r"[`*_>\-]", "", s)
    s = re.sub(r"\s+", "", s)
    return s.lower()


def _find_heading_index(lines: List[str], heading: str) -> int:
    target = _normalized_heading_text(heading)
    if not target:
        return -1
    for idx, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("#"):
            continue
        h = _normalized_heading_text(s)
        if target in h or h in target:
            return idx
    return -1


def _find_line_index_by_anchor(lines: List[str], anchor_text: str) -> int:
    anchor = (anchor_text or "").strip()
    if not anchor:
        return -1
    for idx, line in enumerate(lines):
        if anchor in line:
            return idx
    return -1


def _fallback_insert_index(lines: List[str], diagram_type: str) -> int:
    keys = _heading_keywords_for_type(diagram_type)
    for idx, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("#"):
            continue
        normalized = _normalized_heading_text(s)
        for key in keys:
            if _normalized_heading_text(key) in normalized:
                return idx

    for idx, line in enumerate(lines):
        if line.strip().startswith("#"):
            return idx
    return 0


async def _plan_illustration_items(
    *,
    workflow,
    document_content: str,
    max_images: int,
    agent_system_prompt: str = "",
) -> List[Dict[str, str]]:
    max_images = max(1, min(int(max_images or 2), 4))
    excerpt = (document_content or "").strip()
    if len(excerpt) > 12000:
        excerpt = excerpt[:12000]

    prompt = f"""你是科研文档配图规划助手。请根据全文内容，规划最多 {max_images} 张图。

只输出 JSON：
{{
  "illustrations": [
    {{
      "title": "图标题",
      "diagram_type": "technical_route|research_framework|infographic",
      "focus_text": "从全文中挑出的关键内容摘要（1-3句）"
    }}
  ]
}}

要求：
1) 标题简洁专业；
2) 优先覆盖“技术路线图、研究框架图”；
3) focus_text 必须来自全文语义，不编造事实；
4) 仅输出 JSON。

全文：
{excerpt}
"""
    system_prompt = "你只输出 JSON。"
    if agent_system_prompt:
        system_prompt = f"{agent_system_prompt}\n\n{system_prompt}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await workflow.writer_agent._chat(messages, temperature=0.2, max_tokens=700)
        obj = _extract_json_obj(raw)
    except Exception:
        obj = {}

    items = obj.get("illustrations") if isinstance(obj, dict) else None
    normalized: List[Dict[str, str]] = []
    if isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            title = str(it.get("title") or "").strip()
            dtype = str(it.get("diagram_type") or "").strip().lower()
            focus_text = str(it.get("focus_text") or "").strip()
            if dtype not in {"technical_route", "research_framework", "infographic"}:
                continue
            if not title:
                title = "技术路线图" if dtype == "technical_route" else ("研究框架图" if dtype == "research_framework" else "科研信息图")
            if not focus_text:
                focus_text = excerpt[:1200]
            normalized.append({
                "title": title[:40],
                "diagram_type": dtype,
                "focus_text": focus_text[:3000],
            })
            if len(normalized) >= max_images:
                break

    if normalized:
        return normalized

    fallback: List[Dict[str, str]] = [
        {"title": "技术路线图", "diagram_type": "technical_route", "focus_text": excerpt[:1800]},
        {"title": "研究框架图", "diagram_type": "research_framework", "focus_text": excerpt[:1800]},
    ]
    return fallback[:max_images]


async def _plan_insertions_with_llm(
    *,
    workflow,
    document_content: str,
    diagrams: List[Dict[str, Any]],
    agent_system_prompt: str = "",
) -> List[Dict[str, str]]:
    excerpt = (document_content or "").strip()
    if len(excerpt) > 14000:
        excerpt = excerpt[:14000]

    diag_lines = []
    for d in diagrams:
        diag_lines.append(
            f"- id: {d.get('diagram_id')} | title: {d.get('title')} | type: {d.get('diagram_type')} | focus: {str(d.get('focus_text') or '')[:120]}"
        )
    diag_text = "\n".join(diag_lines) if diag_lines else "（无）"

    prompt = f"""你是科研文档排版助手。请为每张图确定在全文中的插入位置。

只输出 JSON：
{{
  "placements": [
    {{
      "diagram_id": "图ID",
      "anchor_heading": "优先插入到此标题之后（可为空）",
      "anchor_text": "若无标题则匹配该句子片段（可为空）"
    }}
  ]
}}

规则：
1) 让图片贴近对应章节，避免全部堆在文档开头；
2) 优先使用标题锚点；
3) 不改变正文原意；
4) 仅输出 JSON。

待插入图片：
{diag_text}

全文 Markdown：
{excerpt}
"""
    system_prompt = "你只输出 JSON。"
    if agent_system_prompt:
        system_prompt = f"{agent_system_prompt}\n\n{system_prompt}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    try:
        raw = await workflow.writer_agent._chat(messages, temperature=0.1, max_tokens=700)
        obj = _extract_json_obj(raw)
    except Exception:
        obj = {}

    placements = obj.get("placements") if isinstance(obj, dict) else None
    out: List[Dict[str, str]] = []
    if isinstance(placements, list):
        for p in placements:
            if not isinstance(p, dict):
                continue
            did = str(p.get("diagram_id") or "").strip()
            if not did:
                continue
            out.append({
                "diagram_id": did,
                "anchor_heading": str(p.get("anchor_heading") or "").strip(),
                "anchor_text": str(p.get("anchor_text") or "").strip(),
            })
    return out


def _apply_diagram_insertions(
    *,
    document_content: str,
    diagrams: List[Dict[str, Any]],
    placements: List[Dict[str, str]],
) -> str:
    text = _normalize_markdown_text(document_content or "")
    lines = text.split("\n")

    placement_map = {str(p.get("diagram_id") or "").strip(): p for p in placements if isinstance(p, dict)}

    indexed_blocks: List[tuple[int, int, str]] = []
    for order, d in enumerate(diagrams):
        did = str(d.get("diagram_id") or "").strip()
        if not did:
            continue
        placement = placement_map.get(did, {})
        idx = -1
        anchor_heading = str(placement.get("anchor_heading") or "").strip()
        if anchor_heading:
            idx = _find_heading_index(lines, anchor_heading)
        if idx < 0:
            anchor_text = str(placement.get("anchor_text") or "").strip()
            if anchor_text:
                idx = _find_line_index_by_anchor(lines, anchor_text)
        if idx < 0:
            idx = _fallback_insert_index(lines, str(d.get("diagram_type") or ""))

        snippet = str(d.get("markdown_snippet") or "").strip()
        if not snippet:
            continue
        block_lines = ["", snippet, ""]
        block = "\n".join(block_lines)
        indexed_blocks.append((idx, order, block))

    # Desc insert to keep indices stable
    indexed_blocks.sort(key=lambda x: (x[0], x[1]), reverse=True)
    for idx, _order, block in indexed_blocks:
        insert_at = max(0, min(idx + 1, len(lines)))
        b_lines = block.split("\n")
        lines[insert_at:insert_at] = b_lines

    return _normalize_markdown_text("\n".join(lines))


@router.post("/session/{session_id}/generate-diagram")
async def generate_diagram(session_id: str, request: DiagramRequest):
    """生成图示：`image_model` 走成图模型；`infographic` 走本地信息图渲染（无外部成图依赖）。"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    _ensure_llm_configured()

    registry = get_registry()
    skill = registry.get(session.skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill not found: {session.skill_id}")

    diagram_type = (request.diagram_type or "technical_route").strip().lower() or "technical_route"
    if diagram_type not in {"technical_route", "research_framework", "freestyle", "infographic"}:
        raise HTTPException(status_code=400, detail=f"Unsupported diagram_type: {diagram_type}")

    mode = (request.mode or "infographic").strip().lower() or "infographic"
    if mode not in {"infographic", "image_model", "auto"}:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")
    if mode == "auto":
        mode = "infographic"

    cfg = get_llm_config()
    image_model = (getattr(cfg, "image_model", None) or "").strip()
    if mode == "image_model":
        if not image_model:
            raise HTTPException(status_code=400, detail="未配置成图模型：请先在设置中填写“成图模型（Image Model）”。")
        if not (cfg.base_url or "").strip():
            raise HTTPException(status_code=400, detail="未配置 Base URL，无法调用成图模型。")

    default_title = {
        "technical_route": "技术路线图",
        "research_framework": "研究框架图",
        "freestyle": "科研示意图",
        "infographic": "科研信息图",
    }
    title = (request.title or default_title.get(diagram_type, "图示")).strip()

    if request.selected_text:
        selected_text = (request.selected_text or "").strip()
        requirements_text = selected_text or "（暂无）"
        external_excerpt = (request.context_text or "").strip()
        if len(external_excerpt) > 12000:
            external_excerpt = external_excerpt[:12000]
    else:
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

    raw_spec = {}
    full_context_for_codegen = (request.context_text or external_excerpt or "").strip()
    focus_context_for_codegen = (request.selected_text or requirements_text or "").strip()

    if mode == "infographic":
        raw_spec = await _generate_local_infographic_spec_via_skill(
            workflow=workflow,
            diagram_type=diagram_type,
            title=title,
            full_context=full_context_for_codegen,
            focus_context=focus_context_for_codegen,
        )
    elif diagram_type in {"technical_route", "research_framework"}:
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

        prompt = f"""你是科研申报书图示设计助手。请根据“已知需求”和“材料摘要”，生成可用于绘制“{title}”的结构化 JSON。

只输出 JSON（不要解释、不要 Markdown 代码块）。

硬性约束：
1) 结构必须严格匹配下面的 JSON 结构示例（字段名保持一致）；
2) 不得虚构数据、结果、实验结论；
3) 每个 title <= 14 字；每条 bullets <= 22 字；
4) 信息不足时，使用规范但保守的描述。

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

    def _lines_from_spec() -> str:
        if diagram_type == "technical_route":
            stages = (raw_spec.get("stages") if isinstance(raw_spec, dict) else None) or []
            out = []
            for i, st in enumerate(stages[:6] if isinstance(stages, list) else []):
                if not isinstance(st, dict):
                    continue
                t = str(st.get("title") or f"阶段{i + 1}").strip()
                bs = st.get("bullets") or []
                btxt = "；".join([str(x).strip() for x in (bs[:4] if isinstance(bs, list) else []) if str(x).strip()])
                if t or btxt:
                    out.append(f"{i + 1}. {t}：{btxt}".strip("："))
            return "\n".join(out) if out else requirements_text

        if diagram_type == "research_framework":
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
                    t = str(wp.get("title") or f"WP{i + 1}").strip()
                    bs = wp.get("bullets") or []
                    btxt = "；".join([str(x).strip() for x in (bs[:4] if isinstance(bs, list) else []) if str(x).strip()])
                    if t or btxt:
                        parts.append(f"{t}：{btxt}".strip("："))
            return "\n".join(parts) if parts else requirements_text

        source = ((request.selected_text or "").strip() or requirements_text or "").strip()
        pieces = [x.strip("•- \t") for x in re.split(r"[\n；;]+", source) if x and x.strip("•- \t")]
        if not pieces:
            return "1. 研究目标与问题定义\n2. 方法与技术路径\n3. 验证与成果输出"
        return "\n".join([f"{i + 1}. {v}" for i, v in enumerate(pieces[:10])])

    if diagram_type == "technical_route":
        diagram_kind_cn = "技术路线图"
        layout_hint = "按阶段从左到右或从上到下，4-6 个阶段，箭头清晰表达先后依赖与反馈闭环。"
    elif diagram_type == "research_framework":
        diagram_kind_cn = "研究框架图"
        layout_hint = "采用“目标/问题 → 任务包(WP) → 验证/成果”的层次结构，并标出支撑条件。"
    elif diagram_type == "freestyle":
        diagram_kind_cn = "科研示意图"
        layout_hint = "根据内容组织成逻辑清晰的模块关系图，避免装饰性元素。"
    else:
        diagram_kind_cn = "科研信息图"
        layout_hint = "以信息图样式表达关键模块和关系，强调结构化、可读性、可解释性。"

    if mode == "infographic":
        style_hint = (
            "信息图风格（infographic）：扁平化、卡片分区、统一配色；背景白色或浅色；"
            "中文文字清晰；禁止水印、Logo、摄影风。"
        )
    else:
        style_hint = (
            "科研图示风格：专业、克制、结构导向；以模块框图和流程箭头为主；"
            "中文标签清晰、术语规范；禁止水印、Logo。"
        )

    lines_text = _lines_from_spec()
    image_prompt = f"""请生成一张可直接用于科研申报书的中文{diagram_kind_cn}。

风格要求：
- {style_hint}
- {layout_hint}
- 图中文字必须清晰可读，避免过度拥挤与重叠。

标题：{title}
内容（保持含义，不得虚构数据/结论）：
{lines_text}
"""

    review_prompt = f"""请审核这张图是否满足科研申报书可用标准，并严格输出 JSON：
{{
  "passed": true/false,
  "score": 0-100,
  "issues": ["问题1", "问题2"],
  "improvements": ["改进建议1", "改进建议2"],
  "summary": "一句话结论"
}}

审核维度：
1) 结构完整性：流程/层次是否清晰，关系是否明确；
2) 学术可用性：术语是否规范，是否避免不实结论；
3) 可读性：中文是否清晰，是否拥挤或重叠；
4) 图示质量：布局、对齐、视觉一致性。
"""

    actual_mode = mode
    review_result = None
    review_error = None
    svg_text = ""
    used_spec = raw_spec or {}

    if mode == "infographic":
        try:
            png_bytes, svg_text, used_spec, render_type = _render_local_infographic_assets(
                diagram_type=diagram_type,
                raw_spec=raw_spec,
                lines_text=lines_text,
                title=title,
            )
            review_result = {
                "passed": True,
                "score": 95,
                "issues": [],
                "improvements": [],
                "summary": f"已通过本地信息图引擎生成（{render_type}）。",
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"本地信息图生成失败：{_redact_secrets(str(e))}")
    else:
        from backend.core.diagrams.openai_images import (
            generate_image_png_via_openai_compatible,
            review_image_via_openai_compatible,
        )

        async def _generate_image(prompt_text: str) -> bytes:
            last_err = None
            for size in ("1792x1024", "1024x1024"):
                try:
                    png, _raw = await generate_image_png_via_openai_compatible(
                        base_url=cfg.base_url,
                        api_key=cfg.api_key,
                        model=image_model,
                        prompt=prompt_text,
                        size=size,
                    )
                    return png
                except Exception as e:
                    last_err = e
                    continue
            if last_err is None:
                raise RuntimeError("成图模型未返回图像")
            raise last_err

        async def _review_image(png: bytes) -> dict:
            review, _raw = await review_image_via_openai_compatible(
                base_url=cfg.base_url,
                api_key=cfg.api_key,
                model=image_model,
                review_prompt=review_prompt,
                image_bytes=png,
            )
            return review

        try:
            png_bytes = await _generate_image(image_prompt)
        except Exception as e:
            # image_model 不稳定时，自动回退到本地 infographic，保证功能可用
            gen_error = _redact_secrets(str(e))
            logger.warning("image model generation failed, fallback to local infographic: %s", gen_error[:320])
            try:
                png_bytes, svg_text, used_spec, render_type = _render_local_infographic_assets(
                    diagram_type=diagram_type,
                    raw_spec=raw_spec,
                    lines_text=lines_text,
                    title=title,
                )
                actual_mode = "infographic"
                review_error = gen_error
                review_result = {
                    "passed": True,
                    "score": 88,
                    "issues": ["成图模型接口不可用，已自动降级为本地信息图渲染。"],
                    "improvements": ["如需照片级视觉风格，请恢复 image_model 服务后重试。"],
                    "summary": f"已自动回退到本地信息图引擎（{render_type}）。",
                }
            except Exception as fallback_e:
                raise HTTPException(
                    status_code=502,
                    detail=f"成图模型生成失败：{gen_error}；本地回退也失败：{_redact_secrets(str(fallback_e))}",
                )

        if review_result is None:
            try:
                review_result = await _review_image(png_bytes)
            except Exception as e:
                review_error = _redact_secrets(str(e))
                logger.warning("diagram review failed: %s", review_error[:280])

        if isinstance(review_result, dict) and not review_result.get("passed", True):
            suggestions = review_result.get("improvements") or review_result.get("issues") or []
            if isinstance(suggestions, list) and suggestions:
                suggestion_text = "\n".join([f"- {str(x).strip()}" for x in suggestions if str(x).strip()][:8])
                retry_prompt = f"""{image_prompt}

请根据以下审核意见重绘并提升图示质量（保持原有语义，不得虚构）：
{suggestion_text}
"""
                try:
                    revised = await _generate_image(retry_prompt)
                    png_bytes = revised
                    try:
                        review_result = await _review_image(png_bytes)
                        review_error = None
                    except Exception as e:
                        review_error = _redact_secrets(str(e))
                except Exception as e:
                    logger.warning("diagram retry generation failed: %s", _redact_secrets(str(e))[:260])

    diagram_id = str(uuid.uuid4())
    png_path, svg_path = _diagram_paths(session_id, diagram_id)

    try:
        png_path.write_bytes(png_bytes)
        if svg_text:
            svg_path.write_text(svg_text, encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存图示失败：{_redact_secrets(str(e))}")

    b64_png = base64.b64encode(png_bytes).decode("ascii")
    data_uri = f"data:image/png;base64,{b64_png}"
    snippet = _build_figure_markdown(title, data_uri)

    diagram_record = {
        "id": diagram_id,
        "title": title,
        "diagram_type": diagram_type,
        "mode": actual_mode,
        "created_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "has_png": True,
        "has_svg": bool(svg_text),
        "spec": used_spec or None,
        "meta": {
            "provider": getattr(cfg, "provider_name", None),
            "chat_model": getattr(cfg, "model", None),
            "image_model": image_model or None,
            "review_model": image_model or None,
            "render_engine": "local_infographic" if svg_text else "image_model",
            "review": review_result,
            "review_error": review_error,
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
        "mode": actual_mode,
        "image_data_uri": data_uri,
        "markdown_snippet": snippet,
        "has_svg": bool(svg_text),
        "png_url": f"/api/chat/session/{session_id}/diagrams/{diagram_id}.png",
        "svg_url": f"/api/chat/session/{session_id}/diagrams/{diagram_id}.svg" if svg_text else None,
        "review": review_result,
        "review_error": review_error,
    }


@router.post("/session/{session_id}/generate-illustrations")
async def generate_illustrations(session_id: str, request: GenerateIllustrationsRequest):
    """
    文章配图 Agent：
    1) 基于全文规划要生成的图；
    2) 生成并审核图；
    3) 最后再调用一次 LLM 规划插入位置并完成插入。
    """
    workflow = get_workflow()
    session = workflow.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    if session.phase != "complete":
        raise HTTPException(status_code=400, detail="全文尚未生成完成，请先完成文档生成后再触发配图。")

    _ensure_llm_configured()

    document_content = _normalize_markdown_text(request.document_content or "")
    if len(document_content.strip()) < 30:
        raise HTTPException(status_code=400, detail="文章内容过短，无法自动配图。")

    mode = (request.mode or "infographic").strip().lower() or "infographic"
    if mode not in {"infographic", "image_model", "auto"}:
        raise HTTPException(status_code=400, detail=f"Unsupported mode: {mode}")
    if mode == "auto":
        mode = "infographic"

    max_images = max(1, min(int(request.max_images or 2), 4))

    registry = get_registry()
    schematics_skill = registry.get("scientific-schematics")
    agent_system_prompt = _resolve_skill_system_prompt(schematics_skill)
    if len(agent_system_prompt) > 4000:
        agent_system_prompt = agent_system_prompt[:4000]

    # Step 1) 先基于全文规划配图任务
    items = await _plan_illustration_items(
        workflow=workflow,
        document_content=document_content,
        max_images=max_images,
        agent_system_prompt=agent_system_prompt,
    )

    # Step 2) 逐图生成（仍复用 generate-diagram 主链路，selected_text 为核心，context_text 为全文）
    created: List[Dict[str, Any]] = []
    for item in items:
        try:
            result = await generate_diagram(
                session_id=session_id,
                request=DiagramRequest(
                    title=item.get("title") or None,
                    diagram_type=item.get("diagram_type") or "infographic",
                    mode=mode,
                    selected_text=(item.get("focus_text") or "").strip() or document_content[:1600],
                    context_text=document_content,
                ),
            )
            created.append({
                "diagram_id": result.get("diagram_id"),
                "title": result.get("title"),
                "diagram_type": result.get("diagram_type"),
                "markdown_snippet": result.get("markdown_snippet"),
                "focus_text": item.get("focus_text") or "",
                "review": result.get("review"),
                "review_error": result.get("review_error"),
            })
        except Exception as e:
            logger.warning("auto illustration generate failed: %s", _redact_secrets(str(e))[:260])
            continue

    if not created:
        raise HTTPException(status_code=502, detail="自动配图失败：未生成任何图片。")

    # Step 3) 最后一轮 LLM：决定插图位置
    placements = await _plan_insertions_with_llm(
        workflow=workflow,
        document_content=document_content,
        diagrams=created,
        agent_system_prompt=agent_system_prompt,
    )

    # Step 4) 插入并优化排版
    updated_document = _apply_diagram_insertions(
        document_content=document_content,
        diagrams=created,
        placements=placements,
    )

    return {
        "success": True,
        "session_id": session_id,
        "mode": mode,
        "inserted_count": len(created),
        "updated_document": updated_document,
        "diagrams": created,
        "placements": placements,
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
        "phase": session.phase,
        "is_complete": session.phase == "complete",
        "has_document": bool(session.final_document),
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
