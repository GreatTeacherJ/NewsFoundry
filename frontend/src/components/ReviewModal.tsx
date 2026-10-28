"use client";

import { useEffect } from "react";
import { PressReview } from "@/lib/api";
import styles from "./ReviewModal.module.css";

type Props = { review: PressReview; onClose: () => void };

export default function ReviewModal({ review, onClose }: Props) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className={styles.backdrop} onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="review-dialog-title">
        <header className={styles.header}>
          <div>
            <h2 id="review-dialog-title">{review.title}</h2>
            <time dateTime={review.created_at}>{new Date(review.created_at).toLocaleString("fr-FR")}</time>
          </div>
          <button className={styles.close} onClick={onClose} aria-label="Fermer la revue de presse">×</button>
        </header>
        <div className={styles.content}>{review.content}</div>
        <footer className={styles.footer}>
          <button onClick={() => navigator.clipboard.writeText(review.content)}>Copier</button>
          <button className={styles.done} onClick={onClose}>Fermer</button>
        </footer>
      </section>
    </div>
  );
}
