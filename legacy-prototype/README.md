# Student Analytics and Performance Management System

A full-stack college-project application built with Flask, Flask-SQLAlchemy, Flask-Login, MySQL, Bootstrap 5, and Chart.js.

## Features
- Teacher and student role-based authentication.
- Student CRUD with search and department/semester filters.
- Attendance marking and attendance percentages.
- Subject-wise examination marks and grade calculations.
- Teacher analytics: subject bars, exam trends, grade distribution, attendance comparison, scatter plot, and class statistics.
- Data-driven at-risk detection with transparent reasons.
- Student performance dashboard with strengths, improvement areas, class-average comparisons, and trend direction.
- PDF student reports plus CSV/Excel class exports.
- Responsive UI with dark/light mode.
- Seeded demo data for 12 students and 6 subjects.

## Setup

### 1. Create the MySQL database
```sql
CREATE DATABASE student_analytics CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'student_admin'@'localhost' IDENTIFIED BY 'student_password';
GRANT ALL PRIVILEGES ON student_analytics.* TO 'student_admin'@'localhost';
FLUSH PRIVILEGES;
```

You may use an existing MySQL user instead. In that case, update `DATABASE_URL` in your environment.

### 2. Install dependencies
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment
Copy `.env.example` to `.env` or export the values manually. The app reads standard environment variables; it does not require python-dotenv.

### 4. Run
```bash
python app.py
```
Open `http://127.0.0.1:5000`.

## Demo accounts
Teacher: `teacher@demo.com` / `teacher123`

Student: `student@demo.com` / `student123`

Other seeded students use emails like `stu002@demo.com`, `stu003@demo.com`, etc., with password `student123`.

## Notes
- The default database is MySQL as required by the project specification.
- For a local-only prototype without MySQL, set `DATABASE_URL=sqlite:///student_analytics.db`; the rest of the application remains the same.
- All student-facing routes use the logged-in student's relationship and do not expose another student's records.
- At-risk flags are academic/attendance rules only; the system does not make medical or psychological predictions.
