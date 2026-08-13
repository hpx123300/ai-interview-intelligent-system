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
    "skills": [
        "Python", "FastAPI", "MySQL", "SQLite", "Docker",
        "Vue3", "React", "TypeScript", "DeepSeek",
        "RAG", "Agent", "Function Calling", "Prompt 工程",
    ],
    "weak_areas": ["算法题", "计算机网络", "操作系统"],
    "jd_text": "",
    "jd_analysis": {},
    "resume_text": "",
    "projects": [
        {
            "name": "大学生花钱助手（MoneyMate）",
            "tech_stack": "Python, FastAPI, SQLModel, Vue3, TypeScript, Docker, DeepSeek",
            "description": "面向大学生的记账 Web 应用：多钱包、月度预算、生活费规划、统计报表与 AI 记账助手，已部署上线提供在线演示。",
            "highlights": "AI 一句话记账（JSON mode + Pydantic 双重校验、失败自动降级）；AI 月度消费总结（SSE 流式 + 打字机效果）；FastAPI + SQLModel 8 组 REST API，JWT + Argon2 鉴权、Redis 缓存与固定窗口限流；Docker 多阶段构建 + GitHub Actions CI。",
            "metrics": "27 项接口测试全绿；近 4 个月演示数据；Render 在线部署（demo/demo123456）",
            "story": "从零独立完成全栈：先讲 AI 解析链路怎么保证输出可靠，再讲金额用 Decimal 而非 float、限流与缓存怎么设计；能回答为什么拆表、为什么用 Argon2。",
        },
        {
            "name": "AI 面试智能系统（本 Agent 项目）",
            "tech_stack": "Python, FastAPI, DeepSeek, Function Calling, RAG, SQLite, React, TypeScript",
            "description": "多 Agent + RAG 的面试陪练应用：主管路由 + 三专员（模拟面试官/八股讲师/求职顾问），prep/live/post 完整面试闭环与量化评估。",
            "highlights": "手写多 Agent Harness 与 Function Calling 循环（不依赖 LangGraph）；jieba 关键词 + FAISS/m3e 向量 RRF 混合检索；简历 PDF 与 JD 截图自动解析生成专属面试官；rubric 评分 + ScoreCard 报告 + 学习教练。",
            "metrics": "98 道题库 / 8 份知识库 / 16 条岗位库；实测 Recall@3=0.929、MRR=0.750、路由准确率 100%；23 项 pytest + CI 全绿",
            "story": "从零手写 Function Calling 循环而不是套框架，能讲清路由、记忆、轨迹、容错与评估设计；RAG 混合检索指标来自离线评测集实跑。",
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
