import AppShell from "@/components/AppShell";
import ChatView from "@/components/ChatView";

type Props = { params: Promise<{ id: string }> };

export default async function DiscussionPage({ params }: Props) {
  const { id } = await params;
  return (
    <AppShell active="chat">
      <ChatView discussionId={id} />
    </AppShell>
  );
}
