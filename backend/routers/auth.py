from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from starlette import status

from database import get_db
import models
import schemas
from auth import hash_password, verify_password, create_access_token, get_current_user
from rate_limit import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.Token)
@limiter.limit("10/minute")
def register(request: Request, data: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    existing = (
        db.query(models.Team).filter(models.Team.name == data.team_name).first()
    )
    if existing:
        if existing.status == models.TeamStatus.rejected:
            raise HTTPException(
                status_code=400,
                detail="Este nombre de equipo no está disponible. Si fue rechazado, elige otro nombre o contacta con soporte.",
            )
        team = existing
    else:
        team = models.Team(
            name=data.team_name,
            status=models.TeamStatus.pending_approval,
            requested_at=datetime.utcnow(),
            subscription_tier="free_trial",
            trial_video_used=False,
        )
        db.add(team)
        db.flush()

    user = models.User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        team_id=team.id,
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(team)

    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(
        access_token=token,
        token_type="bearer",
        user=schemas.UserOut.model_validate(user),
        team=schemas.TeamOut.model_validate(team),
    )


@router.post("/login", response_model=schemas.Token)
@limiter.limit("30/minute")
def login(request: Request, data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == data.username).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    team = db.query(models.Team).filter(models.Team.id == user.team_id).first()
    if (
        team
        and team.status == models.TeamStatus.rejected
        and not user.is_admin
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu equipo no fue aprobado. Contacta con soporte.",
        )

    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(
        access_token=token,
        token_type="bearer",
        user=schemas.UserOut.model_validate(user),
        team=schemas.TeamOut.model_validate(team),
    )


@router.get("/me", response_model=schemas.MeResponse)
def me(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    team = (
        db.query(models.Team).filter(models.Team.id == current_user.team_id).first()
    )
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return schemas.MeResponse(
        user=schemas.UserOut.model_validate(current_user),
        team=schemas.TeamOut.model_validate(team),
    )
