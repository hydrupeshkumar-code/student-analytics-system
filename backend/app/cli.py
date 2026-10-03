"""Management commands.

  python -m app.cli create-admin --email admin@college.edu --name "Exam Cell"   # production bootstrap
  python -m app.cli seed-demo                                                   # demo data (empty DB only)
  python -m app.cli seed-history                                                # synthetic training data
"""
import argparse
import getpass
import random
import sys
from datetime import date, timedelta

from .database import SessionLocal
from .models import (
    Assessment, CoPoMapping, Course, CourseOutcome, Enrollment, HistoricalRecord, NcpResult, Program,
    ProgramOutcome, Rubric, RubricCriterion, RubricLevel, Score, ScoreCriterion, StudentProfile, User,
)
from .security import hash_password, validate_password_strength
from .services import prediction
from .services.rubric_engine import compute_rubric_marks

NBA_POS = [
    ("PO1", "Engineering knowledge: apply mathematics, science and engineering fundamentals to solve complex problems."),
    ("PO2", "Problem analysis: identify, formulate and analyse complex engineering problems."),
    ("PO3", "Design/development of solutions for complex problems meeting specified needs."),
    ("PO4", "Conduct investigations of complex problems using research-based knowledge and methods."),
    ("PO5", "Modern tool usage: create, select and apply appropriate techniques, resources and IT tools."),
    ("PO6", "The engineer and society: assess societal, health, safety, legal and cultural issues."),
    ("PO7", "Environment and sustainability: understand the impact of engineering solutions."),
    ("PO8", "Ethics: apply ethical principles and commit to professional ethics."),
    ("PO9", "Individual and team work: function effectively as an individual and in teams."),
    ("PO10", "Communication: communicate effectively on complex engineering activities."),
    ("PO11", "Project management and finance: apply engineering and management principles."),
    ("PO12", "Life-long learning: engage in independent and life-long learning."),
]

FIRST = ["Aarav", "Aditi", "Arjun", "Ananya", "Bhavya", "Charan", "Deepika", "Dev", "Divya", "Gautam", "Harini",
         "Ishaan", "Jahnavi", "Karthik", "Kavya", "Lakshmi", "Manoj", "Meera", "Nikhil", "Nisha", "Pranav",
         "Priya", "Rahul", "Riya", "Rohan", "Sahana", "Sai", "Sanjana", "Siddharth", "Sneha", "Tanvi", "Tarun",
         "Uday", "Varsha", "Vikram", "Yamini", "Zoya", "Akhil", "Bhargavi", "Chaitanya"]
LAST = ["Reddy", "Sharma", "Rao", "Nair", "Patel", "Kumar", "Iyer", "Verma", "Khan", "Gupta", "Naidu", "Menon"]


def create_admin(email: str, name: str, password: str | None):
    with SessionLocal() as db:
        if db.query(User.id).filter_by(email=email.lower()).first():
            sys.exit(f"User {email} already exists")
        if not password:
            password = getpass.getpass("Password for the new admin: ")
        problem = validate_password_strength(password)
        if problem:
            sys.exit(problem)
        db.add(User(name=name, email=email.lower(), role="admin", password_hash=hash_password(password)))
        db.commit()
        print(f"Admin {email} created.")


def seed_history(db, n=1200):
    if db.query(HistoricalRecord.id).filter_by(source="synthetic").first():
        return 0
    rows = prediction.synthetic_history(n)
    db.add_all(rows)
    db.flush()
    return len(rows)


def _rubric(db, owner, title, desc, levels, criteria):
    r = Rubric(owner_id=owner.id, title=title, description=desc)
    r.levels = [RubricLevel(label=l, points=p, position=i) for i, (l, p) in enumerate(levels)]
    r.criteria = [RubricCriterion(name=n, description=d, weight=w, descriptors=ds, position=i)
                  for i, (n, d, w, ds) in enumerate(criteria)]
    db.add(r)
    db.flush()
    return r


