const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("flakai_token");
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

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

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
};

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: { id: number; username: string; email: string; team_id: number };
  team: { id: number; name: string };
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
  status: "uploading" | "processing" | "completed" | "error";
  upload_id: string;
  created_at: string;
  processed_at: string | null;
  event_count: number;
  pending_count: number;
}

export interface EventClip {
  id: number;
  video_id: number;
  event_type: "goal" | "corner" | "throw_in" | "foul";
  timestamp_seconds: number;
  confidence: number;
  clip_filename: string | null;
  review_status: "pending" | "approved" | "rejected";
  created_at: string;
}
