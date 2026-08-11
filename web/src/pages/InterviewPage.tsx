import { useEffect, useState } from "react";
import { ArrowRight, ChevronDown, ImageUp, Play, Sparkles, Wand2 } from "lucide-react";
import { api, type StartResult } from "../lib/api";
import type {
  AnswerFeedback,
  Comparison,
  InterviewDesign,
  Interviewer,
  Profile,
  Question,
  Report,
} from "../lib/types";
import { Badge, Button, Card, DifficultyStars, Field, Progress, Select, Spinner, TextArea } from "../components/ui";
import ScoreCard from "../components/ScoreCard";

const DIRECTIONS = ["AI 应用开发", "Python 后端", "通用开发", "行为面试（STAR）"];

export default function InterviewPage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [phase, setPhase] = useState<"setup" | "live" | "done">("setup");
  const [session, setSession] = useState<StartResult & { direction: string } | null>(null);
  const [index, setIndex] = useState(0);
  const [qaId, setQaId] = useState(0);
  const [feedback, setFeedback] = useState<AnswerFeedback | null>(null);
  const [answerText, setAnswerText] = useState("");
  const [followupText, setFollowupText] = useState("");
  const [reference, setReference] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [interviewer, setInterviewer] = useState<Interviewer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  // setup fields
  const [direction, setDirection] = useState("AI 应用开发");
  const [count, setCount] = useState(6);
  const [goal, setGoal] = useState("");
  const [duration, setDuration] = useState(15);
  const [jdQuickFile, setJdQuickFile] = useState<File | null>(null);
  const [jdQuickPreview, setJdQuickPreview] = useState<string | null>(null);
  const [quickBusy, setQuickBusy] = useState(false);

  useEffect(() => {
    api.getProfile().then(setProfile).catch(() => undefined);
  }, []);

  const questions = session?.questions || [];
  const current = questions[index];
  const total = questions.length;

  async function start(direction: string, count: number, design?: InterviewDesign) {
    setBusy(true);
    setError("");
    try {
      const result = design
        ? await api.startFromDesign(design)
        : await api.startInterview(direction, count);
      setSession(result);
      setIndex(0);
      setQaId(result.qa_id);
      setFeedback(null);
      setReference("");
      setAnswerText("");
      setFollowupText("");
      setReport(null);
      setInterviewer(result.interviewer || null);
      setPhase("live");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function generateDesign() {
    if (!goal.trim()) return;
    setBusy(true);
    setError("");
    try {
      const design = await api.designInterview(
        goal.trim(),
        profile?.jd_text || "",
        profile?.resume_text || "",
        duration,
      );
      await start(direction, count, design);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function quickStartFromJdImage() {
    if (!jdQuickFile) return;
    setQuickBusy(true);
    setError("");
    try {
      const ocr = await api.ocrJdImage(jdQuickFile);
      const current = await api.getProfile();
      const analysis = await api.analyzeJd(ocr.text, current);
      const saved = await api.saveProfile({ ...current, jd_text: ocr.text, jd_analysis: analysis });
      setProfile(saved);
      await start(direction, count);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setQuickBusy(false);
    }
  }

  async function submitAnswer() {
    if (!session || !current || !answerText.trim()) return;
    setBusy(true);
    setError("");
    try {
      const fb = await api.submitAnswer(session.interview_id, qaId, current, answerText.trim());
      setFeedback(fb);
      setReference("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function submitFollowup() {
    if (!followupText.trim()) return;
    setBusy(true);
    try {
      await api.submitFollowup(qaId, followupText.trim());
      await next();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function skip() {
    setBusy(true);
    try {
      await api.skipQuestion(qaId);
      await next();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function next() {
    if (!session) return;
    if (index + 1 < total) {
      const nq = questions[index + 1];
      const res = await api.nextQuestion(session.interview_id, nq);
      setIndex(index + 1);
      setQaId(res.qa_id);
      setFeedback(null);
      setAnswerText("");
      setFollowupText("");
      setReference("");
    } else {
      await finish();
    }
  }

  async function finish() {
    if (!session) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.finishInterview(session.interview_id);
      setReport(res.report);
      setComparison(res.comparison);
      setPhase("done");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function showReference() {
    if (!session || !current) return;
    setBusy(true);
    try {
      const res = await api.getReference(qaId, current.question, answerText || feedback ? answerText : "");
      setReference(res.reference);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (phase === "setup") {
    return (
      <div className="max-w-3xl space-y-4">
        {error && <ErrorBanner text={error} />}
        <Card>
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-accent" />
            <span className="text-[15px] font-bold">开始一场模拟面试</span>
          </div>
          <p className="text-[12.5px] text-muted mt-1.5 leading-relaxed">
            面试官按方向出题 → 你逐题作答 → 面试官按评分标准点评并追问 → 全部答完后生成整场报告与学习教练计划。
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-[1fr_140px_auto] gap-3 mt-5 items-end">
            <Field label="面试方向">
              <Select value={direction} onChange={(e) => setDirection(e.target.value)}>
                {DIRECTIONS.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </Select>
            </Field>
            <Field label="题目数量">
              <Select value={count} onChange={(e) => setCount(Number(e.target.value))}>
                {[4, 6, 8, 10].map((n) => (
                  <option key={n} value={n}>{n} 题</option>
                ))}
              </Select>
            </Field>
            <Button variant="primary" onClick={() => start(direction, count)} disabled={busy}>
              <Play size={14} />
              {busy ? "出题中…" : "开始模拟面试"}
            </Button>
          </div>
          <JdBanner profile={profile} />
        </Card>

        <Card>
          <div className="flex items-center gap-2">
            <Wand2 size={16} className="text-accent" />
            <span className="text-[15px] font-bold">自定义面试设计</span>
          </div>
          <p className="text-[12.5px] text-muted mt-1.5">
            一句话描述考察目标，自动生成完整面试（评估维度 / 题目 / 追问种子），可复用档案里的 JD 与简历作为上下文。
          </p>
          <div className="mt-4 space-y-3">
            <TextArea
              value={goal}
              onChange={(e) => setGoal(e.target.value)}
              placeholder="例如：考察大模型实习生的 RAG 落地能力与项目深挖，含行为面"
              className="min-h-[70px]"
            />
            <div className="flex items-end justify-between gap-3">
              <Field label="目标时长（分钟）">
                <Select value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
                  {[10, 15, 20, 30].map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </Select>
              </Field>
              <Button variant="primary" onClick={generateDesign} disabled={busy || !goal.trim()}>
                <Sparkles size={14} />
                生成面试设计并开始
              </Button>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-2">
            <ImageUp size={16} className="text-accent" />
            <span className="text-[15px] font-bold">JD 图片直通面试官</span>
          </div>
          <p className="text-[12.5px] text-muted mt-1.5">
            上传岗位 JD 截图，自动识别 → 解析岗位画像 → 生成专属面试官（姓名 / 头衔 / 考察重点 / 开场白）→ 直接开面。
          </p>
          <div className="flex items-center gap-3 flex-wrap mt-4">
            <label className="btn btn-secondary cursor-pointer">
              <ImageUp size={14} />
              选择 JD 图片
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0] || null;
                  setJdQuickFile(f);
                  setJdQuickPreview(f ? URL.createObjectURL(f) : null);
                }}
              />
            </label>
            <Button variant="primary" onClick={quickStartFromJdImage} disabled={quickBusy || !jdQuickFile}>
              <Sparkles size={14} />
              {quickBusy ? "识别并生成面试官中…" : "识别并开始面试"}
            </Button>
            {jdQuickPreview && (
              <img
                src={jdQuickPreview}
                alt="JD 截图预览"
                className="h-16 rounded-[8px] border border-line object-contain"
              />
            )}
          </div>
          <p className="text-[11px] text-faint mt-2">
            图片在本机用 macOS Vision 识别（Swift），不会上传到任何服务；识别结果会存入档案供后续复用。
          </p>
        </Card>
      </div>
    );
  }

  if (phase === "done" && report) {
    return (
      <div className="max-w-4xl">
        {error && <ErrorBanner text={error} />}
        <div className="flex items-center justify-between mb-1">
          <div className="text-[12.5px] text-muted">
            {session?.direction} · 已完成
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => {
                setPhase("setup");
                setSession(null);
                setReport(null);
              }}
            >
              再面一场
            </Button>
          </div>
        </div>
        <ScoreCard report={report} comparison={comparison} />
      </div>
    );
  }

  if (!session || !current) return <Spinner text="加载中…" />;

  const projectNote = session.project_count > 0 ? ` · 含 ${session.project_count} 道项目深挖题` : "";

  return (
    <div className="max-w-3xl space-y-4">
      {error && <ErrorBanner text={error} />}
      <div className="flex items-center justify-between text-[12.5px] text-muted">
        <span>
          {session.direction}
          {projectNote}
        </span>
        <span>
          第 {index + 1} / {total} 题
        </span>
      </div>
      <Progress value={(index + 1) / total} max={1} />

      {interviewer && (
        <Card className="!py-4">
          <div className="flex items-start gap-3">
            <div className="h-11 w-11 rounded-full bg-accent text-white grid place-items-center text-[17px] font-bold shrink-0">
              {interviewer.name.slice(0, 1)}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[14px] font-bold">{interviewer.name}</span>
                <Badge tone="accent">{interviewer.role_title}</Badge>
              </div>
              <div className="text-[11.5px] text-muted mt-0.5">{interviewer.tone}</div>
              <p className="text-[12.5px] text-ink-soft mt-1.5">{interviewer.greeting}</p>
              {interviewer.focus?.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {interviewer.focus.slice(0, 5).map((f, i) => (
                    <Badge key={i}>{f}</Badge>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      <QuestionCard question={current} />

      {reference && (
        <Card className="!p-4">
          <div className="text-[12px] font-bold text-ink-soft mb-1.5">参考答案</div>
          <div className="text-[13px] text-ink-soft leading-relaxed whitespace-pre-wrap">{reference}</div>
        </Card>
      )}

      {!feedback ? (
        <>
          <TextArea
            value={answerText}
            onChange={(e) => setAnswerText(e.target.value)}
            placeholder="按面试作答习惯组织：结论 → 展开 → 例子 → 风险点"
          />
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" onClick={submitAnswer} disabled={busy || !answerText.trim()}>
              {busy ? "点评中…" : "提交答案"}
            </Button>
            <Button onClick={skip} disabled={busy}>跳过本题</Button>
            <Button onClick={showReference} disabled={busy}>查看参考答案</Button>
            <Button variant="ghost" onClick={finish} disabled={busy}>
              结束面试并评分
            </Button>
          </div>
        </>
      ) : (
        <FeedbackPanel
          feedback={feedback}
          followupText={followupText}
          setFollowupText={setFollowupText}
          onSubmit={submitFollowup}
          busy={busy}
        />
      )}

      <AnsweredLog interviewId={session.interview_id} />
    </div>
  );
}

function JdBanner({ profile }: { profile: Profile | null }) {
  const jd = profile?.jd_analysis;
  if (!jd?.title) {
    return (
      <p className="text-[11.5px] text-faint mt-3">
        尚未分析目标 JD：去「我的档案」粘贴岗位描述，面试题会更贴合岗位要求。
      </p>
    );
  }
  const gap = jd.gap;
  return (
    <div className="mt-4 rounded-[10px] border border-line bg-[#fcfbf9] px-4 py-3">
      <div className="flex items-center gap-2 flex-wrap">
        <Badge tone="accent">目标 JD</Badge>
        <span className="text-[13px] font-semibold">{jd.title}</span>
        <span className="text-[11.5px] text-muted">
          必须项：{(jd.must_have || []).slice(0, 4).join("、") || "未解析"}
        </span>
      </div>
      {gap?.summary ? (
        <p className="text-[11.5px] text-muted mt-1.5">
          差距分析：{gap.summary}｜应深挖：{(gap.probe_targets || []).slice(0, 3).join("、")}
        </p>
      ) : null}
    </div>
  );
}

function QuestionCard({ question }: { question: Question }) {
  const topicLabel =
    question.topic === "project"
      ? "项目深挖"
      : question.topic === "behavior"
        ? "行为面"
        : question.topic;
  return (
    <Card className="border-t-[3px] border-t-accent !py-5">
      <div className="flex items-center gap-2 flex-wrap text-[11.5px] text-muted">
        <Badge tone="accent">{topicLabel}</Badge>
        <Badge>{question.level}</Badge>
        <span className="inline-flex items-center gap-1.5">
          难度 <DifficultyStars value={question.difficulty} />
        </span>
        {question.competency ? <Badge>考察：{question.competency}</Badge> : null}
      </div>
      <div className="text-[17px] font-semibold leading-relaxed mt-3">{question.question}</div>
      {question.hint && (
        <div className="mt-3 rounded-[9px] bg-[#f6f4ef] px-3.5 py-2.5 text-[12.5px] text-ink-soft">
          提示：{question.hint}
        </div>
      )}
      {question.rubric?.length > 0 && (
        <details className="mt-3 text-[12px] text-muted">
          <summary className="cursor-pointer flex items-center gap-1">
            评分标准 <ChevronDown size={12} />
          </summary>
          <div className="mt-2 space-y-1.5">
            {question.rubric.map((r, i) => (
              <div key={i} className="flex gap-2">
                <span className="w-[130px] shrink-0 font-medium">{r.criterion}</span>
                <span>权重 {r.weight.toFixed(1)} · {r.description}</span>
              </div>
            ))}
          </div>
        </details>
      )}
      {question.followups?.length > 0 && (
        <details className="mt-2 text-[12px] text-muted">
          <summary className="cursor-pointer flex items-center gap-1">
            可能追问方向 <ChevronDown size={12} />
          </summary>
          <ul className="mt-2 list-disc pl-5 space-y-1">
            {question.followups.slice(0, 3).map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}

function FeedbackPanel({
  feedback,
  followupText,
  setFollowupText,
  onSubmit,
  busy,
}: {
  feedback: AnswerFeedback;
  followupText: string;
  setFollowupText: (v: string) => void;
  onSubmit: () => void;
  busy: boolean;
}) {
  return (
    <div className="space-y-3">
      <Card className="!py-4 border-l-[3px] border-l-accent">
        <div className="flex items-center justify-between">
          <div className="text-[12px] font-bold text-ink-soft">面试官点评</div>
          <Badge tone={feedback.score >= 4 ? "ok" : feedback.score >= 3 ? "neutral" : "warn"}>
            本题得分 {feedback.score}/5
          </Badge>
        </div>
        <p className="text-[13.5px] text-ink-soft mt-2 leading-relaxed">{feedback.feedback}</p>
        {feedback.score_hint ? (
          <p className="text-[11.5px] text-muted mt-1.5">{feedback.score_hint}</p>
        ) : null}
      </Card>
      <Card className="!py-4 border-t-[3px] border-t-[#d4d4d8]">
        <div className="text-[11.5px] text-muted">追问</div>
        <div className="text-[15px] font-semibold mt-1">{feedback.followup}</div>
        <TextArea
          className="mt-3 min-h-[70px]"
          value={followupText}
          onChange={(e) => setFollowupText(e.target.value)}
          placeholder="针对追问继续作答…"
        />
        <div className="flex gap-2 mt-3">
          <Button variant="primary" onClick={onSubmit} disabled={busy || !followupText.trim()}>
            <ArrowRight size={14} />
            {busy ? "提交中…" : "提交追问回答"}
          </Button>
        </div>
      </Card>
    </div>
  );
}

function AnsweredLog({ interviewId }: { interviewId: string }) {
  const [items, setItems] = useState<Array<{ question: string; answer: string }>>([]);
  useEffect(() => {
    api
      .getInterview(interviewId)
      .then((d) =>
        setItems(
          d.qa_list
            .filter((q) => q.answer && q.answer !== "（跳过）")
            .slice(0, 4)
            .map((q) => ({ question: q.question, answer: q.answer })),
        ),
      )
      .catch(() => undefined);
  }, [interviewId]);
  if (items.length === 0) return null;
  return (
    <div>
      <div className="text-[12px] font-bold text-ink-soft mb-2">已答题目回顾</div>
      <div className="space-y-1.5">
        {items.map((it, i) => (
          <div key={i} className="text-[12px] text-muted">
            <span className="font-medium text-ink-soft">{it.question}</span>
            <span className="truncate block">回答：{it.answer.slice(0, 120)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ErrorBanner({ text }: { text: string }) {
  return (
    <div className="rounded-[10px] border border-bad/25 bg-[#fdf3f3] px-4 py-2.5 text-[12.5px] text-bad">
      {text}
    </div>
  );
}
