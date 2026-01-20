# Skill Writer - 智能文书写作平台

一个基于 Skill 架构的智能文书生成系统，支持多种文书类型，可扩展学习新的文书格式。

## 核心特性

- **Skill 系统**：每种文书类型对应一个 Skill，包含结构模板、写作规范、评审要点
- **需求理解**：多轮对话澄清用户需求，确保准确把控意图
- **高质量写作**：多 Agent 协作（起草→审核→修改）
- **可扩展**：支持学习新的文书类型并创建新 Skill

## 项目结构

```
skill-writer/
├── backend/
│   ├── core/
│   │   ├── skills/          # Skill 定义
│   │   │   ├── base.py      # Skill 基类
│   │   │   ├── registry.py  # Skill 注册表
│   │   │   └── nsfc.py      # 国自然申报书 Skill
│   │   ├── agents/          # Agent 实现
│   │   │   ├── base.py
│   │   │   ├── requirement_agent.py
│   │   │   ├── writer_agent.py
│   │   │   └── reviewer_agent.py
│   │   └── workflow/        # 工作流编排
│   │       └── document_workflow.py
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
└── data/
    └── skills/              # Skill 数据和范例
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

### Chat API
- `POST /api/chat/` - 与写作助手对话
- `GET /api/chat/session/{session_id}` - 获取会话状态

### Documents API
- `GET /api/documents/` - 获取文档列表
- `POST /api/documents/` - 创建文档
- `GET /api/documents/{doc_id}` - 获取文档详情

## 添加新的 Skill

1. 在 `backend/core/skills/` 目录下创建新文件
2. 继承 `BaseSkill` 类并实现必要方法
3. 使用 `@register_skill` 装饰器注册

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
- **WriterAgent**：根据需求生成文档内容
- **ReviewerAgent**：审核生成的内容质量

### 工作流
使用 LangGraph 编排完整的文书生成流程：
```
初始化 → 需求收集 → 内容生成 → 审核 → 最终化
```

## 技术栈

- **后端**：FastAPI, LangGraph, LangChain, OpenAI API
- **前端**：Vue 3, Tailwind CSS, Vite
- **状态管理**：Pinia
