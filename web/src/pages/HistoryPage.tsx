import { useEffect, useState } from "react";
import { ChevronRight, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import type { InterviewDetail, InterviewSummary } from "../lib/types";
import { Button, Card, EmptyState, SectionTitle } from "../components/ui";
import ScoreCard from "../components/ScoreCard";

export default function HistoryPage() {
  const [interviews, setInterviews] = useState<InterviewSummary[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<InterviewDetail | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const list = await api.listInterviews();
    setInterviews(list);
    if (selected && !list.some((i) => i.id === selected)) setSelected(null);
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    setBusy(true);
    api
      .getInterview(selected)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setBusy(false));
  }, [selected]);

  if (interviews === null) return <EmptyState title="加载中…" />;
  const finished = interviews.filter((i) => i.status === "finished");
  const ongoing = interviews.filter((i) => i.status !== "finished");

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-5">
      <div className="space-y-2">
        {ongoing.length > 0 && (
          <>
            <div className="text-[11.5px] text-muted">进行中 {ongoing.length} 场</div>
            {ongoing.map((o) => (
              <Row key={o.id} item={o} onClick={() => setSelected(o.id)} active={selected === o.id} />
            ))}
          </>
        )}
        <div className="text-[11.5px] text-muted">已完成场次（{finished.length}）</div>
        {finished.length === 0 && ongoing.length === 0 ? (
          <EmptyState title="还没有历史报告" desc="完成一场模拟面试后，评分报告会保存在这里。" />
        ) : (
          finished.map((i) => (
            <Row key={i.id} item={i} onClick={() => setSelected(i.id)} active={selected === i.id} />
          ))
        )}
      </div>

      <div className="min-w-0">
        {busy && <EmptyState title="加载中…" />}
        {!busy && !detail && <EmptyState title="选择左侧一场面试查看报告" />}
        {!busy && detail && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="text-[13px] text-muted">
                {detail.interview.direction} ·{" "}
                {detail.interview.finished_at.slice(0, 16).replace("T", " ")}
              </div>
              <Button
                variant="danger"
                onClick={async () => {
                  await api.deleteInterview(detail.interview.id);
                  setSelected(null);
                  refresh();
                }}
              >
                <Trash2 size={13} />
                删除本场
              </Button>
            </div>
            {detail.report ? (
              <ScoreCard report={detail.report} />
            ) : (
              <EmptyState title="该场次暂无报告" />
            )}
            {detail.qa_list.length > 0 && (
              <>
                <SectionTitle>本场问答记录</SectionTitle>
                <div className="space-y-2">
                  {detail.qa_list.map((qa, i) => (
                    <Card key={qa.id} className="!p-4">
                      <div className="text-[13px] font-semibold">
                        第 {i + 1} 题（{qa.topic} · {qa.level}）：{qa.question}
                      </div>
                      {qa.answer ? (
                        <p className="text-[12.5px] text-ink-soft mt-1.5">
                          <span className="text-muted">我的回答：</span>
                          {qa.answer.slice(0, 300)}
                        </p>
                      ) : null}
                      {qa.feedback ? (
                        <p className="text-[12.5px] text-ink-soft mt-1">
                          <span className="text-muted">点评：</span>
                          {qa.feedback.slice(0, 200)}
                        </p>
                      ) : null}
                      {qa.followup ? (
                        <p className="text-[12.5px] text-ink-soft mt-1">
                          <span className="text-muted">追问：</span>
                          {qa.followup}
                        </p>
                      ) : null}
                      {qa.followup_answer ? (
                        <p className="text-[12.5px] text-ink-soft mt-1">
                          <span className="text-muted">追问作答：</span>
                          {qa.followup_answer.slice(0, 200)}
                        </p>
                      ) : null}
                    </Card>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Row({
  item,
  onClick,
  active,
}: {
  item: InterviewSummary;
  onClick: () => void;
  active: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-[11px] border px-3.5 py-3 transition-colors ${
        active
          ? "border-accent/30 bg-accent-soft"
          : "border-line bg-panel hover:border-accent/25"
      }`}
    >
      <div className="flex items-center justify-between text-[13px] font-medium text-ink-soft">
        <span>{item.direction}</span>
        <span className="text-[12px] text-muted">{item.status === "finished" ? `${item.score} 分` : "进行中"}</span>
      </div>
      <div className="flex items-center justify-between mt-1 text-[11px] text-faint">
        <span>{item.finished_at ? item.finished_at.slice(0, 16).replace("T", " ") : item.created_at.slice(0, 16).replace("T", " ")}</span>
        <ChevronRight size={12} />
      </div>
    </button>
  );
}
