from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=schemas.Token)
def register(data: schemas.UserCreate, db: Session = Depends(get_db)):
    if db.query(models.User).filter(models.User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(models.User).filter(models.User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    team = db.query(models.Team).filter(models.Team.name == data.team_name).first()
    if not team:
        team = models.Team(name=data.team_name)
        db.add(team)
        db.flush()

    user = models.User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        team_id=team.id,
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
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == data.username).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    team = db.query(models.Team).filter(models.Team.id == user.team_id).first()
    token = create_access_token({"sub": str(user.id)})
    return schemas.Token(
        access_token=token,
        token_type="bearer",
        user=schemas.UserOut.model_validate(user),
        team=schemas.TeamOut.model_validate(team),
    )


@router.get("/me", response_model=schemas.UserOut)
def me(current_user: models.User = Depends(__import__("auth").get_current_user)):
    return current_user
