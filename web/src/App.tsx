import { useState } from "react";
import AppShell, { type PageKey } from "./components/AppShell";
import ChatPage from "./pages/ChatPage";
import InterviewPage from "./pages/InterviewPage";
import ReviewPage from "./pages/ReviewPage";
import WarRoomPage from "./pages/WarRoomPage";
import HistoryPage from "./pages/HistoryPage";
import ProfilePage from "./pages/ProfilePage";

export default function App() {
  const [page, setPage] = useState<PageKey>("chat");
  return (
    <AppShell page={page} onNavigate={setPage}>
      {page === "chat" && <ChatPage />}
      {page === "interview" && <InterviewPage />}
      {page === "review" && <ReviewPage />}
      {page === "war" && <WarRoomPage />}
      {page === "history" && <HistoryPage />}
      {page === "profile" && <ProfilePage />}
    </AppShell>
  );
}
