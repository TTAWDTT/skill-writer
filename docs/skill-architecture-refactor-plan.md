# Skill Architecture Refactor Plan

## 目标

本轮改造不推翻现有 Skill 驱动方向，只做“边界澄清 + 关键缺陷修复”，让系统更接近以下分层：

1. `Meta Skill`
   - 例：`base_writing`
   - 职责：承载全局写作规则

2. `Skill Generator`
   - 例：`writer_skill_creator`
   - 职责：从模板学习并生成新的具体 Skill

3. `Concrete Document Skill`
   - 例：`nsfc_general`、`tongji-journal-paper-template`
   - 职责：定义具体文书的字段、结构、提示词与评审标准

4. `Workflow Helper Skill`
   - 例：`session_triadic_guideline`、图示相关系统 Skill
   - 职责：服务工作流中的特定中间步骤，不直接作为文书 Skill 出现

5. `Session Overlay`
   - 职责：会话态补丁，不回写原始 Skill

## 拆分为 3 个 PR

### PR1: Introduce Skill Roles

目标：

- 给 Skill 元数据加入角色字段
- 区分 document / meta_writing / workflow_helper / skill_generator
- 只让 document skill 出现在普通技能列表中
- 只让 document skill 继承 `base_writing`
- 减少硬编码 ID 过滤

主要改动：

- `backend/core/skills/base.py`
- `backend/core/skills/loader.py`
- `backend/core/skills/registry.py`
- `backend/api/routes/skills.py`
- `frontend/src/views/Home.vue`
- `frontend/src/views/SkillDetail.vue`
- 各内置 Skill frontmatter / yaml 元数据

验收标准：

- 首页只展示真正可写作文书的 Skill
- `base_writing` / `session_triadic_guideline` / `writer_skill_creator` 不再依赖硬编码隐藏
- `base_writing` 不再自动包裹系统辅助类 Skill

建议提交信息：

- `refactor(skills): introduce explicit skill roles`

建议 PR 标题：

- `PR1: Introduce explicit skill roles and system skill boundaries`

### PR2: Make Skill Generation Explicit and Validated

目标：

- 强化“模板生成 Skill”这条链路
- 让 `writer_skill_creator` 真正成为 Skill Generator 的配置来源之一
- 为模板生成出来的 Skill 增加结构校验
- 让新 Skill 默认以 `document` 角色写入

主要改动：

- `backend/core/skills/skill_generator.py`
- `backend/core/skills/validator.py`（新增）
- `backend/api/routes/skills.py`

验收标准：

- 模板生成 Skill 前会做结构化校验
- skill_id / section id / field id 冲突等问题能被提前发现
- Skill Generator 的系统提示不再完全靠硬编码常量

建议提交信息：

- `feat(skills): validate generated skill definitions`

建议 PR 标题：

- `PR2: Separate skill generation concerns and validate generated skills`

### PR3: Fix Agent LLM Client Refresh and Update Docs

目标：

- 修复 Agent 长生命周期缓存旧模型配置的问题
- 让配置切换后的 Agent 行为更可预期
- 更新项目文档，说明新的 Skill 分层

主要改动：

- `backend/core/agents/base.py`
- `AGENT.md`
- 本文档

验收标准：

- 修改 LLM 配置后，新请求会按新配置重新初始化 agent client
- 文档能清楚说明 Skill 分层与当前系统边界

建议提交信息：

- `fix(agent): refresh llm client when config changes`

建议 PR 标题：

- `PR3: Refresh agent LLM clients on config changes`

## 风险说明

- 本轮不直接重写 workflow；只先把 Skill 语义和关键缓存问题理顺
- `session_overlay` 仍保留当前 wrapper 方案，但会在文档中明确它不是 Skill 本体
- 由于当前环境无法执行外部 `git.exe/gh.exe`，本轮只能按 PR 颗粒度完成代码与文档，实际 commit / push / PR 创建需在可用 git 环境中执行

## 后续建议

如果这 3 个 PR 稳定后，下一阶段可以考虑：

1. 抽离 `WorkflowPlaybook`
2. 给 Skill 增加更强的 schema/lint 体系
3. 给生成内容增加来源标记与审计链
