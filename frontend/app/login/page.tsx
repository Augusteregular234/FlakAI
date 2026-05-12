"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuthStore } from "@/lib/store";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ username: "", email: "", password: "", team_name: "" });

  const f = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data =
        mode === "login"
          ? await api.auth.login(form.username, form.password)
          : await api.auth.register(form);
      setAuth(data);
      toast.success(mode === "login" ? `Bienvenido, ${data.user.username}` : "Cuenta creada. Espera aprobación.");
      router.push("/dashboard");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Error al autenticar");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex">
      {/* Left — branding */}
      <div className="hidden lg:flex w-1/2 bg-gradient-to-br from-zinc-900 via-zinc-900 to-zinc-950 border-r border-zinc-800 flex-col justify-between p-12">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tight">
            Flak<span className="text-emerald-400">AI</span>
            <span className="text-zinc-600 text-base font-light ml-1">v2</span>
          </h1>
        </div>

        <div className="space-y-8">
          <div>
            <p className="text-4xl font-black text-white leading-tight">
              Análisis táctico<br />
              <span className="text-emerald-400">impulsado por IA</span>
            </p>
            <p className="text-zinc-400 mt-4 text-lg leading-relaxed">
              Sube un partido. La IA detecta Goles, Córners, Faltas y Saques.
              Revisa cada clip. Exporta para entrenar tu propio modelo.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {[
              ["⚽", "Goles", "Detección automática"],
              ["🚩", "Córners", "Con timestamp exacto"],
              ["🟨", "Faltas", "30s de contexto"],
              ["🤾", "Saques", "Revisión humana"],
            ].map(([icon, title, desc]) => (
              <div key={title} className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
                <span className="text-2xl">{icon}</span>
                <p className="text-white font-semibold text-sm mt-2">{title}</p>
                <p className="text-zinc-500 text-xs">{desc}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="text-zinc-700 text-xs">© 2025 FlakAI. MVP — no apto para producción sin configurar Stripe y autenticación.</p>
      </div>

      {/* Right — form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          <div className="lg:hidden text-center mb-8">
            <h1 className="text-3xl font-black text-white">
              Flak<span className="text-emerald-400">AI</span>
            </h1>
          </div>

          <div className="mb-6">
            <h2 className="text-xl font-bold text-white">
              {mode === "login" ? "Iniciar sesión" : "Crear cuenta"}
            </h2>
            <p className="text-zinc-500 text-sm mt-1">
              {mode === "login"
                ? "Accede a tu dashboard de análisis"
                : "Registra tu equipo en FlakAI"}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs font-medium">Usuario</Label>
              <Input
                className="bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-600 focus:border-emerald-600 focus:ring-emerald-600/20"
                placeholder="tu_usuario"
                value={form.username}
                onChange={f("username")}
                autoComplete="username"
                required
              />
            </div>

            {mode === "register" && (
              <>
                <div className="space-y-1.5">
                  <Label className="text-zinc-400 text-xs font-medium">Email</Label>
                  <Input
                    type="email"
                    className="bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-600"
                    placeholder="email@equipo.com"
                    value={form.email}
                    onChange={f("email")}
                    autoComplete="email"
                    required
                  />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-zinc-400 text-xs font-medium">Nombre del Equipo</Label>
                  <Input
                    className="bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-600"
                    placeholder="FC Barcelona"
                    value={form.team_name}
                    onChange={f("team_name")}
                    required
                  />
                </div>
              </>
            )}

            <div className="space-y-1.5">
              <Label className="text-zinc-400 text-xs font-medium">Contraseña</Label>
              <Input
                type="password"
                className="bg-zinc-900 border-zinc-700 text-white placeholder:text-zinc-600"
                placeholder="••••••••"
                value={form.password}
                onChange={f("password")}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                required
              />
            </div>

            <Button
              type="submit"
              className="w-full bg-emerald-500 hover:bg-emerald-400 text-black font-bold h-11 text-sm"
              disabled={loading}
            >
              {loading
                ? "Procesando..."
                : mode === "login"
                ? "Entrar al Dashboard →"
                : "Crear Cuenta →"}
            </Button>
          </form>

          <div className="mt-4 text-center">
            <button
              onClick={() => setMode(mode === "login" ? "register" : "login")}
              className="text-zinc-500 hover:text-white text-sm transition-colors"
            >
              {mode === "login"
                ? "¿Sin cuenta? Registrarse"
                : "¿Ya tienes cuenta? Iniciar sesión"}
            </button>
          </div>

          {mode === "register" && (
            <p className="mt-4 text-xs text-zinc-600 text-center leading-relaxed">
              El equipo requiere aprobación del administrador antes de poder subir vídeos.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
