"use client";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  api, type MlAdminSummary, type Team, type LabelStats,
  type DatasetStats, type TrainingStatus,
} from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function TrainingProgressCard({ status }: { status: TrainingStatus }) {
  const pct = status.total_epochs > 0
    ? Math.round((status.current_epoch / status.total_epochs) * 100)
    : 0;

  const remainingEpochs = status.total_epochs - status.current_epoch;
  const etaSec = status.last_epoch_seconds > 0
    ? remainingEpochs * status.last_epoch_seconds
    : null;
  const etaStr = etaSec
    ? etaSec > 60
      ? `~${Math.round(etaSec / 60)} min restantes`
      : `~${Math.round(etaSec)}s restantes`
    : null;

  const statusColor =
    status.status === "running" ? "text-yellow-400" :
    status.status === "done"    ? "text-emerald-400" :
    status.status === "failed"  ? "text-red-400"     : "text-zinc-500";

  const statusLabel =
    status.status === "running" ? "Entrenando..." :
    status.status === "done"    ? "Completado" :
    status.status === "failed"  ? "Error" : "Inactivo";

  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardHeader>
        <CardTitle className="text-white text-base flex items-center gap-2">
          Estado del entrenamiento
          <span className={`text-sm font-normal ${statusColor}`}>{statusLabel}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {status.status !== "idle" && (
          <>
            <div className="flex justify-between text-sm">
              <span className="text-zinc-500">
                Epoch {status.current_epoch} / {status.total_epochs || "?"}
              </span>
              <span className="text-white font-mono">{pct}%</span>
            </div>
            <div className="h-2.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  status.status === "done" ? "bg-emerald-500" :
                  status.status === "failed" ? "bg-red-600" : "bg-yellow-400"
                }`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="flex gap-6 text-xs text-zinc-500">
              {status.last_val_f1 > 0 && (
                <span>val_f1: <span className="text-white">{status.last_val_f1.toFixed(3)}</span></span>
              )}
              {status.best_val_f1 > 0 && (
                <span>mejor: <span className="text-emerald-400">{status.best_val_f1.toFixed(3)}</span></span>
              )}
              {etaStr && status.status === "running" && (
                <span className="text-yellow-400">{etaStr}</span>
              )}
              {status.model_version > 0 && (
                <span>modelo: <span className="text-white">v{status.model_version}</span></span>
              )}
            </div>
            {status.status === "failed" && status.error && (
              <p className="text-red-400 text-xs">{status.error}</p>
            )}
          </>
        )}
        {status.status === "idle" && (
          <p className="text-zinc-600 text-sm">No hay entrenamiento en curso.</p>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const { user } = useAuthStore();

  const [teams, setTeams] = useState<Team[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const [ml, setMl] = useState<MlAdminSummary | null>(null);
  const [labelStats, setLabelStats] = useState<LabelStats | null>(null);
  const [datasetStats, setDatasetStats] = useState<DatasetStats | null>(null);
  const [trainStatus, setTrainStatus] = useState<TrainingStatus | null>(null);

  const [pseudoThreshold, setPseudoThreshold] = useState(75);
  const [pseudoBusy, setPseudoBusy] = useState(false);
  const [pseudoResult, setPseudoResult] = useState<string | null>(null);

  const [trainBusy, setTrainBusy] = useState(false);
  const [trainResult, setTrainResult] = useState<string | null>(null);

  const [redistributeBusy, setRedistributeBusy] = useState(false);
  const [redistributeResult, setRedistributeResult] = useState<string | null>(null);

  const loadTeams = useCallback(async () => {
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

  const loadTrainStatus = useCallback(async () => {
    try {
      const s = await api.admin.trainingStatus();
      setTrainStatus(s);
    } catch { /* noop */ }
  }, []);

  useEffect(() => {
    if (!user?.is_admin) { router.replace("/dashboard"); return; }
    loadTeams();
    loadTrainStatus();
    Promise.all([
      api.admin.mlSummary().catch(() => null),
      api.admin.labelStats().catch(() => null),
      api.admin.datasetStats().catch(() => null),
    ]).then(([mlData, ls, ds]) => {
      if (mlData) setMl(mlData);
      if (ls) setLabelStats(ls);
      if (ds) setDatasetStats(ds);
    });
  }, [user?.is_admin, router, loadTeams, loadTrainStatus]);

  // Poll training status every 30s while running
  useEffect(() => {
    if (trainStatus?.status !== "running") return;
    const id = setInterval(loadTrainStatus, 30_000);
    return () => clearInterval(id);
  }, [trainStatus?.status, loadTrainStatus]);

  if (!user?.is_admin) return null;

  const approve = async (id: number) => {
    setBusyId(id);
    try { await api.admin.approveTeam(id); await loadTeams(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Error"); }
    finally { setBusyId(null); }
  };

  const reject = async (id: number) => {
    setBusyId(id);
    try { await api.admin.rejectTeam(id); await loadTeams(); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Error"); }
    finally { setBusyId(null); }
  };

  const handlePseudoLabel = async () => {
    setPseudoBusy(true);
    setPseudoResult(null);
    try {
      const res = await api.admin.pseudoLabel(pseudoThreshold);
      setPseudoResult(`${res.pseudo_labeled} clips pseudo-etiquetados. ${res.still_pending} pendientes con confianza baja.`);
      api.admin.labelStats().then(setLabelStats).catch(() => null);
    } catch (e: unknown) {
      setPseudoResult(`Error: ${e instanceof Error ? e.message : "fallo"}`);
    } finally {
      setPseudoBusy(false);
    }
  };

  const handleStartTraining = async () => {
    setTrainBusy(true);
    setTrainResult(null);
    try {
      await api.admin.startTraining(20, 0.001);
      setTrainResult("Entrenamiento iniciado.");
      setTimeout(loadTrainStatus, 3000);
    } catch (e: unknown) {
      setTrainResult(`Error: ${e instanceof Error ? e.message : "fallo"}`);
    } finally {
      setTrainBusy(false);
    }
  };

  const handleRedistribute = async () => {
    setRedistributeBusy(true);
    setRedistributeResult(null);
    try {
      const res = await api.batches.redistribute();
      setRedistributeResult(
        res.assigned > 0
          ? `${res.assigned} clips asignados a ${res.batches_used} lotes.`
          : res.message ?? "Sin clips sin asignar."
      );
    } catch (e: unknown) {
      setRedistributeResult(`Error: ${e instanceof Error ? e.message : "fallo"}`);
    } finally {
      setRedistributeBusy(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Administracion</h1>
        <p className="text-zinc-500 text-sm mt-1">Equipos, modelo y etiquetado.</p>
      </div>

      {/* Training progress */}
      {trainStatus && <TrainingProgressCard status={trainStatus} />}

      {/* Label stats */}
      {labelStats && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-white text-base">Estado del etiquetado</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4 mb-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-emerald-400">{labelStats.manual}</p>
                <p className="text-zinc-500 text-xs mt-1">Manual</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-400">{labelStats.pseudo}</p>
                <p className="text-zinc-500 text-xs mt-1">Pseudo-IA</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-yellow-400">{labelStats.pending}</p>
                <p className="text-zinc-500 text-xs mt-1">Pendiente</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                <div className="h-full flex">
                  <div className="bg-emerald-500" style={{ width: `${labelStats.total > 0 ? (labelStats.manual / labelStats.total) * 100 : 0}%` }} />
                  <div className="bg-blue-500"    style={{ width: `${labelStats.total > 0 ? (labelStats.pseudo / labelStats.total) * 100 : 0}%` }} />
                </div>
              </div>
              <span className="text-zinc-400 text-sm font-mono">{labelStats.labeled_pct}%</span>
            </div>
            <p className="text-zinc-600 text-xs mt-2">{labelStats.manual + labelStats.pseudo} de {labelStats.total} clips etiquetados</p>
          </CardContent>
        </Card>
      )}

      {/* Batch redistribute */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white text-base">Gestion de lotes</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-zinc-500 text-sm">
            A medida que se procesan nuevos partidos, sus clips se asignan automaticamente a los lotes existentes.
            Si hay clips sin asignar puedes redistribuirlos manualmente aqui.
          </p>
          <Button
            onClick={handleRedistribute}
            disabled={redistributeBusy}
            className="bg-zinc-700 hover:bg-zinc-600 text-white"
          >
            {redistributeBusy ? "Redistribuyendo..." : "Redistribuir clips sin lote"}
          </Button>
          {redistributeResult && (
            <p className={`text-sm ${redistributeResult.startsWith("Error") ? "text-red-400" : "text-zinc-300"}`}>
              {redistributeResult}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Pseudo-labeling */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white text-base">Pseudo-etiquetado automatico</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-zinc-500 text-sm">
            Etiqueta clips pendientes usando la confianza del detector. Solo clips con label_source=pending.
            Las etiquetas manuales nunca se sobreescriben.
          </p>
          <div className="flex items-center gap-4">
            <label className="text-zinc-400 text-sm">Umbral:</label>
            <input type="range" min={50} max={95} step={5} value={pseudoThreshold}
              onChange={(e) => setPseudoThreshold(Number(e.target.value))}
              className="flex-1 accent-blue-500" />
            <span className="text-blue-400 font-mono text-sm w-10">{pseudoThreshold}%</span>
          </div>
          <Button onClick={handlePseudoLabel} disabled={pseudoBusy}
            className="bg-blue-600 hover:bg-blue-500 text-white font-bold">
            {pseudoBusy ? "Ejecutando..." : "Ejecutar pseudo-etiquetado"}
          </Button>
          {pseudoResult && (
            <p className={`text-sm ${pseudoResult.startsWith("Error") ? "text-red-400" : "text-zinc-300"}`}>{pseudoResult}</p>
          )}
        </CardContent>
      </Card>

      {/* Model training */}
      {datasetStats && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-white text-base">Entrenamiento del modelo</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-3 gap-3 text-sm">
              <div>
                <p className="text-zinc-500 text-xs">Aprobados</p>
                <p className="text-emerald-400 font-bold">{datasetStats.total_approved}</p>
              </div>
              <div>
                <p className="text-zinc-500 text-xs">Rechazados</p>
                <p className="text-red-400 font-bold">{datasetStats.total_rejected}</p>
              </div>
              <div>
                <p className="text-zinc-500 text-xs">Total etiquetados</p>
                <p className="text-white font-bold">{datasetStats.total_labeled}</p>
              </div>
            </div>
            <p className={`text-sm ${datasetStats.can_train ? "text-emerald-400" : "text-yellow-400"}`}>
              {datasetStats.recommendation}
            </p>
            <Button onClick={handleStartTraining} disabled={trainBusy || !datasetStats.can_train || trainStatus?.status === "running"}
              className="bg-purple-600 hover:bg-purple-500 text-white font-bold disabled:opacity-40">
              {trainBusy ? "Iniciando..." : trainStatus?.status === "running" ? "Entrenando..." : "Iniciar entrenamiento completo"}
            </Button>
            {trainResult && (
              <p className={`text-sm ${trainResult.startsWith("Error") ? "text-red-400" : "text-zinc-300"}`}>{trainResult}</p>
            )}
          </CardContent>
        </Card>
      )}

      {/* ML config */}
      {ml && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardHeader>
            <CardTitle className="text-white text-base">Configuracion del detector</CardTitle>
          </CardHeader>
          <CardContent className="text-zinc-400 text-sm space-y-1 font-mono">
            <p><span className="text-zinc-600">Backend:</span> {ml.detector_backend} <span className="text-zinc-600">v:</span> {ml.model_version}</p>
            <p><span className="text-zinc-600">Ventana clips:</span> {ml.clip_window_seconds}s</p>
            <p><span className="text-zinc-600">Auto-aprobar &gt;=:</span> {ml.auto_approve_confidence}%</p>
          </CardContent>
        </Card>
      )}

      {/* Team approval */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white text-base">Equipos pendientes</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <p className="text-red-400 text-sm border border-red-900 rounded-lg px-3 py-2 bg-red-950/30">{error}</p>}
          {loading ? (
            <p className="text-zinc-500 text-sm">Cargando...</p>
          ) : teams.length === 0 ? (
            <p className="text-zinc-500 text-sm">No hay equipos pendientes.</p>
          ) : (
            <ul className="space-y-3">
              {teams.map((t) => (
                <li key={t.id} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-xl bg-zinc-950 border border-zinc-800">
                  <div>
                    <p className="text-white font-medium">{t.name}</p>
                    <p className="text-zinc-600 text-xs mt-1">ID {t.id}{t.requested_at && <> · {new Date(t.requested_at).toLocaleString()}</>}</p>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <Button className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
                      disabled={busyId === t.id} onClick={() => approve(t.id)}>Aprobar</Button>
                    <Button variant="outline" className="border-red-900 text-red-400 hover:bg-red-950/40"
                      disabled={busyId === t.id} onClick={() => reject(t.id)}>Rechazar</Button>
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
