"""会话记忆：启动时从 SQLite 回填历史，保证跨轮对话不"失忆"。"""

from typing import Any


class Memory:
    def __init__(self, session_id: str, max_messages: int = 24):
        self.session_id = session_id
        self.max_messages = max_messages
        self._messages = self._load_from_db()

    def _load_from_db(self) -> list[dict[str, Any]]:
        try:
            from ..chat_history import load_messages

            history = load_messages(self.session_id, limit=self.max_messages)
            return [
                {"role": m["role"], "content": m["content"]}
                for m in history
                if m["role"] in ("user", "assistant")
            ][-self.max_messages :]
        except Exception:
            return []

    def add(self, message: dict[str, Any]) -> None:
        self._messages.append(message)
        self._messages = self._messages[-self.max_messages :]

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def clear(self) -> None:
        self._messages = []
