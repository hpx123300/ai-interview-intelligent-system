"""LangGraph 版多 Agent 编排。

和 harness.py 的分工：

- harness.py 是自研版：用普通函数把「主管路由 → 专员执行」串起来，状态是隐式的，
  靠对象属性传递。逻辑直白，但新增角色要改 if/else，状态不可见。
- 这一版把状态显式建成 AgentState，路由用条件边（conditional edge）表达，
  每个专员是一个独立节点，可以单独替换、单独测试。

关键取舍：**LangGraph 只接管编排层**。专员内部仍然复用 AgentLoop 里手写的
Function Calling 循环。这样两种引擎的工具执行、记忆、轨迹完全一致，
差异只在「谁来调度」，可以拿同一套测试公平对比，而不是重写一遍业务。

真正用到的框架能力（不是把 if/else 画成图）：

1. **检查点（checkpointer）**：每轮对话落到 SQLite，图状态可序列化、可回放。
   thread_id 按「会话 + 单轮」生成，所以一轮之内的断点续答与事后审计都成立，
   而跨轮记忆仍由 Memory + chat_history 负责，职责不重叠。
2. **中断（interrupt）**：用户要求「完整/正式面试」这类长任务时，图在确认节点
   暂停，把「预计 15 分钟，是否开始」抛给前端；用户确认后从断点恢复，
   而不是靠关键词在前端猜。这是框架价值最直接的地方——手写版要做这件事，
   得自己设计状态机 + 持久化 + 恢复协议。

切换方式：环境变量 AGENT_ENGINE=langgraph。
"""

import sqlite3
import threading
import uuid
from typing import Any, Callable, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from ..config import AGENT_CONFIRM_LONG_TASK, AGENT_CHECKPOINT_PATH, ensure_dirs
from .harness import MultiAgentHarness
from .memory import Memory

# 触发「先确认再开始」的关键词。只匹配明确的「完整面试」诉求，
# 普通的「出个题」「模拟一下」不该被拦，否则每轮都弹确认会烦人。
LONG_TASK_KEYWORDS = ("完整面试", "全流程面试", "正式面试", "一整场", "一场完整的")

CONFIRM_MESSAGE = (
    "这轮模拟面试预计 15 分钟、约 6 轮问答。确认现在开始吗？"
    "（如果只想练一两题，可以直接说出方向，我会用轻量模式。）"
)


class AgentState(TypedDict, total=False):
    """图状态：一次对话的完整上下文。

    LangGraph 的节点只读写这个字典，不依赖实例属性，
    所以每一步的状态都是可见、可序列化、可回放的。
    """

    user_message: str
    route: str          # interviewer / tutor / career / direct
    task: str           # 主管转述给专员的子任务
    reply: str
    trace: list[dict]
    confirmed: bool     # 长任务是否已获用户确认


def _is_long_task(text: str) -> bool:
    return any(k in (text or "") for k in LONG_TASK_KEYWORDS)


