"""AI 面试备战助手 · Streamlit 界面

四大模式：
- 自由对话：多 Agent（主管 + 三个专员）聊天
- 模拟面试：出题 → 逐题作答 → 点评追问 → 整场评分 → 历史对比
- 面经复盘：粘贴真实面试经历，AI 深度复盘
- 历史报告：回看历次面试评分与问答记录
"""

import html
import json
import sys
import uuid
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.cards import parse_trace_cards  # noqa: E402
from backend.app.agent.core import AgentError, MultiAgentHarness  # noqa: E402
from backend.app.agent.memory import Memory  # noqa: E402
from backend.app.chat_history import clear_messages, load_messages, save_message  # noqa: E402
from backend.app.db import init_db  # noqa: E402
from backend.app.interview import DIRECTION_TOPICS, EVAL_DIMENSIONS, InterviewError, InterviewManager  # noqa: E402
from backend.app.interview_store import (  # noqa: E402
    create_interview,
    delete_interview,
    finish_interview,
    get_interview,
    list_interviews,
    load_qa,
    save_qa,
    update_qa,
)

init_db()

TOOL_LABELS = {
    "query_question": "抽取面试题",
    "query_job": "查询岗位",
    "search_knowledge": "检索知识库",
    "delegate": "转交专员处理",
}

