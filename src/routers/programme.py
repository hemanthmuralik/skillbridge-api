from fastapi import APIRouter, Depends
from sqlalchemy import func, case
from sqlalchemy.orm import Session as DBSession

from ..auth import require_roles
from ..database import get_db
from ..models import Attendance, AttendanceStatus, Batch, BatchStudent, Role, Session, User
from ..schemas import InstitutionBatchSummary, InstitutionSummary, ProgrammeSummary

router = APIRouter(prefix="/programme", tags=["programme"])


@router.get("/summary", response_model=ProgrammeSummary)
def programme_summary(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.programme_manager)),
):
    # ── Single query: attendance counts grouped by batch ─────────────────────
    # This replaces the previous N+1 nested loop with one GROUP BY round-trip.
    attendance_stats = (
        db.query(
            Session.batch_id,
            func.count(
                case((Attendance.status == AttendanceStatus.present, 1))
            ).label("present_count"),
            func.count(Attendance.id).label("total_marked"),
        )
        .join(Attendance, Attendance.session_id == Session.id)
        .group_by(Session.batch_id)
        .all()
    )
    stats_by_batch = {
        row.batch_id: {"present": row.present_count, "total": row.total_marked}
        for row in attendance_stats
    }

    # ── Single query: session counts grouped by batch ─────────────────────────
    session_counts = (
        db.query(Session.batch_id, func.count(Session.id).label("cnt"))
        .group_by(Session.batch_id)
        .all()
    )
    sessions_by_batch = {row.batch_id: row.cnt for row in session_counts}

    # ── Single query: student counts grouped by batch ─────────────────────────
    student_counts = (
        db.query(BatchStudent.batch_id, func.count(BatchStudent.student_id).label("cnt"))
        .group_by(BatchStudent.batch_id)
        .all()
    )
    students_by_batch = {row.batch_id: row.cnt for row in student_counts}

    # ── Fetch all batches and institutions in two flat queries ─────────────────
    all_batches = db.query(Batch).all()
    institutions = db.query(User).filter(User.role == Role.institution).all()

    batches_by_inst: dict[str, list] = {inst.id: [] for inst in institutions}
    for batch in all_batches:
        if batch.institution_id in batches_by_inst:
            batches_by_inst[batch.institution_id].append(batch)

    # ── Assemble response from in-memory dicts (zero extra DB hits) ───────────
    inst_summaries = []
    for inst in institutions:
        batch_summaries = []
        for batch in batches_by_inst.get(inst.id, []):
            n_sessions = sessions_by_batch.get(batch.id, 0)
            n_students = students_by_batch.get(batch.id, 0)
            stats = stats_by_batch.get(batch.id, {"present": 0, "total": 0})
            possible = n_sessions * n_students
            rate = round(stats["present"] / possible * 100, 1) if possible > 0 else 0.0

            batch_summaries.append(
                InstitutionBatchSummary(
                    batch_id=batch.id,
                    batch_name=batch.name,
                    total_sessions=n_sessions,
                    total_students=n_students,
                    overall_attendance_rate=rate,
                )
            )
        inst_summaries.append(
            InstitutionSummary(
                institution_id=inst.id,
                institution_name=inst.name,
                batches=batch_summaries,
            )
        )

    unique_students = sum(students_by_batch.values())
    return ProgrammeSummary(
        total_institutions=len(institutions),
        total_batches=len(all_batches),
        total_sessions=sum(sessions_by_batch.values()),
        total_students=unique_students,
        institutions=inst_summaries,
    )
