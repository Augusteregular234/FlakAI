"use client";
import { useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

const CHUNK_SIZE = 5 * 1024 * 1024;

interface FileEntry {
  file: File;
  status: "waiting" | "uploading" | "done" | "error";
  progress: number;
  error?: string;
}

export function VideoUpload() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [queue, setQueue] = useState<FileEntry[]>([]);
  const [running, setRunning] = useState(false);

  const uploadOne = async (file: File, onProgress: (p: number) => void): Promise<void> => {
    const { upload_id } = await api.videos.initUpload(file.name, file.size);
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);

    for (let i = 0; i < totalChunks; i++) {
      const start = i * CHUNK_SIZE;
      const chunk = file.slice(start, Math.min(start + CHUNK_SIZE, file.size));
      await api.videos.uploadChunk(upload_id, i, chunk);
      onProgress(Math.round(((i + 1) / totalChunks) * 90));
    }

    onProgress(95);
    await api.videos.completeUpload(upload_id);
    onProgress(100);
  };

  const runQueue = useCallback(async (entries: FileEntry[]) => {
    setRunning(true);
    for (let i = 0; i < entries.length; i++) {
      setQueue(q => q.map((e, idx) =>
        idx === i ? { ...e, status: "uploading" } : e
      ));
      try {
        await uploadOne(entries[i].file, (p) => {
          setQueue(q => q.map((e, idx) =>
            idx === i ? { ...e, progress: p } : e
          ));
        });
        setQueue(q => q.map((e, idx) =>
          idx === i ? { ...e, status: "done", progress: 100 } : e
        ));
      } catch (err) {
        setQueue(q => q.map((e, idx) =>
          idx === i ? { ...e, status: "error", error: err instanceof Error ? err.message : "Error" } : e
        ));
      }
    }
    setRunning(false);
    setTimeout(() => router.push("/dashboard"), 1500);
  }, [router]);

  const addFiles = useCallback((files: File[]) => {
    const entries: FileEntry[] = files.map(f => ({
      file: f, status: "waiting", progress: 0,
    }));
    setQueue(entries);
    runQueue(entries);
  }, [runQueue]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("video/") || /\.(mp4|mov|avi|mkv)$/i.test(f.name));
    if (files.length) addFiles(files);
  }, [addFiles]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length) addFiles(files);
  }, [addFiles]);

  const done  = queue.filter(e => e.status === "done").length;
  const total = queue.length;
  const current = queue.find(e => e.status === "uploading");
  const overallPct = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <div className="max-w-2xl mx-auto">
      <div
        className={`border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer transition-all
          ${dragging ? "border-emerald-400 bg-emerald-500/5" : "border-zinc-700 hover:border-zinc-500 bg-zinc-900"}
          ${running ? "pointer-events-none opacity-60" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !running && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept="video/*,.mp4,.mov,.avi,.mkv"
          multiple
          className="hidden"
          onChange={handleFileChange}
        />

        {running || total > 0 ? (
          <div className="space-y-4">
            <div className="text-4xl">⚡</div>
            <p className="text-white font-medium">
              {running
                ? `Subiendo ${done + 1} de ${total}${current ? ` — ${current.file.name}` : ""}`
                : `${done} vídeos subidos`}
            </p>
            <Progress value={running ? (current?.progress ?? 0) : 100} className="bg-zinc-800 h-2" />
            <div className="flex justify-between text-xs text-zinc-500">
              <span>Fichero actual: {current?.progress ?? 100}%</span>
              <span>Total: {overallPct}% ({done}/{total})</span>
            </div>

            {/* Lista de ficheros */}
            <div className="mt-3 space-y-1 max-h-48 overflow-y-auto text-left">
              {queue.map((e, i) => (
                <div key={i} className="flex items-center gap-2 text-xs px-2 py-1 rounded-lg bg-zinc-800/60">
                  <span className={
                    e.status === "done"     ? "text-emerald-400" :
                    e.status === "uploading"? "text-yellow-400 animate-pulse" :
                    e.status === "error"    ? "text-red-400" :
                    "text-zinc-600"
                  }>
                    {e.status === "done" ? "✓" : e.status === "uploading" ? "↑" : e.status === "error" ? "✗" : "·"}
                  </span>
                  <span className="flex-1 truncate text-zinc-300">{e.file.name}</span>
                  {e.status === "uploading" && <span className="text-zinc-500">{e.progress}%</span>}
                  {e.status === "error" && <span className="text-red-400 truncate max-w-[120px]">{e.error}</span>}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="text-5xl">🎬</div>
            <p className="text-white text-lg font-medium">Arrastra tus vídeos aquí</p>
            <p className="text-zinc-500 text-sm">
              Puedes seleccionar varios a la vez · MP4, MOV, AVI, MKV · Sin límite de tamaño
            </p>
            <Button className="mt-4 bg-emerald-500 hover:bg-emerald-400 text-black font-bold">
              Seleccionar vídeos
            </Button>
          </div>
        )}
      </div>

      {queue.some(e => e.status === "error") && (
        <div className="mt-4 p-4 bg-red-950/30 border border-red-900 rounded-xl text-red-400 text-sm">
          Algunos vídeos fallaron. Revisa la lista.
        </div>
      )}
    </div>
  );
}
