"""RAG 检索质量评测：验证检索器能否把问题召回正确的来源文档。

用法：python scripts/eval_rag.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agent.rag import knowledge_base

EVAL_SET = [
    ("什么是 GIL", "python_basics.md"),
    ("装饰器怎么用", "python_basics.md"),
    ("深浅拷贝的区别", "python_basics.md"),
    ("MySQL 索引原理", "database.md"),
    ("事务 ACID", "database.md"),
    ("隔离级别有哪些", "database.md"),
    ("TCP 三次握手", "network.md"),
    ("HTTPS 原理", "network.md"),
    ("死锁怎么避免", "os.md"),
    ("进程线程协程", "os.md"),
    ("Function Calling 是什么", "ai_agent.md"),
    ("RAG 流程", "ai_agent.md"),
    ("多 Agent 优缺点", "ai_agent.md"),
    ("简历怎么写", "interview_guide.md"),
]


def run_eval() -> dict:
    hits = 0
    rr_sum = 0.0
    details = []
    for question, expected_source in EVAL_SET:
        results = knowledge_base.search(question, k=3)
        sources = [r["source"] for r in results]
        hit = expected_source in sources
        hits += hit
        rr = 0.0
        for rank, src in enumerate(sources, 1):
            if src == expected_source:
                rr = 1.0 / rank
                break
        rr_sum += rr
        details.append((question, expected_source, sources, hit))
    n = len(EVAL_SET)
    summary = {
        "recall@3": round(hits / n, 3),
        "mrr": round(rr_sum / n, 3),
    }
    for q, exp, got, hit in details:
        print(f"{'✓' if hit else '✗'} {q[:18]:<20} 期望={exp:<20} 实际={got[:2]}")
    print("\nRecall@3:", summary["recall@3"], "| MRR:", summary["mrr"])
    return summary


if __name__ == "__main__":
    run_eval()
