"""把工具调用结果解析成前端可渲染的卡片数据。"""

import json


def parse_trace_cards(trace: list[dict]) -> list[dict]:
    cards = []
    for t in trace:
        if t["step"] != "tool" or "-> " not in t["content"]:
            continue
        name = t["content"].split("(", 1)[0]
        payload = t["content"].split("-> ", 1)[-1].strip()
        if name == "search_knowledge":
            cards.append({"type": "knowledge", "text": payload})
            continue
        try:
            data = json.loads(payload)
        except (TypeError, ValueError):
            continue
        if name == "query_question" and isinstance(data, list) and data:
            cards.append({"type": "questions", "items": data})
        elif name == "query_job" and isinstance(data, list) and data:
            cards.append({"type": "jobs", "items": data})
    return cards
