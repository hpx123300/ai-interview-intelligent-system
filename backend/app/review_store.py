"""面经复盘持久化：保存 / 列表 / 删除，供求职作战室回看。"""

import json
from typing import Any

from sqlalchemy import select

from .db import InterviewReview, get_session


def create_review(profile_key: str, source_text: str, result: dict[str, Any]) -> int:
    with get_session() as session:
        row = InterviewReview(
            profile_key=profile_key,
            source_text=source_text,
            summary=result.get("summary", ""),
            highlights=json.dumps(result.get("highlights", []), ensure_ascii=False),
            weaknesses=json.dumps(result.get("weaknesses", []), ensure_ascii=False),
            key_points=json.dumps(result.get("key_points", []), ensure_ascii=False),
            action_plan=json.dumps(result.get("action_plan", []), ensure_ascii=False),
        )
        session.add(row)
        session.commit()
        return row.id


def list_reviews(profile_key: str = "local", limit: int = 50) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = (
            session.execute(
                select(InterviewReview)
                .where(InterviewReview.profile_key == profile_key)
                .order_by(InterviewReview.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": r.id,
            "summary": r.summary,
            "source_text": r.source_text,
            "highlights": json.loads(r.highlights or "[]"),
            "weaknesses": json.loads(r.weaknesses or "[]"),
            "key_points": json.loads(r.key_points or "[]"),
            "action_plan": json.loads(r.action_plan or "[]"),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def get_review(review_id: int) -> dict[str, Any] | None:
    with get_session() as session:
        row = session.get(InterviewReview, review_id)
    if row is None:
        return None
    return {
        "id": row.id,
        "summary": row.summary,
        "source_text": row.source_text,
        "highlights": json.loads(row.highlights or "[]"),
        "weaknesses": json.loads(row.weaknesses or "[]"),
        "key_points": json.loads(row.key_points or "[]"),
        "action_plan": json.loads(row.action_plan or "[]"),
        "created_at": row.created_at.isoformat(),
    }


def delete_review(review_id: int) -> None:
    with get_session() as session:
        row = session.get(InterviewReview, review_id)
        if row is not None:
            session.delete(row)
            session.commit()
