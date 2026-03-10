# AGENT.md

## 项目定位

这是一个“基于 Skill 的智能文书写作平台”，核心目标不是单纯做模板填空，而是把以下流程串成一个完整会话：

1. 选择写作 Skill
2. 创建会话
3. 收集或编辑需求字段
4. 上传材料并抽取信息
5. 生成会话级三元研究指南
6. 按章节执行 outline -> draft -> review -> revise
7. 对全文做后处理润色
8. 保存、导出、继续补图

这个仓库的真实业务中心是“会话驱动的写作编排”，不是普通 CRUD。

## 技术栈

- 后端：Python、FastAPI、SQLAlchemy、Pydantic Settings
- 前端：Vue 3、Vue Router、Axios、Tailwind CSS、Vite
- 持久化：SQLite
- 模型接入：OpenAI-compatible、Gemini、GitHub Device Flow / Copilot 相关配置

## 目录速览

- `backend/`：后端 API、工作流、Skill 系统、LLM 配置、数据库模型
- `frontend/`：前端页面、路由、API 封装、写作工作台
- `docs/`：审计文档与说明
- `scientific-schematics/`：科研图示相关资源
- `artifacts/`：生成产物
- `run.py`：后端开发启动脚本

## 最重要的文件

- 后端入口：`backend/api/main.py`
- 主工作流：`backend/core/workflow/simple_workflow.py`
- 会话状态：`backend/core/workflow/state.py`
- Session 持久化：`backend/models/session_store.py`
- 数据库模型：`backend/models/database.py`
- Skill 注册与加载：`backend/core/skills/registry.py`、`backend/core/skills/loader.py`
- Chat 路由：`backend/api/routes/chat.py`
- Documents 路由：`backend/api/routes/documents.py`
- Sessions 路由：`backend/api/routes/sessions.py`
- Config 路由：`backend/api/routes/config.py`
- 前端 API 封装：`frontend/src/api/index.js`
- 前端路由：`frontend/src/router/index.js`
- 写作主页面：`frontend/src/views/Write.vue`
- 设置页面：`frontend/src/views/Settings.vue`
- 首页：`frontend/src/views/Home.vue`

## 内置 Skills

当前 `backend/data/skills/` 下可见的内置目录包括：

- `base_writing`
- `nsfc_general`
- `scientific-infographic-codegen`
- `scientific-schematics`
- `session_triadic_guideline`
- `tongji-journal-paper-template`
- `writer_skill_creator`

注意：

- 并不是所有 Skill 都会展示在首页
- 有些是系统 Skill，只用于内部流程

### Skill 分层

当前系统已经开始按职责区分 Skill：

- `document`
  - 真正面向用户写作的文书 Skill
- `meta_writing`
  - 全局元写作规范，当前代表是 `base_writing`
- `skill_generator`
  - 用于“从模板学习并生成新 Skill”的生成器 Skill
- `workflow_helper`
  - 服务工作流中间步骤的系统 Skill，例如会话级 guideline、图示辅助能力

当前约束：

- 首页技能列表只展示 `document` 且 `user_invocable = true` 的 Skill
- `base_writing` 只会自动增强 `document` Skill
- `workflow_helper` 和 `skill_generator` 不再被当成普通文书 Skill 对待

## 真实后端流程

不要只看 README。当前真实流程以 `backend/core/workflow/simple_workflow.py` 和 `backend/api/routes/chat.py` 为准。

### Session phase

当前会话阶段至少包括：

- `init`
- `requirement`
- `guideline`
- `writing`
- `complete`
- `error`

### 写作主链路

典型顺序如下：

1. `POST /api/chat/start`
2. 会话进入 `requirement`
3. 用户通过对话或表单更新 `requirements`
4. 上传材料并抽取字段、补充 `external_information`
5. 生成 `skill_overlay`
6. 在开始写作前，强制生成 `session_guideline`
7. 会话进入 `writing`
8. 每个 section 执行：
   - outline
   - draft
   - review
   - revise（必要时）
