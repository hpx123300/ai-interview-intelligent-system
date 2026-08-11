"""候选人档案：默认档案、SQLite 读写、档案上下文文本（驱动个性化出题）。"""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from .db import UserProfile, get_session

DEFAULT_PROFILE_KEY = "local"

DEFAULT_PROFILE: dict[str, Any] = {
    "profile_key": DEFAULT_PROFILE_KEY,
    "target_role": "大模型 / AI 应用开发实习生",
    "target_direction": "大模型 / AI 应用开发",
    "skills": ["Python", "RAG", "Agent", "Function Calling", "SQLite", "Streamlit"],
    "weak_areas": ["算法题", "计算机网络"],
    "jd_text": "",
    "jd_analysis": {},
    "resume_text": "",
    "projects": [
        {
            "name": "投满分：BERT 文本分类与模型优化",
            "tech_stack": "PyTorch, BERT, 知识蒸馏, 模型剪枝",
            "description": "基于 BERT 的中文新闻标题文本分类项目，覆盖数据清洗、训练、评估与模型压缩优化。",
            "highlights": "对比随机森林/FastText/BERT 三类方案，最终以 BERT 提升准确率，并通过蒸馏与量化压缩模型。",
            "metrics": "训练集 18 万条；评估覆盖准确率/召回/精确率/F1；蒸馏+量化后模型显著变小",
            "story": "从传统机器学习到深度学习的完整链路，能讲清楚为什么 BERT 更强、压缩后怎么验证效果。",
        },
        {
            "name": "本地知识库问答（LangChain + ChatGLM）",
            "tech_stack": "LangChain, ChatGLM2-6B, FAISS, m3e",
            "description": "企业私有知识库问答：文档切块、向量化、FAISS 检索、LLM 基于上下文生成回答。",
            "highlights": "解决私有知识安全与最新知识获取问题，走通『切块→向量化→检索→生成』完整链路。",
            "metrics": "离线私有化部署；m3e-base 向量检索 + ChatGLM2-6B-int4 生成",
            "story": "能讲 RAG 全流程、切块与检索的取舍，以及版本兼容等工程踩坑。",
        },
        {
            "name": "AI 面试智能系统（本 Agent 项目）",
            "tech_stack": "Python, DeepSeek, Function Calling, RAG, SQLite, Streamlit",
            "description": "多 Agent + RAG 的面试陪练应用：主管路由 + 三个专员，完整面试闭环与量化评估。",
            "highlights": "手写多 Agent Harness；关键词+向量 RRF 混合检索；面试闭环状态机；14+ 项自动化测试。",
            "metrics": "90 道题库 / 8 份知识库文档 / 16 条岗位库；Recall@K、MRR、路由准确率等离线评估",
            "story": "从零手写 Function Calling 循环而不是套框架，能讲清路由、记忆、轨迹、容错与评估设计。",
        },
    ],
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def default_profile() -> dict[str, Any]:
    """深拷贝默认档案，避免外部修改污染默认值。"""
    return json.loads(json.dumps(DEFAULT_PROFILE, ensure_ascii=False))


class ProfileStore:
    """个人档案的 SQLite 持久化与读取。"""

    def __init__(self, profile_key: str = DEFAULT_PROFILE_KEY):
        self.profile_key = profile_key

    def load(self) -> dict[str, Any]:
        with get_session() as session:
            row = session.get(UserProfile, self.profile_key)
        if row is None:
            return default_profile()
        return {
            "profile_key": row.profile_key,
            "target_role": row.target_role,
            "target_direction": row.target_direction,
            "skills": json.loads(row.skills or "[]"),
            "weak_areas": json.loads(row.weak_areas or "[]"),
            "projects": json.loads(row.projects or "[]"),
            "jd_text": row.jd_text,
            "jd_analysis": json.loads(row.jd_analysis or "{}"),
            "resume_text": row.resume_text,
            "updated_at": row.updated_at.isoformat(),
        }

    def save(self, data: dict[str, Any]) -> dict[str, Any]:
        clean = {
            "profile_key": self.profile_key,
            "target_role": str(data.get("target_role", "")).strip(),
            "target_direction": str(data.get("target_direction", "")).strip(),
            "skills": json.dumps(data.get("skills", []) or [], ensure_ascii=False),
            "weak_areas": json.dumps(data.get("weak_areas", []) or [], ensure_ascii=False),
            "projects": json.dumps(data.get("projects", []) or [], ensure_ascii=False),
            "jd_text": str(data.get("jd_text", "")),
            "jd_analysis": json.dumps(data.get("jd_analysis", {}) or {}, ensure_ascii=False),
            "resume_text": str(data.get("resume_text", "")),
        }
        with get_session() as session:
            row = session.get(UserProfile, self.profile_key)
            if row is None:
                row = UserProfile(profile_key=self.profile_key)
                session.add(row)
            row.target_role = clean["target_role"]
            row.target_direction = clean["target_direction"]
            row.skills = clean["skills"]
            row.weak_areas = clean["weak_areas"]
            row.projects = clean["projects"]
            row.jd_text = clean["jd_text"]
            row.jd_analysis = clean["jd_analysis"]
            row.resume_text = clean["resume_text"]
            row.updated_at = _now()
            session.commit()
        return self.load()


def profile_context_text(profile: dict[str, Any]) -> str:
    """把档案转成注入提示词的纯文本摘要。"""
    parts = [
        f"目标岗位：{profile.get('target_role') or '未填写'}",
        f"目标方向：{profile.get('target_direction') or '未填写'}",
    ]
    skills = profile.get("skills") or []
    if skills:
        parts.append("技能栈：" + "、".join(skills))
    weak = profile.get("weak_areas") or []
    if weak:
        parts.append("薄弱点：" + "、".join(weak))
    jd_analysis = profile.get("jd_analysis") or {}
    if jd_analysis:
        jd = jd_analysis.get("title") or "目标岗位 JD"
        parts.append(f"目标 JD 画像：{jd}（必须项：{'、'.join(jd_analysis.get('must_have', [])[:5]) or '未解析'}）")
    projects = profile.get("projects") or []
    if projects:
        parts.append("项目经历：")
        for p in projects:
            name = p.get("name") or ""
            tech = p.get("tech_stack") or ""
            desc = p.get("description") or ""
            metrics = p.get("metrics") or ""
            parts.append(f"- {name}（{tech}）：{desc}；量化成果：{metrics}")
    return "\n".join(parts)
