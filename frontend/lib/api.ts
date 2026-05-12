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
      `No hay conexión con la API (${BASE_URL}). Arranca el backend (puerto 8000) o revisa NEXT_PUBLIC_API_URL en frontend/.env.local.`
    );
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    const raw = (err as { detail?: unknown }).detail;
    throw new Error(formatApiError(raw, res.statusText || "Request failed"));
  }
  return res.json();
}

/** Descarga binaria (export CSV/JSONL) con el mismo auth que el resto de la API. */
export async function downloadExport(path: string, filename: string): Promise<void> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, { headers });
  } catch {
    throw new Error(
      `No hay conexión con la API (${BASE_URL}). Arranca el backend en el puerto 8000.`
    );
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
  },
  clips: {
    pending: () => request<EventClip[]>("/api/clips/pending"),
    forVideo: (videoId: number) => request<EventClip[]>(`/api/clips/video/${videoId}`),
    review: (clipId: number, status: "approved" | "rejected") =>
      request<EventClip>(`/api/clips/${clipId}/review`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      }),
    streamUrl: (clipId: number) => `${BASE_URL}/api/clips/${clipId}/stream`,
  },
  /** Etiquetas humanas = clips con decisión Aceptar/Rechazar (no pendientes). */
  exportLabels: {
    teamJsonl: () =>
      downloadExport("/api/export/reviewed?format=jsonl", "flakai_etiquetas_equipo.jsonl"),
    teamCsv: () =>
      downloadExport("/api/export/reviewed?format=csv", "flakai_etiquetas_equipo.csv"),
    adminJsonl: () =>
      downloadExport(
        "/api/admin/export/reviewed?format=jsonl",
        "flakai_etiquetas_todos_equipos.jsonl"
      ),
    adminCsv: () =>
      downloadExport(
        "/api/admin/export/reviewed?format=csv",
        "flakai_etiquetas_todos_equipos.csv"
      ),
  },
};

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
  status: "uploading" | "processing" | "completed" | "error";
  upload_id: string;
  created_at: string;
  processed_at: string | null;
  event_count: number;
  pending_count: number;
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

export interface EventClip {
  id: number;
  video_id: number;
  event_type: "goal" | "corner" | "throw_in" | "foul";
  timestamp_seconds: number;
  confidence: number;
  clip_filename: string | null;
  review_status: "pending" | "approved" | "rejected";
  model_version?: string | null;
  created_at: string;
}
