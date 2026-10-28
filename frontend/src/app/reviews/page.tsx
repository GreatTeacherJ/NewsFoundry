import AppShell from "@/components/AppShell";
import ReviewsView from "@/components/ReviewsView";

export default function ReviewsPage() {
  return (
    <AppShell active="reviews">
      <ReviewsView />
    </AppShell>
  );
}
