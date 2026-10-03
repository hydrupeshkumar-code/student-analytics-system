import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["MODEL_DIR"] = f"{_tmp}/models"
os.environ["ENVIRONMENT"] = "test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import security  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Program, ProgramOutcome, StudentProfile, User  # noqa: E402

# fast hashing in tests
security.hash_password = lambda raw: __import__("bcrypt").hashpw(raw.encode(), __import__("bcrypt").gensalt(4)).decode()


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def client(db):
    security.login_throttle._fails.clear()
    return TestClient(app)


def make_user(db, email, role, name=None, roll=None, program_id=None, password="Passw0rd!"):
    u = User(name=name or email.split("@")[0], email=email, role=role, password_hash=security.hash_password(password))
    if role == "student":
        u.student_profile = StudentProfile(roll_no=roll or email.split("@")[0].upper(), program_id=program_id)
    db.add(u)
    db.commit()
    return u


def login(client, email, password="Passw0rd!"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def world(db, client):
    """Program with POs, an admin, a faculty member, three students and a course."""
    prog = Program(code="BT", name="B.Tech")
    prog.outcomes = [ProgramOutcome(code=f"PO{i}", description=f"PO {i}") for i in (1, 2)]
    db.add(prog)
    db.commit()
    make_user(db, "admin@x.edu", "admin")
    fac = make_user(db, "fac@x.edu", "faculty")
    make_user(db, "other@x.edu", "faculty")
    studs = [make_user(db, f"s{i}@x.edu", "student", roll=f"R{i}", program_id=prog.id) for i in range(1, 4)]
    A, F = login(client, "admin@x.edu"), login(client, "fac@x.edu")
    r = client.post("/api/courses", headers=A, json={
        "code": "CS1", "name": "Course", "program_id": prog.id, "faculty_id": fac.id, "semester": 1,
        "academic_year": "2026-27", "cp_weight": 50, "ncp_weight": 50, "ncp_max_marks": 100})
    assert r.status_code == 201, r.text
    course = r.json()
    r = client.post(f"/api/courses/{course['id']}/students", headers=F, json={"roll_nos": ["R1", "R2", "R3"]})
    assert r.json()["added"] == 3
    return {"A": A, "F": F, "course": course, "students": studs, "program": prog,
            "S1": login(client, "s1@x.edu"), "O": login(client, "other@x.edu")}
