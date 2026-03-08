"""
Jobs API 路由
提供后台任务的基础查询接口
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Any, Dict

from backend.api.security import require_bearer_token
from backend.models.job_store import JobStore

router = APIRouter()
store = JobStore()


class JobCreateRequest(BaseModel):
    """通用 Job 创建请求（预留给将来通用任务使用）"""
    type: str
    payload: Optional[Dict[str, Any]] = None


class JobResponse(BaseModel):
    """Job 基本响应结构"""
    id: str
    type: str
    status: str
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _serialize_job(job) -> JobResponse:
    data = job.to_dict()
    return JobResponse(
        id=data["id"],
        type=data["type"],
        status=data["status"],
        payload=data.get("payload") or None,
        result=data.get("result") or None,
        error=data.get("error"),
    )


@router.post("/", response_model=JobResponse)
async def create_job(request: JobCreateRequest, http_request: Request):
    """
    创建一个通用 Job。
    当前实现仅创建记录，不自动执行任务，后续可扩展。
    """
    owner_token = require_bearer_token(http_request)
    job = store.create_job(owner_token=owner_token, job_type=request.type, payload=request.payload or {})
    return _serialize_job(job)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, http_request: Request):
    """获取单个 Job 状态"""
    owner_token = require_bearer_token(http_request)
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if (job.owner_token or "") != owner_token:
        raise HTTPException(status_code=403, detail="Forbidden")
    return _serialize_job(job)


@router.get("/", response_model=List[JobResponse])
async def list_jobs(http_request: Request, limit: int = 50):
    """列出当前用户最近的 Job"""
    owner_token = require_bearer_token(http_request)
    jobs = store.list_jobs_for_owner(owner_token, limit=limit)
    return [_serialize_job(job) for job in jobs]

