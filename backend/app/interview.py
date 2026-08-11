"""面试闭环核心：prep（JD 画像/差距分析/面试设计/问题计划）→ live（点评追问+逐题评分）→ post（ScoreCard 评分/学习教练/复盘）。

设计借鉴：DeepInterview（Apache-2.0）的 prep/live/post 三段式与 rubric 评分；
聆悟 ai-interview-platform（MIT）的自然语言面试设计与统一评分标准。
代码为本项目重写实现。
"""

import json
import re

from openai import OpenAI

from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, PROJECT_ROOT
from .llm_utils import with_retry
from .profile import profile_context_text
from .tools import query_question, search_knowledge

# 面试方向 -> 题库主题（用于出题检索）
DIRECTION_TOPICS = {
    "Python 后端": ["python", "database", "network", "os", "algorithm"],
    "AI 应用开发": ["ai", "python", "database", "project"],
    "通用开发": ["python", "database", "network", "os", "ai", "algorithm", "project"],
    "行为面试（STAR）": ["behavior", "project", "ai"],
}

EVAL_DIMENSIONS = ["正确性", "深度", "结构", "表达", "风险意识"]

PACKS_DIR = PROJECT_ROOT / "data" / "packs"

_LEVEL_DIFFICULTY = {"基础": 2, "进阶": 3, "场景": 4, "行为": 3}


class InterviewError(Exception):
    pass


def _extract_json(text: str) -> dict:
    """从模型回复中稳健提取 JSON 对象。"""
    text = (text or "").strip()
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except (TypeError, ValueError):
            pass
    raise InterviewError("模型未返回结构化结果，请重试")


def level_for_score(score: float) -> str:
    """0-5 分数 → 掌握等级（>=4 strong / >=3 solid / >=2 developing / weak）。"""
    if score >= 4:
        return "strong"
    if score >= 3:
        return "solid"
    if score >= 2:
        return "developing"
    return "weak"


def _default_rubric(question: dict) -> list[dict]:
    """默认评分标准：正确性 / 深度与逻辑 / 结构与表达（权重和≈1）。"""
    return [
        {"criterion": "正确性", "weight": 0.4, "description": "结论正确、关键点无遗漏"},
        {"criterion": "深度与逻辑", "weight": 0.3, "description": "能讲清原理与取舍，逻辑连贯"},
        {"criterion": "结构与表达", "weight": 0.3, "description": "结论先行、结构清晰、表达自然"},
    ]


def _as_rubric_list(rubric) -> list[dict]:
    """兼容 rubric 的两种形态：list 或 JSON 字符串（DB 读回时为字符串）。"""
    if isinstance(rubric, str):
        try:
            parsed = json.loads(rubric)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return []
    if isinstance(rubric, list):
        return rubric
    return []


def _followups_from_hint(hint: str, topic: str) -> list[str]:
    if topic == "behavior":
        return ["能再给一个具体的例子吗？", "如果换一种情境，你会怎么做？"]
    if hint:
        return [f"关于「{hint}」能再深入讲讲吗？", "有没有实际案例或数据支撑？"]
    return ["能展开讲讲关键细节吗？", "有没有实际案例或数据支撑？"]


def _normalize_question(q: dict, idx: int = 0) -> dict:
    """把题目补齐为完整计划结构（difficulty / competency / rubric / followups）。"""
    topic = q.get("topic") or ""
    level = q.get("level") or "基础"
    hint = q.get("hint") or ""
    competency = q.get("target_competency") or q.get("competency") or (f"{topic}-{level}" if topic else "综合能力")
    rubric = _as_rubric_list(q.get("rubric")) or _default_rubric(q)
    difficulty = int(q.get("difficulty") or _LEVEL_DIFFICULTY.get(level, 3))
    followups = q.get("followups") or _followups_from_hint(hint, topic)
    return {
        "id": q.get("id") or f"q{idx}",
        "question": q.get("question", ""),
        "topic": topic,
        "level": level,
        "hint": hint,
        "difficulty": max(1, min(5, difficulty)),
        "competency": competency,
        "rubric": rubric,
        "followups": followups,
    }


