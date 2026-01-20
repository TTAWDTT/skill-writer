#!/usr/bin/env python
"""
Skill Writer 后端启动脚本
"""
import sys
import os

# 将项目根目录添加到 Python 路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# 同时设置环境变量，确保 uvicorn 的子进程也能找到模块
os.environ['PYTHONPATH'] = PROJECT_ROOT + os.pathsep + os.environ.get('PYTHONPATH', '')

if __name__ == "__main__":
    import uvicorn
    from backend.config import settings

    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"Server: http://localhost:{settings.API_PORT}")
    print(f"Docs: http://localhost:{settings.API_PORT}/docs")
    print(f"Project: {PROJECT_ROOT}")
    print()

    uvicorn.run(
        "backend.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
        reload_dirs=[PROJECT_ROOT] if settings.DEBUG else None,
    )
