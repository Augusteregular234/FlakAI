from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from models import VideoStatus, EventType, ReviewStatus


class TeamCreate(BaseModel):
    name: str


class TeamOut(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    team_name: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    team_id: int
    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserOut
    team: TeamOut


class LoginRequest(BaseModel):
    username: str
    password: str


class VideoOut(BaseModel):
    id: int
    filename: str
    original_name: str
    file_size: int
    status: VideoStatus
    upload_id: str
    created_at: datetime
    processed_at: Optional[datetime] = None
    event_count: Optional[int] = 0
    pending_count: Optional[int] = 0
    model_config = {"from_attributes": True}


class EventClipOut(BaseModel):
    id: int
    video_id: int
    event_type: EventType
    timestamp_seconds: float
    confidence: float
    clip_filename: Optional[str] = None
    review_status: ReviewStatus
    created_at: datetime
    model_config = {"from_attributes": True}


class ReviewUpdate(BaseModel):
    status: ReviewStatus
