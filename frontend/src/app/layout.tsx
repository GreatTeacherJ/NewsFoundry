import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Connexion | NewsFoundry",
  description: "Connectez-vous à votre assistant d’actualités IA NewsFoundry.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
