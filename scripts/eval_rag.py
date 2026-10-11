"""RAG 检索质量评测：验证检索器能否把问题召回正确的来源文档。

指标口径（务必明确，避免误读）：
- 评测集：60 道题，覆盖 8 份知识库文档；
- 命中粒度：**文档级**——只要期望文档出现在 Top-K 结果中即算命中（非片段级）；
- Recall@K：命中题数 / 总题数；
- MRR：期望文档排名倒数的平均值（1/rank，未命中记 0）。

用法：python scripts/eval_rag.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agent.rag import knowledge_base

# (问题, 期望命中的来源文档)
EVAL_SET = [
    # ---- python_basics.md ----
    ("什么是 GIL", "python_basics.md"),
    ("装饰器怎么用", "python_basics.md"),
    ("深浅拷贝的区别", "python_basics.md"),
    ("生成器和迭代器有什么区别", "python_basics.md"),
    ("列表和字典的底层实现", "python_basics.md"),
    ("with 语句的原理是什么", "python_basics.md"),
    ("Python 的垃圾回收机制", "python_basics.md"),
    ("__init__ 和 __new__ 的区别", "python_basics.md"),
    ("asyncio 的原理", "python_basics.md"),
    ("多线程、多进程、协程怎么选", "python_basics.md"),
    ("可变对象和不可变对象的区别", "python_basics.md"),
    ("闭包是什么，有什么作用", "python_basics.md"),
    # ---- database.md ----
    ("MySQL 索引原理", "database.md"),
    ("为什么索引用 B+ 树", "database.md"),
    ("事务 ACID", "database.md"),
    ("隔离级别有哪些", "database.md"),
    ("慢查询怎么优化", "database.md"),
    ("索引失效的场景", "database.md"),
    ("主从复制和读写分离", "database.md"),
    ("乐观锁和悲观锁的区别", "database.md"),
    ("MVCC 的原理", "database.md"),
    ("Redis 缓存穿透、击穿、雪崩", "database.md"),
    ("分库分表怎么做", "database.md"),
    ("SQL 注入怎么防御", "database.md"),
    ("数据库连接池的作用", "database.md"),
    # ---- network.md ----
    ("TCP 三次握手", "network.md"),
    ("TCP 四次挥手为什么需要四次", "network.md"),
    ("HTTPS 原理", "network.md"),
    ("HTTP 常见状态码", "network.md"),
    ("GET 和 POST 的区别", "network.md"),
    ("DNS 解析过程", "network.md"),
    ("浏览器输入 URL 后发生了什么", "network.md"),
    ("TCP 和 UDP 的区别", "network.md"),
    ("Cookie、Session 和 Token 的区别", "network.md"),
    ("跨域是怎么产生的", "network.md"),
    ("TCP 粘包怎么解决", "network.md"),
    ("接口突然变慢怎么排查", "network.md"),
    # ---- os.md ----
    ("进程线程协程", "os.md"),
    ("死锁怎么避免", "os.md"),
    ("虚拟内存和分页", "os.md"),
    ("进程间通信有哪些方式", "os.md"),
    ("用户态和内核态的区别", "os.md"),
    ("上下文切换为什么开销大", "os.md"),
    ("IO 多路复用是什么", "os.md"),
    ("僵尸进程是怎么产生的", "os.md"),
    ("线程池和进程池怎么选", "os.md"),
    # ---- ai_agent.md ----
    ("Function Calling 是什么", "ai_agent.md"),
    ("RAG 流程", "ai_agent.md"),
    ("多 Agent 优缺点", "ai_agent.md"),
    ("Prompt 工程有哪些技巧", "ai_agent.md"),
    ("大模型幻觉怎么缓解", "ai_agent.md"),
    ("Token 和上下文窗口是什么", "ai_agent.md"),
    ("temperature 和 top_p 怎么调", "ai_agent.md"),
    ("RAG 的切块策略怎么选", "ai_agent.md"),
    ("Embedding 和向量库是什么", "ai_agent.md"),
    ("混合检索和 RRF 是什么", "ai_agent.md"),
    ("检索质量怎么评估", "ai_agent.md"),
    ("ReAct 模式是什么", "ai_agent.md"),
    ("Agent 的记忆怎么设计", "ai_agent.md"),
    ("微调和 RAG 怎么选", "ai_agent.md"),
    ("Agent 失败了怎么处理", "ai_agent.md"),
    # ---- interview_guide.md ----
    ("简历怎么写", "interview_guide.md"),
    ("自我介绍怎么讲", "interview_guide.md"),
    ("项目怎么用 STAR 讲", "interview_guide.md"),
    ("面试反问环节问什么", "interview_guide.md"),
    ("行为面试怎么准备", "interview_guide.md"),
    # ---- career_plan.md ----
    ("投递策略是什么", "career_plan.md"),
    ("offer 怎么选、转正怎么看", "career_plan.md"),
    ("技能矩阵怎么自查", "career_plan.md"),
    # ---- project_deep_dive.md ----
    ("讲项目的技术选型怎么说", "project_deep_dive.md"),
    ("项目经历怎么量化表达", "project_deep_dive.md"),
]

# 改述型问题：刻意不复用文档里的术语，检验真实语义召回能力。
# 纯 BM25（关键词）在这组上通常明显掉分——这正是需要开启向量检索的原因。
PARAPHRASE_SET = [
    ("为什么 Python 同一时刻只能有一个线程执行字节码", "python_basics.md"),
    ("怎么给函数动态加功能而不改它的代码", "python_basics.md"),
    ("变量复制之后改一个另一个也跟着变，怎么回事", "python_basics.md"),
    ("加了索引反而没走索引，可能是什么原因", "database.md"),
    ("两个人互相等对方释放资源，怎么预防", "os.md"),
    ("打开网页到看到内容中间发生了什么", "network.md"),
    ("大模型一本正经地胡说八道怎么办", "ai_agent.md"),
    ("怎么让模型只根据我自己的资料回答", "ai_agent.md"),
    ("第一次面试该问面试官什么", "interview_guide.md"),
    ("同时拿到好几个 offer 该怎么决定", "career_plan.md"),
]


def _evaluate(eval_set: list[tuple[str, str]], k: int = 3) -> dict:
    hits = 0
    rr_sum = 0.0
    details = []
    for question, expected_source in eval_set:
        results = knowledge_base.search(question, k=k)
        sources = [r["source"] for r in results]
        hit = expected_source in sources
        hits += hit
        rr = 0.0
        for rank, src in enumerate(sources, 1):
            if src == expected_source:
                rr = 1.0 / rank
                break
        rr_sum += rr
        details.append((question, expected_source, sources, hit))
    n = len(eval_set)
    return {
        "n": n,
        "recall": round(hits / n, 3),
        "mrr": round(rr_sum / n, 3),
        "details": details,
    }


def run_eval() -> dict:
    base = _evaluate(EVAL_SET)
    para = _evaluate(PARAPHRASE_SET)

    print("【A】术语型问题（复用文档术语）")
    for q, exp, got, hit in base["details"]:
        print(f"  {'✓' if hit else '✗'} {q[:20]:<22} 期望={exp:<20} 实际={got[:2]}")
    print(f"  -> n={base['n']}  Recall@3={base['recall']}  MRR={base['mrr']}")

    print("\n【B】改述型问题（不复用文档术语，检验语义召回）")
    for q, exp, got, hit in para["details"]:
        print(f"  {'✓' if hit else '✗'} {q[:22]:<24} 期望={exp:<20} 实际={got[:2]}")
    print(f"  -> n={para['n']}  Recall@3={para['recall']}  MRR={para['mrr']}")

    summary = {
        "vector_enabled": knowledge_base._vector_enabled,
        "base": {"n": base["n"], "recall@3": base["recall"], "mrr": base["mrr"]},
        "paraphrase": {"n": para["n"], "recall@3": para["recall"], "mrr": para["mrr"]},
    }
    mode = "向量 + BM25 混合" if summary["vector_enabled"] else "纯 BM25（未安装 faiss/sentence-transformers）"
    print(f"\n检索模式: {mode} | 命中粒度: 文档级")
    return summary


if __name__ == "__main__":
    run_eval()

