// URL publique de l'API en production. Ce n'est pas un secret : elle sert de
// repli si la variable BACKEND_URL est absente ou mal configurée sur Vercel.
export const PRODUCTION_BACKEND_URL =
  "https://newsfoundry-production-74e5dc89.up.railway.app";

export function resolveBackendUrl(): string {
  const configured = process.env.BACKEND_URL?.trim();
  if (configured) return configured.replace(/\/+$/, "");
  return process.env.NODE_ENV === "production"
    ? PRODUCTION_BACKEND_URL
    : "http://localhost:8000";
}
