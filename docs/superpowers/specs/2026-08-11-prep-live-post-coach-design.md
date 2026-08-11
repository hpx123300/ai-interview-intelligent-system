# 面试备战助手 · Prep/Live/Post + 学习教练 改造设计

日期：2026-08-11
来源：借鉴 DeepInterview（Apache-2.0）与聆悟 ai-interview-platform（MIT）的架构与功能设计，
代码为本项目重写实现；README 中注明借鉴来源。

## 1. 借鉴点

### 1.1 DeepInterview（Apache-2.0）

- **prep / live / post 三段式**：面试前用"重推理"生成完整问题计划（难度曲线、评分标准、
  追问种子、考察能力），面试中保持轻量，面试后重推理生成报告与学习计划。
- **JD 与候选人画像分析**：JD → 结构化 JobSpec（title/must-have/nice-to-have/职责/技术栈）；
  候选人画像 × JD → GapAnalysis（优势/gaps/probe_targets/匹配与缺失技能）。
- **Rubric 评分**：每题按评分标准 0-5 打分并给证据；能力维度强制绑定题目的
  target_competency；level 由分数推导（>=4 strong / >=3 solid / >=2 developing / weak）；
  按能力合并平均；未作答的能力不计入总分（coverage_pct 校正）。
- **ScoreCard 报告**：总分、能力分、亮点/不足、weak_competencies、逐题改进版参考答案、
  next_steps、表达报告、总结。
- **Study Coach**：对每个弱能力生成 StudyModule（标题/理由/预计分钟），RAG 检索知识库
  作为学习材料，形成可执行学习计划。

### 1.2 聆悟 ai-interview-platform（MIT）

- **自然语言 → 完整面试设计**：一句话描述考察目标，生成标题/描述/目标/3-6 条评估维度/
  5-15 道题（含类型、追问种子、时限、必答标记）/推荐设置（模式、追问深度、AI 语气）。
- **统一评分标准**：1-10 分档 + 高质量答案五要素（直接扣题、STAR/PAR 结构、可核实细节、
  JD 关键词、自然语气）；参考答案按"应得 8-9 分"标准生成。
- **追问轮次控制**：follow-up 有明确轮次边界，避免无限追问。

## 2. 取舍（明确不做）

- 不做语音/视频面试（LiveKit、ASR/TTS 超出当前栈）；表达维度用文本评分替代。
- 不做公司调研（依赖外部搜索）；不做 CV 文件解析（支持粘贴简历文本）。
- 不换前端框架（保持 Streamlit）。

## 3. 变更清单

### 3.1 数据库迁移（db.py）

- `interview_qa` 新增列：difficulty(int)、competency(str)、rubric(JSON)、
  seed_followups(JSON)、answer_score(int, 0-5)。
- `interviews` 新增列：plan(JSON 问题计划)、prep(JSON：jd_analysis/gap/design)。
- `user_profiles` 新增列：jd_text、jd_analysis(JSON)、resume_text。
- 轻量迁移：`init_db` 后检查列是否存在，缺失则 ALTER TABLE ADD COLUMN。

### 3.2 prep 阶段（interview.py）

- `analyze_jd(jd_text)` → JobSpec。
- `gap_analysis(profile, job_spec)` → GapAnalysis。
- `design_interview(goal, jd_text, resume_text)` → 面试设计方案（聆悟式）。
- `generate_question_list(direction, count, profile, jd_analysis, gap)` 升级：
  每道题带 difficulty(1-5)、target_competency、rubric(1-3 条，权重和≈1)、followups 种子；
  注入 JD 考察点与 gap 的 probe_targets；题库兜底时按 level 推导 difficulty、按 hint
  生成默认 rubric。
- 新增 `data/packs/`：岗位问题包（round structure / question bank / signals / pitfalls），
  出题时注入（DeepInterview playbook 的简化版）。

### 3.3 live 阶段

- `feedback_and_followup` 增加 `score`（0-5）与 `score_evidence`，落库。
- 题目卡片展示难度、考察能力、rubric 与预埋追问。

### 3.4 post 阶段

- `score_answer`：逐题 rubric 评分（0-5 + level + evidence）。
- `evaluate_interview` 升级为 ScoreCard：保留 total_score/dimensions 兼容旧报告，新增
  competency_scores、weak_competencies、model_answers、next_steps、summary、coverage_pct、
  language_report（表达维度）。
- `reference_answer` 升级：按"8-9 分参考答案"标准生成（结论→展开→例子→风险点）。
- `coach_plan(report)`：对弱能力生成 StudyModule + RAG 学习材料。

### 3.5 内容

- 题库新增 behavior 主题（8 道 STAR 行为题）。
- 面试方向新增「行为面试（STAR）」。
- 新增岗位问题包 2 份（大模型应用开发实习 / Python 后端实习）。

### 3.6 UI（ui/app.py）

- 「我的档案」：目标 JD 粘贴 + 一键分析（展示岗位画像与 gap）+ 简历文本。
- 「模拟面试」：展示 JD 画像摘要；新增"自定义面试设计"（目标描述 → 设计方案 → 直接开面）。
- 面试中：难度/考察能力/rubric/预埋追问展示；点评带 0-5 分。
- 报告页：ScoreCard 新字段 + 学习教练区块（modules + 知识库来源）。
- 作战室：待办清单聚合 next_steps 与 coach modules。

### 3.7 测试与文档

- 新增测试：analyze_jd/gap/design 解析、plan 含 rubric、score_answer level 推导、
  evaluate 兼容旧字段、coach_plan 含模块、DB 迁移幂等。
- README 与面试讲稿更新，注明借鉴 DeepInterview / 聆悟（Apache-2.0 / MIT）。

## 4. 范围外（三期）

- 语音面试、CV 文件解析、公司调研、多模型切换。
