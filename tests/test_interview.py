"""面试闭环测试：mock 大模型，验证出题、点评追问、评分、对比与存储。"""

import json
from types import SimpleNamespace
from unittest import mock

from backend.app.interview import EVAL_DIMENSIONS, InterviewManager, _extract_json
from backend.app.interview_store import (
    create_interview,
    delete_interview,
    finish_interview,
    get_interview,
    load_qa,
    save_qa,
)


def make_chat_response(content):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def patch_client(create_side_effect):
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create_side_effect)))
    patcher = mock.patch("backend.app.interview.OpenAI", return_value=fake_client)
    patcher.start()
    return patcher


def test_extract_json_with_wrapper_text():
    assert _extract_json('好的\n{"total_score": 85}')["total_score"] == 85


def test_generate_question_list_falls_back_to_bank():
    """LLM 出题失败时回退题库，保证流程可用。"""

    def fake_create(**kw):
        return make_chat_response("这不是 JSON")

    patcher = patch_client(fake_create)
    try:
        manager = InterviewManager()
        questions = manager.generate_question_list("Python 后端", 8)
    finally:
        patcher.stop()

    assert len(questions) == 8
    assert all(q.get("question") for q in questions)


def test_generate_question_list_injects_project_questions():
    """带档案出题时插入项目深挖题；LLM 失败时回退模板。"""

    def fake_create(**kw):
        return make_chat_response("这不是 JSON")

    patcher = patch_client(fake_create)
    try:
        manager = InterviewManager()
        profile = {
            "projects": [
                {
                    "name": "投满分 BERT 分类",
                    "tech_stack": "PyTorch/BERT",
                    "description": "文本分类",
                    "metrics": "F1 0.9",
                    "story": "深挖点",
                },
                {
                    "name": "RAG 知识库问答",
                    "tech_stack": "LangChain/FAISS",
                    "description": "本地问答",
                    "metrics": "Recall@3 0.8",
                    "story": "深挖点",
                },
            ]
        }
        questions = manager.generate_question_list("通用开发", 8, profile=profile)
    finally:
        patcher.stop()

    assert len(questions) == 8
    project_qs = [q for q in questions if q.get("topic") == "project"]
    assert project_qs, "应包含项目深挖题"
    assert any("投满分" in q["question"] or "RAG 知识库问答" in q["question"] for q in project_qs)


def test_feedback_and_followup_parses():
    payload = json.dumps(
        {
            "feedback": "结论正确，但缺了边界情况。",
            "followup": "并发高时怎么优化？",
            "score": 4,
            "score_evidence": "提到了缓存但没展开",
            "score_hint": "满分 5 分，本次 4 分",
        },
        ensure_ascii=False,
    )

    def fake_create(**kw):
        return make_chat_response(payload)

    patcher = patch_client(fake_create)
    try:
        result = InterviewManager().feedback_and_followup("问题", "回答")
    finally:
        patcher.stop()

    assert result["feedback"] == "结论正确，但缺了边界情况。"
    assert result["followup"] == "并发高时怎么优化？"
    assert result["score"] == 4


def test_evaluate_interview_parses_scorecard():
    """新评分体系：逐题 rubric 评分（0-5）推导总分 + 叙事部分。"""
    narrative = json.dumps(
        {
            "dimensions": {"正确性": 90, "深度": 80, "结构": 85, "表达": 90, "风险意识": 75},
            "highlights": ["结论清晰"],
            "weaknesses": ["追问部分答得浅"],
            "missing_points": ["没有提到缓存"],
            "suggestions": ["补充性能优化练习"],
            "summary": "整体不错",
            "next_steps": ["补缓存设计", "多练追问"],
            "language_report": {"structure_score": 4, "clarity_score": 4, "conciseness_score": 3, "summary": "表达清晰"},
        },
        ensure_ascii=False,
    )

    def fake_create(**kw):
        system = kw["messages"][0]["content"]
        if "严谨公正的面试考核官" in system:
            return make_chat_response(json.dumps({"score": 4, "evidence": "结论正确，例子具体"}))
        if "应得 8-9 分" in system:
            return make_chat_response(json.dumps({"reference": "改进版参考答案"}))
        return make_chat_response(narrative)

    patcher = patch_client(fake_create)
    try:
        result = InterviewManager().evaluate_interview(
            [{"question": "Q1", "answer": "A1", "feedback": "F1", "followup": "FU", "followup_answer": "FA"}]
        )
    finally:
        patcher.stop()

    assert result["total_score"] == 80  # 4/5 * 20
    assert set(result["dimensions"].keys()) == set(EVAL_DIMENSIONS)
    assert result["suggestions"]
    assert result["competency_scores"][0]["score"] == 4
    assert result["competency_scores"][0]["level"] == "strong"
    assert result["next_steps"]
    assert result["coverage_pct"] == 1.0


