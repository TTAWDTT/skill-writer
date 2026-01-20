"""
FastAPI 主应用
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api.routes import skills, documents, chat, sessions
from backend.api.routes import config as config_routes

# 在模块加载时初始化 Skills（确保在 uvicorn reload 时也能正确加载）
from backend.core.skills.registry import init_skills_from_directory
from backend.models.database import get_database

# 初始化数据库
get_database()

# 加载 Skills
_skill_count = init_skills_from_directory()
print(f"[OK] Loaded {_skill_count} skills from files")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="智能文书写作平台 API",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(skills.router, prefix="/api/skills", tags=["Skills"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(config_routes.router, prefix="/api/config", tags=["Config"])


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# 启动时初始化
@app.on_event("startup")
async def startup():
    print(f"[OK] {settings.APP_NAME} v{settings.APP_VERSION} started")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
