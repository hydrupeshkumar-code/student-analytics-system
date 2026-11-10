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
        # Demo data may join an install that only has administrator accounts, but
        # must never be added on top of academic data or existing non-admin users.
        if db.query(Course.id).first() or db.query(Program.id).first() or \
                db.query(User.id).filter(User.role != "admin").first():
            sys.exit("Academic data or non-admin accounts already exist — demo data can only be loaded into an empty install.")

        def user(name, email, role, pw, dept=None):
            u = User(name=name, email=email, role=role, department=dept, password_hash=hash_password(pw))
            db.add(u)
            return u

        admin = db.query(User).filter_by(email="admin@saap.edu").first()
        if admin:
            admin.name = "Exam Cell Administrator"
            admin.role = "admin"
            admin.password_hash = hash_password("Admin@123")
            admin.is_active = True
            admin.must_change_password = False
        else:
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
        for i in range(30):
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
        communication_rubric = _rubric(db, anita, "Professional Communication Rubric",
                                        "Writing, presentations, audience awareness and professional tone.", levels4, [
            ("Clarity & structure", "Organises the message with a clear purpose and logical flow", 30,
             ["Clear, concise and logically structured", "Mostly clear with minor gaps", "Some structure but unclear in places", "Difficult to follow"]),
            ("Language & tone", "Uses accurate language and a suitable professional tone", 25,
             ["Accurate, polished professional language", "Minor language or tone issues", "Frequent errors affect clarity", "Tone or errors obstruct meaning"]),
            ("Audience awareness", "Adapts content to the intended audience and context", 25,
             ["Highly appropriate to audience and context", "Generally appropriate", "Limited adaptation to audience", "Audience and purpose are unclear"]),
            ("Delivery & evidence", "Supports the message and responds to questions", 20,
             ["Confident delivery with relevant evidence", "Clear delivery with some evidence", "Uneven delivery or limited support", "Unprepared or unsupported delivery"]),
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

        def build_course(code, name, fac, year, sem, cos, copo, finished: bool,
                         assessment_plan=None, credits: float = 4):
            c = Course(code=code, name=name, program_id=cse.id, faculty_id=fac.id, semester=sem,
                       academic_year=year, section="A", credits=credits, cp_weight=50, ncp_weight=50,
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
            plan = assessment_plan or [
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

        # The submission/demo cohort intentionally contains exactly three subjects.
        # Assessment maximums and CP weightages match the requested 30/30/40 breakup.
        # Attendance is kept as a running register at 0% weightage: it is recorded, shown to
        # students and used for attendance risk without changing the 30/30/40 CP split.
        ATTENDANCE = ("Attendance", "attendance", 10, 0, None, [], "in_progress", 0, 0)
        pc = build_course("PC301", "Professional Communication", anita, "2026-27", 5, [
            ("CO1", "Write clear professional emails, summaries and formal documents."),
            ("CO2", "Adapt messages to audience, purpose and workplace context."),
            ("CO3", "Deliver structured presentations and participate in group discussions."),
            ("CO4", "Demonstrate listening, interview and professional interaction skills."),
        ], {"CO1": {"PO10": 3}, "CO2": {"PO10": 3, "PO8": 1},
            "CO3": {"PO10": 3, "PO9": 2}, "CO4": {"PO10": 2, "PO9": 2}}, finished=False,
           assessment_plan=[
               ("Mid-Term Examination", "quiz", 30, 30, None, ["CO1", "CO2"], "completed", 72, 16),
               ("Internal Assessment", "assignment", 30, 30, communication_rubric, ["CO2", "CO3"], "completed", 70, 18),
               ("Final Examination", "practical", 40, 40, communication_rubric, ["CO1", "CO3", "CO4"], "completed", 74, 15),
               ATTENDANCE,
           ], credits=2)

        ds = build_course("CS304", "Data Structures", neha, "2026-27", 5, [
            ("CO1", "Analyse time and space complexity of common data structures."),
            ("CO2", "Implement arrays, linked lists, stacks and queues."),
            ("CO3", "Apply trees, heaps and hash tables to solve problems."),
            ("CO4", "Use graph algorithms and select suitable structures for a problem."),
        ], {"CO1": {"PO1": 3, "PO2": 2}, "CO2": {"PO2": 3, "PO5": 3},
            "CO3": {"PO3": 2, "PO2": 3}, "CO4": {"PO2": 3, "PO5": 2}}, finished=False,
           assessment_plan=[
               ("Mid-Term Examination", "quiz", 30, 30, None, ["CO1", "CO2"], "completed", 68, 20),
               ("Internal Assessment", "assignment", 30, 30, assign_rubric, ["CO2", "CO3"], "completed", 66, 22),
               ("Final Examination", "practical", 40, 40, lab_rubric, ["CO2", "CO3", "CO4"], "completed", 70, 20),
               ATTENDANCE,
           ], credits=4)

        cn = build_course("CS305", "Computer Networks", ravi, "2026-27", 5, [
            ("CO1", "Explain layered network architecture and protocol responsibilities."),
            ("CO2", "Analyse IP addressing, subnetting and routing decisions."),
            ("CO3", "Explain transport, application and common network services."),
            ("CO4", "Use network tools to diagnose connectivity and performance issues."),
        ], {"CO1": {"PO1": 3}, "CO2": {"PO2": 3, "PO5": 2},
            "CO3": {"PO1": 2, "PO2": 2}, "CO4": {"PO4": 2, "PO5": 3}}, finished=False,
           assessment_plan=[
               ("Mid-Term Examination", "quiz", 30, 30, None, ["CO1", "CO2"], "completed", 70, 18),
               ("Internal Assessment", "assignment", 30, 30, assign_rubric, ["CO2", "CO3"], "completed", 64, 22),
               ("Final Examination", "practical", 40, 40, lab_rubric, ["CO3", "CO4"], "completed", 72, 19),
               ATTENDANCE,
           ], credits=4)

        n_hist = seed_history(db)
        prediction.train(db, "auto", admin.id)
        for c in (pc, ds, cn):
            prediction.predict_course(db, c)
        db.commit()
        print(f"Demo data loaded: 4 staff, {len(students)} students, 3 courses (PC, DS, CN; assessment breakup 30/30/40, plus an attendance register), {n_hist} synthetic history rows.")
        print("Logins: admin@saap.edu / Admin@123 · neha@saap.edu / Faculty@123 · student@saap.edu / Student@123")


def seed_demo_subjects(db=None):
    """Deprecated compatibility command: the submission demo now seeds PC, DS and CN together.

    Deliberately does not append the old PC/Python pair, because the requested demo
    scope is exactly three subjects. Existing institutional databases are untouched.
    """
    print("No extra demo subjects added. Use seed-demo on a fresh database for the PC/DS/CN submission cohort.")
    return []


def bootstrap():
    """Idempotent first-run setup driven by environment variables (for hosts without a shell, e.g. Render).

    SEED_DEMO=true                        load demo data when the database is empty
    INITIAL_ADMIN_EMAIL / _PASSWORD / _NAME  create the first administrator if that email does not exist yet
    """
    import os

    with SessionLocal() as db:
        fresh = (db.query(Course.id).first() is None and db.query(Program.id).first() is None
                 and db.query(User.id).filter(User.role != "admin").first() is None)
        users = db.query(User.id).count()
    if fresh and os.getenv("SEED_DEMO", "").lower() in ("1", "true", "yes"):
        print("bootstrap: no courses yet, loading demo data (demo logins: admin@saap.edu / Admin@123)")
        seed_demo()
    elif not fresh:
        # Preserve existing institutional data. The three-subject submission cohort
        # is loaded only into a fresh demo database; never add demo subjects to live data.
        pass

    if users == 0 and not os.getenv("INITIAL_ADMIN_EMAIL") and not os.getenv("SEED_DEMO"):
        print("bootstrap: WARNING — no user accounts exist. Set INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD "
              "(or SEED_DEMO=true) and redeploy, otherwise nobody can sign in.")

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
    sub.add_parser("seed-demo-subjects")
    sub.add_parser("seed-history")
    args = p.parse_args()
    if args.cmd == "bootstrap":
        bootstrap()
    elif args.cmd == "create-admin":
        create_admin(args.email, args.name, args.password)
    elif args.cmd == "seed-demo":
        seed_demo()
    elif args.cmd == "seed-demo-subjects":
        seed_demo_subjects()
    elif args.cmd == "seed-history":
        with SessionLocal() as db:
            n = seed_history(db)
            db.commit()
            print(f"Added {n} synthetic history rows" if n else "Synthetic history already present")


if __name__ == "__main__":
    main()
