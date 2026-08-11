"""多 Agent 编排评测：路由准确率 / 工具准确率 / 回答完整率。

用法：python scripts/eval_agent.py
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agent.harness import MultiAgentHarness
from backend.app.agent.memory import Memory

# (问题, 期望专员或 None(直接回复), 期望工具集)
EVAL_SET = [
    ("模拟一场 Python 后端面试", "interviewer", ["query_question"]),
    ("出一道数据库的题", "interviewer", ["query_question"]),
    ("出几道 AI 相关的面试题", "interviewer", ["query_question"]),
    ("我答完了，帮我点评一下", "interviewer", []),
    ("什么是 GIL", "tutor", ["search_knowledge"]),
    ("讲讲 RAG 的原理", "tutor", ["search_knowledge"]),
    ("MySQL 索引为什么用 B+ 树", "tutor", ["search_knowledge"]),
    ("HTTP 和 HTTPS 的区别", "tutor", ["search_knowledge"]),
    ("死锁怎么避免", "tutor", ["search_knowledge"]),
    ("广州有哪些 AI 开发实习", "career", ["query_job"]),
    ("深圳的 Python 岗位", "career", ["query_job"]),
    ("简历怎么写", "career", ["search_knowledge"]),
    ("自我介绍怎么讲", "career", ["search_knowledge"]),
    ("你好", None, []),
    ("谢谢", None, []),
    ("再见", None, []),
]

LABEL_TO_AGENT = {"模拟面试官": "interviewer", "八股讲师": "tutor", "求职顾问": "career"}


def route_label(trace: list[dict]) -> str | None:
    for t in trace:
        if t["step"] == "think" and "指派给" in t["content"]:
            m = re.search(r"「(.+?)」", t["content"])
            if m:
                return m.group(1)
    return None


def tool_names(trace: list[dict]) -> list[str]:
    names = []
    for t in trace:
        if t["step"] == "tool":
            m = re.match(r"([a-z_]+)\(", t["content"])
            if m:
                names.append(m.group(1))
    return names


def run_eval() -> dict:
    route_hits = tool_hits = complete_hits = 0
    n = len(EVAL_SET)
    print(f"{'问题':<20}{'期望':<10}{'实际':<10}{'路由':<4}{'工具':<20}{'完':<3}")
    for i, (question, expected_agent, expected_tools) in enumerate(EVAL_SET):
        harness = MultiAgentHarness(memory=Memory(f"eval_agent_{i}", max_messages=20))
        reply, trace = harness.chat(question)
        label = route_label(trace)
        actual_agent = LABEL_TO_AGENT.get(label) if label else None
        actual_tools = tool_names(trace)
        route_ok = actual_agent == expected_agent
        tool_ok = all(t in actual_tools for t in expected_tools)
        complete_ok = bool(reply and reply.strip())
        route_hits += route_ok
        tool_hits += tool_ok
        complete_hits += complete_ok
        print(
            f"{question[:18]:<20}{(expected_agent or '直接回复'):<10}{(actual_agent or '直接回复'):<10}"
            f"{'✓' if route_ok else '✗':<4}{','.join(actual_tools)[:18]:<20}{'✓' if complete_ok else '✗':<3}"
        )
    summary = {
        "route_accuracy": round(route_hits / n, 3),
        "tool_accuracy": round(tool_hits / n, 3),
        "completion_rate": round(complete_hits / n, 3),
    }
    print("\n路由准确率:", summary["route_accuracy"], "| 工具准确率:", summary["tool_accuracy"], "| 回答完整率:", summary["completion_rate"])
    return summary


if __name__ == "__main__":
    run_eval()
