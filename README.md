# 🎓 AI 面试备战助手

面向 AI 开发实习的多 Agent + RAG 面试陪练应用，包含 **完整面试闭环**：

- **自由对话**：主管 Agent 路由，三个专员（模拟面试官 / 八股讲师 / 求职顾问）协作，Function Calling 驱动工具调用，RAG 知识库提供有依据的回答
- **模拟面试**：面试官按方向出题（题库检索 + 大模型定制）→ 你逐题作答 → 面试官点评并深挖追问 → 结束整场评分
- **整场评分**：考核官基于完整问答生成结构化报告（总分 + 正确性/深度/结构/表达/风险意识 5 维度 + 亮点/不足/缺失关键点/改进建议）
- **历史对比**：与历史场次做维度级对比，输出进步项、退步项、稳定项、优先加强建议
- **面经复盘**：粘贴真实面试经历，AI 生成亮点、问题、必会知识点与行动清单
- **历史报告**：所有场次的评分与问答记录保存在本地 SQLite，随时回看

## 技术栈

- **Agent**：手写多 Agent Harness（主管路由 + 3 专员），通用 Function Calling 循环（AgentLoop），统一轨迹追踪；面试闭环为独立的状态机模块（InterviewManager：出题/点评追问/评分/对比/复盘，结构化 JSON 输出）
- **RAG**：Markdown 标题感知分块 + 检索；安装 `requirements-rag.txt` 后启用 **关键词 + 向量 RRF 混合检索**（FAISS + m3e，索引持久化 + 文档指纹重建），未安装时自动降级 jieba 关键词
- **后端**：SQLite（会话历史 + 面试场次/问答记录持久化，跨轮记忆回填）
- **LLM**：DeepSeek（OpenAI 兼容，流式输出）
- **前端**：Streamlit 界面（自由对话 / 模拟面试 / 面经复盘 / 历史报告）
- **测试与评估**：pytest（14 项）+ `scripts/eval_agent.py`（路由/工具/完整率）+ `scripts/eval_rag.py`（Recall@3/MRR）+ `scripts/eval_interview.py`（出题/点评/评分/复盘完整率）

## 快速开始

```bash
# 1. 配置 API Key
cp .env.example .env   # 填入 DEEPSEEK_API_KEY

# 2. 双击 start.command（自动建虚拟环境 + 安装依赖 + 打开网页）
# 或手动：
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run ui/app.py
```

打开 http://localhost:8501 即可使用。示例提问：

- 模拟一场 Python 后端面试
- 讲讲 RAG 的原理
- 广州有哪些 AI 开发实习

进入「模拟面试」模式可以体验完整面试闭环：选择方向与题量 → 逐题作答 → 点评追问 → 整场评分与历史对比。

## 可选：开启向量检索 RAG

```bash
.venv/bin/pip install -r requirements-rag.txt
```

首次运行会自动下载 m3e-base 并构建 FAISS 索引（需要网络），之后检索走「关键词 + 向量 RRF 混合召回」；未安装时自动用 jieba 关键词检索。

## 目录结构

```
backend/app/
├── agent/
│   ├── loop.py      # 通用 Agent 循环（Function Calling 引擎）
│   ├── roles.py     # 主管 + 3 专员提示词与工具子集
│   ├── harness.py   # 多 Agent 编排（主管路由 + 专员执行）
│   ├── memory.py    # 会话记忆（SQLite 回填）
│   └── rag.py       # RAG 检索（关键词/向量 RRF 混合，自动降级）
├── interview.py      # 面试闭环：出题/点评追问/整场评分/历史对比/面经复盘
├── interview_store.py# 面试场次与问答记录持久化
├── tools/           # 工具注册中心（题库/岗位库/知识库检索）
├── cards.py         # 工具结果 -> 前端卡片
└── db.py / chat_history.py  # SQLite 会话持久化
ui/app.py            # Streamlit 界面（自由对话 / 模拟面试 / 面经复盘 / 历史报告）
data/knowledge/      # 面试八股知识库（Python/数据库/网络/OS/AI/求职）
data/questions.json  # 面试题库（python/database/network/os/ai/algorithm/project）
data/jobs.json       # 实习岗位库
scripts/eval_agent.py / eval_rag.py / eval_interview.py  # 量化评估
tests/               # pytest（路由/专员/记忆/RAG/面试闭环）
```

## 架构一句话

自由对话：用户消息 → **主管 Agent**（意图路由）→ 指派 **模拟面试官 / 八股讲师 / 求职顾问** → 专员通过 **Function Calling** 调用工具（抽题 / 查岗位 / RAG 检索）→ 基于真实数据流式回答，全程轨迹可追溯。

模拟面试：**出题（题库 RAG + 大模型定制）** → **逐题作答 + 点评追问** → **考核 Agent 整场评分** → **历史对比 Agent 成长分析**，每个环节输出结构化 JSON，落库可回看。

## 面试怎么讲

- 为什么手写 Harness 不用 LangGraph：理解底层（tool_calls 解析、路由、记忆注入），避免框架黑盒
- RAG 混合检索：关键词 + 向量 RRF 融合，兼顾精确匹配与语义召回；评估指标 Recall@3 / MRR 可量化
- 多 Agent 权衡：职责清晰可扩展，代价是更多 LLM 调用与延迟，需要路由与稳定性设计
- 面试闭环设计：状态机管理流程（出题→作答→追问→评分），考核与面试解耦，历史对比让"训练效果"可感知
