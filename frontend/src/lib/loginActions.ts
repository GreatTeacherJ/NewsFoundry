"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { api } from "@/lib/api";
import { jsonBody } from "@/lib/exportApi";

export async function loginAction(email: string, password: string) {

    console.log("loginAction !!!")

    // Appel serveur -> serveur, pas de CORS ici
    const res = await api<{ access_token: string }>("/auth/login", jsonBody({ email, password }));

    console.log("token: ", res.access_token)
    // Next 15+ : cookies() est asynchrone, d'où le await
    const cookieStore = await cookies();
    cookieStore.set("token", res.access_token, {
        httpOnly: true,                                // inaccessible au JS client
        secure: process.env.NODE_ENV === "production", // HTTPS uniquement en prod
        sameSite: "lax",
        path: "/",
        maxAge: 60 * 60 * 8,
    });
}

export async function logoutAction() {
    const cookieStore = await cookies();
    cookieStore.delete("token");
    redirect("/login");
}