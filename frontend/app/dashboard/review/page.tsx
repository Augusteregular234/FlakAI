"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import { api, type EventClip, type LabelingBatch, type LabelSource } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

// ── Constants ────────────────────────────────────────────────────────────

const EVENT_LABELS: Record<string, { icon: string; label: string; key: string }> = {
  goal:           { icon: "goal",   label: "Gol",              key: "1" },
  corner:         { icon: "corner", label: "Corner",           key: "2" },
  throw_in:       { icon: "banda",  label: "Saque de Banda",   key: "3" },
  foul:           { icon: "falta",  label: "Falta",            key: "4" },
  goal_kick:      { icon: "porteria",label: "Saque de Porteria",key: "5" },
  shot_on_target: { icon: "tiro",   label: "Tiro a Porteria",  key: "6" },
};

const EVENT_ICONS: Record<string, string> = {
  goal: "Goal", corner: "Corner", throw_in: "Banda", foul: "Falta",
  goal_kick: "S.Port.", shot_on_target: "Tiro",
};

const EVENT_KEYS = Object.entries(EVENT_LABELS);

const CONF_COLOR = (c: number) =>
  c >= 80 ? "text-emerald-400" : c >= 65 ? "text-yellow-400" : "text-red-400";

const SOURCE_BADGE: Record<LabelSource, string> = {
  pending: "bg-yellow-500/10 text-yellow-400 border border-yellow-800",
  pseudo:  "bg-blue-500/10  text-blue-400  border border-blue-800",
  manual:  "bg-emerald-500/10 text-emerald-400 border border-emerald-800",
};
const SOURCE_LABEL: Record<LabelSource, string> = {
  pending: "Pendiente",
  pseudo:  "Pseudo-IA",
  manual:  "Manual",
};

type SourceFilter = "pending" | "pseudo";

// ── Component ─────────────────────────────────────────────────────────────

