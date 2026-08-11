# 🎓 AI 面试备战助手

面向 AI 开发实习的多 Agent + RAG 面试陪练应用：主管 Agent 路由，三个专员（模拟面试官 / 八股讲师 / 求职顾问）协作，Function Calling 驱动工具调用，RAG 知识库提供有依据的回答。

## 技术栈

- **Agent**：手写多 Agent Harness（主管路由 + 3 专员），通用 Function Calling 循环（AgentLoop），统一轨迹追踪
- **RAG**：Markdown 标题感知分块 + 检索（默认 jieba 关键词；安装 `requirements-rag.txt` 后自动启用 FAISS + m3e 向量检索，索引持久化 + 文档指纹重建）
- **后端**：SQLite（会话历史持久化，跨轮记忆回填）
- **LLM**：DeepSeek（OpenAI 兼容，流式输出）
- **前端**：Streamlit 聊天界面（消息卡片 + 服务明细）
- **测试与评估**：pytest + `scripts/eval_agent.py`（路由/工具/完整率）+ `scripts/eval_rag.py`（Recall@3/MRR）

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

打开 http://localhost:8501 即可对话。示例提问：

- 模拟一场 Python 后端面试
- 讲讲 RAG 的原理
- 广州有哪些 AI 开发实习

## 可选：开启向量检索 RAG

```bash
.venv/bin/pip install -r requirements-rag.txt
```

首次运行会自动下载 m3e-base 并构建 FAISS 索引（需要网络），之后检索走向量召回；未安装时自动用 jieba 关键词检索。

## 目录结构

```
backend/app/
├── agent/
│   ├── loop.py      # 通用 Agent 循环（Function Calling 引擎）
│   ├── roles.py     # 主管 + 3 专员提示词与工具子集
│   ├── harness.py   # 多 Agent 编排（主管路由 + 专员执行）
│   ├── memory.py    # 会话记忆（SQLite 回填）
│   └── rag.py       # RAG 检索（向量/关键词双模式）
├── tools/           # 工具注册中心（题库/岗位库/知识库检索）
├── cards.py         # 工具结果 -> 前端卡片
└── db.py / chat_history.py  # SQLite 会话持久化
ui/app.py            # Streamlit 聊天界面
data/knowledge/      # 面试八股知识库（Python/数据库/网络/OS/AI/求职）
data/questions.json  # 面试题库
data/jobs.json       # 实习岗位库
scripts/eval_agent.py / eval_rag.py  # 量化评估
tests/               # pytest（路由/专员/记忆/RAG）
```

## 架构一句话

用户消息 → **主管 Agent**（意图路由）→ 指派 **模拟面试官 / 八股讲师 / 求职顾问** → 专员通过 **Function Calling** 调用工具（抽题 / 查岗位 / RAG 检索）→ 基于真实数据流式回答，全程轨迹可追溯。

## 面试怎么讲

- 为什么手写 Harness 不用 LangGraph：理解底层（tool_calls 解析、路由、记忆注入），避免框架黑盒
- RAG 双模式：向量缺失自动降级关键词，工程容错；评估指标 Recall@3 / MRR 可量化
- 多 Agent 权衡：职责清晰可扩展，代价是更多 LLM 调用与延迟，需要路由与稳定性设计
