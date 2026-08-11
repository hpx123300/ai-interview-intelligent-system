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
        {"feedback": "结论正确，但缺了边界情况。", "followup": "并发高时怎么优化？", "score_hint": "7/10"},
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


def test_evaluate_interview_parses_dimensions():
    payload = json.dumps(
        {
            "total_score": 85,
            "dimensions": {"正确性": 90, "深度": 80, "结构": 85, "表达": 90, "风险意识": 75},
            "highlights": ["结论清晰"],
            "weaknesses": ["追问部分答得浅"],
            "missing_points": ["没有提到缓存"],
            "suggestions": ["补充性能优化练习"],
        },
        ensure_ascii=False,
    )

    def fake_create(**kw):
        return make_chat_response(payload)

    patcher = patch_client(fake_create)
    try:
        result = InterviewManager().evaluate_interview(
            [{"question": "Q1", "answer": "A1", "feedback": "F1", "followup": "FU", "followup_answer": "FA"}]
        )
    finally:
        patcher.stop()

    assert result["total_score"] == 85
    assert set(result["dimensions"].keys()) == set(EVAL_DIMENSIONS)
    assert result["suggestions"]


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