def _affirmative(value: Any) -> bool:
    """把用户的选择归一成布尔。前端传布尔、文字或 {confirmed: true} 都认。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return _affirmative(value.get("confirmed", value.get("value", "")))
    return str(value or "").strip().lower() in {
        "1", "true", "yes", "y", "ok", "开始", "确认", "好", "好的", "开始吧",
    }


def build_checkpointer(path=None):
    """建 SQLite 检查点。失败时返回 None，图退化为无检查点模式（功能不受影响）。"""
    try:
        ensure_dirs()
        target = path or AGENT_CHECKPOINT_PATH
        conn = sqlite3.connect(str(target), check_same_thread=False)
        from langgraph.checkpoint.sqlite import SqliteSaver

        return SqliteSaver(conn)
    except Exception:  # noqa: BLE001
        return None


class LangGraphHarness:
    """用 StateGraph 表达「主管路由 + 专员执行」的多 Agent 编排。

    对外接口与 MultiAgentHarness 完全一致（chat / chat_stream / trace），
    所以 server 层可以按配置无缝切换。
    """

    def __init__(self, memory: Memory | None = None, checkpointer=None):
        # 复用自研版的 router 与三个专员，保证两种引擎能力一致
        self._base = MultiAgentHarness(memory)
        self.memory = self._base.memory
        self.router = self._base.router
        self.specialists = self._base.specialists
        self.trace: list[dict] = []
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "latency_ms": 0}
        # 待确认的中断：server 读到它就给前端下发确认事件
        self.pending_interrupt: dict | None = None
        self.thread_id: str = ""
        self.checkpointer = checkpointer if checkpointer is not None else build_checkpointer()
        # SQLite 单连接在多线程下需要串行化，和项目里其它 SQLite 用法保持一致的取舍
        self._lock = threading.Lock()
        self.graph = self._build(streaming=False)
        self.stream_graph = self._build(streaming=True)

    # ---------------- 节点 ----------------

    def _router_node(self, state: AgentState) -> AgentState:
        """主管节点：单次 LLM 调用判断意图，写回 route / task。"""
        specialist, task, direct = self.router.route(
            state["user_message"], self.specialists
        )
        if specialist is None:
            return {
                "route": "direct",
                "reply": direct or "",
                "trace": list(self.router.trace),
            }
        name = next(
            (k for k, v in self.specialists.items() if v is specialist), "direct"
        )
        return {
            "route": name,
            "task": task or state["user_message"],
            "trace": list(self.router.trace),
        }

    def _confirm_node(self, state: AgentState) -> AgentState:
        """确认节点：长任务先中断，等用户点「开始」再从断点继续。

        这个节点必须是幂等的——LangGraph 恢复时会从头重放它，
        所以 interrupt() 之前不能有任何副作用（这里只做纯判断）。
        """
        if not AGENT_CONFIRM_LONG_TASK:
            return {}
        if state.get("confirmed") or state.get("route") != "interviewer":
            return {}
        if not _is_long_task(state.get("user_message", "")):
            return {}

        decision = interrupt(
            {
                "type": "confirm",
                "message": CONFIRM_MESSAGE,
                "options": ["开始", "先不开始"],
            }
        )
        if not _affirmative(decision):
            return {
                "route": "direct",
                "reply": "好的，随时可以开始。想先练一两题的话，直接说方向就行。",
                "confirmed": True,
            }
        return {"confirmed": True}

    def _specialist_node(self, name: str):
        """专员节点（非流式）：跑完整的 FC 循环，把回复与轨迹写回状态。"""

        def run(state: AgentState) -> AgentState:
            agent = self.specialists[name]
            reply, trace = agent.chat(state["task"])
            return {
                "reply": reply,
                "trace": list(state.get("trace", [])) + list(trace),
            }

        return run

    def _specialist_node_stream(self, name: str):
        """专员节点（流式）：把 AgentLoop 吐出的 token 通过 custom 流推给调用方。"""

        def run(state: AgentState) -> AgentState:
            agent = self.specialists[name]
            writer = get_stream_writer()
            full = ""
            for chunk in agent.chat_stream(state["task"]):
                if chunk:
                    full += chunk
                    writer(chunk)
            return {
                "reply": full,
                "trace": list(state.get("trace", [])) + list(agent.trace),
            }

        return run

    @staticmethod
    def _pick(state: AgentState) -> str:
        """条件边的分支函数：按 route 决定走哪个专员，direct 直接结束。"""
        route = state.get("route", "direct")
        return route if route in ("interviewer", "tutor", "career") else "direct"

    def _build(self, streaming: bool):
        """组装状态图：router → confirm → 条件边 → 某个专员 → END。"""
        builder = StateGraph(AgentState)
        builder.add_node("router", self._router_node)
        builder.add_node("confirm", self._confirm_node)
        for name in self.specialists:
            node = (
                self._specialist_node_stream(name)
                if streaming
                else self._specialist_node(name)
            )
            builder.add_node(name, node)

        builder.set_entry_point("router")
        builder.add_edge("router", "confirm")
        builder.add_conditional_edges(
            "confirm",
            self._pick,
            {**{name: name for name in self.specialists}, "direct": END},
        )
        for name in self.specialists:
            builder.add_edge(name, END)
        return builder.compile(checkpointer=self.checkpointer)

    # ---------------- 中断与恢复 ----------------

    def _new_thread(self) -> str:
        """一轮对话一个 thread_id：检查点服务于单轮内续答与回放，
        跨轮记忆交给 Memory，避免上一轮遗留的中断影响下一轮。"""
        self.thread_id = f"{self.memory.session_id}:{uuid.uuid4().hex[:8]}"
        return self.thread_id

    def _config(self) -> dict:
        return {"configurable": {"thread_id": self.thread_id}}

    def _capture_interrupt(self, state: dict) -> None:
        """从终态里取出中断信息。不同版本放在 __interrupt__ 里，格式是元组。"""
        raw = (state or {}).get("__interrupt__")
        if not raw:
            self.pending_interrupt = None
            return
        first = raw[0] if isinstance(raw, (list, tuple)) and raw else raw
        value = getattr(first, "value", first)
        self.pending_interrupt = value if isinstance(value, dict) else {"message": str(value)}

    def _collect_usage(self, state: dict) -> None:
        """汇总本轮开销：路由 1 次 + 实际执行的那个专员 N 次。

        图里的节点不直接改 self.usage（并发下会互相覆盖），
        所以等图跑完再从各个 agent 实例上读——它们各自只保存最近一轮的用量。
        """
        parts = [getattr(self.router, "usage", {})]
        specialist = self.specialists.get(state.get("route", ""))
        if specialist is not None:
            parts.append(getattr(specialist, "usage", {}))
        total = {"prompt_tokens": 0, "completion_tokens": 0, "latency_ms": 0}
        for part in parts:
            for key in total:
                total[key] += int((part or {}).get(key, 0) or 0)
        self.usage = total

    def resume(self, value: Any) -> tuple[str, list[dict]]:
        """从断点恢复：把用户的选择作为中断的返回值喂回图。"""
        self.pending_interrupt = None
        with self._lock:
            result = self.graph.invoke(Command(resume=value), self._config())
        self._capture_interrupt(result)
        self._collect_usage(result)
        self.trace = list(result.get("trace", []))
        return result.get("reply", ""), self.trace

    def resume_stream(self, value: Any):
        """流式恢复，和 chat_stream 的消费方式一致。

        注意这里不能加锁：生成器会在 yield 处挂起，持锁跨越 yield 会把
        所有并发请求串行化，甚至在被提前关闭时永久占锁。
        """
        self.pending_interrupt = None
        emitted = False
        final: dict = {}
        for mode, chunk in self.stream_graph.stream(
            Command(resume=value), self._config(), stream_mode=["custom", "values"]
        ):
            if mode == "custom":
                if chunk:
                    emitted = True
                    yield chunk
            elif mode == "values":
                final = chunk
        self._capture_interrupt(final)
        self._collect_usage(final)
        self.trace = list(final.get("trace", []))
        if not emitted:
            reply = final.get("reply", "")
            if reply:
                yield reply

    # ---------------- 对外接口（与 MultiAgentHarness 一致） ----------------

    def chat(
        self, user_message: str, on_tool: Callable[[str], None] | None = None
    ) -> tuple[str, list[dict]]:
        self.trace = []
        self.pending_interrupt = None
        thread = self._new_thread()
        with self._lock:
            result = self.graph.invoke(
                {"user_message": user_message, "trace": []},
                {"configurable": {"thread_id": thread}},
            )
        self._capture_interrupt(result)
        self._collect_usage(result)
        self.trace = list(result.get("trace", []))
        if self.pending_interrupt:
            # 非流式调用没有前端按钮，把确认语作为回复返回，等调用方 resume
            return self.pending_interrupt.get("message", ""), self.trace
        return result.get("reply", ""), self.trace

    def chat_stream(
        self, user_message: str, on_tool: Callable[[str], None] | None = None
    ):
        """流式：custom 流负责吐 token，values 流负责拿到最终状态（含轨迹）。

        注意 direct 分支：主管直接回复时不经过任何专员节点，也就没有 custom 流，
        所以最后要兜底把终态里的 reply 补吐出去，否则前端收不到内容。
        中断分支同理：确认语也要补吐，用户才知道在等什么。
        """
        self.trace = []
        self.pending_interrupt = None
        thread = self._new_thread()
        final: dict[str, Any] = {}
        emitted = False
        for mode, chunk in self.stream_graph.stream(
            {"user_message": user_message, "trace": []},
            {"configurable": {"thread_id": thread}},
            stream_mode=["custom", "values"],
        ):
            if mode == "custom":
                if chunk:
                    emitted = True
                    yield chunk
            elif mode == "values":
                final = chunk
        self._capture_interrupt(final)
        self._collect_usage(final)
        self.trace = list(final.get("trace", []))
        if not emitted:
            reply = self.pending_interrupt.get("message", "") if self.pending_interrupt else final.get("reply", "")
            if reply:
                yield reply

    # ---------------- 便于观察的辅助方法 ----------------

    def describe_graph(self) -> dict[str, list[str]]:
        """把图的结构暴露出来，方便前端/文档展示，也方便测试断言。"""
        return {
            "entry": ["router"],
            "nodes": ["router", "confirm", *self.specialists.keys()],
            "edges": [
                "router -> confirm",
                f"confirm -> {{{', '.join([*self.specialists.keys(), 'direct->END'])}}}",
                *[f"{name} -> END" for name in self.specialists],
            ],
            "checkpointer": type(self.checkpointer).__name__ if self.checkpointer else None,
        }
