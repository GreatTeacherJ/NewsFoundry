"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useState } from "react";
import { api, Discussion } from "@/lib/api";
import styles from "./AppShell.module.css";
import Image from "next/image";
import Header from "./Header";
import { logoutAction } from "@/lib/loginActions";

type Props = {
  children: ReactNode;
};

export default function AppShell({ children }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const [discussions, setDiscussions] = useState<Discussion[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {

    api<Discussion[]>("/discussions").then(setDiscussions)
      .catch((err: Error) => setError(err.message))
      .finally(() => setLoading(false));


  }, [pathname, router]);

  async function createDiscussion() {

    try {
      const discussion = await api<Discussion>("/discussions", {
        method: "POST",
        body: JSON.stringify({ title: "Nouvelle discussion" }),
        headers: { "Content-Type": "application/json" },
      });
      router.push(`/chat/${discussion.id}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Impossible de créer la discussion.",
      );
    }
  }

  function logout() {
    logoutAction()
    router.replace("/");
  }

  return (
    <div className={styles.layout}>
      <aside className={styles.sidebar}>
        <Link
          className={styles.brand}
          href="/home"
          aria-label="NewsFoundry, accueil"
        >
          <Image
            src="/logo.svg"
            width={148}
            height={14}
            alt="Liens vers la page principale"
          />
        </Link>
        <div className={styles.sidebarBody}>

          <section
            className={styles.discussionList}
            aria-labelledby="history-title"
          >

            {loading && <p className={styles.muted}>Chargement…</p>}
            {!loading && discussions.length === 0 && (
              <p className={styles.muted}>Aucune discussion</p>
            )}
            {discussions.map((discussion) => (
              <Link
                className={
                  pathname === `/chat/${discussion.id}`
                    ? styles.conversationActive
                    : styles.conversation
                }
                href={`/chat/${discussion.id}`}
                key={discussion.id}
              >
                <span>{discussion.title}</span>
                <time dateTime={discussion.updated_at}>
                  {new Date(discussion.updated_at).toLocaleDateString("fr-FR")}
                </time>
              </Link>
            ))}
          </section>
        </div>
        <button className={styles.logout} onClick={logout}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <g clipPath="url(#clip0_3341_193)">
              <path d="M11 10.5V14.5C11 15.327 10.327 16 9.5 16H2.5C1.673 16 1 15.327 1 14.5V1.5C1 0.673 1.673 0 2.5 0H9.5C10.327 0 11 0.673 11 1.5V5.5C11 5.776 10.776 6 10.5 6C10.224 6 10 5.776 10 5.5V1.5C10 1.224 9.775 1 9.5 1H2.5C2.225 1 2 1.224 2 1.5V14.5C2 14.776 2.225 15 2.5 15H9.5C9.775 15 10 14.776 10 14.5V10.5C10 10.224 10.224 10 10.5 10C10.776 10 11 10.224 11 10.5ZM14.757 7.346L12.878 5.173C12.697 4.964 12.381 4.942 12.173 5.122C11.964 5.303 11.942 5.619 12.122 5.828L13.569 7.5H6.5C6.224 7.5 6 7.724 6 8C6 8.276 6.224 8.5 6.5 8.5H13.568L12.122 10.173C11.941 10.382 11.964 10.698 12.173 10.879C12.268 10.96 12.384 11 12.5 11C12.64 11 12.779 10.941 12.878 10.827L14.758 8.653C14.914 8.471 15 8.239 15 8C15 7.761 14.914 7.529 14.757 7.346Z" fill="#2A2A31" />
            </g>
            <defs>
              <clipPath id="clip0_3341_193">
                <rect width="16" height="16" fill="white" />
              </clipPath>
            </defs>
          </svg>

          Se déconnecter
        </button>
      </aside>
      <div className={styles.mainArea}>
        {error && (
          <p className={styles.globalError} role="alert">
            {error}
          </p>
        )}
        {children}
      </div>
    </div>
  );
}
