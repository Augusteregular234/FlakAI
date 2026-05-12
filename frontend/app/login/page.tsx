"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  const router = useRouter();
  const { setAuth } = useAuthStore();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    team_name: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data =
        mode === "login"
          ? await api.auth.login(form.username, form.password)
          : await api.auth.register(form);
      setAuth(data);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al iniciar sesión");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-black text-white tracking-tight">
            Flak<span className="text-emerald-400">AI</span>
            <span className="text-zinc-500 text-lg font-light ml-1">v2</span>
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Análisis Táctico de Fútbol</p>
        </div>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-white text-lg">
              {mode === "login" ? "Iniciar Sesión" : "Crear Cuenta"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <Label className="text-zinc-400 text-xs">Usuario</Label>
                <Input
                  className="bg-zinc-800 border-zinc-700 text-white mt-1"
                  placeholder="tu_usuario"
                  value={form.username}
                  onChange={(e) => setForm({ ...form, username: e.target.value })}
                  required
                />
              </div>

              {mode === "register" && (
                <>
                  <div>
                    <Label className="text-zinc-400 text-xs">Email</Label>
                    <Input
                      type="email"
                      className="bg-zinc-800 border-zinc-700 text-white mt-1"
                      placeholder="email@equipo.com"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      required
                    />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-xs">Nombre del Equipo</Label>
                    <Input
                      className="bg-zinc-800 border-zinc-700 text-white mt-1"
                      placeholder="FC Barcelona"
                      value={form.team_name}
                      onChange={(e) => setForm({ ...form, team_name: e.target.value })}
                      required
                    />
                  </div>
                </>
              )}

              <div>
                <Label className="text-zinc-400 text-xs">Contraseña</Label>
                <Input
                  type="password"
                  className="bg-zinc-800 border-zinc-700 text-white mt-1"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  required
                />
              </div>

              {error && (
                <p className="text-red-400 text-xs bg-red-950/30 border border-red-900 rounded px-3 py-2">
                  {error}
                </p>
              )}

              <Button
                type="submit"
                className="w-full bg-emerald-500 hover:bg-emerald-400 text-black font-bold"
                disabled={loading}
              >
                {loading ? "Cargando..." : mode === "login" ? "Entrar" : "Crear Cuenta"}
              </Button>
            </form>

            <p className="text-center text-zinc-600 text-xs mt-4">
              {mode === "login" ? "¿Sin cuenta?" : "¿Ya tienes cuenta?"}{" "}
              <button
                onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
                className="text-emerald-400 hover:underline"
              >
                {mode === "login" ? "Registrarse" : "Iniciar sesión"}
              </button>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
