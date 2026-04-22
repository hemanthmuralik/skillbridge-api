from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, case
from sqlalchemy.orm import Session as DBSession

from ..auth import require_roles
from ..database import get_db
from ..models import Attendance, AttendanceStatus, Batch, BatchStudent, Role, Session, User
from ..schemas import InstitutionBatchSummary, InstitutionSummary

router = APIRouter(prefix="/institutions", tags=["institutions"])


@router.get("/{institution_id}/summary", response_model=InstitutionSummary)
def institution_summary(
    institution_id: str,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.programme_manager)),
):
    institution = db.query(User).filter(
        User.id == institution_id, User.role == Role.institution
    ).first()
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")

    batches = db.query(Batch).filter(Batch.institution_id == institution_id).all()
    if not batches:
        return InstitutionSummary(
            institution_id=institution.id,
            institution_name=institution.name,
            batches=[],
        )

    batch_ids = [b.id for b in batches]

    # One query: session counts per batch
    session_counts = (
        db.query(Session.batch_id, func.count(Session.id).label("cnt"))
        .filter(Session.batch_id.in_(batch_ids))
        .group_by(Session.batch_id)
        .all()
    )
    sessions_by_batch = {row.batch_id: row.cnt for row in session_counts}

    # One query: student counts per batch
    student_counts = (
        db.query(BatchStudent.batch_id, func.count(BatchStudent.student_id).label("cnt"))
        .filter(BatchStudent.batch_id.in_(batch_ids))
        .group_by(BatchStudent.batch_id)
        .all()
    )
    students_by_batch = {row.batch_id: row.cnt for row in student_counts}

    # One query: present attendance counts per batch (via session join)
    attendance_stats = (
        db.query(
            Session.batch_id,
            func.count(
                case((Attendance.status == AttendanceStatus.present, 1))
            ).label("present_count"),
        )
        .join(Attendance, Attendance.session_id == Session.id)
        .filter(Session.batch_id.in_(batch_ids))
        .group_by(Session.batch_id)
        .all()
    )
    present_by_batch = {row.batch_id: row.present_count for row in attendance_stats}

    batch_summaries = []
    for batch in batches:
        n_sessions = sessions_by_batch.get(batch.id, 0)
        n_students = students_by_batch.get(batch.id, 0)
        possible = n_sessions * n_students
        present = present_by_batch.get(batch.id, 0)
        rate = round(present / possible * 100, 1) if possible > 0 else 0.0

        batch_summaries.append(
            InstitutionBatchSummary(
                batch_id=batch.id,
                batch_name=batch.name,
                total_sessions=n_sessions,
                total_students=n_students,
                overall_attendance_rate=rate,
            )
        )

    return InstitutionSummary(
        institution_id=institution.id,
        institution_name=institution.name,
        batches=batch_summaries,
    )
