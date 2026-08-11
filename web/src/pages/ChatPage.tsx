import { useEffect, useRef, useState } from "react";
import { Send, Sparkles, Plus, BookOpen, Briefcase } from "lucide-react";
import { api, clearChatHistory, loadChatHistory, saveChatHistory } from "../lib/api";
import type { ChatMessage, ToolCard } from "../lib/types";
import { Button, Card } from "../components/ui";

const QUICK = ["模拟一场 Python 后端面试", "讲讲 RAG 的原理", "广州有哪些大模型实习"];

interface UiMessage extends ChatMessage {
  cards?: ToolCard[];
  trace?: unknown[];
}

export default function ChatPage() {
  const [messages, setMessages] = useState<UiMessage[]>(loadChatHistory());
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [toolLabel, setToolLabel] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>(() => localStorage.getItem("chat_session") || "");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let sid = sessionId;
    if (!sid) {
      sid = newSessionId();
      localStorage.setItem("chat_session", sid);
      setSessionId(sid);
    }
    api
      .getChatHistory(sid)
      .then((rows) => {
        if (rows.length > 0) {
          const ui = rows.map(({ role, content }) => ({ role, content }));
          setMessages(ui);
          saveChatHistory(ui);
        }
      })
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, toolLabel]);

  async function send(prompt: string) {
    const text = prompt.trim();
    if (!text || busy) return;
    setInput("");
    const next: UiMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    saveChatHistory(next.map(({ role, content }) => ({ role, content })));
    setBusy(true);
    const assistant: UiMessage = { role: "assistant", content: "" };
    try {
      await api.streamChat(text, sessionId, {
        onToken: (t) => {
          assistant.content += t;
          setMessages((prev) => {
            return [...prev.slice(0, -1), { ...assistant }];
          });
        },
        onTool: (label) => setToolLabel(label),
        onCards: (cards) => {
          assistant.cards = cards;
        },
        onTrace: (trace) => {
          assistant.trace = trace;
        },
      });
    } catch (e) {
      assistant.content = `出错了：${(e as Error).message}`;
    } finally {
      setToolLabel(null);
      setBusy(false);
      setMessages((prev) => {
        const copy = [...prev];
        if (copy.length && copy[copy.length - 1].role === "assistant") {
          copy[copy.length - 1] = assistant;
        } else {
          copy.push(assistant);
        }
        saveChatHistory(copy.map(({ role, content }) => ({ role, content })));
        return copy;
      });
    }
  }

  return (
    <div className="max-w-3xl mx-auto flex flex-col" style={{ minHeight: "calc(100vh - 240px)" }}>
      <div className="flex-1 space-y-5">
        {messages.length === 0 && (
          <Card className="py-12 px-8 text-center">
            <div className="mx-auto h-12 w-12 rounded-2xl bg-accent-soft grid place-items-center">
              <Sparkles size={20} className="text-accent" />
            </div>
            <div className="display text-[19px] mt-4">你好，我是 AI 面试备战助手</div>
            <p className="text-[13px] text-muted mt-2 max-w-sm mx-auto">
              可以模拟面试、讲解八股、查实习岗位。主管 Agent 会判断意图并分派给
              模拟面试官 / 八股讲师 / 求职顾问。
            </p>
            <div className="flex flex-wrap justify-center gap-2 mt-6">
              {QUICK.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="chip hover:border-accent/40 hover:text-accent cursor-pointer transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </Card>
        )}

        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}

        {busy && (
          <div className="flex items-center gap-2 text-[12.5px] text-muted pl-1">
            <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
            {toolLabel ? `正在${toolLabel}…` : "正在思考…"}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="sticky bottom-4 mt-6">
        <div className="panel flex items-end gap-2 p-2 pl-4 shadow-[0_8px_30px_rgba(23,23,26,0.08)]">
          <input
            className="flex-1 bg-transparent outline-none text-[14px] py-2"
            placeholder="输入问题，例如：模拟一场 AI 应用开发面试"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(input)}
          />
          {messages.length > 0 && (
            <button
              onClick={async () => {
                if (sessionId) {
                  api.clearChatHistoryServer(sessionId).catch(() => undefined);
                }
                const sid = newSessionId();
                localStorage.setItem("chat_session", sid);
                setSessionId(sid);
                clearChatHistory();
                setMessages([]);
              }}
              className="btn btn-ghost !px-2.5 text-[12px]"
              title="清空对话"
            >
              <Plus size={14} className="rotate-45" />
            </button>
          )}
          <Button variant="primary" onClick={() => send(input)} disabled={busy || !input.trim()}>
            <Send size={14} />
            发送
          </Button>
        </div>
      </div>
    </div>
  );
}

function newSessionId(): string {
  try {
    return `web-${crypto.randomUUID().slice(0, 8)}`;
  } catch {
    return `web-${Math.random().toString(36).slice(2, 10)}${Date.now().toString(36).slice(-4)}`;
  }
}

function MessageBubble({ message }: { message: UiMessage }) {
  const user = message.role === "user";
  const tools = (message.trace || []).filter(
    (t: any) => t.step === "tool",
  ) as Array<{ step: string; content: string }>;
  return (
    <div className={`flex ${user ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[86%] ${user ? "" : "w-full"}`}>
        {!user && (
          <div className="flex items-center gap-2 mb-1.5">
            <div className="h-6 w-6 rounded-lg bg-accent text-white grid place-items-center text-[11px] font-bold">
              面
            </div>
            <span className="text-[11.5px] text-faint">AI 面试备战助手</span>
          </div>
        )}
        <div
          className={`rounded-2xl px-4 py-3 text-[13.5px] leading-relaxed whitespace-pre-wrap ${
            user
              ? "bg-accent text-white rounded-br-md"
              : "bg-panel border border-line rounded-bl-md"
          }`}
        >
          {message.content || (message.trace ? "" : "…")}
        </div>
        {message.cards?.map((card, i) => <ToolCards key={i} card={card} />)}
        {tools.length > 0 && (
          <details className="mt-1.5 text-[11.5px] text-faint">
            <summary className="cursor-pointer select-none">服务明细（{tools.length} 步）</summary>
            <div className="mt-1 space-y-0.5">
              {tools.map((t, i) => (
                <div key={i} className="truncate">{t.content}</div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

function ToolCards({ card }: { card: ToolCard }) {
  if (card.type === "questions" && Array.isArray(card.items)) {
    return (
      <div className="mt-2 space-y-2">
        {card.items.slice(0, 3).map((q: any, i) => (
          <Card key={i} className="!p-3.5">
            <div className="flex items-center gap-2 text-[11px] text-muted">
              <BookOpen size={12} />
              {q.topic} · {q.level}
            </div>
            <div className="text-[13px] font-semibold mt-1">{q.question}</div>
            {q.hint ? <div className="text-[11.5px] text-muted mt-1">💡 {q.hint}</div> : null}
          </Card>
        ))}
      </div>
    );
  }
  if (card.type === "jobs" && Array.isArray(card.items)) {
    return (
      <div className="mt-2 space-y-2">
        {card.items.slice(0, 3).map((j: any, i) => (
          <Card key={i} className="!p-3.5">
            <div className="flex items-center gap-2">
              <Briefcase size={13} className="text-accent" />
              <span className="text-[13px] font-semibold">{j.title}</span>
              <span className="text-[11px] text-muted">{j.company}</span>
            </div>
            <div className="text-[11.5px] text-muted mt-1">
              {j.city} | {j.salary} | {j.direction}
            </div>
          </Card>
        ))}
      </div>
    );
  }
  return null;
}
