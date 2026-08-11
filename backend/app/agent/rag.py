"""RAG 检索：Markdown 标题感知分块 + 检索。

检索策略（自动降级）：
1. 已安装 sentence-transformers + faiss -> 向量 + 关键词 RRF 混合检索（m3e-base，索引持久化）
2. 否则 -> jieba 关键词加权评分（纯 Python，零额外依赖）
文档指纹检测：知识库变更后自动重建索引。
"""

import hashlib
import json
import re
from pathlib import Path

from ..config import KNOWLEDGE_DIR, RAG_INDEX_DIR

try:
    import jieba
except Exception:  # pragma: no cover
    jieba = None


def _split_chunks(text: str, source: str) -> list[dict]:
    """按 Markdown 标题（# / ## / ###）分块，保留章节上下文。"""
    chunks: list[dict] = []
    current_title = source
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines
        body = "\n".join(current_lines).strip()
        if body:
            chunks.append({"title": current_title, "text": body, "source": source})
        current_lines = []

    for line in text.splitlines():
        if re.match(r"^#{1,3}\s", line):
            flush()
            current_title = re.sub(r"^#{1,3}\s*", "", line).strip()
        else:
            current_lines.append(line)
    flush()
    return chunks


class KnowledgeBase:
    def __init__(self):
        self.chunks: list[dict] = []
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
        self._load_vector_index()

    def _load_vector_index(self) -> None:
        """尝试加载/构建向量索引；失败则使用 jieba 关键词检索。"""
        try:
            import faiss
            import numpy as np
            from sentence_transformers import SentenceTransformer

            model_name = "moka-ai/m3e-base"
            meta_path = RAG_INDEX_DIR / "meta.json"
            if meta_path.exists() and json.loads(meta_path.read_text()).get("fingerprint") == self._fingerprint:
                self._embeddings = np.load(RAG_INDEX_DIR / "embeddings.npy")
                self._index = faiss.read_index(str(RAG_INDEX_DIR / "index.faiss"))
            else:
                model = SentenceTransformer(model_name)
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
        except Exception as exc:
            self._vector_enabled = False
            self._embeddings = None
            self._index = None

    def _vector_search(self, query: str, k: int) -> list[dict]:
        import numpy as np
        from sentence_transformers import SentenceTransformer

        if self._embeddings is None:
            model = SentenceTransformer("moka-ai/m3e-base")
            self._embeddings = model.encode([f"{c['title']}\n{c['text']}" for c in self.chunks], normalize_embeddings=True)
        q = SentenceTransformer("moka-ai/m3e-base").encode([query], normalize_embeddings=True)
        scores, idxs = self._index.search(np.asarray(q, dtype="float32"), min(k, len(self.chunks)))
        return [dict(self.chunks[i], score=float(scores[0][j])) for j, i in enumerate(idxs[0])]

    def _keyword_search(self, query: str, k: int) -> list[dict]:
        if jieba is None:
            terms = [t for t in re.split(r"[\s，。；、？（）()0-9A-Za-z]+", query) if len(t) > 1]
        else:
            terms = [t for t in jieba.lcut(query) if len(t) > 1]
        scored = []
        for chunk in self.chunks:
            text = chunk["title"] + "\n" + chunk["text"]
            score = sum(text.count(t) for t in terms)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: -x[0])
        return [dict(c, score=float(s)) for s, c in scored[:k]]

    @staticmethod
    def _rrf_merge(ranked_lists: list[list[dict]], k: int = 60) -> list[dict]:
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
            merged = self._rrf_merge([keyword, vector], k=60)
            return merged[:k]
        except Exception:
            return keyword[:k]


knowledge_base = KnowledgeBase()
