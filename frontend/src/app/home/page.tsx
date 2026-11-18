import AppShell from "@/components/AppShell";
import ChatView from "@/components/ChatView";
import Header from "@/components/Header";

export default function HomePage() {
  return (
    <AppShell >
      <Header active="chat" />
      <ChatView />
    </AppShell>
  );
}
