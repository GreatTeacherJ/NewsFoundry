import AppShell from "@/components/AppShell";
import ChatView from "@/components/ChatView";

export default function HomePage() {
  return (
    <AppShell active="chat">
      <ChatView />
    </AppShell>
  );
}