def seed_demo():
    rng = random.Random(2026)
    with SessionLocal() as db:
        if db.query(User.id).first():
            sys.exit("Database is not empty — demo data can only be loaded into a fresh database.")

        def user(name, email, role, pw, dept=None):
            u = User(name=name, email=email, role=role, department=dept, password_hash=hash_password(pw))
            db.add(u)
            return u

        admin = user("Exam Cell Administrator", "admin@saap.edu", "admin", "Admin@123")
        neha = user("T. Neha", "neha@saap.edu", "faculty", "Faculty@123", "Computer Science & Engineering")
        ravi = user("Dr. Ravi Shankar", "ravi@saap.edu", "faculty", "Faculty@123", "Computer Science & Engineering")
        anita = user("Prof. Anita Desai", "anita@saap.edu", "faculty", "Faculty@123", "Computer Science & Engineering")

        cse = Program(code="BTECH-CSE", name="B.Tech Computer Science & Engineering",
                      department="Computer Science & Engineering")
        cse.outcomes = [ProgramOutcome(code=c, description=d) for c, d in NBA_POS]
        db.add(cse)
        db.flush()

        # ---- students: hidden ability drives realistic, correlated marks
        students = []
        names = set()
        for i in range(40):
            while True:
                nm = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
                if nm not in names:
                    names.add(nm)
                    break
            email = "student@saap.edu" if i == 0 else f"stu{i + 1:03d}@saap.edu"
            u = user(nm, email, "student", "Student@123")
            u.student_profile = StudentProfile(roll_no=f"24STUCHH01{i + 1:04d}", program_id=cse.id,
                                               batch="2024-28", semester=5, section="A")
            ability = rng.gauss(0, 1)
            engagement = rng.gauss(0, 1)
            if i in (6, 13, 27):
                ability, engagement = -1.8, -1.6  # a few clearly struggling students
            students.append((u, ability, engagement))
        db.flush()

        # ---- rubrics
        levels4 = [("Excellent", 4), ("Good", 3), ("Satisfactory", 2), ("Needs improvement", 1)]
        assign_rubric = _rubric(db, neha, "Programming Assignment Rubric",
                                "For design-and-implement assignments.", levels4, [
            ("Correctness", "Program produces correct output for all test cases", 40,
             ["All cases pass incl. edge cases", "Most cases pass", "Basic cases pass", "Fails basic cases"]),
            ("Design & modularity", "Appropriate decomposition and data structures", 25,
             ["Clean, reusable design", "Mostly well structured", "Some structure", "Monolithic"]),
            ("Code quality", "Readability, naming, comments", 20,
             ["Exemplary", "Clear", "Readable with effort", "Hard to follow"]),
            ("Documentation", "Report explains approach and results", 15,
             ["Complete and insightful", "Complete", "Partial", "Missing"]),
        ])
        lab_rubric = _rubric(db, neha, "Laboratory Practical Rubric", "Weekly lab evaluation.", levels4, [
            ("Preparation", "Pre-lab work and understanding of the aim", 20, None),
            ("Execution", "Performs the experiment / implementation independently", 40, None),
            ("Results & analysis", "Correct observations and interpretation", 25, None),
            ("Viva", "Answers questions on the experiment", 15, None),
        ])

        def mark(ability, engagement, base, spread, mx):
            v = base + spread * ability + 4 * engagement + rng.gauss(0, 8)
            return round(max(0, min(mx, mx * v / 100)), 1)

        def level_pick(rubric, ability, engagement):
            sel = {}
            lv = rubric.levels  # sorted high -> low
            for c in rubric.criteria:
                q = 1.9 + 0.9 * ability + 0.4 * engagement + rng.gauss(0, 0.7)
                idx = 0 if q > 2.3 else 1 if q > 1.3 else 2 if q > 0.3 else 3
                sel[c.id] = lv[idx].id
            return sel

        today = date(2026, 10, 3)

        def build_course(code, name, fac, year, sem, cos, copo, finished: bool):
            c = Course(code=code, name=name, program_id=cse.id, faculty_id=fac.id, semester=sem,
                       academic_year=year, section="A", credits=4, cp_weight=50, ncp_weight=50,
                       ncp_max_marks=100, ncp_published=finished)
            c.outcomes = [CourseOutcome(code=k, description=d) for k, d in cos]
            db.add(c)
            db.flush()
            po_by_code = {p.code: p for p in cse.outcomes}
            for co in c.outcomes:
                for po_code, st in copo.get(co.code, {}).items():
                    db.add(CoPoMapping(co_id=co.id, po_id=po_by_code[po_code].id, strength=st))
            for u, _, _ in students:
                db.add(Enrollment(course_id=c.id, student_id=u.id))
            db.flush()
            co = {x.code: x for x in c.outcomes}
            closed = "finalized" if finished else "completed"
            plan = [
                ("Quiz 1", "quiz", 20, 15, None, ["CO1"], closed, 69, 14),
                ("Quiz 2", "quiz", 20, 15, None, ["CO2"], closed, 66, 15),
                ("Assignment 1", "assignment", 25, 20, assign_rubric, ["CO2", "CO3"], closed, 0, 0),
                ("Lab evaluation", "practical", 50, 25, lab_rubric, ["CO3", "CO4"],
                 closed if finished else "in_progress", 0, 0),
                ("Quiz 3", "quiz", 20, 15, None, ["CO4"], closed if finished else "draft", 64, 15),
                ("Attendance", "attendance", 10, 10, None, [], closed if finished else "in_progress", 0, 0),
            ]
            for idx, (title, comp, mx, w, rub, co_codes, status, base, spread) in enumerate(plan):
                a = Assessment(course_id=c.id, title=title, component=comp, max_marks=mx, weightage=w,
                               rubric_id=rub.id if rub else None, status=status,
                               sessions_held=48 if comp == "attendance" else None,
                               due_date=today - timedelta(days=70 - 14 * idx) if not finished
                               else date(2026, 4, 1) - timedelta(days=90 - 14 * idx))
                a.cos = [co[k] for k in co_codes]
                db.add(a)
                db.flush()
                if status == "draft":
                    continue
                for j, (u, ab, en) in enumerate(students):
                    if status == "in_progress" and comp == "practical" and j % 5 == 4:
                        continue  # marking still under way
                    s = Score(assessment_id=a.id, student_id=u.id, graded_by=fac.id)
                    if comp == "attendance":
                        s.attended = int(max(18, min(48, round(48 * (0.84 + 0.08 * en + 0.03 * ab + rng.gauss(0, .04))))))
                        s.marks = round(mx * s.attended / 48, 2)
                    elif rub:
                        sel = level_pick(rub, ab, en)
                        s.marks = compute_rubric_marks(rub, sel, mx)
                        s.criteria = [ScoreCriterion(criterion_id=k, level_id=v) for k, v in sel.items()]
                        if s.marks < 0.5 * mx:
                            s.feedback = "Revisit the weakest criteria in the rubric and see me during office hours."
                        elif s.marks > 0.85 * mx:
                            s.feedback = "Excellent work — well structured and clearly documented."
                    else:
                        if rng.random() < 0.03:
                            s.is_absent = True
                        else:
                            s.marks = mark(ab, en, base, spread, mx)
                    db.add(s)
            if finished:
                for u, ab, en in students:
                    v = 58 + 16 * ab + 3 * en + rng.gauss(0, 9)
                    db.add(NcpResult(course_id=c.id, student_id=u.id, marks=round(max(0, min(100, v)), 1)))
            db.flush()
            return c

        dbms = build_course("CS204", "Database Management Systems", neha, "2025-26", 4, [
            ("CO1", "Explain the relational model, keys and integrity constraints."),
            ("CO2", "Write SQL queries including joins, sub-queries and aggregation."),
            ("CO3", "Design normalised schemas from ER models."),
            ("CO4", "Apply transaction management and concurrency control concepts."),
        ], {"CO1": {"PO1": 3, "PO2": 2}, "CO2": {"PO2": 3, "PO5": 3}, "CO3": {"PO3": 3, "PO2": 2},
            "CO4": {"PO1": 2, "PO4": 2, "PO12": 1}}, finished=True)

        se = build_course("CS301", "Software Engineering", neha, "2026-27", 5, [
            ("CO1", "Compare software process models for a given project context."),
            ("CO2", "Elicit and specify requirements using UML use-case and class diagrams."),
            ("CO3", "Design modular software applying design principles and patterns."),
            ("CO4", "Plan and execute testing strategies and agile project tracking."),
        ], {"CO1": {"PO1": 2, "PO11": 2}, "CO2": {"PO2": 3, "PO10": 2}, "CO3": {"PO3": 3, "PO5": 2},
            "CO4": {"PO4": 2, "PO9": 3, "PO11": 2}}, finished=False)

        os_ = build_course("CS302", "Operating Systems", ravi, "2026-27", 5, [
            ("CO1", "Describe OS structures, processes and threads."),
            ("CO2", "Analyse CPU scheduling algorithms."),
            ("CO3", "Solve synchronisation problems using semaphores and monitors."),
            ("CO4", "Evaluate memory management and file system techniques."),
        ], {"CO1": {"PO1": 3}, "CO2": {"PO2": 3, "PO4": 1}, "CO3": {"PO3": 2, "PO2": 2},
            "CO4": {"PO1": 2, "PO5": 2}}, finished=False)

        _ = anita  # faculty without courses yet, useful for assignment demos

        n_hist = seed_history(db)
        prediction.train(db, "auto", admin.id)
        for c in (dbms, se, os_):
            prediction.predict_course(db, c)
        db.commit()
        print(f"Demo data loaded: 4 staff, {len(students)} students, 3 courses, {n_hist} synthetic history rows.")
        print("Logins: admin@saap.edu / Admin@123 · neha@saap.edu / Faculty@123 · student@saap.edu / Student@123")


