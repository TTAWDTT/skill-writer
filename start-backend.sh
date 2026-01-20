#!/bin/bash
# 启动后端服务

cd "$(dirname "$0")/backend"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate

# 安装依赖
pip install -r requirements.txt -q

# 启动服务
echo "Starting SkillWriter backend on http://localhost:8000"
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
