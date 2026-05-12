# FlakAI v2 — Análisis Táctico de Fútbol

Plataforma SaaS MVP para análisis automático de partidos de fútbol con IA.

## Stack
- **Frontend**: Next.js 15 · Tailwind CSS · Shadcn/UI · Zustand
- **Backend**: Python FastAPI · SQLAlchemy · SQLite
- **IA**: Mock engine (simula detección de Goles, Córners, Saques, Faltas)
- **Video**: FFmpeg (clips de 30s por evento)

## Inicio rápido

```powershell
# Windows — lanza backend + frontend
.\start.ps1
```

Manual:
```bash
# Backend
cd backend && venv\Scripts\python -m uvicorn main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

URLs:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Funcionalidades MVP
- Multi-tenant (equipos) con JWT
- Subida de vídeos por fragmentos (chunked upload, sin límite de tamaño)
- Pipeline IA mock: 3-5 eventos por vídeo, 50-99% confianza
- Auto-aprobación si confianza ≥ 80%, revisión manual si < 80%
- Interface Human-in-the-Loop: Accept/Reject con teclado (A/R/←/→)
- Dashboard de resultados con filtros por tipo de evento
