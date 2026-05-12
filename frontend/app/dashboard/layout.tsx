"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { api } from "@/lib/api";
import { Sidebar } from "@/components/sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { token, setProfile, logout } = useAuthStore();
  const [gate, setGate] = useState<"loading" | "ready" | "pending">("loading");

  useEffect(() => {
    if (!token) router.replace("/login");
  }, [token, router]);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await api.auth.me();
        if (cancelled) return;
        setProfile(data.user, data.team);
        if (data.team.status === "pending_approval" && !data.user.is_admin) {
          setGate("pending");
        } else {
          setGate("ready");
        }
      } catch {
        if (!cancelled) logout();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, setProfile, logout]);

  if (!token) return null;

  if (gate === "loading") {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-zinc-500 text-sm">
        Cargando…
      </div>
    );
  }

  if (gate === "pending") {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col items-center justify-center p-6">
        <div className="max-w-md text-center space-y-4">
          <div className="text-5xl">⏳</div>
          <h1 className="text-xl font-bold text-white">Equipo pendiente de aprobación</h1>
          <p className="text-zinc-400 text-sm leading-relaxed">
            Tu solicitud está en revisión. Cuando un administrador apruebe al equipo{" "}
            <span className="text-emerald-400 font-medium">podrás subir vídeos y usar la app</span>.
          </p>
          <button
            type="button"
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="text-zinc-500 hover:text-white text-sm underline"
          >
            Cerrar sesión
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-zinc-950">
      <Sidebar />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
