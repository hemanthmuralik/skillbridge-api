"""
Seed script: creates 2 institutions, 4 trainers, 15 students, 3 batches,
8 sessions and attendance records so summary endpoints return real data.

Run with:  python -m src.seed
"""
import sys
import os
from datetime import date, time, datetime, timedelta

# Allow running as `python -m src.seed` from /submission
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.database import Base, SessionLocal, engine
from src.models import (
    Attendance,
    AttendanceStatus,
    Batch,
    BatchStudent,
    BatchTrainer,
    Role,
    Session,
    User,
)
from src.auth import hash_password

DEFAULT_PASSWORD = "Password123!"


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ── Institutions ──────────────────────────────────────────────────────
        inst1 = User(
            name="Sunrise Polytechnic",
            email="sunrise@inst.sb",
            hashed_password=hash_password(DEFAULT_PASSWORD),
            role=Role.institution,
        )
        inst2 = User(
            name="Greenfield ITI",
            email="greenfield@inst.sb",
            hashed_password=hash_password(DEFAULT_PASSWORD),
            role=Role.institution,
        )
        db.add_all([inst1, inst2])
        db.flush()

        # ── Programme Manager & Monitoring Officer ────────────────────────────
        pm = User(
            name="Priya Menon",
            email="pm@skillbridge.sb",
            hashed_password=hash_password(DEFAULT_PASSWORD),
            role=Role.programme_manager,
        )
        mo = User(
            name="Rahul Verma",
            email="monitor@skillbridge.sb",
            hashed_password=hash_password(DEFAULT_PASSWORD),
            role=Role.monitoring_officer,
        )
        db.add_all([pm, mo])
        db.flush()

        # ── Trainers ──────────────────────────────────────────────────────────
        trainers_data = [
            ("Arjun Kumar", "arjun@inst.sb", inst1.id),
            ("Divya Nair", "divya@inst.sb", inst1.id),
            ("Suresh Pillai", "suresh@inst.sb", inst2.id),
            ("Lakshmi Rao", "lakshmi@inst.sb", inst2.id),
        ]
        trainers = []
        for name, email, inst_id in trainers_data:
            t = User(
                name=name,
                email=email,
                hashed_password=hash_password(DEFAULT_PASSWORD),
                role=Role.trainer,
                institution_id=inst_id,
            )
            db.add(t)
            trainers.append(t)
        db.flush()

        # ── Students ──────────────────────────────────────────────────────────
        students_raw = [
            ("Aishwarya Bhat", "aishwarya@student.sb"),
            ("Biju Thomas", "biju@student.sb"),
            ("Chitra Devi", "chitra@student.sb"),
            ("Deepak Singh", "deepak@student.sb"),
            ("Esha Patel", "esha@student.sb"),
            ("Farhan Khan", "farhan@student.sb"),
            ("Geetha Ramesh", "geetha@student.sb"),
            ("Harish Babu", "harish@student.sb"),
            ("Indira Mohan", "indira@student.sb"),
            ("Jaya Krishnan", "jaya@student.sb"),
            ("Kiran Shetty", "kiran@student.sb"),
            ("Lavanya Das", "lavanya@student.sb"),
            ("Manu Joseph", "manu@student.sb"),
            ("Nisha Pillai", "nisha@student.sb"),
            ("Omkar Patil", "omkar@student.sb"),
        ]
        students = []
        for name, email in students_raw:
            s = User(
                name=name,
                email=email,
                hashed_password=hash_password(DEFAULT_PASSWORD),
                role=Role.student,
            )
            db.add(s)
            students.append(s)
        db.flush()

        # ── Batches ───────────────────────────────────────────────────────────
        batch1 = Batch(name="Web Dev Cohort A", institution_id=inst1.id)
        batch2 = Batch(name="Data Analytics B", institution_id=inst1.id)
        batch3 = Batch(name="Electrical Basics C", institution_id=inst2.id)
        db.add_all([batch1, batch2, batch3])
        db.flush()

        # Assign trainers to batches
        db.add_all([
            BatchTrainer(batch_id=batch1.id, trainer_id=trainers[0].id),
            BatchTrainer(batch_id=batch2.id, trainer_id=trainers[1].id),
            BatchTrainer(batch_id=batch3.id, trainer_id=trainers[2].id),
            BatchTrainer(batch_id=batch3.id, trainer_id=trainers[3].id),  # shared trainer
        ])

        # Assign students to batches (5 per batch)
        for s in students[:5]:
            db.add(BatchStudent(batch_id=batch1.id, student_id=s.id))
        for s in students[5:10]:
            db.add(BatchStudent(batch_id=batch2.id, student_id=s.id))
        for s in students[10:]:
            db.add(BatchStudent(batch_id=batch3.id, student_id=s.id))
        db.flush()

        # ── Sessions ─────────────────────────────────────────────────────────
        today = date.today()
        sessions_data = [
            # batch1 sessions (3)
            (batch1.id, trainers[0].id, "Intro to HTML", today - timedelta(days=6)),
            (batch1.id, trainers[0].id, "CSS Fundamentals", today - timedelta(days=4)),
            (batch1.id, trainers[0].id, "JavaScript Basics", today - timedelta(days=2)),
            # batch2 sessions (3)
            (batch2.id, trainers[1].id, "Python for Data", today - timedelta(days=5)),
            (batch2.id, trainers[1].id, "Pandas Deep Dive", today - timedelta(days=3)),
            (batch2.id, trainers[1].id, "Data Viz with Matplotlib", today - timedelta(days=1)),
            # batch3 sessions (2)
            (batch3.id, trainers[2].id, "Electrical Safety", today - timedelta(days=7)),
            (batch3.id, trainers[3].id, "Circuit Theory", today - timedelta(days=5)),
        ]

        sessions_objs = []
        for batch_id, trainer_id, title, sess_date in sessions_data:
            sess = Session(
                batch_id=batch_id,
                trainer_id=trainer_id,
                title=title,
                date=sess_date,
                start_time=time(9, 0),
                end_time=time(11, 0),
            )
            db.add(sess)
            sessions_objs.append(sess)
        db.flush()

        # ── Attendance records ────────────────────────────────────────────────
        statuses = [AttendanceStatus.present, AttendanceStatus.present,
                    AttendanceStatus.present, AttendanceStatus.late,
                    AttendanceStatus.absent]

        batch_sessions = {
            batch1.id: sessions_objs[:3],
            batch2.id: sessions_objs[3:6],
            batch3.id: sessions_objs[6:],
        }
        batch_students = {
            batch1.id: students[:5],
            batch2.id: students[5:10],
            batch3.id: students[10:],
        }

        for batch_id, sess_list in batch_sessions.items():
            stud_list = batch_students[batch_id]
            for i, sess in enumerate(sess_list):
                for j, student in enumerate(stud_list):
                    status = statuses[(i + j) % len(statuses)]
                    db.add(Attendance(
                        session_id=sess.id,
                        student_id=student.id,
                        status=status,
                        marked_at=datetime.utcnow() - timedelta(hours=j),
                    ))

        db.commit()

        print("\n✅  Seed complete!\n")
        print("=" * 56)
        print("TEST ACCOUNTS (all passwords: Password123!)")
        print("=" * 56)
        print(f"Institution 1   : sunrise@inst.sb")
        print(f"Institution 2   : greenfield@inst.sb")
        print(f"Trainer 1       : arjun@inst.sb")
        print(f"Trainer 2       : divya@inst.sb")
        print(f"Trainer 3       : suresh@inst.sb")
        print(f"Trainer 4       : lakshmi@inst.sb")
        print(f"Student 1       : aishwarya@student.sb")
        print(f"Programme Mgr   : pm@skillbridge.sb")
        print(f"Monitoring Off. : monitor@skillbridge.sb")
        print("=" * 56)
        print(f"\nInstitution 1 ID : {inst1.id}")
        print(f"Institution 2 ID : {inst2.id}")
        print(f"Batch 1 ID       : {batch1.id}")
        print(f"Batch 2 ID       : {batch2.id}")
        print(f"Batch 3 ID       : {batch3.id}")
        print(f"Session 1 ID     : {sessions_objs[0].id}")

    except Exception as e:
        db.rollback()
        print(f"❌  Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
