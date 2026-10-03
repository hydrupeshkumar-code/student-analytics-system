# Student Assessment & Analytics Platform (SAAP)

**Continuous Evaluation Tracking with Rubric-Based Assessment.** Special Project, Faculty of Science & Technology, IFHE Hyderabad.

SAAP brings the **CP** (Continuous Process: quizzes, assignments, practicals, attendance) and **NCP** (Non-Continuous Process: semester-end exam) evaluations into one rubric-driven system. It includes role-based dashboards, NAAC/NBA-ready CO/PO attainment reports, and an ML early-warning module that flags at-risk students.

| Layer | Technology |
|---|---|
| View | React 19 + TypeScript (Vite SPA), Recharts, Poppins (self-hosted) |
| Controller | Python FastAPI REST API, JWT role authentication |
| Model | MySQL 8 or PostgreSQL (SQLite for local dev) via SQLAlchemy 2 + Alembic migrations |
| ML | scikit-learn logistic regression / decision tree |
| Reports | ReportLab (PDF), openpyxl (Excel) |

## How the requirements map to the build

| Objective (mid-term report §1.2) | Where it lives |
|---|---|
| **O1** Unified CP–NCP data model | `backend/app/models.py`, `services/correlation.py`: one consolidated record per student |
| **O2** Rubric engine (criteria, levels, weightages, auto score) | `services/rubric_engine.py`, Rubric library UI, rubric scorer in Marks entry |
| **O3** Role-based dashboards | Faculty dashboard + course workspace, Student portal, Admin console |
| **O4** CO/PO attainment reports for NAAC/NBA | `services/attainment.py`, `services/reports.py`, PDF/Excel downloads |
| **O5** Predictive early warning with documented accuracy | `services/prediction.py`, Early-warning tab, Admin → Early-warning model |
## Features

**Faculty**
- Course workspace with CP assessments (quiz / assignment / practical / attendance / other), CP weightages capped at 100%, and CO links.
- Assessment lifecycle from the state diagram: *Draft → Marking open → Completed → Finalized*. Completed assessments can be reopened; only an admin can reopen a finalized one.
- Marks entry grid with keyboard navigation, absent flags, per-student feedback, CSV import/export and unsaved-changes protection.
- Rubric scoring: click one performance level per criterion and the marks are computed live. Rubrics are locked against structural edits once they have been used for marking.
- Semester-end (NCP) entry, CSV import, and publishing results to students.
- Consolidated CP–NCP result sheet (Excel export), analytics (component averages, distribution, CP–NCP Pearson correlation with regression line, grade distribution).
- Course outcomes, CO–PO mapping matrix (strength 1–3), attainment thresholds, and the CO/PO attainment report (PDF/Excel).
- Early-warning list with probability, CP features and plain-language reasons.

**Student**
- Per-course component breakdown with class averages, rubric feedback (selected level per criterion), CO progress, risk status with suggested next steps, final grade once results are published, a GPA estimate, and a PDF performance report.
- Students see only *completed* assessments and *published* NCP results. No final grade is shown while any CP marking is still open.

**Administrator**
- Institution overview, user management (single and bulk CSV import with one-time temporary passwords), programs and POs (with NBA PO1–PO12 presets), courses and faculty assignment, program-level PO attainment, academic settings (grade bands, pass rules, thresholds), model training and versioning, and an audit log.

**Security and operations**
- bcrypt password hashing, short-lived access tokens plus refresh tokens, token-version revocation (password change or "sign out everywhere"), forced password change on first login, login throttling, and per-object authorization (faculty only see their own courses, students only their own records).
- Every write is recorded in the audit log. Security headers are set and CSV formula injection is neutralised.
- Alembic migrations, a health endpoint, a single Docker image (API + UI), and Docker Compose with MySQL.

## Calculation rules

- **CP %** = Σ(weightage × assessment %) ÷ Σ(weightage) over released assessments, so students are not penalised for assessments that have not happened yet. A missing score counts as 0 once the assessment is completed.
- **Rubric marks** = max marks × Σ(criterion weight × level points ÷ top points) ÷ Σ(criterion weight).
- **Attendance marks** = attended ÷ sessions held × max marks.
- **Final %** = CP % × CP weight + NCP % × NCP weight (per course, default 50/50). **Pass** requires final ≥ 40% *and* NCP ≥ 35% (configurable). Otherwise the grade is F.
- **CO attainment (NBA direct method):** a student attains a CO at ≥ 60% of marks on the assessments mapped to it. The share of students attaining gives the level (3 ≥ 70%, 2 ≥ 60%, 1 ≥ 50%). CO attainment = CP weight × CP level + NCP weight × NCP level. **PO attainment** = Σ(CO attainment × strength) ÷ Σ(strength). All thresholds are per course.
- **At-risk model:** features are quiz %, assignment %, practical %, attendance % and overall CP % (CP-only, so predictions exist before the exam). Target is fail/pass. Both algorithms are cross-validated, the better one by F1 is selected, and hold-out metrics are stored at the flagging threshold (medium risk, p ≥ 0.35). With no trained model, a transparent rules-based fallback is used.

