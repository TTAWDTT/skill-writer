"""
Chat API 路由
处理与工作流的交互对话，支持流式输出
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path
import json

from backend.core.workflow import get_workflow
from backend.core.skills.registry import get_registry
from backend.core.agents.file_extractor import (
    parse_uploaded_file,
    extract_info_from_multiple_files,
)

try:
    import multipart  # noqa: F401
    MULTIPART_AVAILABLE = True
except Exception:
    MULTIPART_AVAILABLE = False

router = APIRouter()


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
    required_fields = [f for f in skill.requirement_fields if f.required]
    target_fields = required_fields if required_fields else skill.requirement_fields
    return [
        {
            "id": f.id,
            "name": f.name,
            "description": f.description,
        }
        for f in target_fields
    ]


async def _handle_parsed_upload(
    session,
    skill,
    workflow,
    parsed_files: List[dict],
    file_summaries: List[str],
):
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

    extraction_result = await extract_info_from_multiple_files(
        files=parsed_files,
        skill_fields=skill_fields,
        skill_name=skill.metadata.name,
        existing_requirements=session.requirements,
    )

    # 更新会话状态
    for pf in parsed_files:
        session.add_uploaded_file({
            "filename": pf["filename"],
            "content_type": pf.get("content_type", ""),
            "size": pf.get("size", 0),
            "extracted_fields": extraction_result.get("extracted_fields", {}),
        })

    # 追加外部信息
    external_info = extraction_result.get("external_information", "")
    if external_info:
        session.append_external_info(external_info)

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

    # 支持的文件类型
    allowed_extensions = {'.md', '.txt', '.doc', '.docx', '.pdf'}

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
    except Exception as e:
        import traceback
        print(f"[File Upload Error] {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"文件信息提取失败: {str(e)}"
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
        allowed_extensions = {'.md', '.txt', '.doc', '.docx', '.pdf'}

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
        except Exception as e:
            import traceback
            print(f"[File Upload Error] {traceback.format_exc()}")
            raise HTTPException(
                status_code=500,
                detail=f"文件信息提取失败: {str(e)}"
            )


@router.get("/session/{session_id}/files")
async def get_session_files(session_id: str):
    """获取会话上传的文件列表"""
    workflow = get_workflow()
    session = workflow.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return {
        "session_id": session.session_id,
        "files": session.uploaded_files,
        "external_information": session.external_information,
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
        fields = [
            {
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "type": f.field_type,
                "required": f.required,
                "placeholder": f.placeholder,
            }
            for f in skill.requirement_fields
        ]

    return {
        "session_id": session_id,
        "requirements": session.requirements or {},
        "fields": fields,
        "external_information": session.external_information,
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

    # 检查必填字段
    missing_fields = []
    requirements = session.requirements or {}

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