9. 全文交给 `DocumentPolisherAgent` 做后处理
10. 会话进入 `complete`

### 并行草稿

工作流支持并行预生成草稿，受以下环境变量控制：

- `WRITER_PARALLEL_DRAFT`
- `WRITER_PARALLEL_DRAFT_CONCURRENCY`

## 前端真实行为

主交互页面在 `frontend/src/views/Write.vue`。

需要记住的事实：

- 当前前端是 `Vite + Vue 3 + Vue Router + Tailwind`，不是 Astro
- 进入 `/write/:skillId` 时，前端会自动创建 session
- 刷新 `/write/:skillId` 通常会得到一个新的 session，不要默认会续接旧会话
- 前端会在 `localStorage` 里生成并保存 token
- 所有普通 API 请求都会自动带 `Authorization: Bearer <token>`
- SSE 流式生成走 query token：
  `/api/chat/generate/:session_id/stream?access_token=...`
- 上传优先走 multipart；只有 multipart 路由不可用时才回退 JSON 上传
- 上传区、Skill-Fixer、三元指南、Web 搜索、图示、文档预览都集中在一个页面
- `/write/*` 在 `frontend/src/App.vue` 中有专门的宽屏双栏布局逻辑
- 虽然依赖里有 Pinia，但当前主要业务状态基本都堆在各个 view，尤其是 `Write.vue`

## 鉴权与所有权

受保护接口依赖 Bearer Token，逻辑在 `backend/api/security.py`。

这意味着：

- 没有 token 或 token 太短会直接 `401`
- Session 和 Document 都绑定 `owner_token`
- 一些旧数据可能没有 owner，会在首次合法访问时被“认领”
- 手工调接口时，必须在同一条流程里持续使用同一个 token，否则容易出现 403 / 404 / 空数据

## 数据存储事实

Session 不是纯内存态，默认会落到 SQLite。

数据库位置默认在：

- `backend/data/skill_writer.db`

其他重要持久化文件：

- `backend/data/llm_config.json`
- `backend/data/models.json`

Session 中的重要字段包括：

- `requirement_state`
- `requirements`
- `writing_state`
- `sections`
- `review_results`
- `messages`
- `uploaded_files`
- `external_information`
- `skill_overlay`
- `session_guideline`
- `diagrams`
- `final_document`
- `error`

Document 单独建表，并可通过 `session_id` 回连到原始会话。

注意：

- 主生成链路默认把结果写回 `sessions.final_document`
- `documents` 表更像“文档管理/导出层”，不是唯一真实写作状态源

## Skill 系统说明

Skill 是整个项目的蓝图来源。

一个 Skill 通常决定：

- 文书元数据
- requirement fields
- section 结构
- 写作规范
- 评审标准
- system / section prompt

如果要新增 Skill，通常要同时关注：

- `backend/data/skills/<skill_id>/`
- `backend/core/skills/loader.py`
- `backend/core/skills/registry.py`
- `backend/api/routes/skills.py`

注意：

- `skill_overlay` 是“会话级覆盖层”，不应该反向修改原始 Skill 文件
- “从模板生成新 Skill”与“全局元规则 base_writing”是两层能力，不应混为同一对象

## LLM 与配置

模型配置相关逻辑主要在：

- `backend/config.py`
- `backend/api/routes/config.py`
- `backend/core/llm/config_store.py`
- `backend/core/llm/providers.py`
- `frontend/src/views/Settings.vue`

要点：

- 大部分写作接口在模型未配置时会拒绝执行
- 设置页支持 provider preset、自定义 base URL、自定义模型名
- GitHub Device Flow 已接入
- 图示/配图功能依赖 image model 字段，未配置时相关功能会失败
- DeepSeek 这类 OpenAI-compatible 提供商的 `base_url` 需要包含 `/v1`
- 虽然后端会在配置更新后重置 LLM client，但长生命周期 agent 可能仍缓存旧 provider，遇到“切换模型后表现不一致”时优先考虑重启后端进程

