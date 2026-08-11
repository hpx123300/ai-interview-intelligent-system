# AI 面试智能系统 · 焕新改造设计（方案 A）

日期：2026-08-11
状态：已确认（方案 A）
目标岗位画像：大模型 / AI 应用开发实习为主，Python 后端为辅

## 1. 背景与问题

项目已有完整骨架：手写多 Agent Harness（主管路由 + 三个专员）、Function Calling
循环、RAG（关键词 + FAISS/m3e 向量 RRF 混合）、面试闭环状态机、SQLite 持久化、
Streamlit 前端、14 项测试。核心问题：

1. 内容太薄：知识库 6 个文件共 129 行；题库 49 道；岗位库 6 条，撑不起"备战"。
2. 面试不"认人"：出题与候选人真实项目无关，无法深挖项目经历。
3. 性能 bug：`rag.py::_vector_search` 每次检索都重新实例化 embedding 模型，向量检索
   开启后每次问答明显卡顿。
4. 缺作品感：面经复盘不落库、无成长趋势、README 只有功能罗列，没有"面试怎么讲"。

## 2. 设计目标

- 把通用面试工具变成"为候选人（大模型/AI 应用开发方向）定制的面试陪练"。
- 面试内容可个性化：结合候选人真实项目（投满分 BERT 分类、LangChain 本地知识库问答、
  AI 智慧交通、人脸支付等）生成项目深挖题，并输出 STAR 讲述模板。
- 数据可量化：知识库 / 题库 / 岗位库扩容；面试报告、复盘记录落库；成长趋势可视化。
- 工程可讲：修复 RAG 性能 bug，补充 LLM 调用重试，测试覆盖新增能力。

## 3. 变更清单

### 3.1 个人档案（Profile）

- 新增 `backend/app/profile.py`：ProfileStore（基于 SQLite）、默认档案、档案上下文文本。
- 新增数据库表 `user_profiles`：profile_key / target_role / target_direction /
  skills(JSON) / weak_areas(JSON) / projects(JSON) / updated_at。
- 档案结构（projects 数组元素）：
  `{name, tech_stack, description, highlights, metrics, story}`。
- UI 新增「我的档案」页：目标岗位、技能栈、薄弱点、最多 3 个项目（名称/技术栈/描述/
  亮点/量化成果/深挖点）。

### 3.2 个性化出题与专员注入

- `InterviewManager.generate_question_list(direction, count, profile=None)`：
  常规题 + 项目深挖题（约 30%，至少 1 道）。项目题优先 LLM 定制，失败回退模板题
  （"介绍一下你的项目 X / 你在里面解决的最大难点 / 为什么选这个技术栈"）。
- `MultiAgentHarness` 初始化时加载档案，把档案摘要注入模拟面试官与求职顾问的
  system prompt，自由对话中也能基于真实项目提问与给建议。
- 模拟面试开始前展示"已为你定制：含项目深挖 N 题"。

### 3.3 内容翻新

- 知识库扩至 8 个文件（约 400 行）：python_basics / database / network / os /
  ai_agent（含 RAG、Function Calling、Agent 架构、评估）/ interview_guide /
  新增 project_deep_dive.md（项目深挖高频问题）/ 新增 career_plan.md（求职规划）。
- 题库从 49 道扩至约 90 道，重点补 ai / agent / rag / project / algorithm 方向，
  保持 topic/level/hint/answer 结构。
- 岗位库从 6 条扩至约 16 条，覆盖广州/深圳/北京/上海/杭州/远程，标注 direction 便于
  过滤，补充"大模型"方向关键词。

### 3.4 面经复盘落库与求职作战室

- 新增 `backend/app/review_store.py` 与数据库表 `interview_reviews`（原文、摘要、
  亮点/问题/知识点/行动计划 JSON、时间）。
- UI 新增「求职作战室」页：
  - 概览卡片：完成场次、平均分、最高分、最近一次得分；
  - 得分趋势折线图（st.line_chart）；
  - 薄弱维度排行（按历次报告维度均分最低 3 项）；
  - 待办清单：聚合最近报告建议 + 复盘行动计划，checkbox 勾选；
  - 历史复盘列表：查看与删除。
- 「面经复盘」页生成结果后自动落库。

### 3.5 工程修复

- RAG：模块级缓存 embedding 模型单例，`_load_vector_index` 与 `_vector_search` 共用；
  消除每次查询重复加载模型的问题。
- LLM：新增轻量重试工具（3 次，指数退避），用于 AgentLoop、RouterAgent、
  InterviewManager 的 API 调用。

### 3.6 作品化

- 重写 README：一句话定位、架构图（mermaid）、量化指标表、升级后的"面试怎么讲"
  话术（为什么手写 Harness、RRF 混合检索、评估指标、档案驱动出题）。
- 新增 `docs/interview_script.md`：项目讲稿（STAR + 技术决策 + 踩坑 + 追问应对）。

## 4. 测试计划

- `tests/test_profile.py`：默认档案、保存/加载回读、上下文文本包含项目名。
- `tests/test_review_store.py`：复盘 CRUD。
- `tests/test_interview.py`：带档案出题时返回 project 题（LLM 失败回退模板路径）。
- 既有 14 项测试保持通过；最终 `pytest` 全绿。

## 5. 范围外（二期）

- 全栈化（FastAPI + 独立前端）
- 多角色/多题库可配置平台化
- 语音面试、多模型切换
