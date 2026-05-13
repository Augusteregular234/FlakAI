from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
from config import get_settings
import models

SECRET_KEY = get_settings().jwt_secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_jwt(token: str, db: Session) -> models.User:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise exc
    except JWTError:
        raise exc
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise exc
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> models.User:
    return _decode_jwt(token, db)


def get_user_any_token(
    header_token: Optional[str] = Depends(oauth2_scheme_optional),
    query_token: Optional[str] = Query(None, alias="token"),
    db: Session = Depends(get_db),
) -> models.User:
    """Acepta JWT desde Authorization header O query param ?token= (necesario para <video src>)."""
    tok = header_token or query_token
    if not tok:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _decode_jwt(tok, db)


def get_current_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403, detail="Se requieren permisos de administrador"
        )
    return current_user


def require_active_team(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.User:
    """Bloquea rutas de la app si el equipo no está activo (salvo administradores)."""
    if current_user.is_admin:
        return current_user
    team = (
        db.query(models.Team).filter(models.Team.id == current_user.team_id).first()
    )
    if team is None:
        raise HTTPException(status_code=403, detail="Equipo no encontrado")
    if team.status == models.TeamStatus.pending_approval:
        raise HTTPException(
            status_code=403,
            detail="Tu equipo está pendiente de aprobación por el administrador.",
        )
    if team.status == models.TeamStatus.rejected:
        raise HTTPException(
            status_code=403,
            detail="Tu equipo no fue aprobado. Contacta con soporte.",
        )
    return current_user