def bootstrap():
    """Idempotent first-run setup driven by environment variables (for hosts without a shell, e.g. Render).

    SEED_DEMO=true                        load demo data when the database is empty
    INITIAL_ADMIN_EMAIL / _PASSWORD / _NAME  create the first administrator if that email does not exist yet
    """
    import os

    with SessionLocal() as db:
        empty = db.query(User.id).first() is None
    if empty and os.getenv("SEED_DEMO", "").lower() in ("1", "true", "yes"):
        print("bootstrap: empty database, loading demo data")
        seed_demo()

    email = os.getenv("INITIAL_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("INITIAL_ADMIN_PASSWORD", "")
    if email and password:
        with SessionLocal() as db:
            if db.query(User.id).filter_by(email=email).first():
                print(f"bootstrap: admin {email} already exists")
                return
        problem = validate_password_strength(password)
        if problem:
            print(f"bootstrap: INITIAL_ADMIN_PASSWORD rejected — {problem}")
            return
        create_admin(email, os.getenv("INITIAL_ADMIN_NAME", "Administrator"), password)


def main():
    p = argparse.ArgumentParser(prog="python -m app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bootstrap")
    a = sub.add_parser("create-admin")
    a.add_argument("--email", required=True)
    a.add_argument("--name", default="Administrator")
    a.add_argument("--password", help="omit to be prompted")
    sub.add_parser("seed-demo")
    sub.add_parser("seed-history")
    args = p.parse_args()
    if args.cmd == "bootstrap":
        bootstrap()
    elif args.cmd == "create-admin":
        create_admin(args.email, args.name, args.password)
    elif args.cmd == "seed-demo":
        seed_demo()
    elif args.cmd == "seed-history":
        with SessionLocal() as db:
            n = seed_history(db)
            db.commit()
            print(f"Added {n} synthetic history rows" if n else "Synthetic history already present")


if __name__ == "__main__":
    main()
