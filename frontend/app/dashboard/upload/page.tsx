import { VideoUpload } from "@/components/video-upload";

export default function UploadPage() {
  return (
    <div className="p-8">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-white">Subir Vídeo</h2>
        <p className="text-zinc-500 text-sm mt-1">
          La IA detectará Goles, Córners, Saques y Faltas automáticamente
        </p>
      </div>
      <VideoUpload />
    </div>
  );
}
