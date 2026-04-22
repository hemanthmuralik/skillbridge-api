import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..database import get_db
from ..models import Batch, BatchInvite, BatchStudent, BatchTrainer, Role, User
from ..schemas import BatchCreate, BatchOut, InviteCreate, InviteOut, JoinBatchRequest

router = APIRouter(prefix="/batches", tags=["batches"])


@router.post("", response_model=BatchOut, status_code=201)
def create_batch(
    body: BatchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.trainer, Role.institution)),
):
    # Validate institution_id
    inst = db.query(User).filter(
        User.id == body.institution_id, User.role == Role.institution
    ).first()
    if not inst:
        raise HTTPException(status_code=404, detail="Institution not found")

    batch = Batch(name=body.name, institution_id=body.institution_id)
    db.add(batch)
    db.flush()

    # Automatically assign the creating trainer to the batch
    if current_user.role == Role.trainer:
        bt = BatchTrainer(batch_id=batch.id, trainer_id=current_user.id)
        db.add(bt)

    db.commit()
    db.refresh(batch)
    return batch


@router.post("/join", status_code=200)
def join_batch(
    body: JoinBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.student)),
):
    invite = db.query(BatchInvite).filter(BatchInvite.token == body.token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite token not found")
    if invite.used:
        raise HTTPException(status_code=422, detail="Invite token has already been used")
    if invite.expires_at < datetime.utcnow():
        raise HTTPException(status_code=422, detail="Invite token has expired")

    # Idempotent: ignore if already enrolled
    existing = db.query(BatchStudent).filter(
        BatchStudent.batch_id == invite.batch_id,
        BatchStudent.student_id == current_user.id,
    ).first()
    if not existing:
        bs = BatchStudent(batch_id=invite.batch_id, student_id=current_user.id)
        db.add(bs)

    invite.used = True
    db.commit()
    return {"message": "Successfully joined batch", "batch_id": invite.batch_id}


@router.post("/{batch_id}/invite", response_model=InviteOut, status_code=201)
def create_invite(
    batch_id: str,
    body: InviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.trainer)),
):
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Trainer must be assigned to this batch
    assigned = db.query(BatchTrainer).filter(
        BatchTrainer.batch_id == batch_id,
        BatchTrainer.trainer_id == current_user.id,
    ).first()
    if not assigned:
        raise HTTPException(
            status_code=403, detail="You are not assigned to this batch"
        )

    invite = BatchInvite(
        batch_id=batch_id,
        token=secrets.token_urlsafe(32),
        created_by=current_user.id,
        expires_at=datetime.utcnow() + timedelta(hours=body.expires_in_hours),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


@router.get("/{batch_id}/summary")
def batch_summary(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.institution, Role.programme_manager)),
):
    from ..models import Attendance, Session as Sess
    from ..schemas import BatchSummary, SessionSummary, StudentSummary

    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Institution can only view their own batches
    if current_user.role == Role.institution and batch.institution_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied to this batch")

    sessions = db.query(Sess).filter(Sess.batch_id == batch_id).all()
    students = db.query(BatchStudent).filter(BatchStudent.batch_id == batch_id).all()

    session_summaries = []
    for sess in sessions:
        records = db.query(Attendance).filter(Attendance.session_id == sess.id).all()
        session_summaries.append(
            SessionSummary(
                session_id=sess.id,
                session_title=sess.title,
                date=sess.date,
                present_count=sum(1 for r in records if r.status.value == "present"),
                absent_count=sum(1 for r in records if r.status.value == "absent"),
                late_count=sum(1 for r in records if r.status.value == "late"),
            )
        )

    student_summaries = []
    for bs in students:
        student = db.query(User).filter(User.id == bs.student_id).first()
        session_ids = [s.id for s in sessions]
        records = (
            db.query(Attendance)
            .filter(
                Attendance.student_id == bs.student_id,
                Attendance.session_id.in_(session_ids),
            )
            .all()
        )
        student_summaries.append(
            StudentSummary(
                student_id=bs.student_id,
                student_name=student.name if student else "Unknown",
                present=sum(1 for r in records if r.status.value == "present"),
                absent=sum(1 for r in records if r.status.value == "absent"),
                late=sum(1 for r in records if r.status.value == "late"),
                total=len(records),
            )
        )

    return BatchSummary(
        batch_id=batch.id,
        batch_name=batch.name,
        total_sessions=len(sessions),
        total_students=len(students),
        students=student_summaries,
        sessions=session_summaries,
    )
