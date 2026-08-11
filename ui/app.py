"""AI 面试备战助手 · Streamlit 界面（多 Agent 聊天 + 卡片 + 服务明细）。"""

import html
import json
import sys
import uuid
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.cards import parse_trace_cards
from backend.app.agent.core import AgentError, MultiAgentHarness
from backend.app.agent.memory import Memory
from backend.app.chat_history import clear_messages, load_messages, save_message
from backend.app.db import init_db

init_db()

TOOL_LABELS = {
    "query_question": "抽取面试题",
    "query_job": "查询岗位",
    "search_knowledge": "检索知识库",
    "delegate": "转交专员处理",
}

USER_AVATAR = "🙋"
ASSISTANT_AVATAR = "🎓"

st.set_page_config(page_title="AI 面试备战助手", page_icon="🎓", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --brand: #2b6cb0;
        --brand-dark: #1e4e8c;
        --brand-light: #ebf4ff;
        --price: #c0392b;
        --text: #1a202c;
        --muted: #718096;
        --border: #e2e8f0;
        --bg: #f7fafc;
    }
    html, body, .stApp, [class*="st-"], [data-testid] {
        font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB',
            'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif !important;
    }
    .stApp { background: linear-gradient(180deg, #ffffff 0%, #f7fafc 100%); }
    .block-container { max-width: 1100px; padding: 1.5rem 1.2rem 3rem !important; }

    .hero {
        background: linear-gradient(135deg, #2b6cb0 0%, #4299e1 100%);
        border-radius: 14px; padding: 26px 30px; color: #fff; margin-bottom: 14px;
        box-shadow: 0 8px 24px rgba(43,108,176,.25);
    }
    .hero h1 { color: #fff !important; margin: 0 0 8px; font-size: 26px; }
    .hero p { color: rgba(255,255,255,.92); margin: 0; font-size: 14px; }
    .hero .tag {
        display: inline-block; background: rgba(255,255,255,.2); border-radius: 20px;
        padding: 4px 14px; font-size: 12px; margin-top: 10px; margin-right: 8px;
    }

    .section-title {
        display: flex; align-items: center; gap: 8px; font-size: 17px; font-weight: 700;
        color: var(--text); margin: 18px 0 12px; padding-left: 10px;
        border-left: 4px solid var(--brand);
    }

    details.custom-details {
        margin: 8px 0; background: #fff; border: 1px solid var(--border);
        border-radius: 8px; padding: 6px 12px;
    }
    details.custom-details > summary {
        cursor: pointer; font-size: 12px; color: var(--muted); font-weight: 600;
        list-style: none; user-select: none;
    }
    details.custom-details > summary::-webkit-details-marker { display: none; }
    details.custom-details > summary::before {
        content: ''; display: inline-block; width: 7px; height: 7px;
        border-right: 2px solid #a0aec0; border-bottom: 2px solid #a0aec0;
        transform: rotate(-45deg); margin-right: 8px; transition: transform .2s;
    }
    details.custom-details[open] > summary::before { transform: rotate(45deg); }
    .custom-details-body { margin-top: 6px; padding-top: 6px; border-top: 1px dashed var(--border); }

    .trace-step { border-left: 3px solid #bee3f8; padding: 4px 0 4px 12px; margin: 4px 0; font-size: 13px; color: #4a5568; }
    .trace-step.warn { border-left-color: #f6ad55; }

    [data-testid="stChatMessage"] {
        border-radius: 12px !important; padding: 10px 14px !important;
        margin-bottom: 10px !important; border: 1px solid var(--border) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,.05) !important;
    }
    [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {
        background: #f0f7ff !important; border-color: #bee3f8 !important;
    }
    [data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) {
        background: #fff !important;
    }
    [data-testid="stChatMessage"] > div:first-child:not([data-testid="stChatMessageContent"]) {
        width: 38px !important; height: 38px !important; border-radius: 50% !important;
        background: var(--brand-light) !important; font-size: 20px !important;
        display: flex !important; align-items: center; justify-content: center;
    }
    [data-testid="stChatInput"] { border-radius: 12px !important; border: 1px solid #cbd5e0 !important; }
    .stButton > button[kind="primary"] {
        background: var(--brand) !important; border-color: var(--brand) !important;
    }
    .card {
        background: #fff; border: 1px solid var(--border); border-radius: 10px;
        padding: 10px 14px; margin: 6px 0; box-shadow: 0 2px 8px rgba(0,0,0,.04);
    }
    .card .q { font-size: 13px; font-weight: 600; color: var(--text); }
    .card .meta { font-size: 11px; color: var(--muted); margin: 2px 0; }
    .card .hint { font-size: 12px; color: var(--brand-dark); margin-top: 4px; }
    .site-footer { text-align: center; padding: 18px; margin-top: 24px; color: var(--muted); font-size: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_collapsible(title: str, body_html: str, open_default: bool = False) -> None:
    st.markdown(
        f"""
        <details class="custom-details"{' open' if open_default else ''}>
            <summary>{html.escape(title)}</summary>
            <div class="custom-details-body">{body_html}</div>
        </details>
        """,
        unsafe_allow_html=True,
    )


def render_cards(cards: list[dict]) -> None:
    for card in cards:
        ctype = card.get("type")
        if ctype == "questions":
            for q in card.get("items", []):
                st.markdown(
                    f"""
                    <div class="card">
                        <div class="meta">{q.get('topic', '')} · {q.get('level', '')}</div>
                        <div class="q">{html.escape(q.get('question', ''))}</div>
                        <div class="hint">💡 {html.escape(q.get('hint', ''))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        elif ctype == "jobs":
            for j in card.get("items", []):
                st.markdown(
                    f"""
                    <div class="card">
                        <div class="q">💼 {html.escape(j.get('title', ''))} · {html.escape(j.get('company', ''))}</div>
                        <div class="meta">{html.escape(j.get('city', ''))} | {html.escape(j.get('salary', ''))} | {html.escape(j.get('direction', ''))}</div>
                        <div class="hint">要求：{html.escape(j.get('requirements', ''))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        elif ctype == "knowledge":
            try:
                data = json.loads(card["text"])
                body = "".join(
                    f'<div class="trace-step"><b>{html.escape(c.get("title", ""))}</b><br>{html.escape(c.get("text", ""))[:400]}</div>'
                    for c in data[:3]
                )
            except Exception:
                body = f'<div style="white-space:pre-wrap;font-size:12px;">{html.escape(card["text"])[:800]}</div>'
            st.markdown(f'<div class="card"><div class="q">📚 知识库参考（RAG）</div>{body}</div>', unsafe_allow_html=True)


def new_session() -> None:
    st.session_state["session_id"] = f"s-{uuid.uuid4().hex[:6]}"
    st.session_state.messages = None
    st.rerun()


def handle_reply(prompt: str) -> None:
    session_id = st.session_state["session_id"]
    if st.session_state.messages is None:
        st.session_state.messages = []
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)
    try:
        agent = MultiAgentHarness(memory=Memory(session_id))
    except AgentError as exc:
        st.error(f"助手暂不可用：{exc}")
        return
    save_message(session_id, "user", prompt)

    tool_placeholder = st.empty()

    def on_tool(name: str) -> None:
        label = TOOL_LABELS.get(name, name)
        tool_placeholder.markdown(f'<div class="trace-step">🔧 正在{label}…</div>', unsafe_allow_html=True)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        try:
            reply = st.write_stream(agent.chat_stream(prompt, on_tool=on_tool))
            tool_placeholder.empty()
            trace = agent.trace
        except Exception as exc:
            tool_placeholder.empty()
            st.error(f"回复失败，请稍后再试：{exc}")
            return

        steps = [t for t in trace if t["step"] in ("think", "tool")]
        if steps:
            body = "".join(
                f'<div class="trace-step">💭 {html.escape(t["content"])}</div>'
                if t["step"] == "think"
                else f'<div class="trace-step">⚙️ {html.escape(t["content"])}</div>'
                for t in steps
            )
            render_collapsible(f"🔍 本次服务明细（{len(steps)} 步）", body)
        cards = parse_trace_cards(trace)
        if cards:
            render_cards(cards)

    assistant_msg = {"role": "assistant", "content": reply}
    st.session_state.messages.append(assistant_msg)
    save_message(session_id, "assistant", reply)


# ---------------- 主入口 ----------------
st.markdown(
    """
    <div class="hero">
        <h1>🎓 AI 面试备战助手</h1>
        <p>多 Agent + RAG 驱动的面试陪练：模拟面试官出题点评 · 八股讲师查漏补缺 · 求职顾问匹配岗位</p>
        <span class="tag">🤖 多 Agent 编排</span><span class="tag">📚 RAG 知识库</span><span class="tag">⚙️ Function Calling</span>
    </div>
    """,
    unsafe_allow_html=True,
)

st.session_state.setdefault("session_id", "default")
st.session_state.setdefault("messages", None)

with st.sidebar:
    st.markdown("### 🎓 AI 面试备战助手")
    st.markdown(f"**当前会话** · `{st.session_state['session_id']}`")
    if st.button("🆕 新建会话", use_container_width=True):
        new_session()
    st.divider()
    st.markdown("**三个专员**")
    st.markdown("🎙️ 模拟面试官：出题、追问、点评")
    st.markdown("📖 八股讲师：讲解知识点")
    st.markdown("💼 求职顾问：查岗位、简历建议")
    st.divider()
    st.caption("对话自动保存到本地 SQLite，刷新不丢失")

if st.session_state.messages is None:
    history = load_messages(st.session_state["session_id"])
    st.session_state.messages = history or [
        {
            "role": "assistant",
            "content": "你好，我是 AI 面试备战助手 🎓\n\n可以帮你：\n· 模拟一场面试（说\"模拟 Python 后端面试\"）\n· 讲解八股（说\"讲讲 RAG 的原理\"）\n· 查实习岗位（说\"广州有哪些 AI 开发实习\"）",
        }
    ]

for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar=USER_AVATAR if msg["role"] == "user" else ASSISTANT_AVATAR):
        st.markdown(msg["content"])

quick = ["🎙️ 模拟一场 Python 后端面试", "📖 讲讲 RAG 的原理", "💼 广州有哪些 AI 开发实习"]
cols = st.columns(len(quick))
for col, q in zip(cols, quick):
    with col:
        if st.button(q, key=f"quick_{q[:6]}", use_container_width=True):
            handle_reply(q.split(" ", 1)[1])

if prompt := st.chat_input("试试输入：模拟一场 AI 应用开发面试 / 什么是 Function Calling / 深圳的岗位"):
    handle_reply(prompt)

st.markdown('<div class="site-footer">AI 面试备战助手 · 多 Agent + RAG 学习项目 · 数据保存在本地</div>', unsafe_allow_html=True)