export default function ReviewPage() {
  const { user } = useAuthStore();

  // Batch state
  const [batches, setBatches] = useState<LabelingBatch[]>([]);
  const [batchesLoading, setBatchesLoading] = useState(true);
  const [selectedBatch, setSelectedBatch] = useState<number | null>(null);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("pending");
  const [initializing, setInitializing] = useState(false);

  // Clip state
  const [clips, setClips] = useState<EventClip[]>([]);
  const [current, setCurrent] = useState(0);
  const [clipsLoading, setClipsLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Action state
  const [reviewing, setReviewing] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<string | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);

  // Load batches
  const loadBatches = useCallback(async () => {
    setBatchesLoading(true);
    try {
      const data = await api.batches.list();
      setBatches(data);
      // Auto-select first non-completed batch
      if (selectedBatch === null && data.length > 0) {
        const first = data.find((b) => b.status !== "completed") ?? data[0];
        setSelectedBatch(first.id);
      }
    } catch {
      // ignore — show init prompt
    } finally {
      setBatchesLoading(false);
    }
  }, [selectedBatch]);

  useEffect(() => { loadBatches(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Load clips when batch or filter changes
  const loadClips = useCallback(async () => {
    setClipsLoading(true);
    setLoadError(null);
    try {
      let data: EventClip[];
      if (selectedBatch !== null) {
        data = await api.batches.clips(selectedBatch, sourceFilter);
      } else {
        data = sourceFilter === "pending"
          ? await api.clips.pending()
          : await api.clips.pseudo();
      }
      setClips(data);
      setCurrent(0);
    } catch (e: unknown) {
      setLoadError(e instanceof Error ? e.message : "Error al cargar clips");
    } finally {
      setClipsLoading(false);
    }
  }, [selectedBatch, sourceFilter]);

  useEffect(() => {
    if (!batchesLoading) loadClips();
  }, [batchesLoading, loadClips]);

  // Review handlers
  const handleReview = useCallback(async (status: "approved" | "rejected") => {
    const clip = clips[current];
    if (!clip || reviewing) return;
    setReviewing(true);
    try {
      await api.clips.review(clip.id, status);
      const updated = clips.filter((_, i) => i !== current);
      setClips(updated);
      setCurrent(Math.min(current, updated.length - 1));
      setLastAction(status === "approved" ? "Aceptado" : "Rechazado");
      // Refresh batch stats
      loadBatches();
    } catch (e: unknown) {
      setLastAction(`Error: ${e instanceof Error ? e.message : "fallo"}`);
    } finally {
      setReviewing(false);
    }
  }, [clips, current, reviewing, loadBatches]);

  const handleReclassify = useCallback(async (newType: string) => {
    const clip = clips[current];
    if (!clip || reviewing) return;
    setReviewing(true);
    try {
      await api.clips.review(clip.id, "approved", newType);
      const updated = clips.filter((_, i) => i !== current);
      setClips(updated);
      setCurrent(Math.min(current, updated.length - 1));
      const ev = EVENT_LABELS[newType];
      setLastAction(`Reclasificado a ${ev?.label}`);
      loadBatches();
    } catch (e: unknown) {
      setLastAction(`Error: ${e instanceof Error ? e.message : "fallo"}`);
    } finally {
      setReviewing(false);
    }
  }, [clips, current, reviewing, loadBatches]);

  const handleCompleteBatch = async () => {
    if (selectedBatch === null || completing) return;
    setCompleting(true);
    try {
      await api.batches.complete(selectedBatch);
      await loadBatches();
      setLastAction("Lote marcado como completado");
    } catch (e: unknown) {
      setLastAction(`Error: ${e instanceof Error ? e.message : "fallo"}`);
    } finally {
      setCompleting(false);
    }
  };

  const handleInitBatches = async () => {
    setInitializing(true);
    try {
      const result = await api.batches.initialize(10);
      setLastAction(`${result.created} lotes creados con ${result.clips_distributed} clips`);
      await loadBatches();
    } catch (e: unknown) {
      setLastAction(`Error: ${e instanceof Error ? e.message : "fallo al inicializar"}`);
    } finally {
      setInitializing(false);
    }
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === "ArrowRight") setCurrent((c) => Math.min(c + 1, clips.length - 1));
      if (e.key === "ArrowLeft")  setCurrent((c) => Math.max(c - 1, 0));
      if (e.key === "a" || e.key === "A") handleReview("approved");
      if (e.key === "r" || e.key === "R") handleReview("rejected");
      if (e.key === "1") handleReclassify("goal");
      if (e.key === "2") handleReclassify("corner");
      if (e.key === "3") handleReclassify("throw_in");
      if (e.key === "4") handleReclassify("foul");
      if (e.key === "5") handleReclassify("goal_kick");
      if (e.key === "6") handleReclassify("shot_on_target");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [clips.length, handleReview, handleReclassify]);

  const runExport = async (key: string, fn: () => Promise<void>) => {
    setExporting(key);
    try { await fn(); }
    catch (e: unknown) { alert(e instanceof Error ? e.message : "Error al exportar"); }
    finally { setExporting(null); }
  };

  // ── Render: loading batches ─────────────────────────────────────────────
  if (batchesLoading) {
    return <div className="p-8 text-zinc-600">Cargando lotes...</div>;
  }

  // ── Render: no batches yet ──────────────────────────────────────────────
  if (batches.length === 0) {
    return (
      <div className="p-8 flex flex-col items-center justify-center min-h-[60vh] max-w-lg mx-auto text-center">
        <div className="text-5xl mb-4">📦</div>
        <h2 className="text-xl font-bold text-white mb-2">Sin lotes de etiquetado</h2>
        <p className="text-zinc-500 text-sm mb-6">
          Organiza tus clips en 10 lotes para etiquetarlos de forma estructurada.
          Cada lote se marca como completado al terminar.
        </p>
        {lastAction && <p className="text-zinc-400 text-xs mb-4">{lastAction}</p>}
        <Button
          onClick={handleInitBatches}
          disabled={initializing}
          className="bg-emerald-500 hover:bg-emerald-400 text-black font-bold"
        >
          {initializing ? "Creando lotes..." : "Crear 10 lotes automaticamente"}
        </Button>
      </div>
    );
  }

  const selectedBatchData = batches.find((b) => b.id === selectedBatch);

  // ── Render: header bar ──────────────────────────────────────────────────
  const HeaderBar = (
    <div className="flex flex-col sm:flex-row sm:items-center gap-3 mb-5">
      <div className="flex-1 flex flex-wrap items-center gap-3">
        <div>
          <h2 className="text-2xl font-bold text-white">Revision de Clips</h2>
          {lastAction && (
            <p className={`text-xs mt-0.5 ${lastAction.startsWith("Error") ? "text-red-400" : "text-zinc-400"}`}>
              {lastAction}
            </p>
          )}
        </div>

        {/* Batch selector */}
        <select
          value={selectedBatch ?? "all"}
          onChange={(e) => setSelectedBatch(e.target.value === "all" ? null : Number(e.target.value))}
          className="bg-zinc-800 border border-zinc-700 text-zinc-300 text-sm rounded-lg px-3 py-1.5 focus:outline-none focus:border-zinc-500"
        >
          <option value="all">Todos los lotes</option>
          {batches.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name} — {b.manual + b.pseudo}/{b.total} etiquetados
              {b.status === "completed" ? " [completado]" : ""}
            </option>
          ))}
        </select>

        {/* Source filter */}
        <div className="flex rounded-lg border border-zinc-700 overflow-hidden">
          <button
            onClick={() => setSourceFilter("pending")}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              sourceFilter === "pending"
                ? "bg-yellow-500/20 text-yellow-400"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Pendientes
          </button>
          <button
            onClick={() => setSourceFilter("pseudo")}
            className={`px-3 py-1.5 text-xs font-medium transition-colors border-l border-zinc-700 ${
              sourceFilter === "pseudo"
                ? "bg-blue-500/20 text-blue-400"
                : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            Pseudo-IA
          </button>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 shrink-0">
        {selectedBatch !== null && (
          <Button
            onClick={handleCompleteBatch}
            disabled={completing}
            size="sm"
            className={selectedBatchData?.status === "completed"
              ? "bg-zinc-700 hover:bg-emerald-600 text-zinc-300 font-bold"
              : "bg-emerald-600 hover:bg-emerald-500 text-white font-bold"}
          >
            {completing ? "..." : selectedBatchData?.status === "completed" ? "Completado - Recompletar" : "Marcar lote completado"}
          </Button>
        )}
        <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-400 text-xs"
          disabled={!!exporting} onClick={() => runExport("tj", () => api.exportLabels.teamJsonl())}>
          {exporting === "tj" ? "..." : "JSONL"}
        </Button>
        <Button variant="outline" size="sm" className="border-zinc-700 text-zinc-400 text-xs"
          disabled={!!exporting} onClick={() => runExport("tc", () => api.exportLabels.teamCsv())}>
          {exporting === "tc" ? "..." : "CSV"}
        </Button>
        {user?.is_admin && (
          <Button variant="outline" size="sm" className="border-amber-900/40 text-amber-500/90 text-xs"
            disabled={!!exporting} onClick={() => runExport("aj", () => api.exportLabels.adminJsonl())}>
            {exporting === "aj" ? "..." : "Admin JSONL"}
          </Button>
        )}
      </div>
    </div>
  );

  // ── Render: loading clips ───────────────────────────────────────────────
  if (clipsLoading) {
    return <div className="p-6">{HeaderBar}<div className="text-zinc-600 text-sm">Cargando clips...</div></div>;
  }

  if (loadError) {
    return (
      <div className="p-6">
        {HeaderBar}
        <div className="flex flex-col items-center justify-center min-h-[40vh] text-center">
          <div className="text-4xl mb-3">⚠️</div>
          <p className="text-red-400 mb-4">{loadError}</p>
          <Button onClick={loadClips} className="bg-zinc-800 border border-zinc-700">Reintentar</Button>
        </div>
      </div>
    );
  }

  // ── Render: empty state ─────────────────────────────────────────────────
  if (clips.length === 0) {
    const filterLabel = sourceFilter === "pending" ? "pendientes" : "pseudo-etiquetados";
    const batchLabel = selectedBatch !== null ? ` en ${selectedBatchData?.name ?? "este lote"}` : "";
    return (
      <div className="p-6">
        {HeaderBar}
        <div className="flex flex-col items-center justify-center min-h-[40vh] max-w-lg mx-auto text-center">
          <div className="text-5xl mb-4">✅</div>
          <h3 className="text-lg font-bold text-white">Sin clips {filterLabel}{batchLabel}</h3>
          <p className="text-zinc-500 text-sm mt-2 mb-4">
            {sourceFilter === "pseudo"
              ? "No hay clips pseudo-etiquetados. Ejecuta pseudo-etiquetado desde Administracion."
              : "Todos los clips de este lote han sido etiquetados."}
          </p>
          <div className="flex flex-wrap gap-2 justify-center">
            <Button variant="outline" className="border-zinc-700 text-zinc-300" disabled={!!exporting}
              onClick={() => runExport("tj", () => api.exportLabels.teamJsonl())}>
              {exporting === "tj" ? "..." : "Exportar JSONL"}
            </Button>
            <Button variant="outline" className="border-zinc-700 text-zinc-300" disabled={!!exporting}
              onClick={() => runExport("tc", () => api.exportLabels.teamCsv())}>
              {exporting === "tc" ? "..." : "Exportar CSV"}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // ── Render: review interface ────────────────────────────────────────────
  const clip = clips[current];
  const eventInfo = EVENT_LABELS[clip.event_type];
  const src = clip.label_source as LabelSource;

  return (
    <div className="p-6">
      {HeaderBar}

      <div className="flex items-center gap-2 mb-4 text-sm text-zinc-500">
        <span>{current + 1} / {clips.length} clips</span>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${SOURCE_BADGE[src]}`}>
          {SOURCE_LABEL[src]}
        </span>
        {src === "pseudo" && (
          <span className="text-blue-400/70 text-xs">
            Etiqueta IA — confirma o corrige con A/R
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Video + actions */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl overflow-hidden">
            <video
              key={clip.id}
              ref={videoRef}
              src={api.clips.streamUrl(clip.id)}
              controls
              autoPlay
              playsInline
              muted
              className="w-full aspect-video bg-black"
              onLoadedData={() => { if (videoRef.current) videoRef.current.playbackRate = 2; }}
              onError={(e) => console.error("Video error", e.currentTarget.error?.code)}
            />
          </div>

          <div className="flex gap-3">
            <Button onClick={() => handleReview("approved")} disabled={reviewing}
              className="flex-1 h-14 text-lg font-black bg-emerald-500 hover:bg-emerald-400 text-black">
              Aceptar <span className="ml-2 text-xs font-normal opacity-60">[A]</span>
            </Button>
            <Button onClick={() => handleReview("rejected")} disabled={reviewing}
              className="flex-1 h-14 text-lg font-black bg-red-600 hover:bg-red-500 text-white">
              Rechazar <span className="ml-2 text-xs font-normal opacity-60">[R]</span>
            </Button>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4">
            <p className="text-zinc-500 text-xs mb-3 font-medium uppercase tracking-wide">
              Reclasificar y aceptar como...
            </p>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {EVENT_KEYS.map(([type, { label, key }]) => (
                <button
                  key={type}
                  onClick={() => handleReclassify(type)}
                  disabled={reviewing}
                  className={`flex flex-col items-center gap-1 px-3 py-3 rounded-xl border text-sm font-semibold transition-all
                    ${clip.event_type === type
                      ? "border-emerald-600 bg-emerald-500/10 text-emerald-400"
                      : "border-zinc-700 bg-zinc-800/50 text-zinc-300 hover:border-zinc-500"
                    }
                    disabled:opacity-40 disabled:cursor-not-allowed`}
                >
                  <span className="text-xs font-mono text-zinc-600">[{key}]</span>
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-wrap gap-2 text-xs text-zinc-600">
            {[["<>","nav"],["A","ok"],["R","no"],["1","Gol"],["2","Corner"],["3","Banda"],["4","Falta"],["5","S.Port"],["6","Tiro"]].map(([k, d]) => (
              <span key={k} className="bg-zinc-900 border border-zinc-800 px-2 py-1 rounded">
                <kbd className="text-zinc-400 font-mono">{k}</kbd>
                <span className="ml-1">{d}</span>
              </span>
            ))}
          </div>
        </div>

        {/* Info + queue */}
        <div className="space-y-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-5">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-sm font-mono text-zinc-500 uppercase">{clip.event_type}</span>
              <h3 className="text-white font-bold">{eventInfo?.label ?? clip.event_type}</h3>
              <span className={`ml-auto px-2 py-0.5 rounded text-xs font-medium ${SOURCE_BADGE[src]}`}>
                {SOURCE_LABEL[src]}
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-zinc-500">Confianza IA</span>
                <span className={`font-bold ${CONF_COLOR(clip.confidence)}`}>{clip.confidence}%</span>
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
                <span className="text-zinc-400 text-xs truncate max-w-[120px]">{clip.model_version ?? "-"}</span>
              </div>
              {clip.batch_id !== null && (
                <div className="flex justify-between">
                  <span className="text-zinc-500">Lote</span>
                  <span className="text-zinc-400 text-xs">
                    {batches.find((b) => b.id === clip.batch_id)?.name ?? `#${clip.batch_id}`}
                  </span>
                </div>
              )}
            </div>
          </div>

          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="flex-1 border-zinc-700 text-zinc-400"
              disabled={current === 0} onClick={() => setCurrent((c) => c - 1)}>
              Anterior
            </Button>
            <Button variant="outline" size="sm" className="flex-1 border-zinc-700 text-zinc-400"
              disabled={current === clips.length - 1} onClick={() => setCurrent((c) => c + 1)}>
              Siguiente
            </Button>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4">
            <p className="text-zinc-500 text-xs mb-3">Cola ({clips.length})</p>
            <div className="space-y-1 max-h-72 overflow-y-auto">
              {clips.map((c, i) => {
                const csrc = c.label_source as LabelSource;
                return (
                  <button key={c.id} onClick={() => setCurrent(i)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors flex items-center gap-2 ${
                      i === current
                        ? "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-600/30"
                        : "text-zinc-400 hover:bg-zinc-800"
                    }`}>
                    <span className="font-mono text-zinc-600 w-12 shrink-0">{EVENT_ICONS[c.event_type] ?? c.event_type}</span>
                    <span className={`text-xs px-1.5 rounded ${SOURCE_BADGE[csrc]}`}>{SOURCE_LABEL[csrc][0]}</span>
                    <span className={`ml-auto ${CONF_COLOR(c.confidence)}`}>{c.confidence}%</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Batch progress */}
          {selectedBatchData && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4">
              <p className="text-zinc-500 text-xs mb-2">{selectedBatchData.name}</p>
              <div className="flex gap-3 text-xs">
                <span className="text-emerald-400">{selectedBatchData.manual} manual</span>
                <span className="text-blue-400">{selectedBatchData.pseudo} pseudo</span>
                <span className="text-yellow-400">{selectedBatchData.pending} pendiente</span>
              </div>
              <div className="mt-2 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full"
                  style={{
                    width: selectedBatchData.total > 0
                      ? `${Math.round(((selectedBatchData.manual + selectedBatchData.pseudo) / selectedBatchData.total) * 100)}%`
                      : "0%"
                  }}
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
