"""通用 Agent 循环：Function Calling 引擎（多 Agent 共用，提示词/工具/记忆可注入）。"""

import json
import re
from types import SimpleNamespace
from typing import Callable

from openai import OpenAI

from ..config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from .memory import Memory

MAX_ITERATIONS = 6


def strip_thought(text: str) -> str:
    text = re.sub(r"<thought>.*?</thought>\s*", "", text, flags=re.DOTALL).strip()
    if "<thought>" in text:
        text = text.split("<thought>")[0].strip()
    return text


class AgentError(Exception):
    pass


class AgentLoop:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: list[dict],
        tool_functions: dict,
        memory: Memory | None = None,
        max_iterations: int = MAX_ITERATIONS,
        temperature: float = 0.3,
    ):
        if not DEEPSEEK_API_KEY:
            raise AgentError("未配置 DEEPSEEK_API_KEY，请复制 .env.example 为 .env 并填写")
        self.name = name
        self.system_prompt = system_prompt
        self.tools = tools
        self.tool_functions = tool_functions
        self.memory = memory or Memory("default")
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        self.model = DEEPSEEK_MODEL
        self.trace: list[dict] = []

    def _record(self, step: str, content: str) -> None:
        self.trace.append({"step": step, "content": content})

    def _call_llm(self, messages: list[dict]) -> dict:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=self.tools,
            tool_choice="auto",
            temperature=self.temperature,
        )
        return resp.choices[0].message

    def _execute_tool(self, tool_call) -> str:
        name = tool_call.function.name
        try:
            arguments = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError:
            arguments = {}
        func: Callable | None = self.tool_functions.get(name)
        if func is None:
            return f"错误：未知工具 {name}"
        try:
            result = func(**arguments)
            self._record("tool", f"{name}({json.dumps(arguments, ensure_ascii=False)}) -> {result}")
            return result
        except Exception as exc:
            return f"工具执行失败：{exc}"

    def chat(self, user_message: str, on_tool: Callable[[str], None] | None = None) -> tuple[str, list[dict]]:
        self.trace = []
        self.memory.add({"role": "user", "content": user_message})
        messages = [{"role": "system", "content": self.system_prompt}] + self.memory.get_messages()
        for _ in range(self.max_iterations):
            self._record("think", "正在分析问题并决定是否调用工具…")
            message = self._call_llm(messages)
            if not message.tool_calls:
                reply = strip_thought(message.content or "（模型未返回内容）")
                self.memory.add({"role": "assistant", "content": reply})
                self._record("answer", reply)
                return reply, self.trace
            self.memory.add({"role": "assistant", "content": message.content or "", "tool_calls": message.tool_calls})
            messages = [{"role": "system", "content": self.system_prompt}] + self.memory.get_messages()
            for tool_call in message.tool_calls:
                if on_tool:
                    on_tool(tool_call.function.name)
                result = self._execute_tool(tool_call)
                self.memory.add({"role": "tool", "tool_call_id": tool_call.id, "content": result})
            messages = [{"role": "system", "content": self.system_prompt}] + self.memory.get_messages()
        reply = "抱歉，这个问题比较复杂，我没能在有限步骤内完成，请换个问法试试。"
        self._record("answer", reply)
        return reply, self.trace

    def chat_stream(self, user_message: str, on_tool: Callable[[str], None] | None = None):
        """流式版：工具调用轮不产出文本，最终回答逐块 yield。"""
        self.trace = []
        self.memory.add({"role": "user", "content": user_message})
        messages = [{"role": "system", "content": self.system_prompt}] + self.memory.get_messages()
        for _ in range(self.max_iterations):
            self._record("think", "正在分析问题并决定是否调用工具…")
            content = ""
            tool_calls: list[dict] = []
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
                temperature=self.temperature,
                stream=True,
            )
            for chunk in stream:
                choice = chunk.choices[0]
                delta = choice.delta
                if delta and delta.content:
                    content += delta.content
                    yield delta.content
                if delta and delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        while len(tool_calls) <= idx:
                            tool_calls.append({"id": "", "name": "", "arguments": ""})
                        if tc.id:
                            tool_calls[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls[idx]["arguments"] += tc.function.arguments
            if not tool_calls:
                content = strip_thought(content)
                self.memory.add({"role": "assistant", "content": content})
                self._record("answer", content)
                return
            tool_call_dicts = [
                {"id": tc["id"], "type": "function",
                 "function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in tool_calls
            ]
            self.memory.add({"role": "assistant", "content": content, "tool_calls": tool_call_dicts})
            messages = [{"role": "system", "content": self.system_prompt}] + self.memory.get_messages()
            call_objects = [
                SimpleNamespace(
                    id=tc["id"],
                    function=SimpleNamespace(name=tc["name"], arguments=tc["arguments"]),
                )
                for tc in tool_calls
            ]
            for tc in call_objects:
                if on_tool:
                    on_tool(tc.function.name)
                result = self._execute_tool(tc)
                self.memory.add({"role": "tool", "tool_call_id": tc.id, "content": result})
            messages = [{"role": "system", "content": self.system_prompt}] + self.memory.get_messages()
        yield "抱歉，这个问题比较复杂，我没能在有限步骤内完成，请换个问法试试。"
