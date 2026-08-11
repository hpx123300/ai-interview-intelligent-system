"""轻量多 Agent Harness：主管路由 + 专员执行 + 统一轨迹。"""

import json
from typing import Callable

from openai import OpenAI

from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from ..llm_utils import with_retry
from ..profile import ProfileStore, profile_context_text
from .loop import AgentError, AgentLoop, strip_thought
from .memory import Memory
from .roles import (
    CAREER_FUNCS,
    CAREER_PROMPT,
    CAREER_TOOLS,
    INTERVIEWER_FUNCS,
    INTERVIEWER_PROMPT,
    INTERVIEWER_TOOLS,
    ROUTER_PROMPT,
    ROUTER_TOOLS,
    SPECIALIST_LABELS,
    TUTOR_FUNCS,
    TUTOR_PROMPT,
    TUTOR_TOOLS,
)


class RouterAgent:
    """主管 Agent：单次 LLM 调用，判断直接回复还是指派专员。"""

    def __init__(self, memory: Memory):
        if not DEEPSEEK_API_KEY:
            raise AgentError("未配置 DEEPSEEK_API_KEY，请复制 .env.example 为 .env 并填写")
        self.memory = memory
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        self.model = DEEPSEEK_MODEL
        self.trace: list[dict] = []

    def _record(self, step: str, content: str) -> None:
        self.trace.append({"step": step, "content": content})

    @with_retry()
    def route(
        self,
        user_message: str,
        specialists: dict[str, AgentLoop],
        on_tool: Callable[[str], None] | None = None,
    ) -> tuple[AgentLoop | None, str | None, str | None]:
        self.trace = []
        messages = (
            [{"role": "system", "content": ROUTER_PROMPT}]
            + self.memory.get_messages()
            + [{"role": "user", "content": user_message}]
        )
        message = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=ROUTER_TOOLS,
            tool_choice="auto",
            temperature=0.2,
        ).choices[0].message

        if not message.tool_calls:
            reply = strip_thought(message.content or "您好，请问有什么可以帮您？")
            self.memory.add({"role": "user", "content": user_message})
            self.memory.add({"role": "assistant", "content": reply})
            self._record("think", "主管：无需指派专员，直接回复")
            self._record("answer", reply)
            return None, None, reply

        try:
            args = json.loads(message.tool_calls[0].function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        agent_name = args.get("agent", "")
        task = (args.get("task") or "").strip() or user_message
        specialist = specialists.get(agent_name)
        label = SPECIALIST_LABELS.get(agent_name, agent_name)

        if specialist is None:
            reply = "抱歉，这个问题我暂时处理不了，您可以试试模拟面试、八股问答或求职咨询。"
            self.memory.add({"role": "user", "content": user_message})
            self.memory.add({"role": "assistant", "content": reply})
            self._record("think", f"主管：目标专员「{label}」不存在")
            self._record("answer", reply)
            return None, None, reply

        self._record("think", f"主管：指派给「{label}」专员处理")
        self._record("tool", f"delegate({agent_name}) -> 任务已转交「{label}」")
        if on_tool:
            on_tool("delegate")
        return specialist, task, None


class MultiAgentHarness:
    """多 Agent 编排入口：主管路由 + 三个专员，统一轨迹供前端展示。"""

    def __init__(self, memory: Memory | None = None):
        self.memory = memory or Memory("default")
        self.router = RouterAgent(self.memory)
        profile = ProfileStore().load()
        profile_text = profile_context_text(profile)
        profile_block = f"\n\n【候选人档案（结合真实经历出题、点评与给建议，不要照抄）】\n{profile_text}"
        self.specialists: dict[str, AgentLoop] = {
            "interviewer": AgentLoop("模拟面试官", INTERVIEWER_PROMPT + profile_block, INTERVIEWER_TOOLS, INTERVIEWER_FUNCS, self.memory),
            "tutor": AgentLoop("八股讲师", TUTOR_PROMPT, TUTOR_TOOLS, TUTOR_FUNCS, self.memory),
            "career": AgentLoop("求职顾问", CAREER_PROMPT + profile_block, CAREER_TOOLS, CAREER_FUNCS, self.memory),
        }
        self.trace: list[dict] = []

    def _route(self, user_message: str, on_tool: Callable[[str], None] | None = None):
        return self.router.route(user_message, self.specialists, on_tool=on_tool)

    def chat(self, user_message: str, on_tool: Callable[[str], None] | None = None) -> tuple[str, list[dict]]:
        specialist, task, direct = self._route(user_message, on_tool=on_tool)
        if specialist is None:
            self.trace = list(self.router.trace)
            return direct, self.trace
        reply, _ = specialist.chat(task, on_tool=on_tool)
        self.trace = list(self.router.trace) + list(specialist.trace)
        return reply, self.trace

    def chat_stream(self, user_message: str, on_tool: Callable[[str], None] | None = None):
        specialist, task, direct = self._route(user_message, on_tool=on_tool)
        if specialist is None:
            self.trace = list(self.router.trace)
            yield direct
            return
        yield from specialist.chat_stream(task, on_tool=on_tool)
        self.trace = list(self.router.trace) + list(specialist.trace)
