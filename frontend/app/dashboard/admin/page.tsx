"use client";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type MlAdminSummary, type Team } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function AdminTeamsPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [ml, setMl] = useState<MlAdminSummary | null>(null);

  const load = useCallback(async () => {
    setError("");
    try {
      const list = await api.admin.pendingTeams();
      setTeams(list);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error al cargar equipos");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user?.is_admin) {
      router.replace("/dashboard");
      return;
    }
    load();
    api.admin
      .mlSummary()
      .then(setMl)
      .catch(() => setMl(null));
  }, [user?.is_admin, router, load]);

  const approve = async (id: number) => {
    setBusyId(id);
    try {
      await api.admin.approveTeam(id);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusyId(null);
    }
  };

  const reject = async (id: number) => {
    setBusyId(id);
    try {
      await api.admin.rejectTeam(id);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setBusyId(null);
    }
  };

  if (!user?.is_admin) return null;

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-2">Administración · Equipos</h1>
      <p className="text-zinc-500 text-sm mb-8">
        Aprueba o rechaza solicitudes de nuevos equipos (modelo SaaS cerrado).
      </p>

      {ml && (
        <Card className="bg-zinc-900 border-zinc-800 border-amber-500/20 mb-8">
          <CardHeader>
            <CardTitle className="text-white text-lg">Dataset · ML (solo lectura)</CardTitle>
          </CardHeader>
          <CardContent className="text-zinc-400 text-sm space-y-2 font-mono">
            <p>
              <span className="text-zinc-600">Detector:</span> {ml.detector_backend}{" "}
              <span className="text-zinc-600">· modelo:</span> {ml.model_version}
            </p>
            <p>
              <span className="text-zinc-600">Carpeta dataset:</span>{" "}
              {ml.dataset_dir_exists ? "✓" : "✗"} {ml.dataset_videos_dir}
            </p>
            <p>
              <span className="text-zinc-600">Vídeos detectados:</span> {ml.video_file_count} ·{" "}
              <span className="text-zinc-600">tamaño total:</span>{" "}
              {(ml.total_bytes / (1024 * 1024)).toFixed(1)} MB
            </p>
            <p>
              <span className="text-zinc-600">Manifest:</span>{" "}
              {ml.manifest_exists ? "✓" : "✗"} {ml.manifest_path}
            </p>
            <p className="text-zinc-600 text-xs pt-2">
              Genera el manifest con:{" "}
              <code className="text-emerald-400/90">python scripts/build_dataset_manifest.py</code>
            </p>
          </CardContent>
        </Card>
      )}

      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white text-lg">Pendientes de aprobación</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <p className="text-red-400 text-sm border border-red-900 rounded-lg px-3 py-2 bg-red-950/30">
              {error}
            </p>
          )}
          {loading ? (
            <p className="text-zinc-500 text-sm">Cargando…</p>
          ) : teams.length === 0 ? (
            <p className="text-zinc-500 text-sm">No hay equipos pendientes.</p>
          ) : (
            <ul className="space-y-3">
              {teams.map((t) => (
                <li
                  key={t.id}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-xl bg-zinc-950 border border-zinc-800"
                >
                  <div>
                    <p className="text-white font-medium">{t.name}</p>
                    <p className="text-zinc-600 text-xs mt-1">
                      ID {t.id}
                      {t.requested_at && (
                        <> · Solicitud: {new Date(t.requested_at).toLocaleString()}</>
                      )}
                    </p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <Button
                      className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
                      disabled={busyId === t.id}
                      onClick={() => approve(t.id)}
                    >
                      Aprobar
                    </Button>
                    <Button
                      variant="outline"
                      className="border-red-900 text-red-400 hover:bg-red-950/40"
                      disabled={busyId === t.id}
                      onClick={() => reject(t.id)}
                    >
                      Rechazar
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
