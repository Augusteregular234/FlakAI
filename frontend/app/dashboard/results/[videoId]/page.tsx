"use client";
import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { api, type EventClip, type Video } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

const EVENT_LABELS: Record<string, string> = {
  goal: "⚽ Gol",
  corner: "🚩 Córner",
  throw_in: "🤾 Saque de Banda",
  foul: "🟨 Falta",
};

const EVENT_FILTERS = [
  { key: "all", label: "Todos" },
  { key: "goal", label: "⚽ Goles" },
  { key: "corner", label: "🚩 Córners" },
  { key: "throw_in", label: "🤾 Saques" },
  { key: "foul", label: "🟨 Faltas" },
];

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-500/10 text-yellow-400 border-yellow-800",
  approved: "bg-emerald-500/10 text-emerald-400 border-emerald-800",
  rejected: "bg-red-500/10 text-red-400 border-red-800",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Pendiente",
  approved: "Aprobado",
  rejected: "Rechazado",
};

export default function ResultsPage() {
  const { videoId } = useParams<{ videoId: string }>();
  const [video, setVideo] = useState<Video | null>(null);
  const [clips, setClips] = useState<EventClip[]>([]);
  const [active, setActive] = useState<EventClip | null>(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [v, c] = await Promise.all([
        api.videos.get(Number(videoId)),
        api.clips.forVideo(Number(videoId)),
      ]);
      setVideo(v);
      setClips(c);
      if (c.length > 0 && !active) setActive(c[0]);
    } finally {
      setLoading(false);
    }
  }, [videoId, active]);

  useEffect(() => { load(); }, [load]);

  const filtered = filter === "all" ? clips : clips.filter((c) => c.event_type === filter);

  if (loading) return <div className="p-8 text-zinc-600">Cargando...</div>;

  return (
    <div className="p-8">
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-white">{video?.original_name}</h2>
        <div className="flex items-center gap-4 mt-1 text-sm text-zinc-500">
          <span>{clips.length} eventos detectados</span>
          <span>·</span>
          <span>{clips.filter((c) => c.review_status === "approved").length} aprobados</span>
          <span>·</span>
          <span>{clips.filter((c) => c.review_status === "pending").length} pendientes</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          {active ? (
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden">
              <video
                key={active.id}
                src={api.clips.streamUrl(active.id)}
                controls
                autoPlay
                className="w-full aspect-video bg-black"
              />
              <div className="px-5 py-3 flex items-center justify-between">
                <div>
                  <p className="text-white font-medium">{EVENT_LABELS[active.event_type]}</p>
                  <p className="text-zinc-500 text-xs mt-0.5">
                    Min {Math.floor(active.timestamp_seconds / 60)}&apos;{String(Math.floor(active.timestamp_seconds % 60)).padStart(2, "0")}&quot;
                    · Confianza: <span className="text-white">{active.confidence}%</span>
                  </p>
                </div>
                <Badge className={`${STATUS_COLORS[active.review_status]} border`}>
                  {STATUS_LABELS[active.review_status]}
                </Badge>
              </div>
            </div>
          ) : (
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl aspect-video flex items-center justify-center">
              <p className="text-zinc-600">No hay clips para este filtro</p>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {EVENT_FILTERS.map((f) => (
              <Button
                key={f.key}
                size="sm"
                onClick={() => { setFilter(f.key); setActive(filtered[0] ?? null); }}
                className={
                  filter === f.key
                    ? "bg-emerald-500 text-black font-bold hover:bg-emerald-400"
                    : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white"
                }
              >
                {f.label}
              </Button>
            ))}
          </div>

          <div className="space-y-2 max-h-[calc(100vh-300px)] overflow-y-auto">
            {filtered.map((clip) => (
              <button
                key={clip.id}
                onClick={() => setActive(clip)}
                className={`w-full text-left p-4 rounded-xl border transition-all ${
                  active?.id === clip.id
                    ? "bg-emerald-500/5 border-emerald-800"
                    : "bg-zinc-900 border-zinc-800 hover:border-zinc-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-white text-sm font-medium">
                    {EVENT_LABELS[clip.event_type]}
                  </span>
                  <Badge className={`${STATUS_COLORS[clip.review_status]} border text-xs`}>
                    {STATUS_LABELS[clip.review_status]}
                  </Badge>
                </div>
                <div className="flex items-center justify-between mt-1 text-xs text-zinc-500">
                  <span>
                    Min {Math.floor(clip.timestamp_seconds / 60)}&apos;{String(Math.floor(clip.timestamp_seconds % 60)).padStart(2, "0")}&quot;
                  </span>
                  <span className={clip.confidence >= 80 ? "text-emerald-400" : "text-yellow-400"}>
                    {clip.confidence}%
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