def _load_pack_hint(direction: str) -> str:
    """加载 data/packs 下与方向匹配的岗位问题包（DeepInterview playbook 简化版）。"""
    if not PACKS_DIR.exists():
        return ""
    hints: list[str] = []
    for path in sorted(PACKS_DIR.glob("*.md")):
        stem = path.stem
        if stem.split("-")[0] in direction or direction in stem:
            hints.append(path.read_text(encoding="utf-8")[:1800])
    return "\n\n".join(hints)


class InterviewManager:
    """面试流程状态机的 LLM 驱动端：prep / live / post 每个子流程一个方法。"""

    def __init__(self):
        if not DEEPSEEK_API_KEY:
            raise InterviewError("未配置 DEEPSEEK_API_KEY，请复制 .env.example 为 .env 并填写")
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        self.model = DEEPSEEK_MODEL

    @with_retry()
    def _complete(self, system: str, user: str, temperature: float = 0.3, json_mode: bool = True) -> str:
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self.client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def _complete_json(self, system: str, user: str, temperature: float = 0.2) -> dict:
        return _extract_json(self._complete(system, user, temperature=temperature))

    # ================= prep：岗位画像 / 差距分析 / 面试设计 / 问题计划 =================

    def analyze_jd(self, jd_text: str, company: str = "") -> dict:
        """JD → 结构化岗位画像（JobSpec，借鉴 DeepInterview jd_analysis）。"""
        system = """你是招聘经理。把岗位描述解析为结构化岗位画像：职位名称、公司、职级（intern/junior/mid/senior）、必须项、加分项、核心职责、技术栈。忠于原文，不要编造 JD 中没有的要求。
只输出 JSON：{"title": "...", "company_name": "...", "seniority": "intern", "must_have": ["..."], "nice_to_have": ["..."], "responsibilities": ["..."], "tech_stack": ["..."], "raw_text": "..."}"""
        try:
            data = self._complete_json(system, f"目标公司：{company}\n岗位描述：\n{jd_text[:6000]}")
            if data.get("title") or data.get("must_have"):
                data["raw_text"] = jd_text[:6000]
                return data
        except Exception:
            pass
        return {
            "title": "自定义岗位",
            "company_name": company,
            "seniority": "intern",
            "must_have": [],
            "nice_to_have": [],
            "responsibilities": [],
            "tech_stack": [],
            "raw_text": jd_text[:6000],
        }

    def gap_analysis(self, profile: dict, job: dict) -> dict:
        """候选人画像 × 岗位画像 → 差距分析（GapAnalysis，借鉴 DeepInterview）。"""
        system = """你是面试策略师。对比候选人与岗位要求，输出结构化差距分析：优势、差距、面试官应深挖验证的点（probe_targets）、匹配技能、缺失技能、一句话总结。要具体、有依据，不要空话。
只输出 JSON：{"strengths": ["..."], "gaps": ["..."], "probe_targets": ["..."], "matched_skills": ["..."], "missing_skills": ["..."], "summary": "..."}"""
        user = f"候选人档案：\n{profile_context_text(profile)}\n\n岗位要求：\n{json.dumps(job, ensure_ascii=False)}"
        try:
            data = self._complete_json(system, user)
            if data.get("strengths") or data.get("gaps"):
                return data
        except Exception:
            pass
        return {
            "strengths": [],
            "gaps": [],
            "probe_targets": [],
            "matched_skills": [],
            "missing_skills": [],
            "summary": "暂未生成差距分析",
        }

    def design_interview(
        self,
        goal: str,
        jd_text: str = "",
        resume_text: str = "",
        duration: int = 15,
    ) -> dict:
        """自然语言考察目标 → 完整面试设计（借鉴聆悟 generator 的面试结构）。"""
        system = """你是资深面试设计师。根据用户的一句话考察目标，设计完整面试方案：
- title（面试主题标题）、description（一两句说明）、objective（考察目标）；
- assessment_criteria：3-6 条可衡量的评估维度（名称+说明）；
- questions：5-12 道题，按逻辑顺序组织：暖场/开场 → 核心考察题放中间 → 结尾开放式；
  每道题给出 text、type（OPEN_ENDED/RESEARCH/CODING/BEHAVIOR）、follow_up_prompts（2-3 个追问种子）、time_limit_seconds（null 或秒数）、is_required；
- recommended_settings：mode（CHAT）、follow_up_depth（LIGHT/MODERATE/DEEP）、ai_tone（PROFESSIONAL/FRIENDLY）。
所有内容用简体中文。只输出 JSON：
{"title": "...", "description": "...", "objective": "...", "assessment_criteria": [{"name": "...", "description": "..."}], "questions": [{"text": "...", "type": "OPEN_ENDED", "follow_up_prompts": ["..."], "time_limit_seconds": null, "is_required": true}], "recommended_settings": {"mode": "CHAT", "follow_up_depth": "MODERATE", "ai_tone": "PROFESSIONAL"}}"""
        user = f"考察目标：{goal}\n目标时长约 {duration} 分钟"
        if jd_text.strip():
            user += f"\n\n岗位描述：\n{jd_text[:4000]}"
        if resume_text.strip():
            user += f"\n\n候选人简历：\n{resume_text[:4000]}"
        try:
            data = self._complete_json(system, user, temperature=0.3)
            if data.get("questions"):
                return data
        except Exception:
            pass
        raise InterviewError("面试设计生成失败，请换个描述试试")

    def generate_interviewer(self, context: dict | None = None) -> dict:
        """根据岗位画像 / 面试设计生成一位拟真面试官（LLM 失败回退默认画像）。"""
        system = """你是面试筹备导演。根据提供的岗位画像，生成一位拟真面试官：
- name：中文姓名（常见姓氏 + 名，2-3 字）
- role_title：头衔，如"大模型应用开发团队 · 资深工程师"
- focus：3-5 个考察重点（结合 must_have / 职责 / 评估维度，具体不要空话）
- tone：一句话描述面试风格（如"节奏紧凑、爱追问细节、会打断验证深度"）
- greeting：60 字内的开场白，自然口语化，含简短自我介绍与开场引导
只输出 JSON：{"name": "...", "role_title": "...", "focus": ["..."], "tone": "...", "greeting": "..."}"""
        try:
            data = self._complete_json(
                system,
                f"岗位画像：\n{json.dumps(context or {}, ensure_ascii=False)[:3000]}",
                temperature=0.4,
            )
            if data.get("name") and data.get("greeting"):
                return data
        except Exception:
            pass
        focus = []
        if context:
            focus = [str(x) for x in (context.get("must_have") or context.get("focus") or [])[:4]]
        return {
            "name": "陈老师",
            "role_title": "资深面试官",
            "focus": focus or ["综合能力", "项目深挖"],
            "tone": "专业友好、注重追问细节",
            "greeting": "你好，我是今天负责面试的面试官，我们直接开始吧——先做个简短的自我介绍？",
        }

    def parse_resume(self, resume_text: str) -> dict:
        """从简历文本提取结构化档案：目标岗位 / 技能栈 / 项目经历（LLM 失败回退空档案）。"""
        system = """你是资深简历解析器。从候选人简历文本中提取结构化信息：
- target_role：目标岗位（如"大模型应用开发实习生"；简历没写明就按经历推断）
- target_direction：目标方向（如"大模型 / AI 应用开发"）
- skills：技能栈列表（5-12 个，含具体技术，如 Python、RAG、PyTorch、FAISS、FastAPI）
- weak_areas：可能薄弱/需要补强的方向（1-3 个，基于经历推断，没有就空数组）
- projects：最多 3 个最有分量的项目，每个包含：
  - name（项目名称）、tech_stack（技术栈）、description（项目做什么、你负责什么）、
    metrics（量化成果，没有就写空串）、story（面试可深挖点：技术决策/难点/踩坑，没有就写空串）
只输出 JSON：{"target_role": "...", "target_direction": "...", "skills": ["..."], "weak_areas": ["..."], "projects": [{"name": "...", "tech_stack": "...", "description": "...", "metrics": "...", "story": "..."}]}"""
        try:
            data = self._complete_json(system, f"简历文本：\n{resume_text[:8000]}", temperature=0.1)
            projects = [p for p in (data.get("projects") or []) if p.get("name")][:3]
            return {
                "target_role": str(data.get("target_role", "") or ""),
                "target_direction": str(data.get("target_direction", "") or ""),
                "skills": [str(s) for s in (data.get("skills") or []) if str(s).strip()][:12],
                "weak_areas": [str(s) for s in (data.get("weak_areas") or []) if str(s).strip()][:3],
                "projects": projects,
            }
        except Exception:
            return {
                "target_role": "",
                "target_direction": "",
                "skills": [],
                "weak_areas": [],
                "projects": [],
            }

    # ---------------- 出题（问题计划） ----------------
    def generate_question_list(
        self,
        direction: str = "通用开发",
        count: int = 8,
        profile: dict | None = None,
        jd_analysis: dict | None = None,
        gap: dict | None = None,
    ) -> list[dict]:
        """基于题库 + 档案 + JD 差距分析生成完整问题计划（每道题含 rubric / 难度 / 追问种子）。"""
        topics = DIRECTION_TOPICS.get(direction, DIRECTION_TOPICS["通用开发"])
        bank: list[dict] = []
        seen: set[str] = set()
        for topic in topics:
            try:
                items = json.loads(query_question(topic=topic, level=""))
            except Exception:
                items = []
            for item in items:
                q = item.get("question", "")
                if q and q not in seen:
                    seen.add(q)
                    bank.append(item)
        if not bank:
            raise InterviewError("题库暂不可用，请检查 data/questions.json")

        system = """你是资深面试官，负责给候选人生成一套高质量面试题单（含评分标准与追问种子）。
要求：
1. 结合题库候选、候选人档案与岗位要求出题（至少一半来自题库候选）；
2. 覆盖基础、进阶与开放场景题，遵循先易后难的难度曲线（difficulty 1-5）；
3. 每道题给出：question、topic、level（基础/进阶/场景）、hint、difficulty（1-5）、target_competency（考察能力）、rubric（1-3 条评分标准，权重和约 1.0）、followups（2-3 个追问种子）。
只输出 JSON：{"questions": [{"question": "...", "topic": "...", "level": "...", "hint": "...", "difficulty": 3, "target_competency": "...", "rubric": [{"criterion": "...", "weight": 0.4, "description": "..."}], "followups": ["..."]}]}"""
        candidates = json.dumps(bank[:20], ensure_ascii=False)
        user_parts = [f"面试方向：{direction}", f"题库候选：\n{candidates}", f"请生成 {count} 道题。"]
        if profile:
            user_parts.append(f"候选人档案：\n{profile_context_text(profile)}")
        if jd_analysis:
            jd = jd_analysis
            user_parts.append(
                "岗位考察点：\n"
                f"- 职位：{jd.get('title', '')}（{jd.get('seniority', '')}）\n"
                f"- 必须项：{'、'.join(jd.get('must_have', []) or [])}\n"
                f"- 加分项：{'、'.join(jd.get('nice_to_have', []) or [])}\n"
                f"- 职责：{'；'.join(jd.get('responsibilities', []) or [])}"
            )
        if gap and (gap.get("probe_targets") or gap.get("missing_skills")):
            user_parts.append(
                "应深挖验证的点：\n"
                f"- probe_targets：{'、'.join(gap.get('probe_targets', []) or [])}\n"
                f"- 缺失技能：{'、'.join(gap.get('missing_skills', []) or [])}"
            )
        pack_hint = _load_pack_hint(direction)
        if pack_hint:
            user_parts.append(f"岗位问题包参考（round structure / signals / pitfalls）：\n{pack_hint}")

        base: list[dict] = []
        try:
            data = self._complete_json(system, "\n\n".join(user_parts))
            questions = [q for q in data.get("questions", []) if q.get("question")]
            base = [_normalize_question(q, i) for i, q in enumerate(questions[:count])]
        except Exception:
            base = []
        if not base:
            # 兜底：直接用题库（补齐评分标准）
            base = [
                _normalize_question(
                    {
                        "question": b["question"],
                        "topic": b.get("topic", ""),
                        "level": b.get("level", ""),
                        "hint": b.get("hint", ""),
                    },
                    i,
                )
                for i, b in enumerate(bank[:count])
            ]
        # 个性化：结合候选人真实项目插入深挖题（约 30%，至少 1 道）
        projects = (profile or {}).get("projects") or []
        if projects:
            p_count = max(1, min(3, round(count * 0.3)))
            p_questions = self.generate_project_questions(projects, p_count)
            if p_questions:
                base = base[: max(0, count - len(p_questions))] + p_questions
        return base[:count]

    def generate_project_questions(self, projects: list[dict], count: int = 2) -> list[dict]:
        """针对候选人真实项目生成深挖题（含 rubric）；LLM 失败时回退通用模板。"""
        if not projects:
            return []
        system = """你是资深面试官，负责针对候选人的真实项目经历生成深挖面试题。
要求：
1. 题目要具体、能深挖（技术选型、难点排查、量化结果、失败与改进），不要泛泛而问；
2. 结合候选人的技术栈与量化成果设计追问点；
3. 每道题给出 question、topic（project）、level（场景）、hint、difficulty（1-5）、target_competency、rubric、followups。
只输出 JSON：{"questions": [{"question": "...", "topic": "project", "level": "场景", "hint": "...", "difficulty": 4, "target_competency": "项目深挖", "rubric": [{"criterion": "...", "weight": 0.4, "description": "..."}], "followups": ["..."]}]}"""
        briefs = "\n".join(
            f"- 项目：{p.get('name', '')}；技术栈：{p.get('tech_stack', '')}；描述：{p.get('description', '')}；"
            f"量化成果：{p.get('metrics', '')}；深挖点：{p.get('story', '')}"
            for p in projects[:3]
        )
        try:
            data = self._complete_json(system, f"候选人的项目经历：\n{briefs}\n请生成 {count} 道项目深挖题。")
            questions = [q for q in data.get("questions", []) if q.get("question")]
            if questions:
                return [_normalize_question(q, i) for i, q in enumerate(questions[:count])]
        except Exception:
            pass
        templates = [
            "介绍一下你的项目「{name}」？你负责什么、最终成果如何？",
            "项目「{name}」里你遇到的最大难点是什么？怎么排查和解决的？",
            "项目「{name}」为什么选这套技术栈？对比过其他方案吗？",
            "如果重做项目「{name}」，你会怎么改进？",
        ]
        result: list[dict] = []
        for i in range(count):
            project = projects[i % len(projects)]
            name = project.get("name") or "该项目"
            result.append(
                _normalize_question(
                    {
                        "question": templates[i % len(templates)].format(name=name),
                        "topic": "project",
                        "level": "场景",
                        "hint": "用 STAR 结构讲：背景 → 任务 → 行动 → 结果，突出技术决策与量化数据",
                        "target_competency": "项目深挖",
                    },
                    i,
                )
            )
        return result

    # ================= live：点评 + 追问 + 逐题评分 =================

    def feedback_and_followup(
        self,
        question: str,
        answer: str,
        rubric: list[dict] | None = None,
        competency: str = "",
    ) -> dict:
        """针对当前回答给出点评、追问与 0-5 分评分（评分标准驱动）。"""
        rubric_list = _as_rubric_list(rubric) or _default_rubric({"question": question})
        rubric_lines = "\n".join(
            f"- {r.get('criterion')}（权重 {float(r.get('weight', 0.3)):.1f}）：{r.get('description')}"
            for r in rubric_list
        )
        system = """你是严格但友善的面试官。候选人刚回答了一道题。
按评分标准打分（0=完全未答，3=合格，5=优秀），并给出得分证据。
输出 JSON：
{
  "feedback": "对回答的简短点评（对错 + 为什么 + 缺失点，100 字内）",
  "followup": "基于其回答继续深挖的一个追问（不要重复原题）",
  "score": 0-5 的整数,
  "score_evidence": "得分依据（引用回答中的具体内容）",
  "score_hint": "满分 5 分，本次得分 X 分的原因（一句话）"
}"""
        return self._complete_json(
            system,
            f"题目：{question}\n考察能力：{competency or '综合'}\n评分标准：\n{rubric_lines}\n候选人回答：\n{answer}",
            temperature=0.3,
        )

    def score_answer(self, question: dict, answer: str) -> dict:
        """post 阶段：按题目 rubric 对单题回答打分（competency 强制绑定题目，level 由分数推导）。"""
        rubric = _as_rubric_list(question.get("rubric")) or _default_rubric(question)
        competency = question.get("competency") or question.get("target_competency") or "综合能力"
        rubric_lines = "\n".join(
            f"- {r.get('criterion')}（权重 {float(r.get('weight', 0.3)):.1f}）：{r.get('description')}"
            for r in rubric
        )
        system = """你是严谨公正的面试考核官。按评分标准给候选人的单题回答打 0-5 分（0=无相关内容，3=合格，5=优秀），并在 evidence 中引用回答中的具体证据。
只输出 JSON：{"score": 0-5 的数字, "evidence": "..."}"""
        answer_block = answer.strip() if answer and answer.strip() else "（未作答）"
        try:
            data = self._complete_json(
                system,
                f"考察能力：{competency}\n题目：{question.get('question', '')}\n评分标准：\n{rubric_lines}\n候选人回答：\n{answer_block}",
            )
            score = max(0, min(5, int(round(float(data.get("score", 0) or 0)))))
            evidence = str(data.get("evidence", "") or "")
        except Exception:
            score = 0
            evidence = "（无法评分）"
        return {"competency": competency, "score": score, "evidence": evidence, "level": level_for_score(score)}

    # ================= post：整场评分（ScoreCard） =================

    def evaluate_interview(self, qa_list: list[dict], plan: list[dict] | None = None) -> dict:
        """基于整场问答生成 ScoreCard：总分 + 维度 + 能力分 + 参考答案 + 下一步。"""
        # 1) 逐题 rubric 评分（仅统计有效作答）
        answered = [
            qa for qa in qa_list
            if (qa.get("answer") or "").strip() and qa.get("answer") != "（跳过）"
        ]
        scored_answers = [(qa, self.score_answer(qa, qa.get("answer", ""))) for qa in answered]
        buckets: dict[str, list[dict]] = {}
        order: list[str] = []
        for qa, scored in scored_answers:
            comp = scored["competency"]
            if comp not in buckets:
                buckets[comp] = []
                order.append(comp)
            buckets[comp].append(scored)
        comp_scores = []
        for comp in order:
            group = buckets[comp]
            avg = round(sum(c["score"] for c in group) / len(group), 1)
            evidence = "；".join(c["evidence"] for c in group if c["evidence"]) or "按评分标准打分"
            comp_scores.append({"competency": comp, "score": avg, "evidence": evidence, "level": level_for_score(avg)})
        overall5 = round(sum(c["score"] for c in comp_scores) / len(comp_scores), 1) if comp_scores else 0.0
        total_score = max(0, min(100, round(overall5 * 20)))
        weak_competencies = [c["competency"] for c in comp_scores if c["level"] in ("weak", "developing")]

        # 2) 叙事部分：维度分 + 亮点/不足 + 总结 + 下一步（LLM）
        transcript = []
        for i, qa in enumerate(qa_list, 1):
            transcript.append(
                f"[第{i}题] {qa.get('question', '')}\n"
                f"候选人回答：{qa.get('answer', '（未作答）')}\n"
                f"面试官点评：{qa.get('feedback', '')}\n"
                f"追问：{qa.get('followup', '')}\n"
                f"追问作答：{qa.get('followup_answer', '（未作答）')}"
            )
        system = f"""你是考核官，根据整场面试问答记录生成结构化中文评分。
评分维度（各 0-100）：{"/".join(EVAL_DIMENSIONS)}。
另需生成语言/表达报告（structure_score/clarity_score/conciseness_score 均 0-5）。
只输出 JSON：
{{
  "dimensions": {{"正确性": 80, "深度": 75, "结构": 85, "表达": 90, "风险意识": 70}},
  "highlights": ["亮点1", "亮点2"],
  "weaknesses": ["不足1", "不足2"],
  "missing_points": ["缺失的关键点"],
  "suggestions": ["具体改进建议"],
  "summary": "两句话总结本场表现",
  "next_steps": ["接下来优先补的 2-4 件事"],
  "language_report": {{"structure_score": 4, "clarity_score": 4, "conciseness_score": 3, "summary": "表达方面的一句话点评"}}
}}"""
        comp_lines = "\n".join(f"- {c['competency']}: {c['score']}/5 ({c['level']})" for c in comp_scores) or "- （无有效作答）"
        try:
            narrative = self._complete_json(system, "\n\n".join(transcript) + f"\n\n逐题能力分：\n{comp_lines}", temperature=0.2)
        except Exception:
            narrative = {
                "dimensions": {},
                "highlights": [],
                "weaknesses": [],
                "missing_points": [],
                "suggestions": [],
                "summary": "",
                "next_steps": [],
                "language_report": {},
            }

        # 3) 参考答案：只给最弱的 3 道已答题目生成改进版
        model_answers: list[dict] = []
        weakest = sorted(scored_answers, key=lambda pair: pair[1]["score"])[:3]
        for qa, _ in weakest:
            try:
                ref = self.reference_answer(qa.get("question", ""), qa.get("answer", ""))
                if ref:
                    model_answers.append({"question": qa.get("question", ""), "answer": ref})
            except Exception:
                pass

        return {
            "total_score": total_score,
            "dimensions": narrative.get("dimensions", {}),
            "highlights": narrative.get("highlights", []),
            "weaknesses": narrative.get("weaknesses", []),
            "missing_points": narrative.get("missing_points", []),
            "suggestions": narrative.get("suggestions", []),
            "summary": narrative.get("summary", ""),
            "next_steps": narrative.get("next_steps", []),
            "language_report": narrative.get("language_report", {}),
            "competency_scores": comp_scores,
            "weak_competencies": weak_competencies,
            "model_answers": model_answers,
            "coverage_pct": round(len(answered) / len(qa_list), 2) if qa_list else 1.0,
        }

    def coach_plan(self, report: dict) -> dict:
        """学习教练：针对弱能力生成 StudyModule，并用 RAG 检索知识库作为学习材料。"""
        weak = (report.get("weak_competencies") or [])[:4]
        comp_map = {c.get("competency"): c for c in report.get("competency_scores", []) or []}
        modules: list[dict] = []
        for competency in weak:
            evidence = comp_map.get(competency, {}).get("evidence", "")
            try:
                refs = json.loads(search_knowledge(query=competency, k=2))
                sources = [f"{r.get('source')} · {r.get('title', '')}" for r in refs]
                snippets = "\n".join(
                    f"- [{r.get('source')}] {r.get('title', '')}: {r.get('text', '')[:200]}" for r in refs
                )
            except Exception:
                sources = []
                snippets = ""
            system = """你是面试备考教练。针对候选人在面试中暴露的弱能力，设计一个聚焦、可执行的学习模块，并给出学习要点。
只输出 JSON：{"title": "...", "rationale": "结合失分证据的一句话理由", "est_min": 10-45 的整数, "focus_points": ["2-4 个学习要点"]}"""
            try:
                module = self._complete_json(
                    system,
                    f"弱能力：{competency}\n面试失分证据：{evidence or '（未记录）'}\n知识库参考：\n{snippets or '（无）'}",
                )
            except Exception:
                module = {
                    "title": f"补强：{competency}",
                    "rationale": evidence or "系统性复习该能力",
                    "est_min": 30,
                    "focus_points": ["复习基础知识", "做 2-3 道对应真题并复盘"],
                }
            module["competency"] = competency
            module["sources"] = sources
            modules.append(module)
        return {
            "summary": f"根据本场面试，为 {len(modules)} 个薄弱能力生成了学习模块。",
            "modules": modules,
            "total_min": sum(int(m.get("est_min", 0) or 0) for m in modules),
        }

    # ================= 参考答案 =================

    def reference_answer(self, question: str, answer: str = "") -> str:
        """生成"应得 8-9 分"的改进版参考答案（结构：结论→展开→例子→风险点；行为题用 STAR）。"""
        try:
            bank = json.loads(query_question(topic="", level=""))
            for item in bank:
                if item.get("question", "").strip() == question.strip():
                    if not answer.strip():
                        return item.get("answer", "")
        except Exception:
            pass
        try:
            refs = json.loads(search_knowledge(query=question, k=3))
            context = "\n".join(f"- [{r.get('source')}] {r.get('text', '')}" for r in refs)
        except Exception:
            context = ""
        system = """你是资深面试教练。基于知识库参考与候选人实际回答，写一份应得 8-9 分的参考答案。
要求：
1. 直接扣题，结构清晰：技术题用"结论 → 展开 → 例子 → 风险点"，行为题用 STAR；
2. 如果提供了候选人回答，在此基础上改进，而不是另起炉灶；
3. 包含关键得分点，长度 150 字内。
只输出 JSON：{"reference": "..."}"""
        try:
            data = self._complete_json(
                system,
                f"题目：{question}\n候选人回答：{answer or '（无）'}\n知识库参考：\n{context or '（无）'}",
            )
            return data.get("reference", "")
        except Exception:
            return "参考答案暂不可用，可让八股讲师检索知识库讲解。"

    # ================= 历史对比 / 面经复盘 =================

    def compare_with_history(self, current: dict, history: list[dict]) -> dict:
        """把本场报告与历史场次做维度级对比。"""
        if not history:
            return {
                "history_count": 0,
                "note": "暂无历史场次，本场为第一次完整面试。",
                "progress": [],
                "regress": [],
                "stable": [],
                "priority": [],
            }
        avg = {
            d: round(sum(float(r.get("dimensions", {}).get(d, 0) or 0) for r in history) / len(history))
            for d in EVAL_DIMENSIONS
        }
        system = f"""你是求职教练。对比本场与历史平均表现，输出 JSON：
{{
  "history_count": {len(history)},
  "history_avg": {json.dumps(avg, ensure_ascii=False)},
  "progress": ["相比历史进步/提升的维度与证据"],
  "regress": ["相比历史退步/下降的维度"],
  "stable": ["保持稳定的方面"],
  "priority": ["接下来最该优先加强的 1-2 点"]
}}"""
        return self._complete_json(
            system,
            f"本场报告：{json.dumps(current, ensure_ascii=False)}",
            temperature=0.2,
        )

    def review_experience(self, text: str) -> dict:
        """对真实面试经历做深度复盘，给出改进建议。"""
        system = """你是面试复盘教练。根据用户贴出的真实面试经历，输出结构化复盘，只输出 JSON：
{
  "summary": "两句话概括这次面试的核心情况",
  "highlights": ["表现好的点"],
  "weaknesses": ["暴露的问题（要具体，结合经历原文）"],
  "key_points": ["这次面试涉及的必会知识点清单"],
  "action_plan": ["接下来 1-2 周可执行的学习/练习计划"]
}"""
        return self._complete_json(system, f"面试经历原文：\n{text[:6000]}", temperature=0.3)
