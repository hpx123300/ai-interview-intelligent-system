"""RAG 检索：Markdown 标题感知分块 + 混合检索。

检索策略（自动降级）：
1. 已安装 sentence-transformers + faiss -> 向量 + BM25 关键词 RRF 混合检索（m3e-base，索引持久化）
2. 否则 -> 纯 BM25 关键词检索（jieba 分词，零额外依赖）

文档指纹检测：知识库变更后自动重建索引。
"""

import hashlib
import json
import math
import re
from pathlib import Path

from ..config import (
    KNOWLEDGE_DIR,
    RAG_CHUNK_MAX_CHARS,
    RAG_CHUNK_OVERLAP_CHARS,
    RAG_INDEX_DIR,
    RAG_RRF_K,
)

try:
    import jieba
except Exception:  # pragma: no cover
    jieba = None

_EMBEDDING_MODEL = None


def _get_embedding_model():
    """模块级缓存 embedding 模型单例，避免每次检索重复加载模型。"""
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        from sentence_transformers import SentenceTransformer

        _EMBEDDING_MODEL = SentenceTransformer("moka-ai/m3e-base")
    return _EMBEDDING_MODEL


def _split_long(text: str, size: int, overlap: int) -> list[str]:
    """把过长的小节切成带重叠的窗口，避免边界处的上下文被截断。"""
    if len(text) <= size:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        parts.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return parts


def _split_chunks(text: str, source: str) -> list[dict]:
    """按 Markdown 标题（# / ## / ###）分块，保留章节标题作为上下文。

    过长小节会再切成 CHUNK_MAX_CHARS 的窗口、相邻窗口保留 CHUNK_OVERLAP_CHARS 重叠。
    """
    chunks: list[dict] = []
    current_title = source
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines
        body = "\n".join(current_lines).strip()
        current_lines = []
        if not body:
            return
        for piece in _split_long(body, RAG_CHUNK_MAX_CHARS, RAG_CHUNK_OVERLAP_CHARS):
            chunks.append({"title": current_title, "text": piece, "source": source})

    for line in text.splitlines():
        if re.match(r"^#{1,3}\s", line):
            flush()
            current_title = re.sub(r"^#{1,3}\s*", "", line).strip()
        else:
            current_lines.append(line)
    flush()
    return chunks


def _tokenize(text: str) -> list[str]:
    """中文用 jieba 分词，英文/数字用正则切分；无 jieba 时退化为正则。"""
    if jieba is None:
        return [t for t in re.split(r"[\s，。；、？（）()]+", text) if t]
    return [t for t in jieba.lcut(text) if t.strip()]


