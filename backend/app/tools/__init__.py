"""工具注册中心：Agent 可调用的工具都在这里声明（JSON Schema + 实现）。"""

import json

from ..config import JOBS_JSON, QUESTIONS_JSON
from ..agent.rag import knowledge_base


def query_question(topic: str = "", level: str = "") -> str:
    """从面试题库按主题/难度抽题。"""
    try:
        bank = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return "题库暂不可用"
    items = bank
    if topic:
        items = [q for q in items if topic in q.get("topic", "")]
    if level:
        items = [q for q in items if level == q.get("level", "")]
    if not items:
        return "该主题下暂无题目，换个主题试试（如 python / database / network / ai）"
    return json.dumps(items[:5], ensure_ascii=False)


def query_job(city: str = "", direction: str = "") -> str:
    """查询实习岗位库（按城市/方向筛选）。"""
    try:
        jobs = json.loads(JOBS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return "岗位库暂不可用"
    items = jobs
    if city:
        items = [j for j in items if city in j.get("city", "")]
    if direction:
        items = [j for j in items if direction in j.get("direction", "")]
    if not items:
        return "没有匹配的岗位，换个关键词试试（如 广州 / AI / Python）"
    return json.dumps(items[:5], ensure_ascii=False)


def search_knowledge(query: str = "", k: int = 3) -> str:
    """检索面试知识库（RAG），返回相关章节原文。"""
    results = knowledge_base.search(query or "面试", k=int(k))
    if not results:
        return "知识库暂无相关内容"
    return json.dumps(results, ensure_ascii=False)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_question",
            "description": "从面试题库按主题/难度抽取面试题。主题可选：python/database/network/os/ai/algorithm。当用户要求出题、模拟面试、刷题时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "主题，如 python / database / network / os / ai"},
                    "level": {"type": "string", "description": "难度，如 基础 / 进阶"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_job",
            "description": "查询实习岗位库（按城市/方向筛选），如：广州的 AI 开发实习、Python 后端实习。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市，如 广州 / 深圳 / 远程"},
                    "direction": {"type": "string", "description": "方向，如 AI / Python / 后端"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "检索面试知识库（RAG），返回相关章节原文，用于讲解八股知识、查答案、复习考点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要检索的问题或知识点，如：MySQL索引原理"},
                    "k": {"type": "number", "description": "返回章节数量，默认 3"},
                },
                "required": ["query"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "query_question": query_question,
    "query_job": query_job,
    "search_knowledge": search_knowledge,
}
