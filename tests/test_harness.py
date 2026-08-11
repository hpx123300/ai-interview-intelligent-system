"""多 Agent Harness 测试：mock 大模型，验证路由、专员执行与记忆回填。"""

import json
from types import SimpleNamespace
from unittest import mock

from backend.app.agent.harness import MultiAgentHarness
from backend.app.agent.memory import Memory
from backend.app.chat_history import clear_messages, save_message


def make_message(content, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def make_tool_call(name, arguments):
    return SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments, ensure_ascii=False)),
    )


def make_chat_response(message):
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def patch_all_clients(create_side_effect):
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create_side_effect)))
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


def test_router_delegates_to_interviewer():
    """主管指派模拟面试官，专员抽题后回答，轨迹包含路由与工具步骤。"""
    calls = {"interviewer": 0}

    def fake_create(**kw):
        system = kw["messages"][0]["content"]
        if "负责判断用户意图" in system:
            return make_chat_response(
                make_message(None, [make_tool_call("delegate", {"agent": "interviewer", "task": "模拟一场 Python 面试"})])
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
        harness = MultiAgentHarness(memory=Memory("test_harness_session", max_messages=20))
        reply, trace = harness.chat("模拟一场 Python 面试")
    finally:
        stop_patchers(patchers)

    assert "GIL" in reply
    contents = [t["content"] for t in trace]
    assert any("指派给" in c and "模拟面试官" in c for c in contents)
    assert any("query_question" in c for c in contents)


def test_router_direct_reply_for_greeting():
    """寒暄不指派专员，主管直接回复。"""

    def fake_create(**kw):
        return make_chat_response(make_message("你好，欢迎来到面试智能系统！", None))

    patchers = patch_all_clients(fake_create)
    try:
        harness = MultiAgentHarness(memory=Memory("test_harness_session", max_messages=20))
        reply, trace = harness.chat("你好")
    finally:
        stop_patchers(patchers)

    assert "你好" in reply
    assert not any("指派给" in t["content"] for t in trace)


def test_specialists_have_scoped_tools():
    """每个专员只能看到自己的工具子集。"""
    from backend.app.agent.roles import CAREER_TOOLS, INTERVIEWER_TOOLS, TUTOR_TOOLS

    def names(tools):
        return {t["function"]["name"] for t in tools}

    assert names(INTERVIEWER_TOOLS) == {"query_question", "search_knowledge"}
    assert names(TUTOR_TOOLS) == {"search_knowledge"}
    assert names(CAREER_TOOLS) == {"query_job", "search_knowledge"}


def test_memory_seeds_from_db():
    """Memory 初始化时应回填 SQLite 中已持久化的会话历史。"""
    clear_messages("seed_test_session")
    save_message("seed_test_session", "user", "我想模拟面试")
    save_message("seed_test_session", "assistant", "好的，开始吧")

    m = Memory("seed_test_session")
    roles = [msg["role"] for msg in m.get_messages()]
    assert roles == ["user", "assistant"]
    clear_messages("seed_test_session")
