from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from ..auth import require_roles
from ..database import get_db
from ..models import Attendance, BatchStudent, Role, Session, User
from ..schemas import AttendanceMark, AttendanceOut

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/mark", response_model=AttendanceOut, status_code=201)
def mark_attendance(
    body: AttendanceMark,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.student)),
):
    # Verify session exists
    sess = db.query(Session).filter(Session.id == body.session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify student is enrolled in the session's batch
    enrolled = db.query(BatchStudent).filter(
        BatchStudent.batch_id == sess.batch_id,
        BatchStudent.student_id == current_user.id,
    ).first()
    if not enrolled:
        raise HTTPException(
            status_code=403,
            detail="You are not enrolled in the batch for this session",
        )

    # Prevent duplicate attendance records
    existing = db.query(Attendance).filter(
        Attendance.session_id == body.session_id,
        Attendance.student_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=422,
            detail="Attendance already marked for this session",
        )

    record = Attendance(
        session_id=body.session_id,
        student_id=current_user.id,
        status=body.status,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
