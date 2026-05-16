const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("flakai_token");
}

function formatApiError(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        typeof item === "object" && item !== null && "msg" in item
          ? String((item as { msg: string }).msg)
          : JSON.stringify(item)
      )
      .join("; ");
  }
  if (detail !== null && typeof detail === "object") return JSON.stringify(detail);
  return fallback;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  } catch {
    throw new Error(
      `No hay conexion con la API (${BASE_URL}). Arranca el backend (puerto 8000) o revisa NEXT_PUBLIC_API_URL en frontend/.env.local.`
    );
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const raw = (err as { detail?: unknown }).detail;
    throw new Error(formatApiError(raw, res.statusText || "Request failed"));
  }
  return res.json();
}

export async function downloadExport(path: string, filename: string): Promise<void> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { headers });
  } catch {
    throw new Error(`No hay conexion con la API (${BASE_URL}).`);
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const raw = (err as { detail?: unknown }).detail;
    throw new Error(formatApiError(raw, res.statusText || "Download failed"));
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export type TeamStatus = "pending_approval" | "active" | "rejected";
export type LabelSource = "pending" | "manual" | "pseudo";

export const api = {
  auth: {
    login: (username: string, password: string) =>
      request<AuthResponse>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      }),
    register: (data: RegisterData) =>
      request<AuthResponse>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(data),
      }),
    me: () =>
      request<{ user: AuthResponse["user"]; team: AuthResponse["team"] }>("/api/auth/me"),
  },
  admin: {
    pendingTeams: () => request<Team[]>(`/api/admin/teams/pending`),
    approveTeam: (id: number) =>
      request<Team>(`/api/admin/teams/${id}/approve`, { method: "POST" }),
    rejectTeam: (id: number) =>
      request<Team>(`/api/admin/teams/${id}/reject`, { method: "POST" }),
    mlSummary: () => request<MlAdminSummary>(`/api/admin/ml/summary`),
    labelStats: () => request<LabelStats>("/api/admin/ml/label-stats"),
    datasetStats: () => request<DatasetStats>("/api/admin/ml/dataset/stats"),
    pseudoLabel: (threshold = 75) =>
      request<PseudoLabelResult>(
        `/api/admin/ml/pseudo-label?confidence_threshold=${threshold}`,
        { method: "POST" }
      ),
    startTraining: (epochs = 20, lr = 0.001) =>
      request<Record<string, unknown>>(
        `/api/admin/ml/training/start?epochs=${epochs}&lr=${lr}`,
        { method: "POST" }
      ),
    trainingStatus: () => request<TrainingStatus>("/api/admin/ml/training/status"),
  },
  videos: {
    list: () => request<Video[]>("/api/videos/"),
    get: (id: number) => request<Video>(`/api/videos/${id}`),
    initUpload: (filename: string, fileSize: number) => {
      const form = new FormData();
      form.append("filename", filename);
      form.append("file_size", String(fileSize));
      return request<{ upload_id: string; video_id: number }>("/api/videos/upload/init", {
        method: "POST",
        body: form,
        headers: {},
      });
    },
    uploadChunk: (uploadId: string, chunkIndex: number, chunk: Blob) => {
      const form = new FormData();
      form.append("chunk_index", String(chunkIndex));
      form.append("chunk", chunk, `chunk_${chunkIndex}`);
      return request<{ chunk_index: number; status: string }>(
        `/api/videos/upload/${uploadId}/chunk`,
        { method: "POST", body: form, headers: {} }
      );
    },
    completeUpload: (uploadId: string) =>
      request<{ video_id: number; status: string }>(
        `/api/videos/upload/${uploadId}/complete`,
        { method: "POST" }
      ),
    delete: (videoId: number) =>
      request<{ deleted: number }>(`/api/videos/${videoId}`, { method: "DELETE" }),
  },
  clips: {
    pending: (batchId?: number) =>
      request<EventClip[]>(
        `/api/clips/pending${batchId !== undefined ? `?batch_id=${batchId}` : ""}`
      ),
    pseudo: (batchId?: number) =>
      request<EventClip[]>(
        `/api/clips/pseudo${batchId !== undefined ? `?batch_id=${batchId}` : ""}`
      ),
    forVideo: (videoId: number) => request<EventClip[]>(`/api/clips/video/${videoId}`),
    review: (clipId: number, status: "approved" | "rejected", eventType?: string) =>
      request<EventClip>(`/api/clips/${clipId}/review`, {
        method: "PATCH",
        body: JSON.stringify({ status, ...(eventType ? { event_type: eventType } : {}) }),
      }),
    streamUrl: (clipId: number) => {
      const token = getToken();
      const query = token ? `?token=${encodeURIComponent(token)}` : "";
      return `${BASE_URL}/api/clips/${clipId}/stream${query}`;
    },
  },
  batches: {
    list: () => request<LabelingBatch[]>("/api/batches/"),
    initialize: (n = 10) =>
      request<{ created: number; clips_distributed: number }>(
        `/api/batches/initialize?n=${n}`,
        { method: "POST" }
      ),
    redistribute: () =>
      request<{ assigned: number; batches_used?: number; message?: string }>(
        "/api/batches/redistribute",
        { method: "POST" }
      ),
    complete: (id: number) =>
      request<LabelingBatch>(`/api/batches/${id}/complete`, { method: "PATCH" }),
    clips: (id: number, source?: "pending" | "pseudo" | "manual") =>
      request<EventClip[]>(
        `/api/batches/${id}/clips${source ? `?source=${source}` : ""}`
      ),
  },
  billing: {
    plans: () => request<BillingPlans>("/api/billing/plans"),
    createCheckout: (tier: "pro" | "club") =>
      request<{ url: string }>("/api/billing/create-checkout-session", {
        method: "POST",
        body: JSON.stringify({ tier }),
      }),
    createPortal: () =>
      request<{ url: string }>("/api/billing/create-portal-session", { method: "POST" }),
  },
  exportLabels: {
    teamJsonl: () =>
      downloadExport("/api/export/reviewed?format=jsonl", "flakai_etiquetas_equipo.jsonl"),
    teamCsv: () =>
      downloadExport("/api/export/reviewed?format=csv", "flakai_etiquetas_equipo.csv"),
    adminJsonl: () =>
      downloadExport("/api/admin/export/reviewed?format=jsonl", "flakai_etiquetas_todos.jsonl"),
    adminCsv: () =>
      downloadExport("/api/admin/export/reviewed?format=csv", "flakai_etiquetas_todos.csv"),
  },
};

