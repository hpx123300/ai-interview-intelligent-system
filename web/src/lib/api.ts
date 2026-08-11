import type {
  AnswerFeedback,
  ChatMessage,
  Dashboard,
  Interviewer,
  InterviewDesign,
  InterviewDetail,
  InterviewSummary,
  JdAnalysis,
  Profile,
  Question,
  Report,
  Review,
  ToolCard,
  Comparison,
} from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = Array.isArray(data?.detail)
      ? data.detail.map((d: { msg?: string }) => d.msg || "").join("；")
      : data?.detail;
    throw new Error(data?.error || detail || `请求失败（${res.status}）`);
  }
  return data as T;
}

export interface StartResult {
  interview_id: string;
  questions: Question[];
  project_count: number;
  qa_id: number;
  direction: string;
  interviewer?: Interviewer;
}

export interface FinishResult {
  report: Report;
  comparison: Comparison;
}

export const api = {
  getProfile: () => request<Profile>("/api/profile"),
  saveProfile: (p: Partial<Profile>) =>
    request<Profile>("/api/profile", {
      method: "PUT",
      body: JSON.stringify({ profile: p }),
    }),
  analyzeJd: (jdText: string, profile?: Partial<Profile>) =>
    request<JdAnalysis>("/api/profile/analyze-jd", {
      method: "POST",
      body: JSON.stringify({ jd_text: jdText, profile: profile || {} }),
    }),

  startInterview: (direction: string, count: number) =>
    request<StartResult>("/api/interview/start", {
      method: "POST",
      body: JSON.stringify({ direction, count }),
    }),
  designInterview: (goal: string, jdText: string, resumeText: string, duration: number) =>
    request<InterviewDesign>("/api/interview/design", {
      method: "POST",
      body: JSON.stringify({ goal, jd_text: jdText, resume_text: resumeText, duration }),
    }),
  startFromDesign: (design: InterviewDesign) =>
    request<StartResult>("/api/interview/start", {
      method: "POST",
      body: JSON.stringify({ design }),
    }),

  submitAnswer: (interviewId: string, qaId: number, question: Question, answer: string) =>
    request<AnswerFeedback>("/api/interview/answer", {
      method: "POST",
      body: JSON.stringify({ interview_id: interviewId, qa_id: qaId, question, answer }),
    }),
  submitFollowup: (qaId: number, answer: string) =>
    request<{ ok: boolean }>("/api/interview/followup", {
      method: "POST",
      body: JSON.stringify({ qa_id: qaId, answer }),
    }),
  nextQuestion: (interviewId: string, question: Question) =>
    request<{ qa_id: number }>("/api/interview/next", {
      method: "POST",
      body: JSON.stringify({ interview_id: interviewId, question }),
    }),
  skipQuestion: (qaId: number) =>
    request<{ ok: boolean }>("/api/interview/skip", {
      method: "POST",
      body: JSON.stringify({ qa_id: qaId }),
    }),
  getReference: (qaId: number, question: string, answer: string = "") =>
    request<{ reference: string }>("/api/interview/reference", {
      method: "POST",
      body: JSON.stringify({ qa_id: qaId, question, answer }),
    }),
  finishInterview: (interviewId: string) =>
    request<FinishResult>("/api/interview/finish", {
      method: "POST",
      body: JSON.stringify({ interview_id: interviewId }),
    }),

  listInterviews: () => request<InterviewSummary[]>("/api/interviews"),
  getInterview: (id: string) => request<InterviewDetail>(`/api/interviews/${id}`),
  deleteInterview: (id: string) =>
    request<{ ok: boolean }>(`/api/interviews/${id}`, { method: "DELETE" }),
  dashboard: () => request<Dashboard>("/api/dashboard"),

  createReview: (text: string) =>
    request<{ review: Review }>("/api/reviews", {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  listReviews: () => request<Review[]>("/api/reviews"),
  deleteReview: (id: number) =>
    request<{ ok: boolean }>(`/api/reviews/${id}`, { method: "DELETE" }),

  async streamChat(
    prompt: string,
    sessionId: string,
    handlers: {
      onToken: (t: string) => void;
      onTool: (label: string) => void;
      onCards: (cards: ToolCard[]) => void;
      onTrace: (trace: unknown[]) => void;
    },
  ): Promise<string> {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: prompt, session_id: sessionId }),
    });
    if (!res.ok || !res.body) {
      throw new Error(`对话请求失败（${res.status}）`);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let full = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data:")) continue;
        const payload = trimmed.slice(5).trim();
        if (!payload) continue;
        try {
          const msg = JSON.parse(payload);
          if (msg.type === "token") {
            full += msg.text;
            handlers.onToken(msg.text);
          } else if (msg.type === "tool") {
            handlers.onTool(msg.label);
          } else if (msg.type === "cards") {
            handlers.onCards(msg.cards);
          } else if (msg.type === "trace") {
            handlers.onTrace(msg.trace);
          }
        } catch {
          // ignore malformed frames
        }
      }
    }
    return full;
  },

  getChatHistory: (sessionId: string) =>
    request<ChatMessage[]>(`/api/chat/history?session_id=${encodeURIComponent(sessionId)}`),
  clearChatHistoryServer: (sessionId: string) =>
    request<{ ok: boolean }>(`/api/chat/history?session_id=${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
    }),
  ocrJdImage: async (file: File): Promise<{ text: string; ocr: string }> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/jd/ocr", { method: "POST", body: form });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(data?.error || `图片识别失败（${res.status}）`);
    }
    return data;
  },
  parseResume: async (file: File): Promise<{ text: string; parsed: Partial<Profile> }> => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/resume/parse", { method: "POST", body: form });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(data?.error || `简历解析失败（${res.status}）`);
    }
    return data;
  },
};

export function loadChatHistory(): ChatMessage[] {
  try {
    return JSON.parse(localStorage.getItem("chat_history") || "[]");
  } catch {
    return [];
  }
}

export function saveChatHistory(messages: ChatMessage[]) {
  localStorage.setItem("chat_history", JSON.stringify(messages.slice(-40)));
}

export function clearChatHistory() {
  localStorage.removeItem("chat_history");
}
