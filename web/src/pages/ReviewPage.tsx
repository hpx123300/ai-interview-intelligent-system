import { useState } from "react";
import { FileText, Save } from "lucide-react";
import { api } from "../lib/api";
import type { Review } from "../lib/types";
import { Button, BulletList, Card, SectionTitle, Spinner, TextArea } from "../components/ui";

export default function ReviewPage() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [review, setReview] = useState<Review | null>(null);

  async function run() {
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.createReview(text.trim());
      setReview(res.review);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl space-y-4">
      {error && (
        <div className="rounded-[10px] border border-bad/25 bg-[#fdf3f3] px-4 py-2.5 text-[12.5px] text-bad">{error}</div>
      )}
      <Card>
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-accent" />
          <span className="text-[15px] font-bold">面试复盘</span>
        </div>
        <p className="text-[12.5px] text-muted mt-1.5">
          把真实面试经历贴进来，AI 会整理出亮点、暴露的问题、必会知识点和行动清单。经历越具体，复盘越有效。
        </p>
        <TextArea
          className="mt-4 min-h-[160px]"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="例如：面了一家 AI 创业公司……问了 RAG 原理，我讲了流程但没答出向量检索细节……"
        />
        <div className="mt-3">
          <Button variant="primary" onClick={run} disabled={busy || !text.trim()}>
            {busy ? <Spinner text="复盘教练分析中…" /> : (
              <>
                <Save size={14} />
                开始复盘
              </>
            )}
          </Button>
        </div>
      </Card>

      {review && (
        <>
          <SectionTitle>复盘结果（已保存到求职作战室）</SectionTitle>
          <Card className="!py-4 text-[13.5px] leading-relaxed text-ink-soft">{review.summary}</Card>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <div className="text-[12.5px] font-bold text-ink-soft mb-2">亮点</div>
              <BulletList items={review.highlights} />
              <div className="text-[12.5px] font-bold text-ink-soft mb-2 mt-5">必会知识点</div>
              <BulletList items={review.key_points} />
            </Card>
            <Card>
              <div className="text-[12.5px] font-bold text-ink-soft mb-2">暴露的问题</div>
              <BulletList items={review.weaknesses} />
              <div className="text-[12.5px] font-bold text-ink-soft mb-2 mt-5">行动计划</div>
              <BulletList items={review.action_plan} />
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
