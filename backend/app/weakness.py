"""跨场次的弱点画像：把历史面试报告聚合成一段可注入提示词的文本。

为什么需要这一层：

单场面试的评分只说明「这次答得怎么样」，但面试陪练真正该做的是
「记住你反复错在哪」。没有这层，每一场都是从零开始的陌生人。

实现上刻意不用向量库：评分维度、建议条目都是结构化数据，
SQL 聚合比语义检索更准，也更容易解释「为什么这条建议会出现」。
"""

import json
from collections import Counter

from .interview_store import get_interview, list_interviews
from .profile import DEFAULT_PROFILE_KEY

DIMENSIONS = ("正确性", "深度", "结构", "表达", "风险意识")


def build_summary(profile_key: str = DEFAULT_PROFILE_KEY, limit: int = 5) -> dict:
    """聚合最近 N 场已完成的面试，返回维度均分与高频问题。"""
    rows = [r for r in list_interviews(profile_key, limit=limit * 3) if r.get("status") == "finished"]
    reports: list[dict] = []
    for row in rows[:limit]:
        detail = get_interview(row["id"])
        if not detail or not detail.get("report"):
            continue
        try:
            reports.append(json.loads(detail["report"]))
        except Exception:  # noqa: BLE001
            continue

    if not reports:
        return {"sessions": 0, "avg_score": None, "weak_dimensions": [], "recurring": []}

    scores = [int(r.get("total_score", 0) or 0) for r in reports]
    dim_scores: dict[str, list[float]] = {d: [] for d in DIMENSIONS}
    for report in reports:
        dims = report.get("dimensions") or {}
        for name in DIMENSIONS:
            value = dims.get(name)
            if isinstance(value, (int, float)):
                dim_scores[name].append(float(value))

    averages = [
        {"name": name, "score": round(sum(vs) / len(vs), 1)}
        for name, vs in dim_scores.items()
        if vs
    ]
    averages.sort(key=lambda item: item["score"])

    # 建议条目跨场次去重后按出现次数排序——重复出现说明是稳定短板，
    # 只出现一次的多半是那场题目的偶发问题。
    counter: Counter[str] = Counter()
    for report in reports:
        for key in ("suggestions", "next_steps"):
            for item in report.get(key) or []:
                text = str(item).strip()
                if text:
                    counter[text] += 1
    recurring = [text for text, count in counter.most_common(5) if count >= 2]

    return {
        "sessions": len(reports),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "trend": scores[::-1],  # 时间正序，方便前端画折线
        "weak_dimensions": averages[:2],
        "recurring": recurring,
    }


def weakness_context_text(profile_key: str = DEFAULT_PROFILE_KEY, limit: int = 5) -> str:
    """拼成提示词片段。没有历史数据时返回空串，避免给模型塞无意义的占位。"""
    summary = build_summary(profile_key, limit)
    if not summary["sessions"]:
        return ""
    weak = "、".join(f"{d['name']}（{d['score']}/5）" for d in summary["weak_dimensions"])
    lines = [
        f"最近 {summary['sessions']} 场模拟面试，平均总分 {summary['avg_score']}。",
        f"维度短板：{weak}。" if weak else "",
    ]
    if summary["recurring"]:
        lines.append("反复出现的问题：" + "；".join(summary["recurring"][:3]) + "。")
    lines.append("出题与点评时优先覆盖上述短板，并明确指出「这是你上次也出现过的问题」。")
    return "\n".join(line for line in lines if line)
