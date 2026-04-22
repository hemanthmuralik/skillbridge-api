from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from ..auth import get_monitoring_user
from ..database import get_db
from ..models import Attendance, Batch, Session, User
from ..schemas import MonitoringAttendanceOut, MonitoringAttendanceRecord

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/attendance", response_model=MonitoringAttendanceOut)
def monitoring_attendance(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_monitoring_user),
    limit: int = Query(default=50, ge=1, le=500, description="Records per page"),
    offset: int = Query(default=0, ge=0, description="Number of records to skip"),
):
    """
    Read-only view of all attendance records across the programme.
    Paginated: use `limit` and `offset` query params (default: 50 per page).
    Uses a single JOIN query — no N+1 round-trips.
    """
    # Single JOIN query across all relevant tables
    stmt = (
        select(
            Attendance.id.label("attendance_id"),
            Attendance.session_id,
            Attendance.student_id,
            Attendance.status,
            Attendance.marked_at,
            Session.title.label("session_title"),
            Session.batch_id,
            Batch.name.label("batch_name"),
            User.name.label("student_name"),
        )
        .join(Session, Session.id == Attendance.session_id)
        .join(Batch, Batch.id == Session.batch_id)
        .join(User, User.id == Attendance.student_id)
        .order_by(Attendance.marked_at.desc())
    )

    total = db.execute(select(Attendance.id).join(
        Session, Session.id == Attendance.session_id
    )).fetchall().__len__()  # count without loading data

    rows = db.execute(stmt.limit(limit).offset(offset)).fetchall()

    records = [
        MonitoringAttendanceRecord(
            attendance_id=row.attendance_id,
            session_id=row.session_id,
            session_title=row.session_title,
            batch_id=row.batch_id,
            batch_name=row.batch_name,
            student_id=row.student_id,
            student_name=row.student_name,
            status=row.status,
            marked_at=row.marked_at,
        )
        for row in rows
    ]

    return MonitoringAttendanceOut(total=total, records=records)


# Explicitly reject all mutating methods with 405
@router.post("/attendance", include_in_schema=False)
@router.put("/attendance", include_in_schema=False)
@router.patch("/attendance", include_in_schema=False)
@router.delete("/attendance", include_in_schema=False)
def monitoring_attendance_readonly():
    raise HTTPException(
        status_code=405,
        detail="Method Not Allowed. The monitoring attendance endpoint is read-only.",
    )
