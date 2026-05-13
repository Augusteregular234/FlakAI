"use client";
import { useEffect, useState, useCallback } from "react";
import { api, type EventClip } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const EVENT_LABELS: Record<string, { icon: string; label: string; key: string }> = {
  goal:     { icon: "⚽", label: "Gol",           key: "1" },
  corner:   { icon: "🚩", label: "Córner",        key: "2" },
  throw_in: { icon: "🤾", label: "Saque de Banda", key: "3" },
  foul:     { icon: "🟨", label: "Falta",          key: "4" },
};
const EVENT_KEYS = Object.entries(EVENT_LABELS);

const CONFIDENCE_COLOR = (c: number) =>
  c >= 80 ? "text-emerald-400" : c >= 65 ? "text-yellow-400" : "text-red-400";

export default function ReviewPage() {
  const { user } = useAuthStore();
  const [clips, setClips] = useState<EventClip[]>([]);
  const [current, setCurrent] = useState(0);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<string | null>(null);

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

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowRight") setCurrent((c) => Math.min(c + 1, clips.length - 1));
      if (e.key === "ArrowLeft")  setCurrent((c) => Math.max(c - 1, 0));
      if (e.key === "a" || e.key === "A") handleReview("approved");
      if (e.key === "r" || e.key === "R") handleReview("rejected");
      // 1-4: reclassify + approve
      if (e.key === "1") handleReclassify("goal");
      if (e.key === "2") handleReclassify("corner");
      if (e.key === "3") handleReclassify("throw_in");
      if (e.key === "4") handleReclassify("foul");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  const runExport = async (key: string, fn: () => Promise<void>) => {
    setExporting(key);
    try { await fn(); }
    catch (e: unknown) { alert(e instanceof Error ? e.message : "Error al exportar"); }
    finally { setExporting(null); }
  };

  const advance = (current: number, clips: EventClip[]) => {
    const updated = clips.filter((_, i) => i !== current);
    return { updated, next: Math.min(current, updated.length - 1) };
  };

  const handleReview = async (status: "approved" | "rejected") => {
    const clip = clips[current];
    if (!clip || reviewing) return;
    setReviewing(true);
    try {
      await api.clips.review(clip.id, status);
      const { updated, next } = advance(current, clips);
      setClips(updated);
      setCurrent(next);
      setLastAction(status === "approved" ? `✅ Aceptado` : `❌ Rechazado`);
    } finally {
      setReviewing(false);
    }
  };

  const handleReclassify = async (newType: string) => {
    const clip = clips[current];
    if (!clip || reviewing) return;
    setReviewing(true);
    try {
      await api.clips.review(clip.id, "approved", newType);
      const { updated, next } = advance(current, clips);
      setClips(updated);
      setCurrent(next);
      const ev = EVENT_LABELS[newType];
      setLastAction(`${ev?.icon} Reclasificado → ${ev?.label}`);
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
          Puedes exportar las etiquetas humanas para entrenar modelos.
        </p>
        <div className="flex flex-wrap gap-2 justify-center">
          <Button variant="outline" className="border-zinc-700 text-zinc-300" disabled={!!exporting}
            onClick={() => runExport("tj", () => api.exportLabels.teamJsonl())}>
            {exporting === "tj" ? "…" : "Exportar equipo JSONL"}
          </Button>
          <Button variant="outline" className="border-zinc-700 text-zinc-300" disabled={!!exporting}
            onClick={() => runExport("tc", () => api.exportLabels.teamCsv())}>
            {exporting === "tc" ? "…" : "Exportar equipo CSV"}
          </Button>
          {user?.is_admin && (
            <>
              <Button variant="outline" className="border-amber-900/50 text-amber-400/90" disabled={!!exporting}
                onClick={() => runExport("aj", () => api.exportLabels.adminJsonl())}>
                {exporting === "aj" ? "…" : "Admin · JSONL global"}
              </Button>
              <Button variant="outline" className="border-amber-900/50 text-amber-400/90" disabled={!!exporting}
                onClick={() => runExport("ac", () => api.exportLabels.adminCsv())}>
                {exporting === "ac" ? "…" : "Admin · CSV global"}
              </Button>
            </>
          )}
        </div>
      </div>
    );
  }

  const clip = clips[current];
  const detected = EVENT_LABELS[clip.event_type];

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-5">
        <div>
          <h2 className="text-2xl font-bold text-white">Revisión de Clips</h2>
          <p className="text-zinc-500 text-sm mt-1">
            {current + 1} / {clips.length} pendientes
          </p>
          {lastAction && (
            <p className="text-zinc-400 text-xs mt-1 animate-pulse">{lastAction}</p>
          )}
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-400 text-xs"
            disabled={!!exporting} onClick={() => runExport("tj", () => api.exportLabels.teamJsonl())}>
            {exporting === "tj" ? "…" : "JSONL"}
          </Button>
          <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-400 text-xs"
            disabled={!!exporting} onClick={() => runExport("tc", () => api.exportLabels.teamCsv())}>
            {exporting === "tc" ? "…" : "CSV"}
          </Button>
          {user?.is_admin && (
            <Button variant="outline" size="sm" className="border-amber-900/40 text-amber-500/90 text-xs"
              disabled={!!exporting} onClick={() => runExport("aj", () => api.exportLabels.adminJsonl())}>
              {exporting === "aj" ? "…" : "Admin JSONL"}
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Video + actions */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden">
            <video
              key={clip.id}
              src={api.clips.streamUrl(clip.id)}
              controls
              autoPlay
              playsInline
              className="w-full aspect-video bg-black"
              onError={(e) => console.error("Video error", e.currentTarget.error?.code, e.currentTarget.src)}
            />
          </div>

          {/* Accept / Reject */}
          <div className="flex gap-3">
            <Button onClick={() => handleReview("approved")} disabled={reviewing}
              className="flex-1 h-14 text-lg font-black bg-emerald-500 hover:bg-emerald-400 text-black">
              ✅ Aceptar <span className="ml-2 text-xs font-normal opacity-60">[A]</span>
            </Button>
            <Button onClick={() => handleReview("rejected")} disabled={reviewing}
              className="flex-1 h-14 text-lg font-black bg-red-600 hover:bg-red-500 text-white">
              ❌ Rechazar <span className="ml-2 text-xs font-normal opacity-60">[R]</span>
            </Button>
          </div>

          {/* Reclassify */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4">
            <p className="text-zinc-500 text-xs mb-3 font-medium uppercase tracking-wide">
              Reclasificar y aceptar como…
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {EVENT_KEYS.map(([type, { icon, label, key }]) => {
                const isCurrentType = clip.event_type === type;
                return (
                  <button
                    key={type}
                    onClick={() => handleReclassify(type)}
                    disabled={reviewing}
                    className={`flex flex-col items-center gap-1.5 px-3 py-3 rounded-xl border text-sm font-semibold transition-all
                      ${isCurrentType
                        ? "border-emerald-600 bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-600/40"
                        : "border-zinc-700 bg-zinc-800/50 text-zinc-300 hover:border-zinc-500 hover:bg-zinc-700/50"
                      }
                      disabled:opacity-40 disabled:cursor-not-allowed`}
                  >
                    <span className="text-xl">{icon}</span>
                    <span className="leading-tight text-center">{label}</span>
                    <span className="text-xs opacity-50">[{key}]</span>
                  </button>
                );
              })}
            </div>
            <p className="text-zinc-600 text-xs mt-3">
              Si el clip es correcto pero la IA lo clasificó mal, usa estos botones para corregir el tipo y aceptarlo.
            </p>
          </div>

          {/* Keyboard hint */}
          <div className="flex flex-wrap gap-2 text-xs text-zinc-600">
            {[["←→", "navegar"], ["A", "aceptar"], ["R", "rechazar"], ["1", "⚽ Gol"], ["2", "🚩 Córner"], ["3", "🤾 Saque"], ["4", "🟨 Falta"]].map(([k, desc]) => (
              <span key={k} className="bg-zinc-900 border border-zinc-800 px-2 py-1 rounded">
                <kbd className="text-zinc-400 font-mono">{k}</kbd>
                <span className="ml-1 text-zinc-600">{desc}</span>
              </span>
            ))}
          </div>
        </div>

        {/* Info panel + queue */}
        <div className="space-y-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-2xl">{detected?.icon}</span>
              <h3 className="text-white font-bold text-lg">{detected?.label ?? clip.event_type}</h3>
              <Badge className="ml-auto bg-yellow-500/10 text-yellow-400 border-yellow-800 border text-xs">
                Pendiente
              </Badge>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-zinc-500">Confianza IA</span>
                <span className={`font-bold ${CONFIDENCE_COLOR(clip.confidence)}`}>
                  {clip.confidence}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Minuto</span>
                <span className="text-white">
                  {Math.floor(clip.timestamp_seconds / 60)}&apos;
                  {String(Math.floor(clip.timestamp_seconds % 60)).padStart(2, "0")}&quot;
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Modelo</span>
                <span className="text-zinc-400 text-xs truncate max-w-[120px]">
                  {clip.model_version ?? "—"}
                </span>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="flex-1 border-zinc-700 text-zinc-400"
              disabled={current === 0} onClick={() => setCurrent((c) => c - 1)}>
              ← Anterior
            </Button>
            <Button variant="outline" size="sm" className="flex-1 border-zinc-700 text-zinc-400"
              disabled={current === clips.length - 1} onClick={() => setCurrent((c) => c + 1)}>
              Siguiente →
            </Button>
          </div>

          {/* Queue */}
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4">
            <p className="text-zinc-500 text-xs mb-3">Cola de revisión ({clips.length})</p>
            <div className="space-y-1 max-h-72 overflow-y-auto">
              {clips.map((c, i) => {
                const ev = EVENT_LABELS[c.event_type];
                return (
                  <button key={c.id} onClick={() => setCurrent(i)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors flex items-center gap-2 ${
                      i === current
                        ? "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-600/30"
                        : "text-zinc-400 hover:bg-zinc-800"
                    }`}>
                    <span>{ev?.icon}</span>
                    <span className="flex-1 truncate">{ev?.label}</span>
                    <span className={CONFIDENCE_COLOR(c.confidence)}>{c.confidence}%</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