class BM25:
    """轻量 BM25 检索器。

    相比"原始词频计数"，BM25 引入 IDF（抑制高频无意义词）与文档长度归一化
    （抑制长文档天然占优），是关键词召回的标准基线。
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._tf: list[dict[str, int]] = []
        self._len: list[int] = []
        self._df: dict[str, int] = {}
        self._avgdl = 0.0
        self._n = 0

    def fit(self, docs: list[str]) -> "BM25":
        self._tf, self._len, self._df = [], [], {}
        for doc in docs:
            counts: dict[str, int] = {}
            for term in _tokenize(doc):
                counts[term] = counts.get(term, 0) + 1
            self._tf.append(counts)
            self._len.append(sum(counts.values()))
            for term in counts:
                self._df[term] = self._df.get(term, 0) + 1
        self._n = len(docs)
        self._avgdl = (sum(self._len) / self._n) if self._n else 0.0
        return self

    def _idf(self, term: str) -> float:
        df = self._df.get(term, 0)
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def score(self, query: str, index: int) -> float:
        counts = self._tf[index]
        dl = self._len[index] or 1
        avgdl = self._avgdl or 1.0
        total = 0.0
        for term in set(_tokenize(query)):
            tf = counts.get(term, 0)
            if not tf:
                continue
            denom = tf + self.k1 * (1 - self.b + self.b * dl / avgdl)
            total += self._idf(term) * tf * (self.k1 + 1) / denom
        return total


class KnowledgeBase:
    def __init__(self):
        self.chunks: list[dict] = []
        self._bm25 = BM25()
        self._embeddings = None
        self._index = None
        self._vector_enabled = False
        self._fingerprint = ""

    def _docs_fingerprint(self) -> str:
        h = hashlib.md5()
        for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
            h.update(path.read_bytes())
        return h.hexdigest()

    def load(self) -> None:
        fingerprint = self._docs_fingerprint()
        if self.chunks and fingerprint == self._fingerprint:
            return
        self._fingerprint = fingerprint
        chunks: list[dict] = []
        for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
            chunks.extend(_split_chunks(path.read_text(encoding="utf-8"), path.name))
        self.chunks = chunks
        self._bm25 = BM25().fit([f"{c['title']}\n{c['text']}" for c in chunks])
        self._load_vector_index()

    def _load_vector_index(self) -> None:
        """尝试加载/构建向量索引；失败则退化为纯 BM25 检索。"""
        try:
            import faiss
            import numpy as np

            meta_path = RAG_INDEX_DIR / "meta.json"
            if meta_path.exists() and json.loads(meta_path.read_text()).get("fingerprint") == self._fingerprint:
                self._embeddings = np.load(RAG_INDEX_DIR / "embeddings.npy")
                self._index = faiss.read_index(str(RAG_INDEX_DIR / "index.faiss"))
            else:
                model = _get_embedding_model()
                texts = [f"{c['title']}\n{c['text']}" for c in self.chunks]
                self._embeddings = model.encode(texts, normalize_embeddings=True)
                self._index = faiss.IndexFlatIP(self._embeddings.shape[1])
                self._index.add(self._embeddings)
                RAG_INDEX_DIR.mkdir(parents=True, exist_ok=True)
                np.save(RAG_INDEX_DIR / "embeddings.npy", self._embeddings)
                faiss.write_index(self._index, str(RAG_INDEX_DIR / "index.faiss"))
                (RAG_INDEX_DIR / "meta.json").write_text(
                    json.dumps({"fingerprint": self._fingerprint}, ensure_ascii=False), encoding="utf-8"
                )
            self._vector_enabled = True
        except Exception:
            self._vector_enabled = False
            self._embeddings = None
            self._index = None

    def _vector_search(self, query: str, k: int) -> list[dict]:
        import numpy as np

        q = _get_embedding_model().encode([query], normalize_embeddings=True)
        scores, idxs = self._index.search(np.asarray(q, dtype="float32"), min(k, len(self.chunks)))
        return [dict(self.chunks[i], score=float(scores[0][j])) for j, i in enumerate(idxs[0])]

    def _keyword_search(self, query: str, k: int) -> list[dict]:
        scored = []
        for i, chunk in enumerate(self.chunks):
            score = self._bm25.score(query, i)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: -x[0])
        return [dict(c, score=round(float(s), 4)) for s, c in scored[:k]]

    @staticmethod
    def _rrf_merge(ranked_lists: list[list[dict]], k: int = RAG_RRF_K) -> list[dict]:
        """Reciprocal Rank Fusion：融合多路召回结果，保留来源与融合得分。"""
        fused: dict[str, dict] = {}
        for results in ranked_lists:
            for rank, item in enumerate(results):
                key = f"{item.get('source')}::{item.get('title')}"
                if key not in fused:
                    fused[key] = dict(item)
                    fused[key]["rrf_score"] = 0.0
                    fused[key]["ranks"] = []
                fused[key]["rrf_score"] += 1.0 / (k + rank + 1)
                fused[key]["ranks"].append(rank + 1)
        merged = sorted(fused.values(), key=lambda x: -x["rrf_score"])
        for item in merged:
            item["score"] = round(item["rrf_score"], 4)
            item.pop("ranks", None)
        return merged

    def search(self, query: str, k: int = 3) -> list[dict]:
        self.load()
        if not self.chunks:
            return []
        keyword = self._keyword_search(query, k=max(k, 5))
        if not self._vector_enabled:
            return keyword[:k]
        try:
            vector = self._vector_search(query, k=max(k, 5))
            merged = self._rrf_merge([keyword, vector], k=RAG_RRF_K)
            return merged[:k]
        except Exception:
            return keyword[:k]


knowledge_base = KnowledgeBase()
