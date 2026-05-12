import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "sonner";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "FlakAI v2 — Análisis Táctico de Fútbol",
  description: "Plataforma SaaS de análisis automático de partidos con IA",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-zinc-950">
        {children}
        <Toaster
          position="bottom-right"
          theme="dark"
          toastOptions={{
            style: { background: "#18181b", border: "1px solid #27272a", color: "#fff" },
          }}
        />
      </body>
    </html>
  );
}
