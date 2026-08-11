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

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
DB_PATH = DATA_DIR / "interview.db"
QUESTIONS_JSON = DATA_DIR / "questions.json"
JOBS_JSON = DATA_DIR / "jobs.json"
RAG_INDEX_DIR = DATA_DIR / "rag_index"


def ensure_dirs() -> None:
    for d in (DATA_DIR, KNOWLEDGE_DIR, RAG_INDEX_DIR):
        d.mkdir(parents=True, exist_ok=True)
