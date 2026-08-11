import { useEffect, useState } from "react";
import { CheckCircle2, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import type { Dashboard } from "../lib/types";
import { Button, Card, EmptyState, Progress, SectionTitle, Stat } from "../components/ui";

const DONE_KEY = "war_todo_done";

export default function WarRoomPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [done, setDone] = useState<Set<number>>(() => {
    try {
      return new Set(JSON.parse(localStorage.getItem(DONE_KEY) || "[]"));
    } catch {
      return new Set();
    }
  });
  const [reviews, setReviews] = useState(data?.reviews || []);

  async function refresh() {
    const d = await api.dashboard();
    setData(d);
    setReviews(d.reviews);
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  function toggle(i: number) {
    const next = new Set(done);
    if (next.has(i)) next.delete(i);
    else next.add(i);
    setDone(next);
    localStorage.setItem(DONE_KEY, JSON.stringify([...next]));
  }

  if (!data) return <EmptyState title="加载中…" />;
  if (data.total_sessions === 0 && data.reviews.length === 0) {
    return (
      <div className="max-w-3xl">
        <EmptyState
          title="还没有数据"
          desc="完成一场模拟面试或一次面经复盘后，这里会长出你的成长曲线。"
        />
      </div>
    );
  }

  return (
    <div className="max-w-4xl space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Stat label="完成场次" value={data.total_sessions} />
        <Stat label="平均分" value={data.avg_score ?? "—"} />
        <Stat label="最高分" value={data.max_score ?? "—"} />
        <Stat label="最近一次" value={data.last_score ?? "—"} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <SectionTitle>得分趋势</SectionTitle>
          {data.trend.length > 1 ? (
            <TrendChart values={data.trend} />
          ) : (
            <p className="text-[12.5px] text-muted">至少完成两场模拟面试后展示趋势。</p>
          )}
        </Card>
        <Card>
          <SectionTitle>薄弱维度</SectionTitle>
          <div className="space-y-3">
            {data.weak_dimensions.map((d) => (
              <div key={d.name}>
                <div className="flex justify-between text-[12.5px] text-ink-soft mb-1">
                  <span>{d.name}</span>
                  <span>{d.score}</span>
                </div>
                <Progress value={d.score} max={100} />
              </div>
            ))}
          </div>
          <p className="text-[11.5px] text-faint mt-3">
            优先补分最低的维度，配合「历史报告」定位薄弱环节。
          </p>
        </Card>
      </div>

      <Card>
        <SectionTitle>待办清单（来自评分建议 + 学习教练 + 复盘行动计划）</SectionTitle>
        {data.todos.length === 0 ? (
          <p className="text-[12.5px] text-muted">暂无待办，完成一场面试或复盘后自动生成。</p>
        ) : (
          <>
            <div className="space-y-1.5">
              {data.todos.map((todo, i) => {
                const checked = done.has(i);
                return (
                  <button
                    key={i}
                    onClick={() => toggle(i)}
                    className={`w-full text-left flex items-start gap-2.5 rounded-[9px] px-3 py-2 transition-colors hover:bg-[#f6f4ef] ${
                      checked ? "opacity-50" : ""
                    }`}
                  >
                    <CheckCircle2
                      size={16}
                      className={checked ? "text-ok mt-0.5" : "text-faint mt-0.5"}
                    />
                    <span className={`text-[13px] ${checked ? "line-through text-muted" : "text-ink-soft"}`}>
                      {todo}
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="mt-3">
              <Button
                variant="ghost"
                onClick={() => {
                  setDone(new Set());
                  localStorage.removeItem(DONE_KEY);
                }}
              >
                清空勾选
              </Button>
            </div>
          </>
        )}
      </Card>

      {reviews.length > 0 && (
        <>
          <SectionTitle>历史复盘（{reviews.length}）</SectionTitle>
          <div className="space-y-2">
            {reviews.map((rv) => (
              <Card key={rv.id} className="!p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold">
                      {rv.created_at.slice(0, 16).replace("T", " ")} · {rv.summary.slice(0, 40)}
                    </div>
                    <details className="mt-2 text-[12px] text-muted">
                      <summary className="cursor-pointer">查看详情</summary>
                      <div className="mt-2 space-y-2">
                        <div><span className="font-medium text-ink-soft">亮点：</span>{rv.highlights.join("；")}</div>
                        <div><span className="font-medium text-ink-soft">问题：</span>{rv.weaknesses.join("；")}</div>
                        <div><span className="font-medium text-ink-soft">知识点：</span>{rv.key_points.join("；")}</div>
                        <div><span className="font-medium text-ink-soft">行动：</span>{rv.action_plan.join("；")}</div>
                      </div>
                    </details>
                  </div>
                  <Button
                    variant="danger"
                    className="!px-2.5"
                    onClick={async () => {
                      await api.deleteReview(rv.id);
                      refresh();
                    }}
                  >
                    <Trash2 size={13} />
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function TrendChart({ values }: { values: number[] }) {
  const w = 420;
  const h = 130;
  const pad = 8;
  const max = Math.max(...values, 60);
  const min = Math.min(...values, 0);
  const span = Math.max(max - min, 1);
  const stepX = values.length > 1 ? (w - pad * 2) / (values.length - 1) : 0;
  const pts = values.map((v, i) => {
    const x = pad + i * stepX;
    const y = h - pad - ((v - min) / span) * (h - pad * 2);
    return [x, y] as const;
  });
  const line = pts.map((p) => p.join(",")).join(" ");
  return (
    <div>
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto">
        <polyline
          points={line}
          fill="none"
          stroke="#4338ca"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {pts.map((p, i) => (
          <circle key={i} cx={p[0]} cy={p[1]} r="3.5" fill="#4338ca" />
        ))}
      </svg>
      <div className="flex justify-between text-[11px] text-faint mt-1">
        {pts.map((p, i) => (
          <span key={i}>{values[i]}</span>
        ))}
      </div>
    </div>
  );
}
