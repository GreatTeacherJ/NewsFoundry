"use client";

import { useEffect, useState } from "react";
import { ApiError, api, PressReview } from "@/lib/api";
import ReviewModal from "@/components/ReviewModal";
import styles from "./ReviewsView.module.css";

export default function ReviewsView() {
  const [reviews, setReviews] = useState<PressReview[]>([]);
  const [selected, setSelected] = useState<PressReview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("newsfoundry_token");
    if (!token) return;
    api<PressReview[]>("/press-reviews", token)
      .then(setReviews)
      .catch((err: Error) => setError(err instanceof ApiError ? err.message : "Impossible de charger les revues."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className={styles.page}>
      <header className={styles.pageHeading}>
        <h1>Revues de Presse</h1>
        <p>Consultez et gérez vos revues de presse générées par l’IA</p>
      </header>
      {error && <p className={styles.error} role="alert">{error}</p>}
      {loading && <p className={styles.muted}>Chargement des revues…</p>}
      {!loading && !error && reviews.length === 0 && <p className={styles.empty}>Aucune revue de presse. Générez-en une depuis une discussion.</p>}
      <section className={styles.grid} aria-label="Vos revues de presse">
        {reviews.map((review) => (
          <article className={styles.card} key={review.id}>
            <header className={styles.cardHeader}>
              <div>
                <h2>{review.title}</h2>
                <time dateTime={review.created_at}>{new Date(review.created_at).toLocaleString("fr-FR")}</time>
              </div>
              <span className={styles.tag}>Politique</span>
            </header>
            <p className={styles.preview}>{review.content}</p>
            <button className={styles.open} onClick={() => setSelected(review)}>Consulter la revue</button>
          </article>
        ))}
      </section>
      {selected && <ReviewModal review={selected} onClose={() => setSelected(null)} />}
    </main>
  );
}