// ── Types ──────────────────────────────────────────────────────────────────

export interface Team {
  id: number;
  name: string;
  status: TeamStatus;
  requested_at: string | null;
  approved_at: string | null;
  trial_video_used: boolean;
  subscription_tier: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: {
    id: number;
    username: string;
    email: string;
    team_id: number;
    is_admin?: boolean;
  };
  team: Team;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
  team_name: string;
}

export interface Video {
  id: number;
  filename: string;
  original_name: string;
  file_size: number;
  duration_seconds?: number | null;
  status: "uploading" | "queued" | "processing" | "completed" | "error";
  upload_id: string;
  created_at: string;
  processed_at: string | null;
  event_count: number;
  pending_count: number;
  processing_started_at: string | null;
  processing_events_done: number;
  processing_events_total: number;
}

export interface EventClip {
  id: number;
  video_id: number;
  event_type: "goal" | "corner" | "throw_in" | "foul" | "goal_kick" | "shot_on_target";
  timestamp_seconds: number;
  confidence: number;
  clip_filename: string | null;
  review_status: "pending" | "approved" | "rejected";
  model_version?: string | null;
  created_at: string;
  batch_id: number | null;
  label_source: LabelSource;
}

export interface LabelingBatch {
  id: number;
  name: string;
  status: "pending" | "completed";
  created_at: string;
  completed_at: string | null;
  total: number;
  manual: number;
  pseudo: number;
  pending: number;
}

export interface LabelStats {
  total: number;
  manual: number;
  pseudo: number;
  pending: number;
  labeled_pct: number;
}

export interface PseudoLabelResult {
  pseudo_labeled: number;
  still_pending: number;
  threshold: number;
}

export interface MlAdminSummary {
  detector_backend: string;
  model_version: string;
  dataset_videos_dir: string;
  dataset_dir_exists: boolean;
  video_file_count: number;
  total_bytes: number;
  manifest_path: string;
  manifest_exists: boolean;
  clip_window_seconds: number;
  auto_approve_confidence: number;
}

export interface TrainingStatus {
  status: "idle" | "running" | "done" | "failed";
  started_at: number;
  finished_at: number;
  mode: string;
  samples: number;
  best_val_f1: number;
  model_version: number;
  error: string;
  current_epoch: number;
  total_epochs: number;
  last_val_f1: number;
  last_epoch_seconds: number;
  logs: string[];
}

export interface DatasetStats {
  approved_by_type: Record<string, number>;
  total_approved: number;
  total_rejected: number;
  total_pending: number;
  total_labeled: number;
  ready_classes: string[];
  can_train: boolean;
  recommendation: string;
}

export interface BillingPlan {
  tier: string;
  label: string;
  price_eur: number;
  video_limit: number | null;
  features: string[];
  cta: string | null;
  recommended?: boolean;
}

export interface BillingPlans {
  current_tier: string;
  plans: BillingPlan[];
}
