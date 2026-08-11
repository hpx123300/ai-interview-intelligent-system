"""RAG 检索测试：分块、关键词检索、指纹。"""

from backend.app.agent.rag import KnowledgeBase, _split_chunks


def test_split_by_headers():
    text = "# 主题A\n内容A1\n内容A2\n\n## 小节\n内容B\n"
    chunks = _split_chunks(text, "test.md")
    assert len(chunks) == 2
    assert chunks[0]["title"] == "主题A"
    assert "内容A2" in chunks[0]["text"]
    assert chunks[1]["title"] == "小节"


def test_keyword_search_returns_relevant():
    kb = KnowledgeBase()
    kb.load()
    results = kb.search("什么是 GIL", k=3)
    assert results, "关键词检索应有结果"
    assert any("python_basics" in r["source"] for r in results)


def test_fingerprint_stable():
    kb1 = KnowledgeBase()
    kb1.load()
    kb2 = KnowledgeBase()
    kb2.load()
    assert kb1._fingerprint == kb2._fingerprint
