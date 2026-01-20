@echo off
REM 启动后端服务 (Windows)

cd /d "%~dp0backend"

REM 检查虚拟环境
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 安装依赖
pip install -r requirements.txt -q

REM 启动服务
echo Starting SkillWriter backend on http://localhost:8000
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
