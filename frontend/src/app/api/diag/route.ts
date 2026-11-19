import { NextResponse } from "next/server";
import { resolveBackendUrl } from "@/lib/backendUrl";

// Route de diagnostic temporaire : ouvrir /api/diag dans le navigateur.
// Elle indique quelle URL de backend est utilisée et si elle répond.
// À supprimer une fois le déploiement validé.
export const dynamic = "force-dynamic";

export async function GET() {
  const backendUrl = resolveBackendUrl();
  const startedAt = Date.now();
  const base = {
    envVarSet: Boolean(process.env.BACKEND_URL),
    backendUrl,
    nodeEnv: process.env.NODE_ENV ?? null,
    vercelUrl: process.env.VERCEL_URL ?? null,
  };

  try {
    const response = await fetch(`${backendUrl}/health`, { cache: "no-store" });
    const body = (await response.text()).slice(0, 200);
    return NextResponse.json({
      ...base,
      backendStatus: response.status,
      backendBody: body,
      latencyMs: Date.now() - startedAt,
    });
  } catch (error) {
    return NextResponse.json(
      {
        ...base,
        backendStatus: null,
        error: error instanceof Error ? error.message : String(error),
        latencyMs: Date.now() - startedAt,
      },
      { status: 502 },
    );
  }
}
