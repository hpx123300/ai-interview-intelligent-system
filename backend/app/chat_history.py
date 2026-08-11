"""会话历史读写：SQLite 落盘，页面刷新 / 重启不丢失。"""

import json

from sqlalchemy import select

from .db import ChatMessage, get_session


def save_message(session_id: str, role: str, content: str) -> None:
    with get_session() as session:
        session.add(ChatMessage(session_id=session_id, role=role, content=content))
        session.commit()


def load_messages(session_id: str, limit: int = 50) -> list[dict]:
    with get_session() as session:
        rows = (
            session.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.id.asc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
    return [{"role": r.role, "content": r.content} for r in rows]


def clear_messages(session_id: str) -> None:
    with get_session() as session:
        session.query(ChatMessage).filter_by(session_id=session_id).delete()
        session.commit()
