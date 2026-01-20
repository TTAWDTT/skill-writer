"""
Documents API 路由
处理生成的文档
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

router = APIRouter()

# 简单的内存存储（生产环境应使用数据库）
_documents = {}


class DocumentCreate(BaseModel):
    """创建文档请求"""
    title: str
    skill_id: str
    content: str
    session_id: Optional[str] = None


class DocumentUpdate(BaseModel):
    """更新文档请求"""
    title: Optional[str] = None
    content: Optional[str] = None


class DocumentResponse(BaseModel):
    """文档响应"""
    id: str
    title: str
    skill_id: str
    content: str
    created_at: str
    updated_at: str


@router.post("/", response_model=DocumentResponse)
async def create_document(doc: DocumentCreate):
    """创建新文档"""
    doc_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    document = {
        "id": doc_id,
        "title": doc.title,
        "skill_id": doc.skill_id,
        "content": doc.content,
        "session_id": doc.session_id,
        "created_at": now,
        "updated_at": now,
    }

    _documents[doc_id] = document
    return DocumentResponse(**document)


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(skill_id: Optional[str] = None):
    """获取文档列表"""
    docs = list(_documents.values())

    if skill_id:
        docs = [d for d in docs if d["skill_id"] == skill_id]

    # 按更新时间倒序
    docs.sort(key=lambda x: x["updated_at"], reverse=True)

    return [DocumentResponse(**d) for d in docs]


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str):
    """获取单个文档"""
    if doc_id not in _documents:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    return DocumentResponse(**_documents[doc_id])


@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(doc_id: str, update: DocumentUpdate):
    """更新文档"""
    if doc_id not in _documents:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    doc = _documents[doc_id]

    if update.title is not None:
        doc["title"] = update.title
    if update.content is not None:
        doc["content"] = update.content

    doc["updated_at"] = datetime.now().isoformat()

    return DocumentResponse(**doc)


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """删除文档"""
    if doc_id not in _documents:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    del _documents[doc_id]
    return {"message": "Document deleted"}


@router.get("/{doc_id}/export")
async def export_document(doc_id: str, format: str = "markdown"):
    """导出文档"""
    if doc_id not in _documents:
        raise HTTPException(status_code=404, detail=f"Document not found: {doc_id}")

    doc = _documents[doc_id]

    if format == "markdown":
        return {
            "format": "markdown",
            "content": doc["content"],
            "filename": f"{doc['title']}.md",
        }
    elif format == "html":
        # 简单的 Markdown 转 HTML（生产环境应使用 markdown 库）
        html_content = f"<html><body><h1>{doc['title']}</h1><pre>{doc['content']}</pre></body></html>"
        return {
            "format": "html",
            "content": html_content,
            "filename": f"{doc['title']}.html",
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
