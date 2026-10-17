import { useState } from "react";
import AppShell, { type PageKey } from "./components/AppShell";
import ErrorBoundary from "./components/ErrorBoundary";
import ChatPage from "./pages/ChatPage";
import InterviewPage from "./pages/InterviewPage";
import InsightsPage from "./pages/InsightsPage";
import HistoryPage from "./pages/HistoryPage";
import ProfilePage from "./pages/ProfilePage";

export default function App() {
  const [page, setPage] = useState<PageKey>("chat");
  // 切页时重置错误边界：一个页面崩了不该连累其他页面
  const [epoch, setEpoch] = useState(0);

  return (
    <AppShell
      page={page}
      onNavigate={(p) => {
        setPage(p);
        setEpoch((n) => n + 1);
      }}
    >
      <ErrorBoundary key={`${page}-${epoch}`} onReset={() => setEpoch((n) => n + 1)}>
        {page === "chat" && <ChatPage />}
        {page === "interview" && <InterviewPage />}
        {page === "war" && <InsightsPage />}
        {page === "history" && <HistoryPage />}
        {page === "profile" && <ProfilePage />}
      </ErrorBoundary>
    </AppShell>
  );
}
