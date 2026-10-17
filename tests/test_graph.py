"""LangGraph 编排测试：mock 大模型，验证路由、直答、流式与引擎切换。

和 test_harness.py 用的是同一套 mock 手法——因为两种引擎共用 router 与专员，
只有调度方式不同，所以同一份假模型输出能同时验证两边行为是否一致。
"""

import json
from types import SimpleNamespace
from unittest import mock

from backend.app.agent.graph import LangGraphHarness
from backend.app.agent.memory import Memory


def make_message(content, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def make_tool_call(name, arguments):
    return SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments, ensure_ascii=False)),
    )


def make_chat_response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def make_chunk(text):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text, tool_calls=None))]
    )


def patch_all_clients(create_side_effect):
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create_side_effect))
    )
    patchers = [
        mock.patch("backend.app.agent.loop.OpenAI", return_value=fake_client),
        mock.patch("backend.app.agent.harness.OpenAI", return_value=fake_client),
    ]
    for p in patchers:
        p.start()
    return patchers


def stop_patchers(patchers):
    for p in patchers:
        p.stop()


def test_graph_routes_to_interviewer():
    """主管通过条件边走到 interviewer 节点，轨迹里应包含路由与工具步骤。"""
    calls = {"interviewer": 0}

    def fake_create(**kw):
        system = kw["messages"][0]["content"]
        if "负责判断用户意图" in system:
            return make_chat_response(
                make_message(
                    None,
                    [make_tool_call("delegate", {"agent": "interviewer", "task": "模拟一场 Python 面试"})],
                )
            )
        if "模拟面试官" in system:
            calls["interviewer"] += 1
            if calls["interviewer"] == 1:
                return make_chat_response(
                    make_message(None, [make_tool_call("query_question", {"topic": "python"})])
                )
            return make_chat_response(make_message("第一题：说说 Python 的 GIL。", None))
        return make_chat_response(make_message("兜底回复", None))

    patchers = patch_all_clients(fake_create)
    try:
        harness = LangGraphHarness(memory=Memory("test_graph_session", max_messages=20))
        reply, trace = harness.chat("模拟一场 Python 面试")
    finally:
        stop_patchers(patchers)

    assert "GIL" in reply
    contents = [t["content"] for t in trace]
    assert any("指派给" in c and "模拟面试官" in c for c in contents)
    assert any("query_question" in c for c in contents)


def test_graph_direct_reply_for_greeting():
    """寒暄走 direct 分支直接结束，不进入任何专员节点。"""

    def fake_create(**kw):
        return make_chat_response(make_message("你好，欢迎来到面试智能系统！", None))

    patchers = patch_all_clients(fake_create)
    try:
        harness = LangGraphHarness(memory=Memory("test_graph_session", max_messages=20))
        reply, trace = harness.chat("你好")
    finally:
        stop_patchers(patchers)

    assert "你好" in reply
    assert not any("指派给" in t["content"] for t in trace)


def test_graph_stream_yields_tokens_and_trace():
    """流式路径：custom 流吐 token，values 流带回最终轨迹。"""

    def fake_create(**kw):
        system = kw["messages"][0]["content"]
        if kw.get("stream"):
            return iter([make_chunk("第一题："), make_chunk("说说 GIL。")])
        if "负责判断用户意图" in system:
            return make_chat_response(
                make_message(
                    None,
                    [make_tool_call("delegate", {"agent": "interviewer", "task": "出题"})],
                )
            )
        return make_chat_response(make_message("兜底", None))

    patchers = patch_all_clients(fake_create)
    try:
        harness = LangGraphHarness(memory=Memory("test_graph_stream", max_messages=20))
        chunks = list(harness.chat_stream("出个题"))
        trace = list(harness.trace)
    finally:
        stop_patchers(patchers)

    assert "".join(chunks) == "第一题：说说 GIL。"
    assert any("指派给" in t["content"] for t in trace)


def test_graph_stream_direct_reply_still_emits_text():
    """主管直答时没有 custom 流，但终态里的回复必须补吐出去，否则前端空白。"""

    def fake_create(**kw):
        return make_chat_response(make_message("你好，有什么可以帮你？", None))

    patchers = patch_all_clients(fake_create)
    try:
        harness = LangGraphHarness(memory=Memory("test_graph_stream_direct", max_messages=10))
        chunks = list(harness.chat_stream("你好"))
    finally:
        stop_patchers(patchers)

    assert "".join(chunks) == "你好，有什么可以帮你？"


def test_graph_structure_is_explicit():
    """图结构可被断言：一个入口、四个节点、专员到 END。"""
    harness = LangGraphHarness(memory=Memory("test_graph_structure", max_messages=10))
    shape = harness.describe_graph()

    assert shape["entry"] == ["router"]
    assert set(shape["nodes"]) == {"router", "interviewer", "tutor", "career"}
    assert len(shape["edges"]) == 4  # router 条件边 + 三个专员到 END


def test_build_harness_switches_engine(monkeypatch):
    """AGENT_ENGINE 决定返回哪种编排实现，两者接口一致。"""
    from backend.app.agent import core
    from backend.app.agent.harness import MultiAgentHarness

    monkeypatch.setattr("backend.app.config.AGENT_ENGINE", "langgraph")
    assert isinstance(core.build_harness(Memory("engine_a", 10)), LangGraphHarness)
    assert core.current_engine() == "langgraph"

    monkeypatch.setattr("backend.app.config.AGENT_ENGINE", "custom")
    assert isinstance(core.build_harness(Memory("engine_b", 10)), MultiAgentHarness)
    assert core.current_engine() == "custom"
