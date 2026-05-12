"use client";
import { useEffect, useState, useCallback } from "react";
import { api, type EventClip } from "@/lib/api";
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
  const [clips, setClips] = useState<EventClip[]>([]);
  const [current, setCurrent] = useState(0);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);

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
      <div className="p-8 flex flex-col items-center justify-center min-h-[60vh]">
        <div className="text-6xl mb-4">✅</div>
        <h2 className="text-xl font-bold text-white">Sin clips pendientes</h2>
        <p className="text-zinc-500 text-sm mt-2">
          Todos los clips han sido revisados
        </p>
      </div>
    );
  }

  const clip = clips[current];

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white">Revisión de Clips</h2>
          <p className="text-zinc-500 text-sm mt-1">
            {current + 1} / {clips.length} pendientes · Usa ← → para navegar · A=Aceptar · R=Rechazar
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden">
            <video
              key={clip.id}
              src={api.clips.streamUrl(clip.id)}
              controls
              autoPlay
              className="w-full aspect-video bg-black"
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
