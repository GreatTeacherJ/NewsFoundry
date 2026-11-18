import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function proxy(request: NextRequest) {

    const { pathname } = request.nextUrl;
    const isPublic = pathname === "/";


    const token = request.cookies.get("token")?.value;
    // Pas de token sur une page protégée -> redirection vers /login
    if (!token && !isPublic) {
        const loginUrl = new URL("/", request.url);
        return NextResponse.redirect(loginUrl);
    }

    // Déjà connecté : inutile d'afficher /login
    if (token && isPublic) {
        return NextResponse.redirect(new URL("/home", request.url));
    }

    return NextResponse.next();
}

export const config = {
    // Exclut les fichiers statiques, images et routes internes de Next
    matcher: ["/((?!api|_next/static|_next/image|favicon.ico|logo.svg).*)"],
};