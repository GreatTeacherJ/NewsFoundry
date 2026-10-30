"use client";

import { useEffect, useState } from "react";
import { api, PressReview } from "@/lib/api";
import { ApiError } from "@/lib/exportApi";
import ReviewModal from "@/components/ReviewModal";
import styles from "./ReviewsView.module.css";

export default function ReviewsView() {
  const [reviews, setReviews] = useState<PressReview[]>([]);
  const [selected, setSelected] = useState<PressReview | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {

    api<PressReview[]>("/press-reviews")
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
                <div className={styles.wrapperDate}>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M5.3335 1.3335V4.00016" stroke-width="1.33333" stroke-linecap="round" stroke-linejoin="round" stroke="#717182" />
                    <path d="M10.6665 1.3335V4.00016" stroke-width="1.33333" stroke-linecap="round" stroke-linejoin="round" stroke="#717182" />
                    <path d="M3.33333 2.6665H12.6667C13.403 2.6665 14 3.26346 14 3.99984V13.3332C14 14.0696 13.403 14.6665 12.6667 14.6665H3.33333C2.59695 14.6665 2 14.0696 2 13.3332V3.99984C2 3.26346 2.59695 2.6665 3.33333 2.6665Z" stroke-width="1.33333" stroke-linecap="round" stroke-linejoin="round" stroke="#717182" />
                    <path d="M2 6.6665H14" stroke-width="1.33333" stroke-linecap="round" stroke-linejoin="round" stroke="#717182" />
                  </svg>

                  <time dateTime={review.created_at}>{new Date(review.created_at).toLocaleString("fr-FR")}</time>
                </div>
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
