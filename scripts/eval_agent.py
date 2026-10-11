"""多 Agent 编排评测：路由准确率 / 工具准确率 / 回答完整率。

指标口径（务必明确）：
- 评测集：50 道题，覆盖 4 类意图（interviewer / tutor / career / 直接回复）；
- 路由准确率：主管 Agent 指派的专员与期望一致的比例；
- 工具准确率：期望工具全部出现在实际调用中的比例；
- 回答完整率：回复非空的比例。

注意：本脚本会真实调用大模型 API，需要 .env 中配置 DEEPSEEK_API_KEY。

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
    # ---- interviewer：出题 / 模拟面试 / 点评作答 ----
    ("模拟一场 Python 后端面试", "interviewer", ["query_question"]),
    ("出一道数据库的题", "interviewer", ["query_question"]),
    ("出几道 AI 相关的面试题", "interviewer", ["query_question"]),
    ("来一道网络方面的题", "interviewer", ["query_question"]),
    ("考我一道操作系统的题", "interviewer", ["query_question"]),
    ("我想练一下 MySQL 面试", "interviewer", []),
    ("给我来一道算法题", "interviewer", []),
    ("模拟一次 AI 应用开发岗的面试", "interviewer", []),
    ("我答完了，帮我点评一下", "interviewer", []),
    ("刚才那题我答得怎么样", "interviewer", []),
    ("这题我答对了吗", "interviewer", []),
    ("继续下一题", "interviewer", []),
    ("面试可以开始了吗", "interviewer", []),
    ("帮我按真实面试的节奏来", "interviewer", []),
    # ---- tutor：知识点讲解 / 八股 ----
    ("什么是 GIL", "tutor", ["search_knowledge"]),
    ("讲讲 RAG 的原理", "tutor", ["search_knowledge"]),
    ("MySQL 索引为什么用 B+ 树", "tutor", ["search_knowledge"]),
    ("HTTP 和 HTTPS 的区别", "tutor", ["search_knowledge"]),
    ("死锁怎么避免", "tutor", ["search_knowledge"]),
    ("装饰器是什么", "tutor", ["search_knowledge"]),
    ("深浅拷贝有什么区别", "tutor", ["search_knowledge"]),
    ("TCP 三次握手的过程", "tutor", ["search_knowledge"]),
    ("事务的 ACID 是什么", "tutor", ["search_knowledge"]),
    ("缓存穿透、击穿、雪崩分别是什么", "tutor", ["search_knowledge"]),
    ("Function Calling 是什么", "tutor", ["search_knowledge"]),
    ("多 Agent 架构有什么优缺点", "tutor", ["search_knowledge"]),
    ("进程和线程有什么区别", "tutor", ["search_knowledge"]),
    ("大模型的幻觉怎么缓解", "tutor", ["search_knowledge"]),
    ("讲一下 MVCC 的原理", "tutor", ["search_knowledge"]),
    ("IO 多路复用是什么", "tutor", ["search_knowledge"]),
    # ---- career：岗位 / 简历 / 求职规划 ----
    ("广州有哪些 AI 开发实习", "career", ["query_job"]),
    ("深圳的 Python 岗位", "career", ["query_job"]),
    ("帮我查一下杭州的后端实习", "career", ["query_job"]),
    ("北京有哪些大模型相关的岗位", "career", ["query_job"]),
    ("简历怎么写", "career", ["search_knowledge"]),
    ("自我介绍怎么讲", "career", ["search_knowledge"]),
    ("项目经历怎么用 STAR 讲", "career", ["search_knowledge"]),
    ("面试反问环节该问什么", "career", ["search_knowledge"]),
    ("怎么规划实习投递时间线", "career", ["search_knowledge"]),
    ("拿到多个 offer 怎么选", "career", ["search_knowledge"]),
    ("我这个背景适合投什么岗位", "career", []),
    ("帮我看看我的求职方向对不对", "career", []),
    # ---- 直接回复：寒暄 / 闲聊 / 感谢 ----
    ("你好", None, []),
    ("谢谢", None, []),
    ("再见", None, []),
    ("在吗", None, []),
    ("今天天气不错", None, []),
    ("辛苦了", None, []),
    ("你是谁", None, []),
    ("你能做什么", None, []),
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
    print(f"{'问题':<22}{'期望':<12}{'实际':<12}{'路由':<4}{'工具':<22}{'完':<3}")
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
            f"{question[:20]:<22}{(expected_agent or '直接回复'):<12}{(actual_agent or '直接回复'):<12}"
            f"{'✓' if route_ok else '✗':<4}{','.join(actual_tools)[:20]:<22}{'✓' if complete_ok else '✗':<3}"
        )
    summary = {
        "n": n,
        "route_accuracy": round(route_hits / n, 3),
        "tool_accuracy": round(tool_hits / n, 3),
        "completion_rate": round(complete_hits / n, 3),
    }
    print(
        f"\n评测集: {n} 题 | 路由准确率: {summary['route_accuracy']} "
        f"| 工具准确率: {summary['tool_accuracy']} | 回答完整率: {summary['completion_rate']}"
    )
    return summary


if __name__ == "__main__":
    run_eval()
