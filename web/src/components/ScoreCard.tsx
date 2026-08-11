import type { Comparison, Report } from "../lib/types";
import { Badge, BulletList, Card, LevelBadge, Progress, SectionTitle, Verdict } from "./ui";

const DIMS = ["正确性", "深度", "结构", "表达", "风险意识"];

export default function ScoreCard({ report, comparison }: { report: Report; comparison?: Comparison | null }) {
  const total = report.total_score || 0;
  const dims = report.dimensions || {};
  const comps = report.competency_scores || [];
  const lang = report.language_report || {};
  const coach = report.coach_plan;
  const coverage = Math.round((report.coverage_pct ?? 1) * 100);

  return (
    <div className="space-y-1">
      <div className="grid grid-cols-1 lg:grid-cols-[200px_1fr_1fr] gap-4">
        <Card className="text-center !py-6">
          <div className="display text-[44px] leading-none text-accent">{total}</div>
          <div className="text-[12px] text-muted mt-1.5">综合得分</div>
          <div className="mt-2">
            <Verdict score={total} />
          </div>
        </Card>
        <Card>
          <SectionTitle>维度得分</SectionTitle>
          <div className="space-y-2.5">
            {DIMS.map((d) => (
              <div key={d}>
                <div className="flex justify-between text-[12px] text-ink-soft mb-1">
                  <span>{d}</span>
                  <span>{Math.round(dims[d] || 0)}</span>
                </div>
                <Progress value={dims[d] || 0} max={100} />
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <SectionTitle>与历史对比</SectionTitle>
          {comparison && comparison.history_count > 0 ? (
            <div className="space-y-2">
              {DIMS.map((d) => {
                const s = Math.round(dims[d] || 0);
                const a = Math.round((comparison.history_avg || {})[d] || 0);
                const delta = s - a;
                const arrow = delta > 5 ? "↑" : delta < -5 ? "↓" : "→";
                const cls = delta > 5 ? "text-ok" : delta < -5 ? "text-bad" : "text-muted";
                return (
                  <div key={d} className="flex justify-between text-[12px]">
                    <span className="text-ink-soft">{d}</span>
                    <span className={cls}>
                      {arrow} {s} vs {a}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-[12.5px] text-muted">首次完整面试，暂无历史场次可对比。</p>
          )}
        </Card>
      </div>

      {comps.length > 0 && (
        <>
          <SectionTitle>能力得分（0-5）</SectionTitle>
          <Card>
            <div className="space-y-3">
              {comps.map((c, i) => (
                <div key={i}>
                  <div className="flex items-center justify-between text-[12.5px] mb-1">
                    <span className="font-medium text-ink-soft flex items-center gap-2">
                      {c.competency}
                      <LevelBadge level={c.level} />
                    </span>
                    <span className="text-ink-soft">{c.score}</span>
                  </div>
                  <Progress value={c.score} max={5} />
                  {c.evidence ? (
                    <details className="mt-1 text-[11.5px] text-muted">
                      <summary className="cursor-pointer">得分依据</summary>
                      <div className="mt-1">{c.evidence}</div>
                    </details>
                  ) : null}
                </div>
              ))}
            </div>
            <p className="text-[11.5px] text-faint mt-3">有效作答覆盖率 {coverage}%（未作答的能力不计入弱项）</p>
          </Card>
        </>
      )}

      {report.summary && (
        <>
          <SectionTitle>面试官总结</SectionTitle>
          <Card className="!py-4 text-[13.5px] leading-relaxed text-ink-soft">{report.summary}</Card>
        </>
      )}

      <SectionTitle>亮点 / 不足 / 缺失 / 建议</SectionTitle>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card>
          <div className="text-[12.5px] font-bold text-ink-soft mb-2">亮点</div>
          <BulletList items={report.highlights} />
          <div className="text-[12.5px] font-bold text-ink-soft mb-2 mt-5">不足</div>
          <BulletList items={report.weaknesses} />
        </Card>
        <Card>
          <div className="text-[12.5px] font-bold text-ink-soft mb-2">缺失关键点</div>
          <BulletList items={report.missing_points} />
          <div className="text-[12.5px] font-bold text-ink-soft mb-2 mt-5">改进建议</div>
          <BulletList items={report.suggestions} />
        </Card>
      </div>

      {(lang.structure_score !== undefined || lang.clarity_score !== undefined) && (
        <>
          <SectionTitle>表达报告（0-5）</SectionTitle>
          <Card className="!py-4">
            <div className="grid grid-cols-3 gap-3 text-center">
              {[
                ["结构", lang.structure_score],
                ["清晰", lang.clarity_score],
                ["简洁", lang.conciseness_score],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <div className="text-[11.5px] text-muted">{label}</div>
                  <div className="display text-[22px]">{value ?? "—"}</div>
                </div>
              ))}
            </div>
            {lang.summary ? <p className="text-[12.5px] text-muted mt-3">{lang.summary}</p> : null}
          </Card>
        </>
      )}

      {report.next_steps?.length > 0 && (
        <>
          <SectionTitle>下一步行动</SectionTitle>
          <Card>
            <BulletList items={report.next_steps} />
          </Card>
        </>
      )}

      {report.model_answers?.length > 0 && (
        <>
          <SectionTitle>改进版参考答案（挑最弱题）</SectionTitle>
          <div className="space-y-2">
            {report.model_answers.slice(0, 3).map((ma, i) => (
              <Card key={i} className="!p-4">
                <div className="text-[13px] font-semibold">{ma.question}</div>
                <div className="text-[13px] text-ink-soft mt-2 leading-relaxed whitespace-pre-wrap">{ma.answer}</div>
              </Card>
            ))}
          </div>
        </>
      )}

      {coach?.modules?.length ? (
        <>
          <SectionTitle>学习教练 · 本周计划（约 {coach.total_min} 分钟）</SectionTitle>
          <div className="space-y-2">
            {coach.modules.map((m, i) => (
              <Card key={i} className="!p-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-[13.5px] font-semibold">
                    📚 {m.title}
                    <Badge>{m.competency}</Badge>
                  </div>
                  <span className="text-[11.5px] text-muted shrink-0">{m.est_min} 分钟</span>
                </div>
                <p className="text-[12.5px] text-muted mt-1.5">为什么补：{m.rationale}</p>
                <div className="mt-2.5">
                  <div className="text-[12px] font-bold text-ink-soft mb-1.5">学习要点</div>
                  <BulletList items={m.focus_points} />
                </div>
                {m.sources?.length ? (
                  <div className="mt-3">
                    <div className="text-[12px] font-bold text-ink-soft mb-1.5">知识库材料</div>
                    <BulletList items={m.sources} />
                  </div>
                ) : null}
              </Card>
            ))}
          </div>
        </>
      ) : null}

      {comparison && comparison.history_count > 0 && (
        <>
          <SectionTitle>成长对比（历史 {comparison.history_count} 场）</SectionTitle>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <div className="text-[12.5px] font-bold text-ok mb-2">进步</div>
              <BulletList items={comparison.progress} />
              <div className="text-[12.5px] font-bold text-bad mb-2 mt-5">退步</div>
              <BulletList items={comparison.regress} />
            </Card>
            <Card>
              <div className="text-[12.5px] font-bold text-ink-soft mb-2">稳定</div>
              <BulletList items={comparison.stable} />
              <div className="text-[12.5px] font-bold text-warn mb-2 mt-5">优先加强</div>
              <BulletList items={comparison.priority} />
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
