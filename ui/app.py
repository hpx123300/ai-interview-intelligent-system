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
from backend.app.profile import DEFAULT_PROFILE, ProfileStore, profile_context_text  # noqa: E402
from backend.app.review_store import create_review, delete_review, list_reviews  # noqa: E402

init_db()

TOOL_LABELS = {
    "query_question": "抽取面试题",
    "query_job": "查询岗位",
    "search_knowledge": "检索知识库",
    "delegate": "转交专员处理",
}

PROFILE_KEY = "local"
MODE_CHAT = "自由对话"
MODE_INTERVIEW = "模拟面试"
MODE_REVIEW = "面经复盘"
MODE_WAR = "求职作战室"
MODE_HISTORY = "历史报告"
MODE_PROFILE = "我的档案"

st.set_page_config(page_title="面试备战助手", page_icon="📋", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --bg: #f7f7f8;
        --surface: #ffffff;
        --ink: #18181b;
        --ink-2: #3f3f46;
        --muted: #71717a;
        --line: #e4e4e7;
        --accent: #4f46e5;
        --accent-soft: #eef2ff;
        --green: #16a34a;
        --amber: #b45309;
        --red: #dc2626;
    }
    html, body, .stApp, [class*="st-"], [data-testid] {
        font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB',
            'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif !important;
        color: var(--ink);
    }
    .stApp { background: var(--bg); }
    .block-container { max-width: 1080px; padding: 1rem 1.5rem 3rem !important; }

    /* ---------- 顶部 ---------- */
    .app-header {
        display: flex; align-items: center; gap: 12px;
        padding: 6px 0 14px; border-bottom: 1px solid var(--line); margin-bottom: 18px;
    }
    .app-header .logo {
        width: 34px; height: 34px; border-radius: 9px; background: var(--accent); color: #fff;
        display: flex; align-items: center; justify-content: center;
        font-size: 15px; font-weight: 700; flex: none;
    }
    .app-header .titles { line-height: 1.25; }
    .app-header .title { font-size: 16px; font-weight: 700; color: var(--ink); }
    .app-header .subtitle { font-size: 12px; color: var(--muted); }

    /* ---------- 面板与卡片 ---------- */
    .panel {
        background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
        padding: 16px 18px; margin: 10px 0;
    }
    .panel-title { font-size: 14px; font-weight: 700; color: var(--ink); margin-bottom: 8px; }
    .panel-desc { font-size: 12.5px; color: var(--muted); line-height: 1.7; }

    .section-title {
        font-size: 13px; font-weight: 700; color: var(--ink-2); margin: 20px 0 8px;
        letter-spacing: .02em;
    }

    .muted { color: var(--muted); font-size: 12.5px; }
    .small { font-size: 12px; color: var(--muted); }

    /* ---------- 题目 ---------- */
    .q-panel { border-top: 3px solid var(--accent); }
    .q-meta { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
    .q-text { font-size: 16.5px; font-weight: 600; color: var(--ink); line-height: 1.7; }
    .q-hint {
        margin-top: 12px; font-size: 12.5px; color: var(--ink-2); line-height: 1.6;
        background: var(--bg); border-radius: 8px; padding: 9px 12px;
    }

    /* ---------- 点评 ---------- */
    .feedback {
        border-left: 3px solid var(--accent); background: #fafafa;
        padding: 11px 14px; margin: 8px 0; border-radius: 0 8px 8px 0;
    }
    .feedback .label { font-size: 12px; font-weight: 700; color: var(--ink-2); margin-bottom: 4px; }
    .feedback .body { font-size: 13.5px; color: var(--ink-2); line-height: 1.7; }

    /* ---------- 报告 ---------- */
    .score-card { text-align: center; padding: 14px 8px; }
    .score-num { font-size: 42px; font-weight: 800; color: var(--accent); line-height: 1.05; }
    .score-lbl { font-size: 12.5px; color: var(--muted); margin-top: 2px; }
    .score-verdict { font-size: 13.5px; font-weight: 700; margin-top: 8px; }
    .verdict-pass { color: var(--green); }
    .verdict-fail { color: var(--amber); }

    .report-sec { margin: 10px 0; }
    .report-sec .title { font-size: 13px; font-weight: 700; color: var(--ink-2); margin-bottom: 4px; }
    .report-sec ul { margin: 0; padding-left: 18px; }
    .report-sec li { font-size: 13px; color: var(--ink-2); line-height: 1.8; }

    .diff-up { color: var(--green); }
    .diff-down { color: var(--red); }
    .diff-flat { color: var(--muted); }

    /* ---------- 对话 ---------- */
    [data-testid="stChatMessage"] {
        border-radius: 10px !important; padding: 9px 14px !important;
        margin-bottom: 8px !important;
    }
    [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {
        justify-content: flex-end;
    }
    [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) {
        background: var(--accent-soft) !important;
    }
    [data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) {
        background: var(--surface) !important; border: 1px solid var(--line) !important;
    }
    [data-testid="stChatMessage"] > div:first-child:not([data-testid="stChatMessageContent"]) {
        display: none !important;
    }
    [data-testid="stChatMessageContent"] { max-width: 86% !important; }
    [data-testid="stChatInput"] {
        border-radius: 10px !important; border: 1px solid var(--line) !important;
        background: var(--surface) !important;
    }
    [data-testid="stChatInput"]:focus-within { border-color: var(--accent) !important; }

    /* ---------- 控件微调 ---------- */
    .stButton > button {
        border-radius: 8px !important; font-weight: 500;
    }
    .stButton > button[kind="primary"] {
        background: var(--accent) !important; border-color: var(--accent) !important;
    }
    [data-testid="stTextArea"] textarea { border-radius: 10px !important; border-color: var(--line) !important; }
    [data-testid="stTextArea"] textarea:focus { border-color: var(--accent) !important; }

    /* 分段选择器 */
    [data-testid="stSegmentedControl"] {
        background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
        padding: 4px;
    }
    [data-testid="stSegmentedControl"] button {
        border-radius: 7px !important; font-size: 13px !important;
    }

    /* 进度条 */
    [data-testid="stProgress"] > div > div > div { background: var(--accent) !important; }

    .site-footer { text-align: center; padding: 20px; margin-top: 26px; color: var(--muted); font-size: 11.5px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------- 通用渲染 ----------------
def render_collapsible(title: str, body_html: str, open_default: bool = False) -> None:
    st.markdown(
        f"""
        <details style="margin:6px 0;font-size:12px;color:var(--muted)">
            <summary style="cursor:pointer;user-select:none">{html.escape(title)}</summary>
            <div style="margin-top:6px;padding-top:6px;border-top:1px dashed var(--line)">{body_html}</div>
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
                    <div class="panel">
                        <div class="small">{html.escape(q.get('topic', ''))} · {html.escape(q.get('level', ''))}</div>
                        <div style="font-size:14px;font-weight:600;margin-top:4px">{html.escape(q.get('question', ''))}</div>
                        <div class="q-hint" style="margin-top:8px">💡 {html.escape(q.get('hint', ''))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        elif ctype == "jobs":
            for j in card.get("items", []):
                st.markdown(
                    f"""
                    <div class="panel">
                        <div style="font-size:14px;font-weight:600">{html.escape(j.get('title', ''))} · {html.escape(j.get('company', ''))}</div>
                        <div class="small" style="margin-top:4px">{html.escape(j.get('city', ''))} | {html.escape(j.get('salary', ''))} | {html.escape(j.get('direction', ''))}</div>
                        <div class="q-hint" style="margin-top:8px">要求：{html.escape(j.get('requirements', ''))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        elif ctype == "knowledge":
            try:
                data = json.loads(card["text"])
                body = "".join(
                    f'<div style="margin:6px 0"><b>{html.escape(c.get("title", ""))}</b><br>'
                    f'<span class="small">{html.escape(c.get("text", ""))[:400]}</span></div>'
                    for c in data[:3]
                )
            except Exception:
                body = f'<div style="white-space:pre-wrap;font-size:12.5px">{html.escape(card["text"])[:800]}</div>'
            st.markdown(f'<div class="panel"><div class="panel-title">知识库参考</div>{body}</div>', unsafe_allow_html=True)


def _ul(items: list[str]) -> str:
    if not items:
        return '<div class="muted">暂无</div>'
    return "<ul>" + "".join(f"<li>{html.escape(str(x))}</li>" for x in items) + "</ul>"


def _diff_class(score: int, avg: int) -> str:
    if score - avg > 5:
        return "diff-up"
    if score - avg < -5:
        return "diff-down"
    return "diff-flat"


def render_report(report: dict, comparison: dict | None = None) -> None:
    if not report:
        st.info("暂无评分数据。")
        return
    total = int(report.get("total_score", 0) or 0)
    dims = report.get("dimensions", {})
    verdict_html = (
        '<span class="score-verdict verdict-pass">达标</span>'
        if total >= 60
        else '<span class="score-verdict verdict-fail">待加强</span>'
    )

    c1, c2, c3 = st.columns([1, 2, 2])
    with c1:
        st.markdown(
            f"""
            <div class="panel score-card">
                <div class="score-num">{total}</div>
                <div class="score-lbl">综合得分</div>
                <div>{verdict_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown('<div class="section-title" style="margin-top:0">维度得分</div>', unsafe_allow_html=True)
        for d in EVAL_DIMENSIONS:
            score = int(dims.get(d, 0) or 0)
            st.markdown(f'<div class="small" style="display:flex;justify-content:space-between"><span>{d}</span><span>{score}</span></div>', unsafe_allow_html=True)
            st.progress(min(score, 100) / 100)
    with c3:
        st.markdown('<div class="section-title" style="margin-top:0">与历史对比</div>', unsafe_allow_html=True)
        if comparison and comparison.get("history_count", 0) > 0:
            hist_avg = comparison.get("history_avg", {})
            for d in EVAL_DIMENSIONS:
                s = int(dims.get(d, 0) or 0)
                a = int(hist_avg.get(d, 0) or 0)
                delta = s - a
                arrow = "↑" if delta > 5 else ("↓" if delta < -5 else "→")
                cls = _diff_class(s, a)
                st.markdown(f'<div class="small" style="display:flex;justify-content:space-between"><span>{d}</span><span class="{cls}">{arrow} {s} vs {a}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="muted">首次完整面试，暂无历史场次可对比。</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-title">面试官总结</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="report-sec"><div class="title">亮点</div>' + _ul(report.get("highlights", [])) + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="report-sec"><div class="title">不足</div>' + _ul(report.get("weaknesses", [])) + "</div>", unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="report-sec"><div class="title">缺失关键点</div>' + _ul(report.get("missing_points", [])) + "</div>", unsafe_allow_html=True)
        st.markdown('<div class="report-sec"><div class="title">改进建议</div>' + _ul(report.get("suggestions", [])) + "</div>", unsafe_allow_html=True)

    if comparison and comparison.get("history_count", 0) > 0:
        st.markdown(f'<div class="section-title">成长对比（历史 {comparison.get("history_count")} 场）</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="report-sec"><div class="title">进步</div>' + _ul(comparison.get("progress", [])) + "</div>", unsafe_allow_html=True)
            st.markdown('<div class="report-sec"><div class="title">退步</div>' + _ul(comparison.get("regress", [])) + "</div>", unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="report-sec"><div class="title">稳定</div>' + _ul(comparison.get("stable", [])) + "</div>", unsafe_allow_html=True)
            st.markdown('<div class="report-sec"><div class="title">优先加强</div>' + _ul(comparison.get("priority", [])) + "</div>", unsafe_allow_html=True)


def render_question_card(q: dict, index: int, total: int) -> None:
    topic = "项目深挖" if q.get("topic") == "project" else q.get("topic", "")
    st.markdown(
        f"""
        <div class="panel q-panel">
            <div class="q-meta">第 {index} / {total} 题 · {html.escape(topic)} · {html.escape(q.get('level', ''))}</div>
            <div class="q-text">{html.escape(q.get('question', ''))}</div>
            <div class="q-hint">提示：{html.escape(q.get('hint', ''))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_feedback(feedback: str, followup: str, score_hint: str = "") -> None:
    st.markdown(
        f"""
        <div class="feedback">
            <div class="label">面试官点评</div>
            <div class="body">{html.escape(feedback)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if score_hint:
        st.caption(f"预判得分：{score_hint}")
    st.markdown(
        f"""
        <div class="panel" style="border-top:3px solid #d4d4d8">
            <div class="q-meta">追问</div>
            <div class="q-text" style="font-size:15px">{html.escape(followup)}</div>
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
    with st.chat_message("user", avatar="🙋"):
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
        tool_placeholder.markdown(f'<div class="muted">正在{label}…</div>')

    with st.chat_message("assistant", avatar="🎓"):
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
                f'<div style="margin:4px 0;font-size:12px;color:var(--muted)">{html.escape(t["content"])}</div>'
                for t in steps
            )
            render_collapsible(f"服务明细（{len(steps)} 步）", body)
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
                "content": "你好，我是面试备战助手。\n\n可以帮你：\n· 模拟一场面试（说“模拟 Python 后端面试”）\n· 讲解八股（说“讲讲 RAG 的原理”）\n· 查实习岗位（说“广州有哪些 AI 开发实习”）",
            }
        ]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🙋" if msg["role"] == "user" else "🎓"):
            st.markdown(msg["content"])

    quick = ["模拟一场 Python 后端面试", "讲讲 RAG 的原理", "广州有哪些 AI 开发实习"]
    cols = st.columns(len(quick))
    for col, q in zip(cols, quick):
        with col:
            if st.button(q, key=f"quick_{q[:6]}", use_container_width=True):
                handle_reply(q)

    if prompt := st.chat_input("输入问题，例如：模拟一场 AI 应用开发面试 / 什么是 Function Calling"):
        handle_reply(prompt)


# ---------------- 模拟面试 ----------------
def _start_interview() -> None:
    manager = InterviewManager()
    direction = st.session_state["iv_direction"]
    count = int(st.session_state["iv_count"])
    profile = ProfileStore(PROFILE_KEY).load()
    with st.spinner(f"正在为「{direction}」方向出题…"):
        questions = manager.generate_question_list(direction, count, profile=profile)
        project_count = sum(1 for q in questions if q.get("topic") == "project")
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
            "reference": "",
            "report": None,
            "comparison": None,
            "project_count": project_count,
        }
    st.rerun()


def _submit_answer(answer: str) -> None:
    iv = st.session_state["interview"]
    manager = InterviewManager()
    current = iv["questions"][iv["index"]]
    with st.spinner("面试官正在点评…"):
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
    iv["reference"] = ""
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
    with st.spinner("正在生成参考答案…"):
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
    with st.spinner("正在生成本场评分报告…"):
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
            <div class="panel">
                <div class="panel-title">开始一场模拟面试</div>
                <div class="panel-desc">面试官按方向出题 → 你逐题作答 → 面试官点评并追问 → 全部答完后生成整场评分报告与历史对比。已绑定你的个人档案，题目会结合真实项目深挖（可在「我的档案」里维护）。</div>
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
            st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)
            if st.button("开始模拟面试", type="primary", use_container_width=True):
                _start_interview()
        if iv is not None and iv.get("stage") == "finished" and iv.get("report"):
            st.markdown('<div class="section-title">最近一次面试报告</div>', unsafe_allow_html=True)
            render_report(iv["report"], iv.get("comparison"))
        return

    total = len(iv["questions"])
    index = iv["index"] + 1
    project_note = f' · 含 {iv.get("project_count", 0)} 道项目深挖题' if iv.get("project_count") else ""
    st.markdown(f'<div class="small" style="display:flex;justify-content:space-between"><span>{iv["direction"]}{project_note}</span><span>{index} / {total}</span></div>', unsafe_allow_html=True)
    st.progress(min(iv["index"] / total, 1.0))

    current = iv["questions"][iv["index"]]
    render_question_card(current, iv["index"] + 1, total)

    if iv.get("reference"):
        with st.expander("参考答案", expanded=True):
            st.markdown(iv["reference"])
    elif st.button("查看参考答案", key="btn_ref"):
        _show_reference()
        st.rerun()

    if iv["stage"] == "question":
        answer = st.text_area(
            "你的回答",
            key=f"answer_{iv['qa_id']}",
            height=110,
            placeholder="按面试作答习惯组织：结论 → 展开 → 例子 → 风险点",
        )
        bc1, bc2, bc3 = st.columns([1, 1, 1])
        with bc1:
            if st.button("提交答案", type="primary", use_container_width=True, key="btn_submit"):
                if not answer.strip():
                    st.warning("先写下你的回答再提交。")
                else:
                    _submit_answer(answer.strip())
                    st.rerun()
        with bc2:
            if st.button("跳过本题", use_container_width=True, key="btn_skip"):
                _skip_question()
                st.rerun()
        with bc3:
            if st.button("结束面试并评分", use_container_width=True, key="btn_end1"):
                _finish_interview()
                st.rerun()
    elif iv["stage"] == "followup":
        render_feedback(iv["pending_feedback"], iv["pending_followup"], iv["pending_score_hint"])
        followup_answer = st.text_area(
            "追问回答",
            key=f"followup_{iv['qa_id']}",
            height=90,
            placeholder="针对追问继续作答…",
        )
        fc1, fc2 = st.columns([1, 1])
        with fc1:
            if st.button("提交追问回答", type="primary", use_container_width=True, key="btn_followup"):
                if not followup_answer.strip():
                    st.warning("先写下追问回答再提交。")
                else:
                    _submit_followup(followup_answer.strip())
                    st.rerun()
        with fc2:
            if st.button("结束面试并评分", use_container_width=True, key="btn_end2"):
                _finish_interview()
                st.rerun()

    st.divider()
    st.markdown('<div class="small">已答题目回顾</div>', unsafe_allow_html=True)
    for qa in load_qa(iv["id"])[:-1]:
        st.markdown(f"**{qa['question']}**")
        st.caption(f"回答：{qa['answer'][:120]}")


# ---------------- 面经复盘 ----------------
def render_review_tab() -> None:
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">面试复盘</div>
            <div class="panel-desc">把真实面试经历贴进来，AI 会整理出亮点、暴露的问题、必会知识点和行动清单。经历越具体，复盘越有效。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    text = st.text_area("面试经历", height=180, key="review_text", placeholder="例如：面了一家 AI 创业公司……问了 RAG 原理，我讲了流程但没答出向量检索细节……")
    if st.button("开始复盘", type="primary"):
        if not text.strip():
            st.warning("先粘贴面试经历再开始复盘。")
        else:
            with st.spinner("复盘教练正在分析…"):
                try:
                    result = InterviewManager().review_experience(text.strip())
                except InterviewError as exc:
                    st.error(f"复盘失败：{exc}")
                    return
            create_review(PROFILE_KEY, text.strip(), result)
            st.caption("已保存到「求职作战室」的历史复盘，可随时回看。")
            st.session_state["review_result"] = result
    result = st.session_state.get("review_result")
    if result:
        st.markdown('<div class="section-title">复盘结果</div>', unsafe_allow_html=True)
        st.markdown(f'**概括：** {html.escape(result.get("summary", ""))}')
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="report-sec"><div class="title">亮点</div>' + _ul(result.get("highlights", [])) + "</div>", unsafe_allow_html=True)
            st.markdown('<div class="report-sec"><div class="title">必会知识点</div>' + _ul(result.get("key_points", [])) + "</div>", unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="report-sec"><div class="title">暴露的问题</div>' + _ul(result.get("weaknesses", [])) + "</div>", unsafe_allow_html=True)
            st.markdown('<div class="report-sec"><div class="title">行动计划</div>' + _ul(result.get("action_plan", [])) + "</div>", unsafe_allow_html=True)


# ---------------- 求职作战室 ----------------
def _dimension_averages(reports: list[dict]) -> dict[str, float]:
    dims: dict[str, list[float]] = {d: [] for d in EVAL_DIMENSIONS}
    for r in reports:
        dim = r.get("dimensions") or {}
        for d in EVAL_DIMENSIONS:
            val = dim.get(d)
            if isinstance(val, (int, float)):
                dims[d].append(float(val))
    return {d: (sum(vals) / len(vals) if vals else 0.0) for d, vals in dims.items()}


def render_war_room_tab() -> None:
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">求职作战室</div>
            <div class="panel-desc">面试场次、得分趋势、薄弱维度与待办清单都在这里。完成模拟面试与面经复盘后自动更新。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    rows = [i for i in list_interviews(PROFILE_KEY) if i["status"] == "finished"]
    reports: list[dict] = []
    for i in rows:
        row = get_interview(i["id"])
        if row and row["report"]:
            try:
                reports.append({"interview": i, "report": json.loads(row["report"])})
            except Exception:
                pass

    scores = [int(r["report"].get("total_score", 0) or 0) for r in reports]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("完成场次", len(scores))
    with c2:
        st.metric("平均分", round(sum(scores) / len(scores), 1) if scores else "—")
    with c3:
        st.metric("最高分", max(scores) if scores else "—")
    with c4:
        st.metric("最近一次", scores[-1] if scores else "—")

    if not scores:
        st.info("还没有已完成场次。去「模拟面试」完成一场，或先「面经复盘」一次真实面试，这里就会长出你的成长曲线。")
        return

    st.markdown('<div class="section-title">得分趋势</div>', unsafe_allow_html=True)
    ordered = sorted(reports, key=lambda r: r["interview"]["finished_at"])
    st.line_chart({"得分": [int(r["report"].get("total_score", 0) or 0) for r in ordered]})

    st.markdown('<div class="section-title">薄弱维度</div>', unsafe_allow_html=True)
    avg = _dimension_averages([r["report"] for r in reports])
    weak = sorted(avg.items(), key=lambda kv: kv[1])[:3]
    for d, v in weak:
        st.markdown(f'<div class="small" style="display:flex;justify-content:space-between"><span>{d}</span><span>{round(v, 1)}</span></div>', unsafe_allow_html=True)
        st.progress(min(v, 100) / 100)
    st.caption("优先补分最低的维度，配合「历史报告」定位薄弱环节。")

    st.markdown('<div class="section-title">待办清单（来自评分建议 + 复盘行动计划）</div>', unsafe_allow_html=True)
    suggestions: list[str] = []
    for r in reports[-3:]:
        suggestions.extend(str(s) for s in (r["report"].get("suggestions", []) or []))
    for rv in list_reviews(PROFILE_KEY, limit=5):
        suggestions.extend(str(s) for s in (rv.get("action_plan", []) or []))
    seen: set[str] = set()
    todos = [s for s in suggestions if not (s in seen or seen.add(s))]
    done_key = "war_todo_done"
    st.session_state.setdefault(done_key, set())
    if not todos:
        st.markdown('<div class="muted">暂无待办，完成一场面试或一次复盘后会自动生成。</div>', unsafe_allow_html=True)
    for i, item in enumerate(todos):
        checked = st.checkbox(item, key=f"todo_{i}", value=i in st.session_state[done_key])
        if checked:
            st.session_state[done_key].add(i)
        else:
            st.session_state[done_key].discard(i)
    if todos and st.button("清空勾选"):
        st.session_state[done_key] = set()
        st.rerun()

    reviews = list_reviews(PROFILE_KEY)
    if reviews:
        st.markdown(f'<div class="section-title">历史复盘（{len(reviews)}）</div>', unsafe_allow_html=True)
        for rv in reviews:
            label = f"{rv['created_at'][:16].replace('T', ' ')} · {rv['summary'][:28]}"
            with st.expander(label):
                if rv.get("source_text"):
                    with st.expander("面试经历原文"):
                        st.markdown(rv["source_text"])
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown('<div class="report-sec"><div class="title">亮点</div>' + _ul(rv.get("highlights", [])) + "</div>", unsafe_allow_html=True)
                    st.markdown('<div class="report-sec"><div class="title">必会知识点</div>' + _ul(rv.get("key_points", [])) + "</div>", unsafe_allow_html=True)
                with c2:
                    st.markdown('<div class="report-sec"><div class="title">暴露的问题</div>' + _ul(rv.get("weaknesses", [])) + "</div>", unsafe_allow_html=True)
                    st.markdown('<div class="report-sec"><div class="title">行动计划</div>' + _ul(rv.get("action_plan", [])) + "</div>", unsafe_allow_html=True)
                if st.button("删除本条", key=f"del_rv_{rv['id']}"):
                    delete_review(rv["id"])
                    st.rerun()


# ---------------- 我的档案 ----------------
MAX_PROJECTS = 3


def render_profile_tab() -> None:
    store = ProfileStore(PROFILE_KEY)
    version = st.session_state.setdefault("profile_version", 0)
    if f"profile_form_{version}" not in st.session_state:
        st.session_state[f"profile_form_{version}"] = store.load()
    form = st.session_state[f"profile_form_{version}"]
    projects = form.get("projects") or []

    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">我的档案</div>
            <div class="panel-desc">填一次，模拟面试就会结合你的真实项目出深挖题，求职顾问也会给更贴合的规划建议。项目尽量写量化成果（F1、接口数、数据量），面试官最吃这一套。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("用默认示例填充", use_container_width=True):
            st.session_state[f"profile_form_{version}"] = DEFAULT_PROFILE
            st.session_state["profile_version"] = version + 1
            st.rerun()

    with st.form("profile_form"):
        cc1, cc2 = st.columns(2)
        with cc1:
            target_role = st.text_input("目标岗位", value=form.get("target_role", ""), key=f"pf_role_{version}")
        with cc2:
            target_direction = st.text_input("目标方向", value=form.get("target_direction", ""), key=f"pf_dir_{version}")
        skills = st.text_input("技能栈（逗号分隔）", value=", ".join(form.get("skills") or []), key=f"pf_skills_{version}")
        weak = st.text_input("薄弱点（逗号分隔）", value=", ".join(form.get("weak_areas") or []), key=f"pf_weak_{version}")
        st.markdown('<div class="section-title" style="margin-top:8px">项目经历（最多 3 个）</div>', unsafe_allow_html=True)

        filled: list[dict] = []
        for i in range(MAX_PROJECTS):
            p = projects[i] if i < len(projects) else {}
            st.markdown(f"**项目 {i + 1}**")
            cc1, cc2 = st.columns(2)
            with cc1:
                name = st.text_input("项目名称", value=p.get("name", ""), key=f"pf_p{i}_name_{version}")
            with cc2:
                tech = st.text_input("技术栈", value=p.get("tech_stack", ""), key=f"pf_p{i}_tech_{version}")
            desc = st.text_input("一句话描述", value=p.get("description", ""), key=f"pf_p{i}_desc_{version}")
            cc3, cc4 = st.columns(2)
            with cc3:
                metrics = st.text_input("量化成果", value=p.get("metrics", ""), key=f"pf_p{i}_metrics_{version}", placeholder="如：F1 0.92 / 接口 8 组 / 18 万条数据")
            with cc4:
                story = st.text_input("深挖点 / 故事", value=p.get("story", ""), key=f"pf_p{i}_story_{version}", placeholder="技术决策、踩坑或面试官会追问的点")
            if name.strip():
                filled.append(
                    {
                        "name": name.strip(),
                        "tech_stack": tech.strip(),
                        "description": desc.strip(),
                        "metrics": metrics.strip(),
                        "story": story.strip(),
                    }
                )
        submitted = st.form_submit_button("保存档案", type="primary")

    if submitted:
        saved = store.save(
            {
                "target_role": target_role.strip(),
                "target_direction": target_direction.strip(),
                "skills": [s.strip() for s in skills.split(",") if s.strip()],
                "weak_areas": [s.strip() for s in weak.split(",") if s.strip()],
                "projects": filled,
            }
        )
        st.session_state[f"profile_form_{version}"] = saved
        st.success("档案已保存：模拟面试将按你的目标岗位与项目经历个性化出题。")

    st.markdown('<div class="section-title">档案预览（将注入面试官 / 求职顾问）</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="panel" style="white-space:pre-wrap;font-size:13px;line-height:1.8">{html.escape(profile_context_text(form))}</div>', unsafe_allow_html=True)


# ---------------- 历史报告 ----------------
def render_history_tab() -> None:
    interviews = list_interviews(PROFILE_KEY)
    finished = [i for i in interviews if i["status"] == "finished"]
    ongoing = [i for i in interviews if i["status"] == "ongoing"]
    if ongoing:
        st.markdown(f'<div class="muted" style="margin-bottom:8px">进行中 {len(ongoing)} 场</div>', unsafe_allow_html=True)
        for o in ongoing:
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(f"**{o['direction']}** · 开始于 {o['created_at'][:16].replace('T', ' ')}")
            with c2:
                if st.button("删除", key=f"del_on_{o['id']}", use_container_width=True):
                    delete_interview(o["id"])
                    st.rerun()
    if not finished:
        if not ongoing:
            st.info("还没有历史报告。完成一场模拟面试后，评分报告会保存在这里。")
        return

    st.markdown(f'<div class="section-title">已完成场次（{len(finished)}）</div>', unsafe_allow_html=True)
    options = {
        f"{i['direction']} · {i['score']} 分 · {i['finished_at'][:16].replace('T', ' ')}": i["id"]
        for i in finished
    }
    label = st.selectbox("选择一场面试", list(options.keys()), key="history_select")
    iid = options[label]
    col_a, col_b = st.columns([5, 1])
    with col_b:
        if st.button("删除本场", use_container_width=True):
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

    st.markdown('<div class="section-title">本场问答记录</div>', unsafe_allow_html=True)
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
header_left, header_right = st.columns([2, 3])
with header_left:
    st.markdown(
        """
        <div class="app-header">
            <div class="logo">面</div>
            <div class="titles">
                <div class="title">面试备战助手</div>
                <div class="subtitle">多 Agent 模拟面试 · 整场评分 · 复盘</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with header_right:
    mode = st.segmented_control(
        "模式",
        [MODE_CHAT, MODE_INTERVIEW, MODE_REVIEW, MODE_WAR, MODE_HISTORY, MODE_PROFILE],
        key="mode",
        label_visibility="collapsed",
        default=MODE_CHAT,
    )

if mode == MODE_CHAT:
    chat_top = st.columns([4, 1])
    with chat_top[1]:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        if st.button("新建会话", use_container_width=True):
            new_session()
    render_chat_tab()
elif mode == MODE_INTERVIEW:
    render_interview_tab()
elif mode == MODE_REVIEW:
    render_review_tab()
elif mode == MODE_WAR:
    render_war_room_tab()
elif mode == MODE_HISTORY:
    render_history_tab()
else:
    render_profile_tab()

st.markdown('<div class="site-footer">面试备战助手 · 面试记录保存在本地 SQLite</div>', unsafe_allow_html=True)
