from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import models
import schemas
from auth import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/teams/pending", response_model=list[schemas.TeamOut])
def list_pending_teams(
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_admin),
):
    q = db.query(models.Team).filter(
        models.Team.status == models.TeamStatus.pending_approval
    )
    return q.order_by(models.Team.id.desc()).all()


@router.post("/teams/{team_id}/approve", response_model=schemas.TeamOut)
def approve_team(
    team_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if team.status != models.TeamStatus.pending_approval:
        raise HTTPException(status_code=400, detail="El equipo no está pendiente de aprobación")

    team.status = models.TeamStatus.active
    team.approved_at = datetime.utcnow()
    team.approved_by_user_id = admin.id
    db.commit()
    db.refresh(team)
    return team


@router.post("/teams/{team_id}/reject", response_model=schemas.TeamOut)
def reject_team(
    team_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(get_current_admin),
):
    team = db.query(models.Team).filter(models.Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    if team.status != models.TeamStatus.pending_approval:
        raise HTTPException(status_code=400, detail="El equipo no está pendiente de aprobación")

    team.status = models.TeamStatus.rejected
    team.approved_at = datetime.utcnow()
    team.approved_by_user_id = admin.id
    base = team.name.split(" [rechazado-", 1)[0]
    team.name = f"{base} [rechazado-{team.id}]"

    db.commit()
    db.refresh(team)
    return team
