"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { api, ApiError, jsonBody } from "@/lib/api";
import styles from "./LoginForm.module.css";
import Image from "next/image";

export default function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isRegistering, setIsRegistering] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isRegistering) {
        await api("/auth/register", undefined, jsonBody({ email, password }));
      }
      const result = await api<{ access_token: string }>("/auth/login", undefined, jsonBody({ email, password }));
      localStorage.setItem("newsfoundry_token", result.access_token);
      router.push("/home");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "La connexion a échoué.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className={styles.card} aria-labelledby="login-title">
      <div className={styles.logo} aria-label="NewsFoundry">
        <Image 
        src="logo.svg"
        width={202}
        height={20}
        alt=""
        />

      </div>
      <h1 id="login-title" className={styles.description}>
        Connectez-vous pour accéder à votre assistant d’actualités IA
      </h1>
      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="email">
            Adresse email
          </label>
          <input
            className={styles.input}
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            placeholder="votre.email@exemple.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>
        <div className={styles.field}>
          <label className={styles.label} htmlFor="password">
            Mot de passe
          </label>
          <input
            className={styles.input}
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={8}
            maxLength={72}
            required
          />
        </div>
        {error && <p className={styles.error} role="alert">{error}</p>}
        <button className={styles.submit} type="submit" disabled={loading}>
          {loading ? "Patientez…" : isRegistering ? "Créer mon compte" : "Se connecter"}
        </button>
      </form>
      <button
        className={styles.switchMode}
        type="button"
        onClick={() => {
          setIsRegistering((current) => !current);
          setError("");
        }}
      >
        {isRegistering ? "J’ai déjà un compte" : "Créer un compte"}
      </button>
    </section>
  );
}