def test_analyze_jd_and_gap_and_coach():
    """prep/post 新增方法：JD 画像、差距分析、学习教练。"""
    jd_payload = json.dumps(
        {
            "title": "大模型应用开发实习生",
            "company_name": "某公司",
            "seniority": "intern",
            "must_have": ["Python", "RAG"],
            "nice_to_have": ["Agent"],
            "responsibilities": ["开发 RAG 问答"],
            "tech_stack": ["Python", "FAISS"],
            "raw_text": "",
        },
        ensure_ascii=False,
    )
    gap_payload = json.dumps(
        {
            "strengths": ["有 RAG 项目"],
            "gaps": ["算法薄弱"],
            "probe_targets": ["RAG 评估"],
            "matched_skills": ["Python"],
            "missing_skills": ["Redis"],
            "summary": "整体匹配",
        },
        ensure_ascii=False,
    )
    module_payload = json.dumps(
        {"title": "补强：RAG 评估", "rationale": "失分在评估指标", "est_min": 30, "focus_points": ["Recall@K", "忠实度"]},
        ensure_ascii=False,
    )

    def fake_create(**kw):
        system = kw["messages"][0]["content"]
        if "把岗位描述解析为结构化岗位画像" in system:
            return make_chat_response(jd_payload)
        if "对比候选人与岗位要求" in system:
            return make_chat_response(gap_payload)
        return make_chat_response(module_payload)

    patcher = patch_client(fake_create)
    try:
        manager = InterviewManager()
        job = manager.analyze_jd("要求 Python 与 RAG")
        gap = manager.gap_analysis({"skills": ["Python", "RAG"], "projects": []}, job)
        plan = manager.coach_plan(
            {
                "weak_competencies": ["RAG 评估"],
                "competency_scores": [{"competency": "RAG 评估", "score": 1, "evidence": "指标说不清"}],
            }
        )
    finally:
        patcher.stop()

    assert job["title"] == "大模型应用开发实习生"
    assert gap["probe_targets"] == ["RAG 评估"]
    assert plan["modules"][0]["competency"] == "RAG 评估"
    assert plan["modules"][0]["est_min"] == 30


def test_design_interview_generates_plan():
    payload = json.dumps(
        {
            "title": "RAG 工程能力面试",
            "description": "考察 RAG 落地能力",
            "objective": "判断能否独立完成 RAG 开发",
            "assessment_criteria": [{"name": "检索设计", "description": "分块与混合检索"}],
            "questions": [
                {"text": "讲讲 RAG 流程", "type": "OPEN_ENDED", "follow_up_prompts": ["分块多大？"], "time_limit_seconds": None, "is_required": True}
            ],
            "recommended_settings": {"mode": "CHAT", "follow_up_depth": "MODERATE", "ai_tone": "PROFESSIONAL"},
        },
        ensure_ascii=False,
    )

    patcher = patch_client(lambda **kw: make_chat_response(payload))
    try:
        result = InterviewManager().design_interview("考察 RAG 落地能力")
    finally:
        patcher.stop()

    assert result["title"] == "RAG 工程能力面试"
    assert result["questions"][0]["text"] == "讲讲 RAG 流程"
    assert result["assessment_criteria"][0]["name"] == "检索设计"


def test_score_answer_handles_db_rubric_string():
    """DB 读回的 rubric 是 JSON 字符串，score_answer 不应崩溃（回归测试）。"""

    def fake_create(**kw):
        return make_chat_response(json.dumps({"score": 4, "evidence": "结论正确，例子具体"}))

    patcher = patch_client(fake_create)
    try:
        result = InterviewManager().score_answer(
            {
                "question": "Q1",
                "rubric": json.dumps(
                    [{"criterion": "正确性", "weight": 0.4, "description": "结论正确"}],
                    ensure_ascii=False,
                ),
            },
            "回答",
        )
    finally:
        patcher.stop()

    assert result["score"] == 4
    assert result["level"] == "strong"


def test_compare_without_history():
    patcher = patch_client(lambda **kw: make_chat_response("{}"))
    try:
        result = InterviewManager().compare_with_history({"total_score": 80}, [])
    finally:
        patcher.stop()
    assert result["history_count"] == 0


def test_interview_store_crud():
    iid = "test-iv-001"
    delete_interview(iid)
    create_interview(iid, "Python 后端")
    qa_id = save_qa(iid, question="Q1", topic="python", level="基础", hint="提示")
    finish_interview(iid, {"total_score": 85, "dimensions": {"正确性": 90}})

    row = get_interview(iid)
    assert row is not None
    assert row["status"] == "finished"
    assert row["score"] == 85

    qa = load_qa(iid)
    assert qa[0]["question"] == "Q1"
    assert qa[0]["topic"] == "python"
    assert qa_id > 0

    delete_interview(iid)
    assert get_interview(iid) is None
