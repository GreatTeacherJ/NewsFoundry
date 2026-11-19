"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { safeApi } from "@/lib/api";
import { jsonBody } from "@/lib/exportApi";

type LoginResult = { ok: true } | { ok: false; message: string };

export async function loginAction(
  email: string,
  password: string,
): Promise<LoginResult> {
  // Appel serveur -> serveur, pas de CORS ici
  const result = await safeApi<{ access_token: string }>(
    "/auth/login",
    jsonBody({ email, password }),
  );

  if (!result.ok) return { ok: false, message: result.message };

  // Next 15+ : cookies() est asynchrone, d'où le await
  const cookieStore = await cookies();
  cookieStore.set("token", result.data.access_token, {
    httpOnly: true,                                // inaccessible au JS client
    secure: process.env.NODE_ENV === "production", // HTTPS uniquement en prod
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 8,
  });

  return { ok: true };
}

export async function logoutAction() {
  const cookieStore = await cookies();
  cookieStore.delete("token");
  redirect("/login");
}
