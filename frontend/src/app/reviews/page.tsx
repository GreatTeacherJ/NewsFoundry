import AppShell from "@/components/AppShell";
import ReviewsView from "@/components/ReviewsView";
import Header from "@/components/Header";

export default function ReviewsPage() {
  return (
    <AppShell>
      <Header active="reviews" />
      <ReviewsView />
    </AppShell>
  );
}
