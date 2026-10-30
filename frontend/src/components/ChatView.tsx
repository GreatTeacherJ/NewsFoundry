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
        //s'il n'y à pas de discution en créer une
        const created = await api<Discussion>("/discussions", jsonBody({ title: draft.trim().slice(0, 80) }));
        //Récuperer l'id de la nouvelle session
        activeId = String(created.id);
      }
      //récupérer la liste des message de la discussion
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
          <div className={message.role === "user" ? (styles.wrapperMessage + " " + styles.right) : (styles.wrapperMessage + " " + styles.left)}>
            {message.role === "assistant" &&
              <span className={styles.chatIcon}>
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M0 16C0 7.16344 7.16344 0 16 0C24.8366 0 32 7.16344 32 16C32 24.8366 24.8366 32 16 32C7.16344 32 0 24.8366 0 16Z" fill="#ECEEF2" />
                  <path d="M16.0005 10C16.3685 10.0002 16.6665 10.2989 16.6665 10.667V12.666H20.0005C21.1047 12.6662 22.0001 13.5619 22.0005 14.666V16.666H22.6665C23.0346 16.666 23.3333 16.965 23.3335 17.333C23.3335 17.7012 23.0347 18 22.6665 18H22.0005V20C22.0003 21.1043 21.1048 21.9998 20.0005 22H12.0005C10.8962 21.9998 10.0007 21.1043 10.0005 20V18H9.3335C8.96547 17.9998 8.6665 17.7011 8.6665 17.333C8.66668 16.9651 8.96558 16.6662 9.3335 16.666H10.0005V14.666C10.0008 13.5619 10.8963 12.6662 12.0005 12.666H15.3335V11.334H13.3335C12.9656 11.3338 12.6667 11.0349 12.6665 10.667C12.6665 10.2989 12.9655 10.0002 13.3335 10H16.0005ZM12.0005 14C11.6327 14.0002 11.3348 14.2982 11.3345 14.666V20C11.3346 20.3679 11.6326 20.6658 12.0005 20.666H20.0005C20.3684 20.6658 20.6673 20.3679 20.6675 20V17.3418C20.6674 17.339 20.6665 17.3358 20.6665 17.333C20.6665 17.3297 20.6674 17.3265 20.6675 17.3232V14.666C20.6671 14.2982 20.3683 14.0002 20.0005 14H12.0005ZM14.0005 16C14.3687 16 14.6675 16.2988 14.6675 16.667V18C14.6673 18.368 14.3686 18.667 14.0005 18.667C13.6324 18.667 13.3337 18.368 13.3335 18V16.667C13.3335 16.2988 13.6323 16 14.0005 16ZM18.0005 16C18.3687 16 18.6675 16.2988 18.6675 16.667V18C18.6673 18.368 18.3686 18.667 18.0005 18.667C17.6324 18.667 17.3337 18.368 17.3335 18V16.667C17.3335 16.2988 17.6323 16 18.0005 16Z" fill="#2A2A31" />
                </svg>
              </span>
            }

            <article key={message.id} className={message.role === "user" ? styles.userMessage : styles.assistantMessage}>
              <p>{message.content}</p>
              <time dateTime={message.created_at}>{new Date(message.created_at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}</time>
            </article>
            {message.role === "user" &&
              <span className={styles.chatIcon}>
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M0 16C0 7.16344 7.16344 0 16 0C24.8366 0 32 7.16344 32 16C32 24.8366 24.8366 32 16 32C7.16344 32 0 24.8366 0 16Z" fill="#030213" />
                  <path d="M20.6668 22V20.6667C20.6668 19.9594 20.3859 19.2811 19.8858 18.781C19.3857 18.281 18.7074 18 18.0002 18H14.0002C13.2929 18 12.6146 18.281 12.1145 18.781C11.6144 19.2811 11.3335 19.9594 11.3335 20.6667V22" stroke-width="1.33333" stroke-linecap="round" stroke-linejoin="round" stroke="white" />
                  <path d="M18.6668 12.6667C18.6668 14.1394 17.4729 15.3333 16.0002 15.3333C14.5274 15.3333 13.3335 14.1394 13.3335 12.6667C13.3335 11.1939 14.5274 10 16.0002 10C17.4729 10 18.6668 11.1939 18.6668 12.6667Z" stroke-width="1.33333" stroke-linecap="round" stroke-linejoin="round" stroke="white" />
                </svg>

              </span>
            }
          </div>
        ))}
        <div ref={endRef} />
      </section>
      {error && <p className={styles.error} role="alert">{error}</p>}

      <form className={styles.wrapperComposer} onSubmit={sendMessage}>
        <label className={styles.srOnly} htmlFor="message">Votre message</label>
        <textarea className={styles.composer} id="message" value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="Tapez votre message ici…" rows={1} />
        <button className={styles.composerButton} type="submit" aria-label="Envoyer le message" disabled={busy || !draft.trim()}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M9.6907 14.4572C9.71603 14.5203 9.76006 14.5742 9.81688 14.6116C9.87371 14.6489 9.9406 14.668 10.0086 14.6663C10.0766 14.6646 10.1424 14.6421 10.1973 14.6018C10.2521 14.5616 10.2933 14.5055 10.3154 14.4412L14.6487 1.77454C14.67 1.71547 14.6741 1.65154 14.6604 1.59024C14.6468 1.52894 14.6159 1.4728 14.5715 1.42839C14.5271 1.38398 14.471 1.35314 14.4097 1.33947C14.3484 1.3258 14.2844 1.32987 14.2254 1.35121L1.5587 5.68454C1.49436 5.7066 1.43832 5.74782 1.39808 5.80266C1.35785 5.85749 1.33535 5.92332 1.33361 5.99131C1.33186 6.05931 1.35096 6.1262 1.38834 6.18303C1.42571 6.23985 1.47958 6.28388 1.5427 6.30921L6.82937 8.42921C6.99649 8.49612 7.14833 8.59618 7.27574 8.72336C7.40315 8.85054 7.50349 9.0022 7.5707 9.16921L9.6907 14.4572Z" stroke-width="1.33333" stroke-linecap="round" stroke-linejoin="round" stroke="white" />
            <path d="M14.5692 1.43115L7.27588 8.72382" stroke-width="1.33333" stroke-linecap="round" stroke-linejoin="round" stroke="white" />
          </svg>
        </button>
      </form>
      {review && <ReviewModal review={review} onClose={() => setReview(null)} />}
    </main>
  );
}
