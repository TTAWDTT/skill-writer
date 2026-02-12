现在需要撰写 **"{{section_title}}"** 部分，用于支撑科研图示生成与图文一致性。

## 项目基础信息
- 项目名称：{{project_title}}
- 研究主题：{{research_theme}}
- 核心问题：{{core_problem}}
- 研究目标：{{research_objectives}}
- 任务包：{{work_packages}}
- 方法与技术：{{methods_and_tools}}
- 图示重点：{{diagram_focus}}
- 视觉偏好：{{visual_style}}
{% if figure_caption_notes %}
- 图注补充要求：{{figure_caption_notes}}
{% endif %}

{% if validation_plan %}
## 验证方案
{{validation_plan}}
{% endif %}

{% if expected_outputs %}
## 预期成果
{{expected_outputs}}
{% endif %}

## 本章节约束
- 章节说明：{{section_description}}
- 写作指导：{{section_writing_guide}}
- 字数限制：{{section_word_limit}}
- 评审要点：{{section_evaluation_points}}

{% if written_sections %}
## 已完成章节（保持一致）
{% for section_id, content in written_sections.items() %}
### {{section_id}}
{{content}}
{% endfor %}
{% endif %}

请直接输出章节正文。要求：
1) 给出明确的节点、步骤或模块；
2) 关系描述必须可被直接映射为图示连线；
3) 术语口径前后一致，不要同义词混写；
4) 不写与图示无关的背景扩展；
5) 不输出额外解释或免责声明。
