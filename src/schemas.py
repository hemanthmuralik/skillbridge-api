from datetime import date, time, datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator
from .models import Role, AttendanceStatus


# ── Auth ─────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Role
    institution_id: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MonitoringTokenRequest(BaseModel):
    key: str


# ── User ─────────────────────────────────────────────────────────────────────

class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: Role
    institution_id: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Batches ───────────────────────────────────────────────────────────────────

class BatchCreate(BaseModel):
    name: str
    institution_id: str


class BatchOut(BaseModel):
    id: str
    name: str
    institution_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class InviteCreate(BaseModel):
    expires_in_hours: int = 48


class InviteOut(BaseModel):
    id: str
    batch_id: str
    token: str
    expires_at: datetime
    used: bool

    model_config = {"from_attributes": True}


class JoinBatchRequest(BaseModel):
    token: str


# ── Sessions ─────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    title: str
    date: date
    start_time: time
    end_time: time
    batch_id: str

    @field_validator("end_time")
    @classmethod
    def end_after_start(cls, v, info):
        if "start_time" in info.data and v <= info.data["start_time"]:
            raise ValueError("end_time must be after start_time")
        return v


class SessionOut(BaseModel):
    id: str
    batch_id: str
    trainer_id: str
    title: str
    date: date
    start_time: time
    end_time: time
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Attendance ────────────────────────────────────────────────────────────────

class AttendanceMark(BaseModel):
    session_id: str
    status: AttendanceStatus = AttendanceStatus.present


class AttendanceOut(BaseModel):
    id: str
    session_id: str
    student_id: str
    status: AttendanceStatus
    marked_at: datetime

    model_config = {"from_attributes": True}


class AttendanceRecord(BaseModel):
    student_id: str
    student_name: str
    student_email: str
    status: AttendanceStatus
    marked_at: datetime


class SessionAttendanceOut(BaseModel):
    session_id: str
    session_title: str
    records: List[AttendanceRecord]


# ── Summary schemas ───────────────────────────────────────────────────────────

class StudentSummary(BaseModel):
    student_id: str
    student_name: str
    present: int
    absent: int
    late: int
    total: int


class SessionSummary(BaseModel):
    session_id: str
    session_title: str
    date: date
    present_count: int
    absent_count: int
    late_count: int


class BatchSummary(BaseModel):
    batch_id: str
    batch_name: str
    total_sessions: int
    total_students: int
    students: List[StudentSummary]
    sessions: List[SessionSummary]


class InstitutionBatchSummary(BaseModel):
    batch_id: str
    batch_name: str
    total_sessions: int
    total_students: int
    overall_attendance_rate: float


class InstitutionSummary(BaseModel):
    institution_id: str
    institution_name: str
    batches: List[InstitutionBatchSummary]


class ProgrammeSummary(BaseModel):
    total_institutions: int
    total_batches: int
    total_sessions: int
    total_students: int
    institutions: List[InstitutionSummary]


class MonitoringAttendanceRecord(BaseModel):
    attendance_id: str
    session_id: str
    session_title: str
    batch_id: str
    batch_name: str
    student_id: str
    student_name: str
    status: AttendanceStatus
    marked_at: datetime


class MonitoringAttendanceOut(BaseModel):
    total: int
    records: List[MonitoringAttendanceRecord]
