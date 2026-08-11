import type { ReactNode } from "react";
import { Loader2, Star } from "lucide-react";

export function Button({
  children,
  variant = "secondary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  const map: Record<string, string> = {
    primary: "btn-primary",
    secondary: "btn-secondary",
    ghost: "btn-ghost",
    danger: "btn-danger",
  };
  return (
    <button className={`btn ${map[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}

export function Card({
  children,
  className = "",
  style,
}: {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div className={`panel p-5 ${className}`} style={style}>
      {children}
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-[13px] font-bold tracking-wide text-ink-soft mt-7 mb-2.5 first:mt-0">
      {children}
    </h2>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "accent" | "ok" | "warn" | "bad";
}) {
  const tones: Record<string, string> = {
    neutral: "border-line text-ink-soft bg-panel",
    accent: "border-accent/20 text-accent bg-accent-soft",
    ok: "border-ok/20 text-ok bg-[#f0f9f2]",
    warn: "border-warn/25 text-warn bg-[#fdf6ec]",
    bad: "border-bad/20 text-bad bg-[#fdf3f3]",
  };
  return <span className={`chip ${tones[tone]}`}>{children}</span>;
}

export function LevelBadge({ level }: { level: string }) {
  const map: Record<string, { label: string; tone: "ok" | "neutral" | "warn" | "bad" }> = {
    strong: { label: "扎实", tone: "ok" },
    solid: { label: "合格", tone: "neutral" },
    developing: { label: "待练", tone: "warn" },
    weak: { label: "薄弱", tone: "bad" },
  };
  const item = map[level] || { label: level, tone: "neutral" as const };
  return <Badge tone={item.tone}>{item.label}</Badge>;
}

export function Progress({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="progress-track">
      <div className="progress-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
      {hint ? <p className="text-[11.5px] text-muted mt-1.5">{hint}</p> : null}
    </div>
  );
}

export function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className="input min-h-[100px] resize-y leading-relaxed" {...props} />;
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className="input" {...props} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className="input cursor-pointer" {...props} />;
}

export function Stat({
  label,
  value,
  sub,
}: {
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <Card className="px-5 py-4">
      <div className="text-[11.5px] text-muted">{label}</div>
      <div className="display text-[30px] leading-tight mt-1">{value}</div>
      {sub ? <div className="text-[11.5px] text-faint mt-0.5">{sub}</div> : null}
    </Card>
  );
}

export function Spinner({ text = "处理中…" }: { text?: string }) {
  return (
    <div className="flex items-center gap-2 text-[13px] text-muted">
      <Loader2 size={15} className="animate-spin" />
      {text}
    </div>
  );
}

export function DifficultyStars({ value }: { value: number }) {
  return (
    <span className="inline-flex items-center gap-[2px] align-middle">
      {[1, 2, 3, 4, 5].map((i) => (
        <Star
          key={i}
          size={11}
          className={i <= value ? "text-accent fill-accent" : "text-line fill-line-2"}
        />
      ))}
    </span>
  );
}

export function BulletList({ items }: { items: string[] }) {
  if (!items || items.length === 0) return <div className="text-[12.5px] text-faint">暂无</div>;
  return (
    <ul className="space-y-1.5">
      {items.map((it, i) => (
        <li key={i} className="flex gap-2 text-[13px] text-ink-soft leading-relaxed">
          <span className="text-accent/70 mt-[9px] h-1 w-1 rounded-full bg-accent/50 shrink-0" />
          <span>{it}</span>
        </li>
      ))}
    </ul>
  );
}

export function EmptyState({ title, desc }: { title: string; desc?: string }) {
  return (
    <Card className="py-10 text-center">
      <div className="text-[14px] font-semibold text-ink-soft">{title}</div>
      {desc ? <div className="text-[12.5px] text-muted mt-1.5">{desc}</div> : null}
    </Card>
  );
}

export function Verdict({ score }: { score: number }) {
  const pass = score >= 60;
  return (
    <span
      className={`text-[13px] font-bold ${pass ? "text-ok" : "text-warn"}`}
    >
      {pass ? "达标" : "待加强"}
    </span>
  );
}
