from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
import enum
from database import Base


class VideoStatus(str, enum.Enum):
    uploading = "uploading"
    processing = "processing"
    completed = "completed"
    error = "error"


class EventType(str, enum.Enum):
    goal = "goal"
    corner = "corner"
    throw_in = "throw_in"
    foul = "foul"
    goal_kick = "goal_kick"
    shot_on_target = "shot_on_target"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class TeamStatus(str, enum.Enum):
    pending_approval = "pending_approval"
    active = "active"
    rejected = "rejected"


class Team(Base):
    __tablename__ = "teams"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    status = Column(Enum(TeamStatus), default=TeamStatus.pending_approval, nullable=False)
    requested_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    trial_video_used = Column(Boolean, default=False, nullable=False)
    subscription_tier = Column(String(32), default="free_trial", nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    users = relationship("User", back_populates="team", foreign_keys="[User.team_id]")
    videos = relationship("VideoMatch", back_populates="team")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    team = relationship("Team", back_populates="users", foreign_keys="[User.team_id]")
    videos = relationship("VideoMatch", back_populates="uploader")


class VideoMatch(Base):
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String)
    original_name = Column(String)
    file_path = Column(String)
    file_size = Column(Integer, default=0)
    duration_seconds = Column(Float, nullable=True)
    status = Column(Enum(VideoStatus), default=VideoStatus.uploading)
    upload_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    processing_started_at = Column(DateTime, nullable=True)
    processing_events_done = Column(Integer, default=0, nullable=False)
    processing_events_total = Column(Integer, default=0, nullable=False)
    team = relationship("Team", back_populates="videos")
    uploader = relationship("User", back_populates="videos")
    events = relationship("EventClip", back_populates="video")


class EventClip(Base):
    __tablename__ = "event_clips"
    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"))
    team_id = Column(Integer, ForeignKey("teams.id"))
    event_type = Column(Enum(EventType))
    timestamp_seconds = Column(Float)
    confidence = Column(Float)
    clip_path = Column(String, nullable=True)
    clip_filename = Column(String, nullable=True)
    review_status = Column(Enum(ReviewStatus), default=ReviewStatus.pending)
    model_version = Column(String(64), nullable=True)
    detector_metadata = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    video = relationship("VideoMatch", back_populates="events")
