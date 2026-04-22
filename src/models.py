import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Date, Time, ForeignKey, Enum as SAEnum, Index
from .database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    student = "student"
    trainer = "trainer"
    institution = "institution"
    programme_manager = "programme_manager"
    monitoring_officer = "monitoring_officer"


class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    late = "late"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    # index=True → fast login lookups; unique=True enforced at DB level
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    role = Column(SAEnum(Role), nullable=False)
    institution_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Batch(Base):
    __tablename__ = "batches"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    institution_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BatchTrainer(Base):
    __tablename__ = "batch_trainers"

    batch_id = Column(String, ForeignKey("batches.id"), primary_key=True)
    trainer_id = Column(String, ForeignKey("users.id"), primary_key=True)


class BatchStudent(Base):
    __tablename__ = "batch_students"

    batch_id = Column(String, ForeignKey("batches.id"), primary_key=True)
    student_id = Column(String, ForeignKey("users.id"), primary_key=True)


class BatchInvite(Base):
    __tablename__ = "batch_invites"

    id = Column(String, primary_key=True, default=gen_uuid)
    batch_id = Column(String, ForeignKey("batches.id"), nullable=False, index=True)
    # index=True → invite lookup by token is the hot path (POST /batches/join)
    token = Column(String, unique=True, nullable=False, index=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=gen_uuid)
    # index=True → attendance JOIN and batch summary GROUP BY both filter on batch_id
    batch_id = Column(String, ForeignKey("batches.id"), nullable=False, index=True)
    trainer_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(String, primary_key=True, default=gen_uuid)
    # Composite index → the most common query pattern: "all records for a session"
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    student_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(SAEnum(AttendanceStatus), nullable=False, default=AttendanceStatus.present)
    marked_at = Column(DateTime, default=datetime.utcnow)

    # Composite index speeds up duplicate-check on mark attendance
    # and GROUP BY attendance queries in summary endpoints
    __table_args__ = (
        Index("ix_attendance_session_student", "session_id", "student_id"),
    )
