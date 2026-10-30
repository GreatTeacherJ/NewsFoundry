"use client";

import { SyntheticEvent, useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, Discussion, Message, PressReview } from "@/lib/api";
import { jsonBody, ApiError } from "@/lib/exportApi";
import ReviewModal from "@/components/ReviewModal";
import styles from "./ChatView.module.css";
import Link from "next/link";
import Image from "next/image";

type Props = { discussionId?: string };

export default function ChatView({ discussionId }: Props) {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [discussion, setDiscussion] = useState<Discussion | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<PressReview | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const loadDiscussion = useCallback(async () => {
    if (!discussionId) return;

    try {
      const [currentDiscussion, conversation] = await Promise.all([
        api<Discussion>(`/discussions/${discussionId}`),
        api<Message[]>(`/discussions/${discussionId}/messages`),
      ]);
      setDiscussion(currentDiscussion);
      setMessages(conversation);
      setError("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de charger cette discussion.");
    }
  }, [discussionId]);

  useEffect(() => {
    void Promise.resolve().then(loadDiscussion);
  }, [loadDiscussion]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function sendMessage(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.trim() || busy) return;
    setError("");
    setBusy(true);
    try {

      let activeId = discussionId;
      if (!activeId) {
        const created = await api<Discussion>("/discussions", jsonBody({ title: draft.trim().slice(0, 80) }));
        activeId = String(created.id);
      }
      const result = await api<Message[]>(`/discussions/${activeId}/messages`, jsonBody({ content: draft.trim() }));
      setMessages((previous) => [...previous, ...result]);
      setDiscussion((previous) => previous ?? { id: Number(activeId), title: draft.trim().slice(0, 80), created_at: new Date().toISOString(), updated_at: new Date().toISOString() });
      setDraft("");
      if (!discussionId) router.replace(`/chat/${activeId}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible d’envoyer le message.");
    } finally {
      setBusy(false);
    }
  }

  async function generateReview() {
    if (!discussionId) return;
    setError("");
    setBusy(true);
    try {

      const result = await api<PressReview>(`/discussions/${discussionId}/press-reviews`, { method: "POST" });
      setReview(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Impossible de générer la revue de presse.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className={styles.chatPage}>
      {discussionId &&
        <div className={styles.conversationHeader}>
          <Link className={styles.newConversation}
            href="/home">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640"
              fill="none" stroke="currentColor" strokeWidth="16"
              strokeLinecap="round" strokeLinejoin="round">
              <path d="M576 320H64" />
              <path d="M192 192L64 320L192 448" />
            </svg>
            <div>
              <h1>Nouvelle discussion</h1>
              <p>Conversation active</p>
            </div>
          </Link>
          <button className={styles.reviewButton} onClick={generateReview} disabled={busy}>Générer une revue de presse</button>
        </div>
      }

      <section className={styles.messages} aria-label="Messages de la discussion" aria-live="polite">
        {!discussionId && messages.length === 0 && (

          <div className={styles.welcome}>
            <Image
              src="/botHead.svg"
              width={82}
              height={67}
              alt=""
            />

            <h2>Assistant Revue de Presse IA</h2>
            <p>Posez-moi des questions sur l’actualité récente ou demandez-moi de générer une revue de presse sur un sujet spécifique.</p>
            <strong>Exemples :</strong>
            <ul>
              <li>Quelles sont les dernières nouvelles en politique ?</li>
              <li>Génère une revue de presse sur la technologie</li>
              <li>Résume l’actualité économique de la semaine</li>
            </ul>
          </div>
        )}
        {discussionId && messages.length === 0 && <p className={styles.empty}>Envoyez un message pour commencer cette discussion.</p>}

        {messages.map((message) => (
          <div>

            <article key={message.id} className={message.role === "user" ? styles.userMessage : styles.assistantMessage}>
              <p>{message.content}</p>
              <time dateTime={message.created_at}>{new Date(message.created_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</time>
            </article></div>
        ))}
        <div ref={endRef} />
      </section>
      {error && <p className={styles.error} role="alert">{error}</p>}
      <form className={styles.composer} onSubmit={sendMessage}>
        <label className={styles.srOnly} htmlFor="message">Votre message</label>
        <textarea id="message" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Tapez votre message ici…" rows={1} />
        <button type="submit" aria-label="Envoyer le message" disabled={busy || !draft.trim()}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 20.5 22 12 3 3.5 3 10l13 2-13 2z" fill="currentColor" /></svg>
        </button>
      </form>
      {review && <ReviewModal review={review} onClose={() => setReview(null)} />}
    </main>
  );
}