USER_AVATAR = "🙋"
ASSISTANT_AVATAR = "🎓"
PROFILE_KEY = "local"

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
        --green: #38a169;
        --orange: #dd6b20;
        --red: #e53e3e;
    }
    html, body, .stApp, [class*="st-"], [data-testid] {
        font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB',
            'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif !important;
    }
    .stApp { background: linear-gradient(180deg, #ffffff 0%, #f7fafc 100%); }
    .block-container { max-width: 1100px; padding: 1.2rem 1.2rem 3rem !important; }

    .hero {
        background: linear-gradient(135deg, #2b6cb0 0%, #4299e1 100%);
        border-radius: 14px; padding: 24px 30px; color: #fff; margin-bottom: 12px;
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
        padding: 12px 16px; margin: 8px 0; box-shadow: 0 2px 8px rgba(0,0,0,.04);
    }
    .card .q { font-size: 14px; font-weight: 600; color: var(--text); }
    .card .meta { font-size: 11px; color: var(--muted); margin: 4px 0; }
    .card .hint { font-size: 12px; color: var(--brand-dark); margin-top: 6px; }

    .question-box {
        background: linear-gradient(135deg, #ffffff 0%, #f0f7ff 100%);
        border: 1.5px solid #bee3f8; border-radius: 12px; padding: 18px 20px; margin: 10px 0;
    }
    .question-box .num {
        display: inline-block; background: var(--brand); color: #fff; border-radius: 20px;
        padding: 2px 12px; font-size: 12px; margin-bottom: 8px;
    }
    .question-box .text { font-size: 17px; font-weight: 700; color: var(--text); line-height: 1.6; }
    .question-box .hint { font-size: 12.5px; color: var(--brand-dark); margin-top: 10px; background: #fff; border-radius: 8px; padding: 8px 12px; border: 1px dashed #bee3f8; }

    .feedback-box {
        background: #fffbea; border: 1px solid #fef0c7; border-radius: 10px;
        padding: 12px 16px; margin: 8px 0;
    }
    .feedback-box .label { font-size: 12px; font-weight: 700; color: #975a16; margin-bottom: 4px; }
    .feedback-box .body { font-size: 13.5px; color: #744210; line-height: 1.6; }

    .report-score {
        text-align: center; background: #fff; border: 1px solid var(--border); border-radius: 14px;
        padding: 18px 10px; box-shadow: 0 4px 16px rgba(0,0,0,.06);
    }
    .report-score .num { font-size: 44px; font-weight: 800; color: var(--brand); line-height: 1.1; }
    .report-score .lbl { font-size: 13px; color: var(--muted); }
    .report-score .verdict { font-size: 14px; font-weight: 700; color: var(--green); margin-top: 6px; }

    .report-sec { margin: 12px 0; }
    .report-sec .title { font-size: 14px; font-weight: 700; color: var(--text); margin-bottom: 6px; }
    .report-sec ul { margin: 0; padding-left: 18px; }
    .report-sec li { font-size: 13px; color: #4a5568; line-height: 1.7; }

    .pill { display: inline-block; border-radius: 20px; padding: 3px 12px; font-size: 12px; font-weight: 600; margin-right: 6px; }
    .pill.green { background: #f0fff4; color: var(--green); border: 1px solid #c6f6d5; }
    .pill.orange { background: #fffaf0; color: var(--orange); border: 1px solid #feebc8; }
    .pill.red { background: #fff5f5; color: var(--red); border: 1px solid #fed7d7; }
    .pill.gray { background: #f7fafc; color: var(--muted); border: 1px solid var(--border); }

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
                        <div class="meta">{html.escape(q.get('topic', ''))} · {html.escape(q.get('level', ''))}</div>
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


def render_report(report: dict, comparison: dict | None = None) -> None:
    """渲染完整评分报告 + 历史对比。"""
    if not report:
        st.info("暂无评分数据。")
        return
    total = report.get("total_score", 0)
    dims = report.get("dimensions", {})
    verdict = "通过 ✅" if total >= 60 else "待加强 ⚠️"
    col1, col2, col3 = st.columns([1, 2, 2])
    with col1:
        st.markdown(
            f"""
            <div class="report-score">
                <div class="num">{int(total)}</div>
                <div class="lbl">综合得分</div>
                <div class="verdict">{verdict}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown('<div class="section-title" style="margin-top:0">📈 维度得分</div>', unsafe_allow_html=True)
        for d in EVAL_DIMENSIONS:
            score = int(dims.get(d, 0) or 0)
            st.markdown(f"**{d}** · {score}")
            st.progress(min(score, 100) / 100)
    with col3:
        st.markdown('<div class="section-title" style="margin-top:0">🧭 与历史对比</div>', unsafe_allow_html=True)
        if comparison and comparison.get("history_count", 0) > 0:
            hist_avg = comparison.get("history_avg", {})
            for d in EVAL_DIMENSIONS:
                diff = int(dims.get(d, 0) or 0) - int(hist_avg.get(d, 0) or 0)
                icon = "🟢" if diff > 5 else ("🔴" if diff < -5 else "⚪")
                st.markdown(f"{icon} **{d}**　本场 {int(dims.get(d,0) or 0)}　vs 历史均值 {int(hist_avg.get(d,0) or 0)}")
        else:
            st.caption("首次完整面试，暂无历史场次可对比。多练几场会自动生成进步分析。")

    st.markdown('<div class="section-title">📝 面试官总结</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="report-sec"><div class="title">💪 亮点</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in report.get("highlights", [])) + "</ul></div>", unsafe_allow_html=True)
        st.markdown('<div class="report-sec"><div class="title">🚨 不足</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in report.get("weaknesses", [])) + "</ul></div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="report-sec"><div class="title">❌ 缺失关键点</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in report.get("missing_points", [])) + "</ul></div>", unsafe_allow_html=True)
        st.markdown('<div class="report-sec"><div class="title">🎯 改进建议</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in report.get("suggestions", [])) + "</ul></div>", unsafe_allow_html=True)

    if comparison and comparison.get("history_count", 0) > 0:
        st.markdown('<div class="section-title">📊 成长对比（相对历史 {count} 场）</div>'.format(count=comparison.get("history_count")), unsafe_allow_html=True)
        cc1, cc2 = st.columns(2)
        with cc1:
            st.markdown('<div class="report-sec"><div class="title">🟢 进步</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in comparison.get("progress", [])) + "</ul></div>", unsafe_allow_html=True)
            st.markdown('<div class="report-sec"><div class="title">🔴 退步</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in comparison.get("regress", [])) + "</ul></div>", unsafe_allow_html=True)
        with cc2:
            st.markdown('<div class="report-sec"><div class="title">⚪ 稳定</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in comparison.get("stable", [])) + "</ul></div>", unsafe_allow_html=True)
            st.markdown('<div class="report-sec"><div class="title">🎯 优先加强</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in comparison.get("priority", [])) + "</ul></div>", unsafe_allow_html=True)


def render_question_card(q: dict, index: int, total: int) -> None:
    st.markdown(
        f"""
        <div class="question-box">
            <span class="num">第 {index}/{total} 题</span>
            <div class="meta">{html.escape(q.get('topic', ''))} · {html.escape(q.get('level', ''))}</div>
            <div class="text">{html.escape(q.get('question', ''))}</div>
            <div class="hint">💡 作答提示：{html.escape(q.get('hint', ''))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_feedback(feedback: str, followup: str, score_hint: str = "") -> None:
    st.markdown(
        f"""
        <div class="feedback-box">
            <div class="label">👨‍💼 面试官点评</div>
            <div class="body">{html.escape(feedback)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if score_hint:
        st.caption(f"预判得分：{score_hint}")
    st.markdown(
        f"""
        <div class="question-box" style="border-color:#fef0c7;background:#fffdf5">
            <span class="num">🔎 追问</span>
            <div class="text">{html.escape(followup)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------- 自由对话 ----------------
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


def render_chat_tab() -> None:
    st.session_state.setdefault("session_id", "default")
    st.session_state.setdefault("messages", None)

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


# ---------------- 模拟面试 ----------------
def _start_interview() -> None:
    manager = InterviewManager()
    direction = st.session_state["iv_direction"]
    count = int(st.session_state["iv_count"])
    with st.spinner(f"面试官正在为「{direction}」方向出题…"):
        questions = manager.generate_question_list(direction, count)
        iid = f"iv-{uuid.uuid4().hex[:8]}"
        create_interview(iid, direction)
        first = questions[0]
        qa_id = save_qa(
            iid,
            question=first["question"],
            topic=first.get("topic", ""),
            level=first.get("level", ""),
            hint=first.get("hint", ""),
        )
        st.session_state["interview"] = {
            "id": iid,
            "direction": direction,
            "questions": questions,
            "index": 0,
            "qa_id": qa_id,
            "stage": "question",
            "pending_feedback": "",
            "pending_followup": "",
            "pending_score_hint": "",
            "report": None,
            "comparison": None,
        }
    st.rerun()


def _submit_answer(answer: str) -> None:
    iv = st.session_state["interview"]
    manager = InterviewManager()
    current = iv["questions"][iv["index"]]
    with st.spinner("面试官正在点评并出追问…"):
        result = manager.feedback_and_followup(current["question"], answer)
    update_qa(
        iv["qa_id"],
        answer=answer,
        feedback=result.get("feedback", ""),
        followup=result.get("followup", ""),
    )
    iv["pending_feedback"] = result.get("feedback", "")
    iv["pending_followup"] = result.get("followup", "")
    iv["pending_score_hint"] = result.get("score_hint", "")
    iv["stage"] = "followup"


def _submit_followup(answer: str) -> None:
    iv = st.session_state["interview"]
    update_qa(iv["qa_id"], followup_answer=answer)
    iv["index"] += 1
    if iv["index"] >= len(iv["questions"]):
        _finish_interview()
        return
    _open_next_question()


def _open_next_question() -> None:
    iv = st.session_state["interview"]
    q = iv["questions"][iv["index"]]
    qa_id = save_qa(
        iv["id"],
        question=q["question"],
        topic=q.get("topic", ""),
        level=q.get("level", ""),
        hint=q.get("hint", ""),
    )
    iv["qa_id"] = qa_id
    iv["pending_feedback"] = ""
    iv["pending_followup"] = ""
    iv["pending_score_hint"] = ""
    iv["stage"] = "question"


def _skip_question() -> None:
    iv = st.session_state["interview"]
    update_qa(iv["qa_id"], answer="（跳过）")
    iv["index"] += 1
    if iv["index"] >= len(iv["questions"]):
        _finish_interview()
        return
    _open_next_question()


def _show_reference() -> None:
    iv = st.session_state["interview"]
    manager = InterviewManager()
    current = iv["questions"][iv["index"]]
    with st.spinner("正在检索知识库并生成参考答案…"):
        ref = manager.reference_answer(current["question"])
    update_qa(iv["qa_id"], reference=ref)
    iv["reference"] = ref


def _finish_interview() -> None:
    iv = st.session_state["interview"]
    manager = InterviewManager()
    qa_list = load_qa(iv["id"])
    answered = [q for q in qa_list if q.get("answer") and q["answer"] != "（跳过）"]
    if not answered:
        st.error("本场还没有有效作答，无法评分。请至少回答一道题再结束。")
        return
    with st.spinner("考核官正在生成本场完整评分报告…"):
        report = manager.evaluate_interview(qa_list)
        history = [
            json.loads(r["report"])
            for r in list_interviews(PROFILE_KEY)
            if r["status"] == "finished" and r["id"] != iv["id"] and r["report"]
        ]
        comparison = manager.compare_with_history(report, history)
    finish_interview(iv["id"], report)
    iv["report"] = report
    iv["comparison"] = comparison
    iv["stage"] = "finished"


def render_interview_tab() -> None:
    iv = st.session_state.get("interview")
    if iv is None or iv.get("stage") == "finished":
        st.markdown(
            """
            <div class="card">
                <div class="q">🎙️ 选择方向和题量，开始一场完整的模拟面试</div>
                <div class="hint">流程：面试官出题 → 你逐题作答 → 面试官点评并追问 → 全部答完后生成整场评分报告与历史对比</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.selectbox("面试方向", list(DIRECTION_TOPICS.keys()), key="iv_direction", index=1)
        with c2:
            st.selectbox("题目数量", [4, 6, 8, 10], key="iv_count", index=1)
        with c3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button("🚀 开始模拟面试", type="primary", use_container_width=True):
                _start_interview()
        if iv is not None and iv.get("stage") == "finished" and iv.get("report"):
            st.markdown('<div class="section-title">📊 最近一次面试报告</div>', unsafe_allow_html=True)
            render_report(iv["report"], iv.get("comparison"))
        return

    # 面试进行中
    total = len(iv["questions"])
    index = iv["index"] + 1
    st.markdown(f'<span class="pill gray">📋 {iv["direction"]}</span><span class="pill gray">进度 {index}/{total}</span>', unsafe_allow_html=True)
    st.progress(min(iv["index"] / total, 1.0))

    current = iv["questions"][iv["index"]]
    render_question_card(current, iv["index"] + 1, total)

    if iv.get("reference"):
        with st.expander("📚 参考答案（本题）", expanded=True):
            st.markdown(iv["reference"])
    elif st.button("📚 查看参考答案", key="btn_ref"):
        _show_reference()
        st.rerun()

    if iv["stage"] == "question":
        answer = st.text_area(
            "你的回答",
            key=f"answer_{iv['qa_id']}",
            height=120,
            placeholder="尽量按面试作答习惯组织：结论 → 展开 → 例子/代码 → 风险点",
        )
        bc1, bc2, bc3 = st.columns([1, 1, 1])
        with bc1:
            if st.button("✅ 提交答案", type="primary", use_container_width=True, key="btn_submit"):
                if not answer.strip():
                    st.warning("先写下你的回答再提交哦。")
                else:
                    _submit_answer(answer.strip())
                    st.rerun()
        with bc2:
            if st.button("⏭️ 跳过本题", use_container_width=True, key="btn_skip"):
                _skip_question()
                st.rerun()
        with bc3:
            if st.button("🏁 结束面试并评分", use_container_width=True, key="btn_end1"):
                _finish_interview()
                st.rerun()
    elif iv["stage"] == "followup":
        render_feedback(iv["pending_feedback"], iv["pending_followup"], iv["pending_score_hint"])
        followup_answer = st.text_area(
            "追问回答",
            key=f"followup_{iv['qa_id']}",
            height=100,
            placeholder="针对面试官的追问继续作答…",
        )
        fc1, fc2 = st.columns([1, 1])
        with fc1:
            if st.button("✅ 提交追问回答", type="primary", use_container_width=True, key="btn_followup"):
                if not followup_answer.strip():
                    st.warning("先写下追问回答再提交哦。")
                else:
                    _submit_followup(followup_answer.strip())
                    st.rerun()
        with fc2:
            if st.button("🏁 结束面试并评分", use_container_width=True, key="btn_end2"):
                _finish_interview()
                st.rerun()

    st.divider()
    st.caption("已答题目回顾")
    for qa in load_qa(iv["id"])[:-1]:
        st.markdown(f"**Q：{html.escape(qa['question'])}**")
        st.caption(f"A：{html.escape(qa['answer'][:120])}")


# ---------------- 面经复盘 ----------------
def render_review_tab() -> None:
    st.markdown(
        """
        <div class="card">
            <div class="q">📝 把真实面试经历贴进来，AI 帮你深度复盘</div>
            <div class="hint">可以贴面试中问到的问题、你的回答、卡壳的地方、面试官的反馈，越具体复盘越有价值</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    text = st.text_area("面试经历", height=200, key="review_text", placeholder="例如：面了一家 AI 创业公司……问了 RAG 原理，我讲了流程但没答出向量检索细节……")
    if st.button("🔍 开始复盘", type="primary", use_container_width=False):
        if not text.strip():
            st.warning("先粘贴面试经历再开始复盘。")
        else:
            with st.spinner("复盘教练正在分析…"):
                try:
                    result = InterviewManager().review_experience(text.strip())
                except InterviewError as exc:
                    st.error(f"复盘失败：{exc}")
                    return
            st.session_state["review_result"] = result
    result = st.session_state.get("review_result")
    if result:
        st.markdown('<div class="section-title">📋 复盘报告</div>', unsafe_allow_html=True)
        st.markdown(f'**概括：** {html.escape(result.get("summary", ""))}')
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="report-sec"><div class="title">💪 亮点</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in result.get("highlights", [])) + "</ul></div>", unsafe_allow_html=True)
            st.markdown('<div class="report-sec"><div class="title">📚 必会知识点</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in result.get("key_points", [])) + "</ul></div>", unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="report-sec"><div class="title">🚨 暴露的问题</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in result.get("weaknesses", [])) + "</ul></div>", unsafe_allow_html=True)
            st.markdown('<div class="report-sec"><div class="title">🗓️ 行动计划</div><ul>' + "".join(f"<li>{html.escape(x)}</li>" for x in result.get("action_plan", [])) + "</ul></div>", unsafe_allow_html=True)


# ---------------- 历史报告 ----------------
def render_history_tab() -> None:
    interviews = list_interviews(PROFILE_KEY)
    finished = [i for i in interviews if i["status"] == "finished"]
    ongoing = [i for i in interviews if i["status"] == "ongoing"]
    if ongoing:
        st.markdown('<span class="pill orange">⏳ 进行中 {n} 场</span>'.format(n=len(ongoing)), unsafe_allow_html=True)
        for o in ongoing:
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{o['direction']}** · 开始于 {o['created_at'][:16].replace('T', ' ')}")
            with c2:
                if st.button("🗑️ 删除", key=f"del_on_{o['id']}", use_container_width=True):
                    delete_interview(o["id"])
                    st.rerun()
    if not finished:
        if not ongoing:
            st.info("还没有历史报告。去「模拟面试」完成一场面试后，评分报告会自动保存在这里。")
        return

    st.markdown('<div class="section-title">📊 已完成场次（{n}）</div>'.format(n=len(finished)), unsafe_allow_html=True)
    options = {
        f"{i['direction']} · {i['score']} 分 · {i['finished_at'][:16].replace('T', ' ')}": i["id"]
        for i in finished
    }
    label = st.selectbox("选择一场面试查看报告", list(options.keys()), key="history_select")
    iid = options[label]
    col_a, col_b = st.columns([5, 1])
    with col_b:
        if st.button("🗑️ 删除本场", use_container_width=True):
            delete_interview(iid)
            st.rerun()

    row = get_interview(iid)
    if not row or not row["report"]:
        st.warning("该场次暂无报告。")
        return
    report = json.loads(row["report"])
    history = [
        json.loads(r["report"])
        for r in list_interviews(PROFILE_KEY)
        if r["status"] == "finished" and r["id"] != iid and r["report"]
    ]
    with st.spinner("正在加载历史对比…"):
        comparison = InterviewManager().compare_with_history(report, history)
    render_report(report, comparison)

    st.markdown('<div class="section-title">🗒️ 本场问答记录</div>', unsafe_allow_html=True)
    for i, qa in enumerate(load_qa(iid), 1):
        st.markdown(f"**第 {i} 题（{qa['topic']} · {qa['level']}）**：{qa['question']}")
        if qa.get("answer"):
            st.caption(f"我的回答：{qa['answer'][:300]}")
        if qa.get("feedback"):
            st.caption(f"点评：{qa['feedback'][:200]}")
        if qa.get("followup"):
            st.caption(f"追问：{qa['followup']}")
        if qa.get("followup_answer"):
            st.caption(f"追问作答：{qa['followup_answer'][:200]}")
        st.divider()


# ---------------- 主入口 ----------------
st.markdown(
    """
    <div class="hero">
        <h1>🎓 AI 面试备战助手</h1>
        <p>多 Agent + RAG 驱动的面试陪练：模拟面试闭环 · 整场评分 · 成长对比 · 面经复盘</p>
        <span class="tag">🤖 多 Agent 编排</span><span class="tag">📚 RAG 知识库</span><span class="tag">⚙️ Function Calling</span><span class="tag">📊 面试闭环</span>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### 🎓 AI 面试备战助手")
    st.markdown("**功能导航**")
    mode = st.radio(
        "选择模式",
        ["💬 自由对话", "🎙️ 模拟面试", "📝 面经复盘", "📊 历史报告"],
        key="mode",
    )
    st.divider()
    if mode == "💬 自由对话":
        st.markdown(f"**当前会话** · `{st.session_state.get('session_id', 'default')}`")
        if st.button("🆕 新建会话", use_container_width=True):
            new_session()
        st.divider()
        st.markdown("**三个专员**")
        st.markdown("🎙️ 模拟面试官：出题、追问、点评")
        st.markdown("📖 八股讲师：讲解知识点")
        st.markdown("💼 求职顾问：查岗位、简历建议")
        st.divider()
        st.caption("对话自动保存到本地 SQLite，刷新不丢失")
    elif mode == "🎙️ 模拟面试":
        st.markdown("**面试闭环**")
        st.markdown("出题 → 作答 → 点评追问 → 整场评分 → 历史对比")
        st.divider()
        if st.button("↩️ 返回起始页（放弃当前面试）", use_container_width=True):
            st.session_state.pop("interview", None)
            st.rerun()
    elif mode == "📝 面经复盘":
        st.markdown("**复盘价值**")
        st.markdown("把真实面试经历转化为：亮点、问题、必会知识点、行动清单")
    else:
        st.markdown("**历史报告**")
        st.markdown("回看每场面试的评分、成长曲线与完整问答记录")
        st.divider()
        if st.button("🧹 清空全部历史", use_container_width=True):
            for i in list_interviews(PROFILE_KEY):
                delete_interview(i["id"])
            st.rerun()

if mode == "💬 自由对话":
    render_chat_tab()
elif mode == "🎙️ 模拟面试":
    render_interview_tab()
elif mode == "📝 面经复盘":
    render_review_tab()
else:
    render_history_tab()

st.markdown('<div class="site-footer">AI 面试备战助手 · 多 Agent + RAG 学习项目 · 面试记录保存在本地 SQLite</div>', unsafe_allow_html=True)
