"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api, type Video, type LabelingBatch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const STATUS_LABELS: Record<string, string> = {
  uploading:  "Subiendo",
  queued:     "En Cola",
  processing: "Procesando",
  completed:  "Completado",
  error:      "Error",
};

const STATUS_COLORS: Record<string, string> = {
  uploading:  "bg-blue-500/10 text-blue-400 border-blue-800",
  queued:     "bg-purple-500/10 text-purple-400 border-purple-800",
  processing: "bg-yellow-500/10 text-yellow-400 border-yellow-800",
  completed:  "bg-emerald-500/10 text-emerald-400 border-emerald-800",
  error:      "bg-red-500/10 text-red-400 border-red-800",
};

function formatBytes(bytes: number) {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatEta(seconds: number): string {
  if (!isFinite(seconds) || seconds <= 0) return "";
  if (seconds < 60) return `~${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `~${m}m ${s}s`;
}

function ProcessingProgress({ v }: { v: import("@/lib/api").Video }) {
  const total = v.processing_events_total;
  const done = v.processing_events_done;
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;

  let eta = "";
  if (done > 0 && total > 0 && v.processing_started_at) {
    const elapsed = (Date.now() - new Date(v.processing_started_at).getTime()) / 1000;
    const rate = done / elapsed;
    const remaining = (total - done) / rate;
    eta = formatEta(remaining);
  }

  return (
    <div className="flex-1 min-w-0 mt-2">
      <div className="flex justify-between text-xs text-zinc-500 mb-1">
        <span>{total > 0 ? `${done} / ${total} clips` : "Detectando eventos..."}</span>
        <span className="text-yellow-400 font-medium">
          {total > 0 ? `${pct}%` : ""}
          {eta && <span className="ml-2 text-zinc-500">{eta}</span>}
        </span>
      </div>
      <div className="w-full h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-yellow-400 rounded-full transition-all duration-500"
          style={{ width: total > 0 ? `${pct}%` : "0%" }}
        />
      </div>
    </div>
  );
}

function BatchProgress({ batches }: { batches: LabelingBatch[] }) {
  if (batches.length === 0) return null;
  const total = batches.reduce((s, b) => s + b.total, 0);
  const labeled = batches.reduce((s, b) => s + b.manual + b.pseudo, 0);
  const completed = batches.filter((b) => b.status === "completed").length;
  const pct = total > 0 ? Math.round((labeled / total) * 100) : 0;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 mb-6">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-zinc-300">Progreso de etiquetado</h3>
        <Link href="/dashboard/review" className="text-xs text-emerald-400 hover:underline">
          Ir a revision
        </Link>
      </div>
      <div className="flex gap-4 text-xs text-zinc-500 mb-2">
        <span><span className="text-white font-medium">{completed}</span>/{batches.length} lotes completados</span>
        <span><span className="text-white font-medium">{labeled}</span>/{total} clips etiquetados</span>
        <span className="text-emerald-400 font-medium">{pct}%</span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className="h-full flex">
          <div className="bg-emerald-500" style={{ width: `${batches.reduce((s,b)=>s+b.manual,0)/Math.max(total,1)*100}%` }} />
          <div className="bg-blue-500"    style={{ width: `${batches.reduce((s,b)=>s+b.pseudo,0)/Math.max(total,1)*100}%` }} />
        </div>
      </div>
      <div className="flex gap-4 mt-2 text-xs">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />Manual</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />Pseudo-IA</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-zinc-700 inline-block" />Pendiente</span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [batches, setBatches] = useState<LabelingBatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.videos.list();
      setVideos(data);
    } catch {
      /* noop */
    } finally {
      setLoading(false);
    }
  }, []);

  const deleteVideo = async (id: number) => {
    setDeletingId(id);
    try {
      await api.videos.delete(id);
      setVideos((prev) => prev.filter((v) => v.id !== id));
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Error al eliminar");
    } finally {
      setDeletingId(null);
    }
  };

  useEffect(() => {
    load();
    api.batches.list().then(setBatches).catch(() => null);
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <div className="p-8">
      <BatchProgress batches={batches} />
      <div className="flex items-center justify-between mb-8">
        <div>
          <h2 className="text-2xl font-bold text-white">Mis Vídeos</h2>
          <p className="text-zinc-500 text-sm mt-1">{videos.length} partidos analizados</p>
          <Link
            href="/dashboard/review"
            className="text-zinc-600 hover:text-emerald-400 text-xs mt-2 inline-block"
          >
            Revisión de clips · exportar etiquetas para entrenamiento →
          </Link>
        </div>
        <Link href="/dashboard/upload">
          <Button className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold">
            ↑ Subir Vídeo
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="text-zinc-600 text-sm">Cargando...</div>
      ) : videos.length === 0 ? (
        <div className="text-center py-24">
          <p className="text-zinc-600 text-lg">No hay vídeos aún</p>
          <Link href="/dashboard/upload">
            <Button className="mt-4 bg-emerald-500 hover:bg-emerald-400 text-black font-bold">
              Subir primer vídeo
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {videos.map((v) => (
            <div
              key={v.id}
              className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 hover:border-zinc-700 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <p className="text-white font-medium truncate">{v.original_name}</p>
                  <p className="text-zinc-600 text-xs mt-1">
                    {formatBytes(v.file_size)} · {new Date(v.created_at).toLocaleDateString("es-ES")}
                  </p>
                </div>

                <div className="flex items-center gap-4 ml-4 shrink-0">
                  {v.status === "completed" && (
                    <div className="text-right text-xs text-zinc-500">
                      <span className="text-white font-medium">{v.event_count}</span> eventos
                      {v.pending_count > 0 && (
                        <span className="ml-2 text-yellow-400">
                          · <span className="font-medium">{v.pending_count}</span> pendientes
                        </span>
                      )}
                    </div>
                  )}

                  <Badge className={`${STATUS_COLORS[v.status]} border text-xs`}>
                    {STATUS_LABELS[v.status]}
                    {v.status === "processing" && "..."}
                  </Badge>

                  {v.status === "completed" && (
                    <Link href={`/dashboard/results/${v.id}`}>
                      <Button size="sm" variant="outline" className="border-zinc-700 text-zinc-300 hover:text-white">
                        Ver
                      </Button>
                    </Link>
                  )}

                  {v.status !== "processing" && (
                    <button
                      onClick={() => deleteVideo(v.id)}
                      disabled={deletingId === v.id}
                      title="Eliminar vídeo"
                      className="text-zinc-600 hover:text-red-400 transition-colors disabled:opacity-40 text-lg leading-none"
                    >
                      {deletingId === v.id ? "..." : "×"}
                    </button>
                  )}
                </div>
              </div>

              {v.status === "queued" && (() => {
                const pos = videos
                  .filter(x => x.status === "queued")
                  .sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())
                  .findIndex(x => x.id === v.id) + 1;
                return (
                  <div className="mt-2 flex items-center gap-2 text-xs text-purple-400">
                    <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
                    Posición {pos} en cola — esperando slot de procesamiento
                  </div>
                );
              })()}
              {v.status === "processing" && <ProcessingProgress v={v} />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
