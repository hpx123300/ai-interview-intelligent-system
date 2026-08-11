import type { ReactNode } from "react";
import {
  ClipboardList,
  History,
  LayoutDashboard,
  MessageSquare,
  UserRound,
  FileText,
} from "lucide-react";

export type PageKey = "chat" | "interview" | "review" | "war" | "history" | "profile";

const NAV: Array<{ key: PageKey; label: string; icon: typeof MessageSquare }> = [
  { key: "chat", label: "自由对话", icon: MessageSquare },
  { key: "interview", label: "模拟面试", icon: ClipboardList },
  { key: "review", label: "面经复盘", icon: FileText },
  { key: "war", label: "求职作战室", icon: LayoutDashboard },
  { key: "history", label: "历史报告", icon: History },
  { key: "profile", label: "我的档案", icon: UserRound },
];

const TITLES: Record<PageKey, { eyebrow: string; title: string; desc: string }> = {
  chat: { eyebrow: "Free Chat", title: "自由对话", desc: "多 Agent 协作：面试官 / 八股讲师 / 求职顾问" },
  interview: { eyebrow: "Mock Interview", title: "模拟面试", desc: "JD 画像 + 项目深挖 + 评分标准驱动的完整闭环" },
  review: { eyebrow: "Review", title: "面经复盘", desc: "把真实面试经历贴进来，AI 生成复盘与行动清单" },
  war: { eyebrow: "War Room", title: "求职作战室", desc: "得分趋势 / 薄弱维度 / 待办清单 / 复盘归档" },
  history: { eyebrow: "History", title: "历史报告", desc: "回看历次面试的评分报告与问答记录" },
  profile: { eyebrow: "Profile", title: "我的档案", desc: "目标岗位 + 项目经历 + 目标 JD，驱动个性化出题" },
};

export default function AppShell({
  page,
  onNavigate,
  children,
}: {
  page: PageKey;
  onNavigate: (p: PageKey) => void;
  children: ReactNode;
}) {
  const meta = TITLES[page];
  return (
    <div className="min-h-screen flex">
      {/* 侧边栏 */}
      <aside className="hidden md:flex w-[208px] shrink-0 flex-col border-r border-line bg-[#f6f4ef] px-3 py-5">
        <div className="flex items-center gap-2.5 px-2 mb-8">
          <div className="h-8 w-8 rounded-[10px] bg-accent text-white grid place-items-center font-bold text-[15px]">
            面
          </div>
          <div className="leading-tight">
            <div className="text-[13.5px] font-bold text-ink">面试备战助手</div>
            <div className="text-[10.5px] text-faint">AI Interview Coach</div>
          </div>
        </div>
        <nav className="space-y-1">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = page === item.key;
            return (
              <button
                key={item.key}
                onClick={() => onNavigate(item.key)}
                className={`w-full flex items-center gap-2.5 rounded-[10px] px-3 py-2 text-[13px] font-medium transition-colors ${
                  active
                    ? "bg-panel text-accent shadow-[0_1px_2px_rgba(23,23,26,0.06)] border border-line"
                    : "text-ink-soft hover:bg-panel/70"
                }`}
              >
                <Icon size={15} strokeWidth={2} />
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="mt-auto px-2 pt-6 text-[10.5px] leading-relaxed text-faint">
          借鉴 DeepInterview · 聆悟
          <br />
          面试记录保存在本地 SQLite
        </div>
      </aside>

      {/* 主区域 */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* 移动端导航 */}
        <div className="md:hidden flex gap-1.5 overflow-x-auto px-4 pt-4 pb-1 border-b border-line bg-paper">
          {NAV.map((item) => {
            const Icon = item.icon;
            const active = page === item.key;
            return (
              <button
                key={item.key}
                onClick={() => onNavigate(item.key)}
                className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-[12px] font-medium whitespace-nowrap ${
                  active ? "bg-accent text-white" : "bg-panel text-muted border border-line"
                }`}
              >
                <Icon size={12} />
                {item.label}
              </button>
            );
          })}
        </div>
        <header className="px-6 md:px-10 pt-7 md:pt-9 pb-2">
          <div className="eyebrow">{meta.eyebrow}</div>
          <h1 className="display text-[26px] md:text-[30px] mt-1 text-ink">{meta.title}</h1>
          <p className="text-[13px] text-muted mt-1.5">{meta.desc}</p>
        </header>
        <main className="flex-1 px-6 md:px-10 pb-16 pt-4">{children}</main>
      </div>
    </div>
  );
}
