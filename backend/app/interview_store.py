"""面试场次存储：创建/读取/更新面试与问答记录（SQLite）。"""

import json

from sqlalchemy import select

from .db import Interview, InterviewQA, get_session


def create_interview(
    interview_id: str,
    direction: str,
    profile_key: str = "local",
    plan: str = "",
    prep: str = "",
) -> None:
    with get_session() as session:
        session.add(
            Interview(
                id=interview_id,
                direction=direction,
                profile_key=profile_key,
                plan=plan,
                prep=prep,
            )
        )
        session.commit()


def get_interview(interview_id: str) -> dict | None:
    with get_session() as session:
        row = session.get(Interview, interview_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "direction": row.direction,
            "status": row.status,
            "score": row.score,
            "report": row.report,
            "plan": row.plan,
            "prep": row.prep,
            "created_at": row.created_at.isoformat(),
            "finished_at": row.finished_at.isoformat() if row.finished_at else "",
        }


def list_interviews(profile_key: str = "local", limit: int = 50) -> list[dict]:
    with get_session() as session:
        rows = (
            session.execute(
                select(Interview)
                .where(Interview.profile_key == profile_key)
                .order_by(Interview.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": r.id,
            "direction": r.direction,
            "status": r.status,
            "score": r.score,
            "plan": r.plan,
            "prep": r.prep,
            "created_at": r.created_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else "",
        }
        for r in rows
    ]


def finish_interview(interview_id: str, report: dict) -> None:
    from datetime import datetime, timezone

    with get_session() as session:
        row = session.get(Interview, interview_id)
        if row is None:
            return
        row.status = "finished"
        row.score = int(report.get("total_score", 0) or 0)
        row.report = json.dumps(report, ensure_ascii=False)
        row.finished_at = datetime.now(timezone.utc)
        session.commit()


def save_qa(
    interview_id: str,
    *,
    question: str,
    topic: str = "",
    level: str = "",
    hint: str = "",
    difficulty: int = 0,
    competency: str = "",
    rubric: str = "[]",
    seed_followups: str = "[]",
    answer: str = "",
    answer_score: int = 0,
    feedback: str = "",
    followup: str = "",
    followup_answer: str = "",
    reference: str = "",
) -> int:
    """保存一道面试题记录，返回新记录 id。"""
    with get_session() as session:
        row = InterviewQA(
            interview_id=interview_id,
            question=question,
            topic=topic,
            level=level,
            hint=hint,
            difficulty=difficulty,
            competency=competency,
            rubric=rubric,
            seed_followups=seed_followups,
            answer=answer,
            answer_score=answer_score,
            feedback=feedback,
            followup=followup,
            followup_answer=followup_answer,
            reference=reference,
        )
        session.add(row)
        session.commit()
        return row.id


def update_qa(
    qa_id: int,
    *,
    answer: str | None = None,
    answer_score: int | None = None,
    feedback: str | None = None,
    followup: str | None = None,
    followup_answer: str | None = None,
    reference: str | None = None,
) -> None:
    with get_session() as session:
        row = session.get(InterviewQA, qa_id)
        if row is None:
            return
        if answer is not None:
            row.answer = answer
        if answer_score is not None:
            row.answer_score = answer_score
        if feedback is not None:
            row.feedback = feedback
        if followup is not None:
            row.followup = followup
        if followup_answer is not None:
            row.followup_answer = followup_answer
        if reference is not None:
            row.reference = reference
        session.commit()


def load_qa(interview_id: str) -> list[dict]:
    with get_session() as session:
        rows = (
            session.execute(
                select(InterviewQA)
                .where(InterviewQA.interview_id == interview_id)
                .order_by(InterviewQA.id.asc())
            )
            .scalars()
            .all()
        )
    return [
        {
            "id": r.id,
            "question": r.question,
            "topic": r.topic,
            "level": r.level,
            "hint": r.hint,
            "difficulty": r.difficulty,
            "competency": r.competency,
            "rubric": r.rubric,
            "seed_followups": r.seed_followups,
            "answer": r.answer,
            "answer_score": r.answer_score,
            "feedback": r.feedback,
            "followup": r.followup,
            "followup_answer": r.followup_answer,
            "reference": r.reference,
        }
        for r in rows
    ]


def delete_interview(interview_id: str) -> None:
    with get_session() as session:
        session.query(InterviewQA).filter_by(interview_id=interview_id).delete()
        row = session.get(Interview, interview_id)
        if row is not None:
            session.delete(row)
        session.commit()
