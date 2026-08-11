"""面试闭环评测：出题完整率 / 点评追问完整率 / 评分结构完整率 / 复盘结构完整率。

用法：python scripts/eval_interview.py
（需要已配置 DEEPSEEK_API_KEY，会调用真实大模型）
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.interview import DIRECTION_TOPICS, EVAL_DIMENSIONS, InterviewManager  # noqa: E402


def run_eval() -> dict:
    manager = InterviewManager()
    metrics = {"question_ok": 0, "question_total": 0, "feedback_ok": 0, "feedback_total": 0,
               "evaluate_ok": 0, "review_ok": 0}

    # 1) 出题：每个方向生成 4 题，检查字段完整
    for direction in DIRECTION_TOPICS:
        metrics["question_total"] += 1
        questions = manager.generate_question_list(direction, 4)
        if len(questions) == 4 and all(q.get("question") and q.get("hint") for q in questions):
            metrics["question_ok"] += 1
            print(f"✓ 出题 {direction}: {len(questions)} 道，字段完整")
        else:
            print(f"✗ 出题 {direction}: 数量或字段不完整")

    # 2) 点评 + 追问：两条问答样本
    samples = [
        ("RAG 的流程是什么？", "先把文档分块向量化，提问时检索相关片段拼进 prompt，让模型基于资料回答。"),
        ("什么是 Function Calling？", "模型输出结构化工具调用，程序执行后把结果回填给模型再生成回答。"),
    ]
    for q, a in samples:
        metrics["feedback_total"] += 1
        result = manager.feedback_and_followup(q, a)
        if result.get("feedback") and result.get("followup"):
            metrics["feedback_ok"] += 1
            print(f"✓ 点评追问: {q[:18]}… -> feedback + followup 完整")
        else:
            print(f"✗ 点评追问: {q[:18]}… 缺少字段")

    # 3) 整场评分：维度完整
    report = manager.evaluate_interview(
        [{"question": q, "answer": a, "feedback": "基本正确", "followup": "如何优化？", "followup_answer": "加缓存"} for q, a in samples]
    )
    dims = report.get("dimensions", {})
    if report.get("total_score") and all(d in dims for d in EVAL_DIMENSIONS):
        metrics["evaluate_ok"] = 1
        print(f"✓ 整场评分: {report['total_score']} 分，5 维度齐全")
    else:
        print(f"✗ 整场评分: 缺字段 {report}")

    # 4) 复盘：字段完整
    review = manager.review_experience("面了一家 AI 公司，RAG 原理讲清了，但追问向量检索细节卡住了，项目选型理由没答好。")
    if review.get("summary") and review.get("weaknesses") and review.get("action_plan"):
        metrics["review_ok"] = 1
        print(f"✓ 面经复盘: 概括/不足/行动计划齐全")
    else:
        print(f"✗ 面经复盘: 缺字段 {review}")

    return metrics


if __name__ == "__main__":
    m = run_eval()
    q_rate = m["question_ok"] / max(m["question_total"], 1)
    f_rate = m["feedback_ok"] / max(m["feedback_total"], 1)
    print(
        f"\n出题完整率: {q_rate:.0%} | 点评追问完整率: {f_rate:.0%} | "
        f"评分结构完整率: {m['evaluate_ok']:.0%} | 复盘结构完整率: {m['review_ok']:.0%}"
    )
