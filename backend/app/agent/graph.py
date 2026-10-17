"""LangGraph 版多 Agent 编排。

和 harness.py 的分工：

- harness.py 是自研版：用普通函数把「主管路由 → 专员执行」串起来，状态是隐式的，
  靠对象属性传递。逻辑直白，但新增角色要改 if/else，状态不可见。
- 这一版把状态显式建成 AgentState，路由用条件边（conditional edge）表达，
  每个专员是一个独立节点，可以单独替换、单独测试。

关键取舍：**LangGraph 只接管编排层**。专员内部仍然复用 AgentLoop 里手写的
Function Calling 循环。这样两种引擎的工具执行、记忆、轨迹完全一致，
差异只在「谁来调度」，可以拿同一套测试公平对比，而不是重写一遍业务。

切换方式：环境变量 AGENT_ENGINE=langgraph。
"""

from typing import Any, Callable, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, StateGraph

from .harness import MultiAgentHarness
from .memory import Memory


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


class LangGraphHarness:
    """用 StateGraph 表达「主管路由 + 专员执行」的多 Agent 编排。

    对外接口与 MultiAgentHarness 完全一致（chat / chat_stream / trace），
    所以 server 层可以按配置无缝切换。
    """

    def __init__(self, memory: Memory | None = None):
        # 复用自研版的 router 与三个专员，保证两种引擎能力一致
        self._base = MultiAgentHarness(memory)
        self.memory = self._base.memory
        self.router = self._base.router
        self.specialists = self._base.specialists
        self.trace: list[dict] = []
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
        """组装状态图：router → 条件边 → 某个专员 → END。"""
        builder = StateGraph(AgentState)
        builder.add_node("router", self._router_node)
        for name in self.specialists:
            node = (
                self._specialist_node_stream(name)
                if streaming
                else self._specialist_node(name)
            )
            builder.add_node(name, node)

        builder.set_entry_point("router")
        builder.add_conditional_edges(
            "router",
            self._pick,
            {**{name: name for name in self.specialists}, "direct": END},
        )
        for name in self.specialists:
            builder.add_edge(name, END)
        return builder.compile()

    # ---------------- 对外接口（与 MultiAgentHarness 一致） ----------------

    def chat(
        self, user_message: str, on_tool: Callable[[str], None] | None = None
    ) -> tuple[str, list[dict]]:
        self.trace = []
        result = self.graph.invoke({"user_message": user_message, "trace": []})
        self.trace = list(result.get("trace", []))
        return result.get("reply", ""), self.trace

    def chat_stream(
        self, user_message: str, on_tool: Callable[[str], None] | None = None
    ):
        """流式：custom 流负责吐 token，values 流负责拿到最终状态（含轨迹）。

        注意 direct 分支：主管直接回复时不经过任何专员节点，也就没有 custom 流，
        所以最后要兜底把终态里的 reply 补吐出去，否则前端收不到内容。
        """
        self.trace = []
        final: dict[str, Any] = {}
        emitted = False
        for mode, chunk in self.stream_graph.stream(
            {"user_message": user_message, "trace": []},
            stream_mode=["custom", "values"],
        ):
            if mode == "custom":
                if chunk:
                    emitted = True
                    yield chunk
            elif mode == "values":
                final = chunk
        self.trace = list(final.get("trace", []))
        if not emitted:
            reply = final.get("reply", "")
            if reply:
                yield reply

    # ---------------- 便于观察的辅助方法 ----------------

    def describe_graph(self) -> dict[str, list[str]]:
        """把图的结构暴露出来，方便前端/文档展示，也方便测试断言。"""
        return {
            "entry": ["router"],
            "nodes": ["router", *self.specialists.keys()],
            "edges": [
                f"router -> {{{', '.join([*self.specialists.keys(), 'direct->END'])}}}",
                *[f"{name} -> END" for name in self.specialists],
            ],
        }
