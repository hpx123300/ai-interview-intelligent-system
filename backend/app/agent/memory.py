"""会话记忆：启动时从 SQLite 回填历史，保证跨轮对话不"失忆"。

截断在**安全边界**进行。大模型 API 对消息序列有两条硬约束：
1. 每条 tool 消息必须紧跟在带 tool_calls 的 assistant 消息之后；
2. 带 tool_calls 的 assistant 消息，其每个 tool_call_id 都必须有对应的 tool 响应。

按条数硬截断会破坏这两种配对，导致 API 直接报 400。因此出参前统一修剪一次。
"""

from typing import Any

_TOOL_ROLE = "tool"


def sanitize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把消息序列修剪为 API 可接受的形态。

    丢弃：开头的孤儿 tool 消息；缺少任一 tool 响应的 assistant.tool_calls 组。
    """
    start = 0
    while start < len(messages) and messages[start].get("role") == _TOOL_ROLE:
        start += 1

    result: list[dict[str, Any]] = []
    total = len(messages)
    i = start
    while i < total:
        msg = messages[i]
        role = msg.get("role")
        tool_calls = msg.get("tool_calls")

        if role == "assistant" and tool_calls:
            expected = set()
            for tc in tool_calls:
                tc_id = getattr(tc, "id", None) or (tc.get("id") if isinstance(tc, dict) else None)
                if tc_id:
                    expected.add(tc_id)
            j = i + 1
            answered: set[str] = set()
            while j < total and messages[j].get("role") == _TOOL_ROLE:
                answered.add(messages[j].get("tool_call_id"))
                j += 1
            if expected and expected.issubset(answered):
                result.extend(messages[i:j])
            i = j
            continue

        if role == _TOOL_ROLE:
            i += 1
            continue

        result.append(msg)
        i += 1

    return result


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
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages :]

    def get_messages(self) -> list[dict[str, Any]]:
        return sanitize_messages(list(self._messages))

    def clear(self) -> None:
        self._messages = []
