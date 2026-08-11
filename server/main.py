"""AI 面试备战助手 · FastAPI 后端（复用 backend.app 逻辑，服务新前端）。

聊天走 SSE 流式；面试闭环为无状态协议（客户端持有题单，服务端落库）；
构建后的前端由本服务静态托管（单页回退到 index.html）。
"""

import json
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi import File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.agent.core import AgentError, MultiAgentHarness  # noqa: E402
from backend.app.agent.memory import Memory  # noqa: E402
from backend.app.cards import parse_trace_cards  # noqa: E402
from backend.app.chat_history import clear_messages, load_messages, save_message  # noqa: E402
from backend.app.db import init_db  # noqa: E402
from backend.app.interview import DIRECTION_TOPICS, InterviewError, InterviewManager, _default_rubric  # noqa: E402
from backend.app.interview_store import (  # noqa: E402
    create_interview,
    delete_interview,
    finish_interview,
    get_interview,
    list_interviews,
    load_qa,
    save_qa,
    update_qa,
)
from backend.app.profile import DEFAULT_PROFILE_KEY as PROFILE_KEY, ProfileStore  # noqa: E402
from backend.app.review_store import create_review, delete_review, list_reviews  # noqa: E402

init_db()

app = FastAPI(title="AI 面试备战助手 API", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = ProfileStore(PROFILE_KEY)


def _err(exc: Exception, status: int = 500) -> JSONResponse:
    return JSONResponse({"error": str(exc)}, status_code=status)


OCR_SWIFT = Path(__file__).resolve().parent / "ocr_vision.swift"


# ---------------- 健康检查 ----------------
@app.get("/api/health")
def health():
    return {"ok": True}


# ---------------- JD 图片 OCR ----------------
@app.post("/api/jd/ocr")
async def jd_ocr(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        return JSONResponse({"error": "图片内容为空"}, status_code=400)
    if not shutil.which("swift"):
        return JSONResponse({"error": "本机未安装 Swift，无法识别图片；请直接在档案页粘贴 JD 文本"}, status_code=400)
    suffix = Path(file.filename or "jd.png").suffix or ".png"
    tmp_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        proc = subprocess.run(
            ["swift", str(OCR_SWIFT), tmp_path],
            capture_output=True,
            text=True,
            timeout=90,
        )
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "OCR 识别超时，请换一张更清晰的截图"}, status_code=400)
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
    if proc.returncode != 0 or not (proc.stdout or "").strip():
        detail = (proc.stderr or "").strip()[:200]
        return JSONResponse({"error": f"OCR 识别失败：{detail or '图片无法识别'}"}, status_code=400)
    return {"text": proc.stdout.strip(), "ocr": "vision"}


