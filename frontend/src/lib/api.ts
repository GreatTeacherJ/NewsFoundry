"use server"

import { cookies } from "next/headers";
import { ApiError } from "./exportApi";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type User = { id: number; email: string };
export type Discussion = {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
};
export type Message = {
  id: number;
  discussion_id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};
export type PressReview = {
  id: number;
  discussion_id: number;
  title: string;
  content: string;
  created_at: string;
};



export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {


  let token
  if (path !== "/auth/register" && path !== "/auth/login") {
    const cookie = await cookies()
    token = cookie.get("token")?.value
  }


  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("Impossible de joindre le serveur. Vérifiez votre connexion.", 0);
  }

  if (!response.ok) {
    const result = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiError(result?.detail ?? "Une erreur est survenue. Réessayez.", response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}


