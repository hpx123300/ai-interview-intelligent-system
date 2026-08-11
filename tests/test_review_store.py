"""面经复盘存储测试：创建 / 读取 / 列表 / 删除。"""

from backend.app.review_store import create_review, delete_review, get_review, list_reviews


def test_review_crud():
    review_id = create_review(
        "local",
        "面了一家 AI 创业公司，问了 RAG 原理……",
        {
            "summary": "整体表现不错，RAG 细节需加强",
            "highlights": ["项目讲得清楚"],
            "weaknesses": ["向量检索细节答得浅"],
            "key_points": ["RAG 流程", "混合检索"],
            "action_plan": ["复习 RRF 融合公式", "重做一次模拟面试"],
        },
    )
    row = get_review(review_id)
    assert row is not None
    assert row["summary"].startswith("整体表现")
    assert row["highlights"] == ["项目讲得清楚"]
    assert "混合检索" in row["key_points"]

    rows = list_reviews("local")
    assert any(r["id"] == review_id for r in rows)

    delete_review(review_id)
    assert get_review(review_id) is None
