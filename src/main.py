from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from .routers import attendance, auth, batches, institutions, monitoring, programme, sessions

# Create all tables on startup (idempotent)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SkillBridge Attendance API",
    description=(
        "Backend API for the SkillBridge state-level skilling programme. "
        "Supports five roles: student, trainer, institution, programme_manager, monitoring_officer."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(batches.router)
app.include_router(sessions.router)
app.include_router(attendance.router)
app.include_router(monitoring.router)
app.include_router(institutions.router)
app.include_router(programme.router)


@app.get("/", tags=["health"])
def root():
    return {"status": "ok", "service": "SkillBridge Attendance API", "version": "1.0.0"}


@app.get("/health", tags=["health"])
def health():
    return {"status": "healthy"}
