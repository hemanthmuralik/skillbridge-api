from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from ..auth import require_roles
from ..database import get_db
from ..models import Attendance, Batch, BatchStudent, BatchTrainer, Role, Session, User
from ..schemas import (
    AttendanceRecord,
    SessionAttendanceOut,
    SessionCreate,
    SessionOut,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=201)
def create_session(
    body: SessionCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.trainer)),
):
    batch = db.query(Batch).filter(Batch.id == body.batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Trainer must be assigned to this batch
    assigned = db.query(BatchTrainer).filter(
        BatchTrainer.batch_id == body.batch_id,
        BatchTrainer.trainer_id == current_user.id,
    ).first()
    if not assigned:
        raise HTTPException(
            status_code=403, detail="You are not assigned to this batch"
        )

    sess = Session(
        batch_id=body.batch_id,
        trainer_id=current_user.id,
        title=body.title,
        date=body.date,
        start_time=body.start_time,
        end_time=body.end_time,
    )
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


@router.get("/{session_id}/attendance", response_model=SessionAttendanceOut)
def get_session_attendance(
    session_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.trainer)),
):
    sess = db.query(Session).filter(Session.id == session_id).first()
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    # Trainer must own this session or be assigned to the batch
    is_owner = sess.trainer_id == current_user.id
    is_assigned = db.query(BatchTrainer).filter(
        BatchTrainer.batch_id == sess.batch_id,
        BatchTrainer.trainer_id == current_user.id,
    ).first()
    if not is_owner and not is_assigned:
        raise HTTPException(status_code=403, detail="Access denied to this session")

    records = db.query(Attendance).filter(Attendance.session_id == session_id).all()
    attendance_out = []
    for rec in records:
        student = db.query(User).filter(User.id == rec.student_id).first()
        attendance_out.append(
            AttendanceRecord(
                student_id=rec.student_id,
                student_name=student.name if student else "Unknown",
                student_email=student.email if student else "",
                status=rec.status,
                marked_at=rec.marked_at,
            )
        )

    return SessionAttendanceOut(
        session_id=sess.id,
        session_title=sess.title,
        records=attendance_out,
    )
