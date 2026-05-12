"use client";
import { useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

const CHUNK_SIZE = 5 * 1024 * 1024; // 5MB per chunk

export function VideoUpload() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const upload = useCallback(async (file: File) => {
    setUploading(true);
    setError("");
    setProgress(0);
    setStatus("Iniciando...");

    try {
      const { upload_id } = await api.videos.initUpload(file.name, file.size);

      const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
      setStatus(`Subiendo (0/${totalChunks} fragmentos)...`);

      for (let i = 0; i < totalChunks; i++) {
        const start = i * CHUNK_SIZE;
        const end = Math.min(start + CHUNK_SIZE, file.size);
        const chunk = file.slice(start, end);
        await api.videos.uploadChunk(upload_id, i, chunk);
        const pct = Math.round(((i + 1) / totalChunks) * 90);
        setProgress(pct);
        setStatus(`Subiendo (${i + 1}/${totalChunks} fragmentos)...`);
      }

      setStatus("Ensamblando vídeo...");
      setProgress(95);
      await api.videos.completeUpload(upload_id);
      setProgress(100);
      setStatus("¡Procesamiento iniciado! Redirigiendo...");

      setTimeout(() => router.push("/dashboard"), 1500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Error al subir");
      setUploading(false);
    }
  }, [router]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) upload(file);
  }, [upload]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) upload(file);
  }, [upload]);

  return (
    <div className="max-w-2xl mx-auto">
      <div
        className={`
          border-2 border-dashed rounded-2xl p-16 text-center cursor-pointer transition-all
          ${dragging ? "border-emerald-400 bg-emerald-500/5" : "border-zinc-700 hover:border-zinc-500 bg-zinc-900"}
          ${uploading ? "pointer-events-none opacity-60" : ""}
        `}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !uploading && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept="video/*,.mp4,.mov,.avi,.mkv"
          className="hidden"
          onChange={handleFileChange}
        />

        {uploading ? (
          <div className="space-y-4">
            <div className="text-4xl">⚡</div>
            <p className="text-white font-medium">{status}</p>
            <Progress value={progress} className="bg-zinc-800 h-2" />
            <p className="text-zinc-500 text-sm">{progress}%</p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="text-5xl">🎬</div>
            <p className="text-white text-lg font-medium">
              Arrastra tu vídeo aquí
            </p>
            <p className="text-zinc-500 text-sm">
              o haz clic para seleccionar · MP4, MOV, AVI, MKV · Sin límite de tamaño
            </p>
            <Button className="mt-4 bg-emerald-500 hover:bg-emerald-400 text-black font-bold">
              Seleccionar vídeo
            </Button>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 p-4 bg-red-950/30 border border-red-900 rounded-xl text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="mt-6 grid grid-cols-3 gap-4 text-center">
        {[
          ["Subida por fragmentos", "Vídeos de hasta 100GB"],
          ["Procesado en background", "Sin espera en pantalla"],
          ["IA Simulada", "3-5 eventos por partido"],
        ].map(([title, desc]) => (
          <div key={title} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
            <p className="text-white text-xs font-medium">{title}</p>
            <p className="text-zinc-600 text-xs mt-1">{desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
