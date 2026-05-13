"use client";
import { useEffect, useState, useCallback } from "react";
import { api, type EventClip } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const EVENT_LABELS: Record<string, string> = {
  goal: "⚽ Gol",
  corner: "🚩 Córner",
  throw_in: "🤾 Saque de Banda",
  foul: "🟨 Falta",
};

const CONFIDENCE_COLOR = (c: number) =>
  c >= 80 ? "text-emerald-400" : c >= 65 ? "text-yellow-400" : "text-red-400";

export default function ReviewPage() {
  const { user } = useAuthStore();
  const [clips, setClips] = useState<EventClip[]>([]);
  const [current, setCurrent] = useState(0);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await api.clips.pending();
      setClips(data);
      setCurrent(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") setCurrent((c) => Math.min(c + 1, clips.length - 1));
      if (e.key === "ArrowLeft") setCurrent((c) => Math.max(c - 1, 0));
      if (e.key === "a" || e.key === "A") handleReview("approved");
      if (e.key === "r" || e.key === "R") handleReview("rejected");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  const runExport = async (
    key: string,
    fn: () => Promise<void>
  ) => {
    setExporting(key);
    try {
      await fn();
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : "Error al exportar");
    } finally {
      setExporting(null);
    }
  };

  const handleReview = async (status: "approved" | "rejected") => {
    const clip = clips[current];
    if (!clip || reviewing) return;
    setReviewing(true);
    try {
      await api.clips.review(clip.id, status);
      const updated = clips.filter((_, i) => i !== current);
      setClips(updated);
      setCurrent((c) => Math.min(c, updated.length - 1));
    } finally {
      setReviewing(false);
    }
  };

  if (loading) return <div className="p-8 text-zinc-600">Cargando...</div>;

  if (clips.length === 0) {
    return (
      <div className="p-8 flex flex-col items-center justify-center min-h-[60vh] max-w-lg mx-auto text-center">
        <div className="text-6xl mb-4">✅</div>
        <h2 className="text-xl font-bold text-white">Sin clips pendientes</h2>
        <p className="text-zinc-500 text-sm mt-2 mb-6">
          Puedes exportar las etiquetas humanas (clips ya aceptados o rechazados) para entrenar modelos.
        </p>
        <div className="flex flex-wrap gap-2 justify-center">
          <Button
            variant="outline"
            className="border-zinc-700 text-zinc-300"
            disabled={!!exporting}
            onClick={() => runExport("tj", () => api.exportLabels.teamJsonl())}
          >
            {exporting === "tj" ? "…" : "Exportar equipo JSONL"}
          </Button>
          <Button
            variant="outline"
            className="border-zinc-700 text-zinc-300"
            disabled={!!exporting}
            onClick={() => runExport("tc", () => api.exportLabels.teamCsv())}
          >
            {exporting === "tc" ? "…" : "Exportar equipo CSV"}
          </Button>
          {user?.is_admin && (
            <>
              <Button
                variant="outline"
                className="border-amber-900/50 text-amber-400/90"
                disabled={!!exporting}
                onClick={() => runExport("aj", () => api.exportLabels.adminJsonl())}
              >
                {exporting === "aj" ? "…" : "Admin · JSONL global"}
              </Button>
              <Button
                variant="outline"
                className="border-amber-900/50 text-amber-400/90"
                disabled={!!exporting}
                onClick={() => runExport("ac", () => api.exportLabels.adminCsv())}
              >
                {exporting === "ac" ? "…" : "Admin · CSV global"}
              </Button>
            </>
          )}
        </div>
      </div>
    );
  }

  const clip = clips[current];

  return (
    <div className="p-8">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white">Revisión de Clips</h2>
          <p className="text-zinc-500 text-sm mt-1">
            {current + 1} / {clips.length} pendientes · ← → · A=Aceptar · R=Rechazar
          </p>
          <p className="text-zinc-600 text-xs mt-2 max-w-xl">
            Cada aceptar/rechazar es una etiqueta humana. Exporta al finalizar para dataset de entrenamiento.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <Button
            variant="outline"
            size="sm"
            className="border-zinc-700 text-zinc-400 text-xs"
            disabled={!!exporting}
            onClick={() => runExport("tj", () => api.exportLabels.teamJsonl())}
          >
            {exporting === "tj" ? "…" : "Etiquetas JSONL"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="border-zinc-700 text-zinc-400 text-xs"
            disabled={!!exporting}
            onClick={() => runExport("tc", () => api.exportLabels.teamCsv())}
          >
            {exporting === "tc" ? "…" : "Etiquetas CSV"}
          </Button>
          {user?.is_admin && (
            <Button
              variant="outline"
              size="sm"
              className="border-amber-900/40 text-amber-500/90 text-xs"
              disabled={!!exporting}
              onClick={() => runExport("aj", () => api.exportLabels.adminJsonl())}
            >
              {exporting === "aj" ? "…" : "Admin JSONL"}
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden relative">
            <video
              key={clip.id}
              src={api.clips.streamUrl(clip.id)}
              controls
              autoPlay
              playsInline
              className="w-full aspect-video bg-black"
              onError={(e) => {
                const v = e.currentTarget;
                console.error("Video error", v.error?.code, v.error?.message, v.src);
              }}
            />
          </div>

          <div className="flex gap-4">
            <Button
              onClick={() => handleReview("approved")}
              disabled={reviewing}
              className="flex-1 h-16 text-xl font-black bg-emerald-500 hover:bg-emerald-400 text-black"
            >
              ✅ Aceptar
            </Button>
            <Button
              onClick={() => handleReview("rejected")}
              disabled={reviewing}
              className="flex-1 h-16 text-xl font-black bg-red-600 hover:bg-red-500 text-white"
            >
              ❌ Rechazar
            </Button>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
            <h3 className="text-white font-bold text-lg mb-4">
              {EVENT_LABELS[clip.event_type]}
            </h3>
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-zinc-500">Confianza IA</span>
                <span className={`font-bold text-base ${CONFIDENCE_COLOR(clip.confidence)}`}>
                  {clip.confidence}%
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-500">Minuto</span>
                <span className="text-white">{Math.floor(clip.timestamp_seconds / 60)}&apos;{String(Math.floor(clip.timestamp_seconds % 60)).padStart(2, "0")}&quot;</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-zinc-500">Estado</span>
                <Badge className="bg-yellow-500/10 text-yellow-400 border-yellow-800 border">
                  Pendiente
                </Badge>
              </div>
            </div>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4">
            <p className="text-zinc-500 text-xs mb-3">Cola de revisión</p>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {clips.map((c, i) => (
                <button
                  key={c.id}
                  onClick={() => setCurrent(i)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors ${
                    i === current
                      ? "bg-emerald-500/10 text-emerald-400"
                      : "text-zinc-400 hover:bg-zinc-800"
                  }`}
                >
                  {EVENT_LABELS[c.event_type]} · {c.confidence}%
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
