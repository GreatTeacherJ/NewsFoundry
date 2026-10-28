"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { api, Discussion } from "@/lib/api";
import styles from "./AppShell.module.css";
import Image from "next/image";

type Props = {
  children: ReactNode;
  active: "chat" | "reviews";
};

export default function AppShell({ children, active }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const [discussions, setDiscussions] = useState<Discussion[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("newsfoundry_token");
    if (!token) {
      router.replace("/");
      return;
    }
    api<Discussion[]>("/discussions", token)
      .then(setDiscussions)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));
  }, [pathname, router]);

  async function createDiscussion() {
    const token = localStorage.getItem("newsfoundry_token");
    if (!token) return router.replace("/");
    try {
      const discussion = await api<Discussion>("/discussions", token, {
        method: "POST",
        body: JSON.stringify({ title: "Nouvelle discussion" }),
        headers: { "Content-Type": "application/json" },
      });
      router.push(`/chat/${discussion.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de créer la discussion.");
    }
  }

  function logout() {
    localStorage.removeItem("newsfoundry_token");
    router.replace("/");
  }

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <Link className={styles.brand} href="/home" aria-label="NewsFoundry, accueil">
        <Image 
        src="logo.svg"
        width={148}
        height={14}
        alt="Liens vers la page principale"
        />
        </Link>
        <div className={styles.sidebarBody}>
          <button className={styles.newChat} onClick={createDiscussion}>+ Nouvelle discussion</button>
         
          <section className={styles.discussionList} aria-labelledby="history-title">
            <h2 id="history-title">Discussions récentes</h2>
            {loading && <p className={styles.muted}>Chargement…</p>}
            {!loading && discussions.length === 0 && <p className={styles.muted}>Aucune discussion</p>}
            {discussions.map((discussion) => (
              <Link
                className={pathname === `/chat/${discussion.id}` ? styles.conversationActive : styles.conversation}
                href={`/chat/${discussion.id}`}
                key={discussion.id}
              >
                <span>{discussion.title}</span>
                <time dateTime={discussion.updated_at}>{new Date(discussion.updated_at).toLocaleDateString("fr-FR")}</time>
              </Link>
            ))}
          </section>
        </div>
        <button className={styles.logout} onClick={logout}>Se déconnecter</button>
      </aside>
      <div className={styles.mainArea}>
        <header className={styles.header}>
          <Link className={active === "chat" ? styles.navLinkActive : styles.navLink} href="/home">
          <Image 
          src="bubble.svg"
        width={14}
        height={14}
        alt=""
          />
          Chat</Link>
            <Link className={active === "reviews" ? styles.navLinkActive : styles.navLink} href="/reviews">
            <Image 
          src="doc.svg"
        width={14}
        height={14}
        alt=""
          />
            Revue de presse</Link>
          
        </header>
        {error && <p className={styles.globalError} role="alert">{error}</p>}
        {children}
      </div>
    </div>
  );
}
