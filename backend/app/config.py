"""全局配置：从 .env 读取，所有模块从这里拿配置。"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# 大模型
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Agent 单轮最大工具调用步数（防止死循环，可按需调大）
AGENT_MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", "6"))

# 多 Agent 编排引擎：
#   custom    = 自研主管路由（harness.py），默认，零额外依赖
#   langgraph = LangGraph 状态图（graph.py），需安装 langgraph
# 两种引擎的专员、工具、记忆、轨迹完全一致，差异只在编排层，可公平对比。
AGENT_ENGINE = os.getenv("AGENT_ENGINE", "custom").strip().lower()

# 长任务（完整模拟面试）开始前是否先中断确认。
# 关掉后 LangGraph 版退化成直接执行，方便对比「有无人工介入」的差异。
AGENT_CONFIRM_LONG_TASK = os.getenv("AGENT_CONFIRM_LONG_TASK", "true").strip().lower() in {
    "1", "true", "yes", "on",
}

# LangGraph 检查点库：记录每轮对话的图状态，支持断点续答与事后回放。
# 单独一个文件，避免和面试业务库争锁。
AGENT_CHECKPOINT_PATH = Path(
    os.getenv("AGENT_CHECKPOINT_PATH", str(PROJECT_ROOT / "data" / "agent_checkpoints.db"))
)

# 检索参数
RAG_CHUNK_MAX_CHARS = int(os.getenv("RAG_CHUNK_MAX_CHARS", "500"))
RAG_CHUNK_OVERLAP_CHARS = int(os.getenv("RAG_CHUNK_OVERLAP_CHARS", "80"))
RAG_RRF_K = int(os.getenv("RAG_RRF_K", "60"))

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
# 测试时指向临时库，避免把 mock 产生的调用记录写进开发库
DB_PATH = Path(os.getenv("INTERVIEW_DB_PATH", str(DATA_DIR / "interview.db")))
QUESTIONS_JSON = DATA_DIR / "questions.json"
JOBS_JSON = DATA_DIR / "jobs.json"
RAG_INDEX_DIR = DATA_DIR / "rag_index"


def ensure_dirs() -> None:
    for d in (DATA_DIR, KNOWLEDGE_DIR, RAG_INDEX_DIR):
        d.mkdir(parents=True, exist_ok=True)