# ---------------- 简历 PDF 自动识别 ----------------
@app.post("/api/resume/parse")
async def resume_parse(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        return JSONResponse({"error": "文件内容为空"}, status_code=400)
    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pass
        text = "\n".join(pages).strip()
    except Exception as exc:
        return JSONResponse({"error": f"PDF 解析失败：{exc}"}, status_code=400)
    if not text:
        return JSONResponse(
            {"error": "该 PDF 是扫描件/无文本层，无法直接提取；请把简历关键页截图后使用「JD 图片识别」"},
            status_code=400,
        )
    try:
        parsed = InterviewManager().parse_resume(text)
    except Exception as exc:
        return JSONResponse({"error": f"简历解析失败：{exc}"}, status_code=400)
    return {"text": text[:6000], "parsed": parsed}


# ---------------- 对话（SSE） ----------------
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if not req.message.strip():
        return JSONResponse({"error": "消息不能为空"}, status_code=400)
    session_id = (req.session_id or "").strip() or f"web-{uuid.uuid4().hex[:8]}"
    try:
        agent = MultiAgentHarness(memory=Memory(session_id, max_messages=40))
    except AgentError as exc:
        return _err(exc, 400)
    save_message(session_id, "user", req.message.strip())

    def gen():
        full = ""
        cards_sent = False
        try:
            yield f"data: {json.dumps({'type': 'session', 'session_id': session_id}, ensure_ascii=False)}\n\n"
            for chunk in agent.chat_stream(req.message, on_tool=lambda name: None):
                if chunk:
                    full += chunk
                    yield f"data: {json.dumps({'type': 'token', 'text': chunk}, ensure_ascii=False)}\n\n"
            trace = list(agent.trace)
            if trace:
                yield f"data: {json.dumps({'type': 'trace', 'trace': trace}, ensure_ascii=False)}\n\n"
            cards = parse_trace_cards(trace)
            if cards:
                cards_sent = True
                yield f"data: {json.dumps({'type': 'cards', 'cards': cards}, ensure_ascii=False)}\n\n"
            if full:
                save_message(session_id, "assistant", full)
            yield "data: {\"type\": \"done\"}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------------- 对话历史 ----------------
@app.get("/api/chat/history")
def chat_history(session_id: str):
    return load_messages(session_id, limit=100)


@app.delete("/api/chat/history")
def chat_history_clear(session_id: str):
    clear_messages(session_id)
    return {"ok": True}


# ---------------- 档案 ----------------
class ProfileSave(BaseModel):
    profile: dict[str, Any]


@app.get("/api/profile")
def get_profile():
    return store.load()


@app.put("/api/profile")
def put_profile(req: ProfileSave):
    try:
        current = store.load()
        merged = {**current, **req.profile}
        return store.save(merged)
    except Exception as exc:
        return _err(exc)


class AnalyzeJdRequest(BaseModel):
    jd_text: str
    profile: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/profile/analyze-jd")
def analyze_jd(req: AnalyzeJdRequest):
    try:
        manager = InterviewManager()
        job = manager.analyze_jd(req.jd_text or "")
        profile = req.profile or store.load()
        gap = manager.gap_analysis(profile, job)
        return {**job, "gap": gap}
    except InterviewError as exc:
        return _err(exc, 400)
    except Exception as exc:
        return _err(exc)


# ---------------- 面试 ----------------
class InterviewStart(BaseModel):
    direction: str = "通用开发"
    count: int = 6
    design: dict[str, Any] | None = None


def _question_payload(q: dict) -> dict:
    return {
        "id": q.get("id", ""),
        "question": q.get("question", ""),
        "topic": q.get("topic", ""),
        "level": q.get("level", ""),
        "hint": q.get("hint", ""),
        "difficulty": int(q.get("difficulty", 0) or 0),
        "competency": q.get("competency", ""),
        "rubric": q.get("rubric", []) or [],
        "followups": q.get("followups", []) or [],
    }


def _design_to_questions(design: dict) -> list[dict]:
    criteria = ((design.get("assessment_criteria") or [{}])[0]).get("name", "综合能力")
    topic_map = {"BEHAVIOR": "behavior", "CODING": "algorithm", "RESEARCH": "ai", "TECHNICAL": "ai"}
    questions: list[dict] = []
    for i, dq in enumerate((design.get("questions") or [])[:10]):
        qtype = (dq.get("type") or "").upper()
        followups = [str(f) for f in (dq.get("follow_up_prompts") or [])]
        questions.append(
            {
                "id": f"dq{i}",
                "question": dq.get("text", ""),
                "topic": topic_map.get(qtype, "ai"),
                "level": "场景",
                "hint": "；".join(followups[:2]) or "按 STAR / 结论先行组织回答",
                "difficulty": 3,
                "competency": criteria,
                "rubric": _default_rubric({"topic": "ai"}),
                "followups": followups or ["能展开讲讲关键细节吗？"],
            }
        )
    return questions


@app.post("/api/interview/start")
def interview_start(req: InterviewStart):
    try:
        manager = InterviewManager()
        profile = store.load()
        if req.design:
            questions = _design_to_questions(req.design)
            direction = f"自定义：{req.design.get('title', '面试')}"[:20]
            prep = {"design": req.design}
            interviewer_context = req.design
        else:
            jd_analysis = profile.get("jd_analysis") or {}
            job_spec = {k: v for k, v in jd_analysis.items() if k != "gap"}
            gap = jd_analysis.get("gap") or None
            questions = manager.generate_question_list(
                req.direction,
                req.count,
                profile=profile,
                jd_analysis=job_spec or None,
                gap=gap,
            )
            direction = req.direction
            prep = {"jd_analysis": job_spec, "gap": gap}
            interviewer_context = job_spec or gap
        try:
            interviewer = manager.generate_interviewer(interviewer_context or None)
        except Exception:
            interviewer = manager.generate_interviewer(None)
        prep["interviewer"] = interviewer
        if not questions:
            raise InterviewError("没有生成有效题目")
        iid = f"iv-{uuid.uuid4().hex[:8]}"
        create_interview(
            iid,
            direction,
            plan=json.dumps(questions, ensure_ascii=False),
            prep=json.dumps(prep, ensure_ascii=False),
        )
        first = questions[0]
        qa_id = save_qa(
            iid,
            question=first["question"],
            topic=first.get("topic", ""),
            level=first.get("level", ""),
            hint=first.get("hint", ""),
            difficulty=int(first.get("difficulty", 0) or 0),
            competency=first.get("competency", ""),
            rubric=json.dumps(first.get("rubric", []), ensure_ascii=False),
            seed_followups=json.dumps(first.get("followups", []), ensure_ascii=False),
        )
        project_count = sum(1 for q in questions if q.get("topic") == "project")
        return {
            "interview_id": iid,
            "questions": [_question_payload(q) for q in questions],
            "project_count": project_count,
            "qa_id": qa_id,
            "direction": direction,
            "interviewer": interviewer,
        }
    except (InterviewError, AgentError) as exc:
        return _err(exc, 400)
    except Exception as exc:
        return _err(exc)


class InterviewDesignRequest(BaseModel):
    goal: str
    jd_text: str = ""
    resume_text: str = ""
    duration: int = 15


@app.post("/api/interview/design")
def interview_design(req: InterviewDesignRequest):
    try:
        design = InterviewManager().design_interview(
            req.goal,
            jd_text=req.jd_text,
            resume_text=req.resume_text,
            duration=req.duration,
        )
        return design
    except InterviewError as exc:
        return _err(exc, 400)
    except Exception as exc:
        return _err(exc)


class AnswerRequest(BaseModel):
    interview_id: str
    qa_id: int
    question: dict[str, Any]
    answer: str


@app.post("/api/interview/answer")
def interview_answer(req: AnswerRequest):
    try:
        manager = InterviewManager()
        result = manager.feedback_and_followup(
            req.question.get("question", ""),
            req.answer,
            rubric=req.question.get("rubric"),
            competency=req.question.get("competency", ""),
        )
        update_qa(
            req.qa_id,
            answer=req.answer,
            answer_score=int(result.get("score", 0) or 0),
            feedback=result.get("feedback", ""),
            followup=result.get("followup", ""),
        )
        return result
    except InterviewError as exc:
        return _err(exc, 400)
    except Exception as exc:
        return _err(exc)


class FollowupRequest(BaseModel):
    qa_id: int
    answer: str


@app.post("/api/interview/followup")
def interview_followup(req: FollowupRequest):
    try:
        update_qa(req.qa_id, followup_answer=req.answer)
        return {"ok": True}
    except Exception as exc:
        return _err(exc)


class NextRequest(BaseModel):
    interview_id: str
    question: dict[str, Any]


@app.post("/api/interview/next")
def interview_next(req: NextRequest):
    try:
        q = req.question
        qa_id = save_qa(
            req.interview_id,
            question=q.get("question", ""),
            topic=q.get("topic", ""),
            level=q.get("level", ""),
            hint=q.get("hint", ""),
            difficulty=int(q.get("difficulty", 0) or 0),
            competency=q.get("competency", ""),
            rubric=json.dumps(q.get("rubric", []), ensure_ascii=False),
            seed_followups=json.dumps(q.get("followups", []), ensure_ascii=False),
        )
        return {"qa_id": qa_id}
    except Exception as exc:
        return _err(exc)


class SkipRequest(BaseModel):
    qa_id: int


@app.post("/api/interview/skip")
def interview_skip(req: SkipRequest):
    try:
        update_qa(req.qa_id, answer="（跳过）")
        return {"ok": True}
    except Exception as exc:
        return _err(exc)


class ReferenceRequest(BaseModel):
    qa_id: int
    question: str
    answer: str = ""


@app.post("/api/interview/reference")
def interview_reference(req: ReferenceRequest):
    try:
        ref = InterviewManager().reference_answer(req.question, req.answer or "")
        update_qa(req.qa_id, reference=ref)
        return {"reference": ref}
    except Exception as exc:
        return _err(exc)


class FinishRequest(BaseModel):
    interview_id: str


@app.post("/api/interview/finish")
def interview_finish(req: FinishRequest):
    try:
        manager = InterviewManager()
        qa_list = load_qa(req.interview_id)
        answered = [q for q in qa_list if q.get("answer") and q["answer"] != "（跳过）"]
        if not answered:
            return JSONResponse({"error": "本场还没有有效作答，无法评分"}, status_code=400)
        report = manager.evaluate_interview(qa_list)
        try:
            report["coach_plan"] = manager.coach_plan(report)
        except Exception:
            report["coach_plan"] = {"summary": "暂未生成学习计划", "modules": [], "total_min": 0}
        history = [
            json.loads(r["report"])
            for r in list_interviews(PROFILE_KEY)
            if r["status"] == "finished" and r["id"] != req.interview_id and r["report"]
        ]
        comparison = manager.compare_with_history(report, history)
        finish_interview(req.interview_id, report)
        return {"report": report, "comparison": comparison}
    except InterviewError as exc:
        return _err(exc, 400)
    except Exception as exc:
        return _err(exc)


# ---------------- 历史 / 作战室 ----------------
@app.get("/api/interviews")
def interviews_list():
    return list_interviews(PROFILE_KEY)


@app.get("/api/interviews/{interview_id}")
def interviews_detail(interview_id: str):
    row = get_interview(interview_id)
    if row is None:
        return JSONResponse({"error": "场次不存在"}, status_code=404)
    report = None
    if row.get("report"):
        try:
            report = json.loads(row["report"])
        except Exception:
            report = None
    return {"interview": row, "report": report, "qa_list": load_qa(interview_id)}


@app.delete("/api/interviews/{interview_id}")
def interviews_delete(interview_id: str):
    delete_interview(interview_id)
    return {"ok": True}


@app.get("/api/dashboard")
def dashboard():
    interviews = [i for i in list_interviews(PROFILE_KEY) if i["status"] == "finished"]
    reports = []
    for i in interviews:
        row = get_interview(i["id"])
        if row and row["report"]:
            try:
                reports.append({"interview": i, "report": json.loads(row["report"])})
            except Exception:
                pass
    scores = [int(r["report"].get("total_score", 0) or 0) for r in reports]
    dim_names = ["正确性", "深度", "结构", "表达", "风险意识"]
    dim_scores: dict[str, list[float]] = {d: [] for d in dim_names}
    for r in reports:
        dim = r["report"].get("dimensions") or {}
        for d in dim_names:
            v = dim.get(d)
            if isinstance(v, (int, float)):
                dim_scores[d].append(float(v))
    weak_dimensions = [
        {"name": d, "score": round(sum(vs) / len(vs), 1) if vs else 0}
        for d, vs in sorted(dim_scores.items(), key=lambda kv: (sum(kv[1]) / len(kv[1])) if kv[1] else 999)
    ][:3]
    ordered = sorted(reports, key=lambda r: r["interview"]["finished_at"])
    todos: list[str] = []
    for r in reports[-3:]:
        todos.extend(str(s) for s in (r["report"].get("suggestions", []) or []))
        todos.extend(str(s) for s in (r["report"].get("next_steps", []) or []))
        for m in (r["report"].get("coach_plan", {}) or {}).get("modules", []) or []:
            todos.append(f"学习模块：{m.get('title', '')}（{m.get('est_min', '?')} 分钟）")
    seen: set[str] = set()
    todos = [t for t in todos if not (t in seen or seen.add(t))]
    return {
        "total_sessions": len(scores),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "max_score": max(scores) if scores else None,
        "last_score": scores[-1] if scores else None,
        "trend": [int(r["report"].get("total_score", 0) or 0) for r in ordered],
        "weak_dimensions": weak_dimensions,
        "todos": todos,
        "reviews": list_reviews(PROFILE_KEY, limit=10),
    }


# ---------------- 面经复盘 ----------------
class ReviewRequest(BaseModel):
    text: str


@app.post("/api/reviews")
def reviews_create(req: ReviewRequest):
    try:
        result = InterviewManager().review_experience(req.text or "")
        rid = create_review(PROFILE_KEY, (req.text or "")[:6000], result)
        return {"review": {**result, "id": rid}}
    except InterviewError as exc:
        return _err(exc, 400)
    except Exception as exc:
        return _err(exc)


@app.get("/api/reviews")
def reviews_list():
    return list_reviews(PROFILE_KEY)


@app.delete("/api/reviews/{review_id}")
def reviews_delete(review_id: int):
    delete_review(review_id)
    return {"ok": True}


# ---------------- 静态前端 ----------------
WEB_DIST = PROJECT_ROOT / "web" / "dist"

if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api/"):
        return JSONResponse({"error": "接口不存在"}, status_code=404)
    index = WEB_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse(
        {
            "error": "前端尚未构建：请先运行 pnpm install && pnpm build（或在 web/ 下运行 pnpm dev 开发模式）"
        },
        status_code=404,
    )