## 开发启动方式

### 后端

在仓库根目录：

```powershell
python run.py
```

或手动：

```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```powershell
cd frontend
npm install
npm run dev
```

Vite 默认把 `/api` 代理到 `http://localhost:8000`。

## 验证修改时的建议路径

仓库里当前看不到清晰的一手自动化测试体系。不要把 `frontend/node_modules/` 里的依赖测试误判为项目测试。

对大多数修改，建议用以下人工冒烟流程：

1. 启动后端
2. 启动前端
3. 打开首页，确认 Skill 列表能加载
4. 进入任意 Skill 的写作页
5. 确认 session 自动创建成功
6. 视改动范围验证：
   - requirements 编辑
   - 文件上传
   - start-generation
   - SSE 生成
   - 文档保存
   - 导出
   - 设置页模型配置

如果改的是后端接口，建议再用同一个 Bearer Token 手工调用一轮关键接口。

## 高风险/高耦合点

- `backend/api/routes/chat.py` 文件很大，职责很多，改动前一定要局部定位清楚
- 上传能力受 phase 限制，默认只允许在 `requirement` 阶段
- `session_guideline` 在当前实现中是开始写作前的强制步骤
- 前端很多行为依赖后端返回字段名，轻易改 response shape 会引发隐性联调问题
- `documents.py` 里包含 Markdown / DOCX / PDF 三种导出逻辑，且带图片处理
- 数据库“迁移”是手写在 `_ensure_session_columns()` 里的，不是 Alembic 之类标准迁移体系

## 常见踩坑

- README 是有帮助的，但不是唯一真相，尤其在 guideline、diagram、session ownership 这些地方
- 如果你只改前端不看工作流，很容易误判某个按钮为什么不能用
- 如果你只改工作流不看前端，很容易漏掉已有字段依赖
- 不要先入为主地去找 Pinia store；当前前端主状态并不依赖它
- 如果你新增 Session 字段但没同步更新序列化 / 反序列化，数据会表面成功、实际丢失
- 如果你修改上传逻辑，必须同时考虑 multipart 和 JSON fallback
- 如果你手工调 SSE 却没带 query token，会误以为流接口坏了

## 新增字段时必须一起改的地方

如果新增 Session 或 Document 字段，通常要同步更新：

1. `backend/models/database.py` 中的 SQLAlchemy model
2. `_ensure_session_columns()` 的兼容补列逻辑
3. `backend/models/session_store.py` 的读写序列化
4. 相关 API 的返回结构
5. 如果前端展示该字段，还要改对应页面读取逻辑

## 建议阅读顺序

新代理进入仓库后，建议按这个顺序理解项目：

1. `README.md`
2. `backend/api/main.py`
3. `backend/core/workflow/simple_workflow.py`
4. `backend/api/routes/chat.py`
5. `backend/models/database.py`
6. `backend/models/session_store.py`
7. `frontend/src/api/index.js`
8. `frontend/src/views/Write.vue`
9. `frontend/src/views/Settings.vue`

## 给后续代理的工作建议

修改任何“生成链路”前，先确认自己改动的是哪一层：

- Skill 定义层
- Session 状态层
- Workflow 编排层
- Route 接口层
- Frontend 交互层

这个项目很多功能是跨层联动的。只改一个文件往往不够。

优先遵循以下原则：

1. 先读 workflow 再改 route
2. 先看前端依赖再改后端 response
3. 保持 `owner_token` 语义稳定
4. 保持 Session 字段 JSON 可序列化
5. 改 Skill 格式时至少跑通一次端到端 session

## 一句话总结

这是一个“以 Session 为核心、以 Skill 为蓝图、以多阶段 Agent 写作为主链路”的研究文书生成系统。凡是看起来像小改动的地方，都可能实际牵动上传、guideline、写作、保存、导出和前端联调。
