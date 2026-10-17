import { useState } from "react";
import WarRoomPage from "./WarRoomPage";
import ReviewPage from "./ReviewPage";

/**
 * 复盘与作战室（合并页）。

  早期拆成两个导航项，但它们看的是同一份数据：作战室里的「待办」来自面试报告，
  面经复盘的产出也回写到同一个 dashboard。用户实际的心智模型是「我的复盘」一件事，
  所以收成一个页面里的两个标签。
 */
type Tab = "war" | "review";

const TABS: Array<{ key: Tab; label: string }> = [
  { key: "war", label: "作战室" },
  { key: "review", label: "面经复盘" },
];

export default function InsightsPage() {
  const [tab, setTab] = useState<Tab>("war");

  return (
    <div>
      <div className="flex gap-1.5 mb-5">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-full px-4 py-1.5 text-[12.5px] font-medium transition-colors ${
              tab === t.key
                ? "bg-accent text-white"
                : "bg-panel text-muted border border-line hover:border-accent/40"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === "war" ? <WarRoomPage /> : <ReviewPage />}
    </div>
  );
}