## Run locally (development)

Requirements: Python 3.12+, Node 20+.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m app.cli seed-demo
uvicorn app.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 (Vite proxies `/api` to port 8000). API docs are at http://localhost:8000/api/docs.

Alternatively, run `npm run build` in `frontend/` once and FastAPI serves the built UI at http://localhost:8000.

**Demo accounts** (created by `seed-demo` only):

| Role | Email | Password |
|---|---|---|
| Admin | admin@saap.edu | Admin@123 |
| Faculty | neha@saap.edu | Faculty@123 |
| Student | student@saap.edu | Student@123 |

Other demo students are `stu002@saap.edu` … `stu040@saap.edu` with the student password. The demo includes one completed course (CS204, NCP published), two running courses, rubrics, CO–PO maps and 1,200 **synthetic** training records. Replace the synthetic records with real anonymised history before relying on predictions (Admin → Early-warning model).

## Deploy on Render (one click)

The repo includes a Render Blueprint, [`render.yaml`](render.yaml). It creates:
- A **web service** built from the `Dockerfile`, serving the API and the React UI on one URL.
- A managed **PostgreSQL** database. Render does not offer managed MySQL, so the app supports PostgreSQL, MySQL and SQLite through `DATABASE_URL`.

To deploy:
1. In Render, click **New → Blueprint**, connect this GitHub repository, and click **Apply**.
2. When prompted, enter `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` (at least 8 characters, letters and numbers). This admin is created on first start.
3. Optional: set `SEED_DEMO=true` before the first deploy to load the demo institution, which is useful for a project review.

What happens automatically:
- `JWT_SECRET` is generated by Render.
- Every start runs migrations, then `python -m app.cli bootstrap`, then the server on `$PORT`.
- Trained early-warning models are stored in the database, so they survive redeploys.

Free-plan notes:
- The free web service sleeps after inactivity.
- The free Postgres database expires after 30 days. Choose paid plans in `render.yaml` for real use.

## Deploy (Docker + MySQL)

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec app python -m app.cli create-admin --email examcell@college.edu --name "Exam Cell"
```

Before starting, edit `.env` and set `MYSQL_PASSWORD`, `MYSQL_ROOT_PASSWORD` and `JWT_SECRET`. Generate the secret with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

The app listens on port 8000. Put it behind HTTPS (nginx, Caddy or a cloud load balancer) and set `CORS_ORIGINS` to your public URL. Migrations run automatically on start. Back up the `mysql-data` volume, plus `ml-models` if you want to keep trained model files.

Going live:
1. Create programs and POs, then bulk-import users (Admin → Users → CSV template).
2. Create courses, assign faculty, and enrol students (or let faculty enrol by roll number).
3. Import anonymised historical CP–NCP records (Admin → Early-warning model → CSV template), train, then refresh predictions.
4. After each semester, publish NCP results and use **Add to ML history** on each course so the model improves over time.

## Tests

```bash
cd backend && pytest -q
cd frontend && npm run typecheck
```

The backend tests cover authentication and token revocation, login throttling, role and object permissions, the rubric formula, CP aggregation (including attendance and absences), the assessment lifecycle, NCP rules and the final grade, CO/PO attainment arithmetic, PDF/Excel generation, ML training and prediction, bulk user import, and CSV injection.

## Project layout

```
backend/
  app/models.py            unified CP–NCP schema
  app/services/            rubric_engine, correlation, attainment, prediction, reports, settings
  app/routers/             auth, users, programs, courses, rubrics, assessments, student, admin
  app/cli.py               create-admin / seed-demo / seed-history
  alembic/                 migrations
  tests/
frontend/src/
  pages/faculty|student|admin, components/, lib/
legacy-prototype/          earlier Flask prototype (kept for reference)
```

## Limitations (as scoped in the report)

- Covers the CP–NCP evaluation and analytics module only. Admissions, fees, timetabling and library are out of scope.
- Baseline ML models only. Prediction quality depends on the volume and quality of the historical data you import.
- Login throttling is per process. With several app instances, also rate-limit at the reverse proxy.
