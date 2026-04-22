"""
Test configuration.

Two fixtures use a real SQLite test database (not mocked) to satisfy the
assignment requirement: "at least two tests should hit a real (test) database."
"""
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set env vars BEFORE importing src modules, because auth.py validates
# SECRET_KEY at import time and will raise ValueError if it's missing/short.
os.environ["SECRET_KEY"] = "test-secret-key-that-is-at-least-32-chars-long!!"
os.environ["MONITORING_API_KEY"] = "monitor-secret-key-2024"
os.environ["DATABASE_URL"] = "sqlite:///./test_skillbridge.db"

from src.database import Base, get_db
from src.main import app

TEST_DB_URL = "sqlite:///./test_skillbridge.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create tables once for the whole test session, then tear down."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./test_skillbridge.db"):
        os.remove("./test_skillbridge.db")


@pytest.fixture
def client(setup_test_db):
    """Return a TestClient wired to the SQLite test database."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
