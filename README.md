# Skill Writer - 智能文书写作平台

一个基于 Skill 架构的智能文书生成系统，支持多种文书类型，可扩展学习新的文书格式。

## 核心特性

- **Skill 系统**：每种文书类型对应一个 Skill，包含结构模板、写作规范、评审要点
- **需求理解**：分层字段（必填/选填/推断）+ 多轮对话澄清
- **高质量写作**：多 Agent 协作（提纲 → 草稿 → 审核 → 修订）
- **文件提取**：上传材料自动抽取字段并补充外部信息
- **可扩展**：支持学习新的文书类型并创建新 Skill

## 项目结构

```
skill-writer/
├── backend/
│   ├── core/
│   │   ├── skills/          # Skill 定义
│   │   │   ├── base.py      # Skill 基类
│   │   │   ├── registry.py  # Skill 注册表
│   │   │   └── loader.py    # 文件化 Skill 加载
│   │   ├── agents/          # Agent 实现
│   │   │   ├── base.py
│   │   │   ├── requirement_agent.py
│   │   │   ├── writer_agent.py
│   │   │   └── reviewer_agent.py
│   │   └── workflow/        # 工作流编排
│   │       ├── simple_workflow.py
│   │       └── state.py
│   ├── api/                 # FastAPI 路由
│   │   ├── main.py
│   │   └── routes/
│   ├── config.py            # 配置
│   └── requirements.txt
├── frontend/                # Vue3 前端
│   ├── src/
│   │   ├── views/
│   │   ├── api/
│   │   └── router/
│   └── package.json
├── backend/data/
│   └── skills/              # Skill 数据和范例
├── workflow_diagram.png     # 工作流图
└── workflow_design_philosophy.md
```

## 快速开始

### 1. 配置环境变量

```bash
cd backend
cp .env.example .env
# 编辑 .env 文件，填入 LLM API Key
```

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

### 4. 访问应用

打开浏览器访问 http://localhost:5173

## API 接口

### Skills API

- `GET /api/skills/` - 获取所有可用 Skill
- `GET /api/skills/{skill_id}` - 获取 Skill 详情
- `POST /api/skills/create-from-template` - 上传模板生成 Skill

### Chat API

- `POST /api/chat/start` - 创建会话
- `GET /api/chat/session/{session_id}/requirements` - 获取需求字段
- `PUT /api/chat/session/{session_id}/requirements` - 保存需求字段
- `POST /api/chat/session/{session_id}/upload-json` - 上传文件提取信息
- `POST /api/chat/session/{session_id}/start-generation` - 开始生成
- `GET /api/chat/generate/{session_id}/stream` - SSE 流式生成

### Documents API

- `GET /api/documents/` - 获取文档列表
- `POST /api/documents/` - 创建文档
- `GET /api/documents/{doc_id}` - 获取文档详情

## 添加新的 Skill

1. 在 `backend/data/skills/` 创建 Skill 目录
2. 添加 `SKILL.md` / `requirements.yaml` / `structure.yaml` / `guidelines.md`
3. 启动后会自动加载

```python
from backend.core.skills import BaseSkill, register_skill

@register_skill
class MyNewSkill(BaseSkill):
    @property
    def metadata(self):
        return SkillMetadata(
            id="my_skill",
            name="我的文书类型",
            ...
        )

    @property
    def structure_template(self):
        return [...]

    @property
    def requirement_fields(self):
        return [...]
```

## 架构说明

### Skill 系统

每个 Skill 定义了一种文书类型，包含：

- **元数据**：名称、描述、标签等
- **结构模板**：文书的章节结构
- **需求字段**：需要收集的用户信息
- **写作风格**：语言风格、禁忌词等

### Agent 系统

- **RequirementAgent**：通过对话收集用户需求
- **WriterAgent**：根据需求生成文档内
- **ReviewerAgent**：审核生成的内容质量

### 工作流

系统采用简化工作流（非 LangGraph），并支持流式 SSE：

```
start_session → collect_requirements → start_generation → outline → draft → review → revise → assemble → complete
```

## 技术栈

- **后端**：FastAPI, LangChain, OpenAI API
- **前端**：Vue 3, Tailwind CSS, Vite
- **状态管理**：Pinia
