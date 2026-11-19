"use server"

import { cookies } from "next/headers";
import { resolveBackendUrl } from "./backendUrl";
import { ApiError } from "./exportApi";

function getApiUrl() {
  return resolveBackendUrl();
}


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
  created_at: string;
  role: "user" | "assistant" | "reviews";
  content: string;
}


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


  const baseUrl = getApiUrl();
  const url = `${baseUrl}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
      cache: "no-store",
    });
  } catch (error) {
    console.error(`[api] échec de connexion vers ${url}`, error);
    throw new ApiError("Impossible de joindre le serveur. Vérifiez votre connexion.", 0);
  }

  if (!response.ok) {
    const result = (await response.json().catch(() => null)) as { detail?: string } | null;
    const message = result?.detail ?? "Une erreur est survenue. Réessayez.";
    console.error(`[api] ${response.status} sur ${url} : ${message}`);
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; message: string };

// Variante de `api` qui ne lève jamais d'exception : les Server Actions qui
// lèvent une erreur sont transformées en 500 génériques par Next.js en
// production (le vrai message est remplacé par un `digest`).
export async function safeApi<T>(
  path: string,
  options: RequestInit = {},
): Promise<ApiResult<T>> {
  try {
    return { ok: true, data: await api<T>(path, options) };
  } catch (error) {
    if (error instanceof ApiError) {
      return { ok: false, status: error.status, message: error.message };
    }
    console.error("[api] erreur inattendue", error);
    return {
      ok: false,
      status: 0,
      message: "Une erreur inattendue est survenue. Réessayez.",
    };
  }
}


