"""对外导出：多 Agent Harness、异常与通用循环。

`build_harness()` 是编排引擎的统一入口：按 AGENT_ENGINE 返回自研版或 LangGraph 版。
两者对外接口完全一致（chat / chat_stream / trace），调用方不需要关心实现。
"""

from .harness import MultiAgentHarness
from .loop import AgentError, AgentLoop, strip_thought  # noqa: F401
from .memory import Memory

__all__ = [
    "MultiAgentHarness",
    "AgentLoop",
    "AgentError",
    "strip_thought",
    "build_harness",
    "current_engine",
]


def current_engine() -> str:
    """当前生效的编排引擎名，供前端 / 日志展示。"""
    from ..config import AGENT_ENGINE

    return "langgraph" if AGENT_ENGINE == "langgraph" else "custom"


def build_harness(memory: Memory | None = None):
    """按配置返回编排引擎实例。

    langgraph 未安装时不让整个服务起不来——自动退回自研版并保持可用，
    这样 .env 写错或者依赖没装都不会导致 500。
    """
    if current_engine() == "langgraph":
        try:
            from .graph import LangGraphHarness

            return LangGraphHarness(memory)
        except ImportError:
            pass
    return MultiAgentHarness(memory)
