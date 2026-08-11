"""面试闭环核心：出题 → 作答 → 点评追问 → 整场评分 → 历史对比 → 面经复盘。

复用与多 Agent 相同的 DeepSeek 底座，用结构化 JSON 输出驱动面试状态机；
与聊天 Agent（harness）解耦，保持每个模块职责单一、可解释。
"""

import json
import re

from openai import OpenAI

from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from .tools import query_question, search_knowledge

# 面试方向 -> 题库主题（用于出题检索）
DIRECTION_TOPICS = {
    "Python 后端": ["python", "database", "network", "os", "algorithm"],
    "AI 应用开发": ["ai", "python", "database", "project"],
    "通用开发": ["python", "database", "network", "os", "ai", "algorithm", "project"],
}

EVAL_DIMENSIONS = ["正确性", "深度", "结构", "表达", "风险意识"]


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


class InterviewManager:
    """面试流程状态机的 LLM 驱动端：每个子流程一个方法，输出结构化 JSON。"""

    def __init__(self):
        if not DEEPSEEK_API_KEY:
            raise InterviewError("未配置 DEEPSEEK_API_KEY，请复制 .env.example 为 .env 并填写")
        self.client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
        self.model = DEEPSEEK_MODEL

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

    # ---------------- 出题 ----------------
    def generate_question_list(self, direction: str = "通用开发", count: int = 8) -> list[dict]:
        """基于题库检索 + LLM 定制生成一套面试题单。"""
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

        system = """你是资深面试官，负责给候选人生成一套高质量面试题单。
要求：
1. 结合提供的题库候选与你的专业经验，输出 count 道题（至少一半来自题库候选）；
2. 覆盖基础、进阶与开放场景题，题目要具体、能考出真实水平；
3. 每道题给出：题目、主题、难度、作答提示（hint）。
只输出 JSON：{"questions": [{"question": "...", "topic": "...", "level": "基础/进阶/场景", "hint": "..."}]}"""
        candidates = json.dumps(bank[:20], ensure_ascii=False)
        user = f"面试方向：{direction}\n题库候选：\n{candidates}\n请生成 {count} 道题。"
        try:
            data = self._complete_json(system, user)
            questions = [q for q in data.get("questions", []) if q.get("question")]
            if questions:
                return questions[:count]
        except Exception:
            pass
        # 兜底：直接用题库
        return [
            {
                "question": b["question"],
                "topic": b.get("topic", ""),
                "level": b.get("level", ""),
                "hint": b.get("hint", ""),
            }
            for b in bank[:count]
        ]

    # ---------------- 点评 + 追问 ----------------
    def feedback_and_followup(self, question: str, answer: str) -> dict:
        """针对当前回答给出简短点评，并生成一个深挖追问。"""
        system = """你是严格但友善的面试官。候选人刚回答了一道题。
输出 JSON：
{
  "feedback": "对回答的简短点评（对错 + 为什么 + 缺失点，100 字内）",
  "followup": "基于其回答继续深挖的一个追问（不要重复原题）",
  "score_hint": "这道题 0-10 的预判得分及原因"
}"""
        return self._complete_json(
            system,
            f"题目：{question}\n候选人回答：{answer}",
            temperature=0.3,
        )

    # ---------------- 参考答案 ----------------
    def reference_answer(self, question: str) -> str:
        """结合知识库检索生成参考答案（题库命中时优先用标准答案）。"""
        try:
            bank = json.loads(query_question(topic="", level=""))
            for item in bank:
                if item.get("question", "").strip() == question.strip():
                    return item.get("answer", "")
        except Exception:
            pass
        try:
            refs = json.loads(search_knowledge(query=question, k=3))
            context = "\n".join(f"- [{r.get('source')}] {r.get('text', '')}" for r in refs)
        except Exception:
            context = ""
        system = "你是资深面试官。基于提供的知识库参考，给出该题一份高质量参考答案（120 字内，包含关键得分点）。只输出 JSON：{\"reference\": \"...\"}"
        try:
            data = self._complete_json(system, f"题目：{question}\n知识库参考：\n{context or '（无）'}")
            return data.get("reference", "")
        except Exception:
            return "参考答案暂不可用，可让八股讲师检索知识库讲解。"

    # ---------------- 整场评分 ----------------
    def evaluate_interview(self, qa_list: list[dict]) -> dict:
        """基于整场问答记录生成结构化评分报告。"""
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
只输出 JSON：
{{
  "total_score": 0-100 的整数,
  "dimensions": {{"正确性": 80, "深度": 75, "结构": 85, "表达": 90, "风险意识": 70}},
  "highlights": ["亮点1", "亮点2"],
  "weaknesses": ["不足1", "不足2"],
  "missing_points": ["缺失的关键点"],
  "suggestions": ["具体改进建议"]
}}"""
        return self._complete_json(system, "\n\n".join(transcript), temperature=0.2)

    # ---------------- 历史对比 ----------------
    def compare_with_history(self, current: dict, history: list[dict]) -> dict:
        """把本场报告与历史场次做维度级对比。"""
        if not history:
            return {"history_count": 0, "note": "暂无历史场次，本场为第一次完整面试。", "progress": [], "regress": [], "stable": [], "priority": []}
        avg = {d: round(sum(float(r.get("dimensions", {}).get(d, 0) or 0) for r in history) / len(history)) for d in EVAL_DIMENSIONS}
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

    # ---------------- 面经复盘 ----------------
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


interview_manager = InterviewManager()
