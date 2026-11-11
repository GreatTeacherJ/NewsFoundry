"use client";

import styles from "./GenerateReviewModal.module.css";
import { Dispatch, SetStateAction } from "react";

type Props = {
  onThemeChange: (theme: string) => void;
  generateReview: () => void
  setOpenModal: Dispatch<SetStateAction<boolean>>
};

export default function GenerateReviewModal({ onThemeChange, generateReview, setOpenModal }: Props) {


  return (
    <div className={styles.backdrop}>
      <section className={styles.dialog} role="dialog" aria-modal="true" aria-labelledby="generate-review-title">
        <button onClick={() => setOpenModal(false)} className={styles.closeRow}>
          <span>Fermer</span>
        </button>
        <header className={styles.heading}>
          <h2 id="generate-review-title">Générer une revue de presse</h2>
          <p>Donner un titre à votre revue de presse</p>
        </header>
        <form className={styles.form}>
          <label className={styles.field}>
            <span>Thème de la revue de presse</span>
            <input type="text" />
          </label>
          <button className={styles.generateButton} onClick={generateReview} type="button">Générer</button>
        </form>
      </section>
    </div>
  );
}
