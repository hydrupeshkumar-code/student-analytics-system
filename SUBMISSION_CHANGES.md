# Special Project submission changes

## Demo scope
- The fresh demo seed creates 30 synthetic students and exactly three course offerings: PC301 Professional Communication, CS304 Data Structures, and CS305 Computer Networks.
- Each course uses the same assessment scheme: Mid-Term Examination (30 marks / 30% weight), Internal Assessment (30 marks / 30% weight), and Final Examination (40 marks / 40% weight).
- Faculty demo login: `neha@saap.edu` / `Faculty@123` (DS and course overview); `ravi@saap.edu` / `Faculty@123` (CN); `anita@saap.edu` / `Faculty@123` (PC).
- Student demo login: `student@saap.edu` / `Student@123`. Additional demo students are `stu002@saap.edu` through `stu030@saap.edu`, using `Student@123`.
- Admin demo login: `admin@saap.edu` / `Admin@123`.

## Student-facing improvements
- Attendance risk and internal-assessment risk remain separate and clearly described as transparent risk indexes, not probabilities.
- Guidance is tiered: strong performance gets stretch goals and book recommendations; developing performance gets targeted improvement steps; high-support-priority performance gets a fundamentals-first recovery plan.
- Course-specific internship guidance covers communication/interview practice (PC), data-structure and coding-interview preparation (DS), and networking labs/troubleshooting (CN).
- Recommended books are shown directly on the student course and academic report pages.

## Loading demo data
Run `python -m app.cli seed-demo` only against a fresh/empty demo database. This seed command intentionally refuses to run when course/program/demo data already exists so it cannot overwrite institutional records. For an existing database, back it up and use a fresh demo database for the submission walkthrough rather than deleting real data.

All seeded student records and marks are synthetic demonstration data. They must not be used to make real academic, internship, or placement decisions.

## Additional teacher-requested improvements (October 2026)
- Faculty Risk page now includes a risk-category filter for overall academic risk, attendance risk, and internal-marks risk, alongside the existing All/High/Medium/Low severity filter.
- Faculty risk table now displays separate attendance and internal-marks warning levels beside the existing overall model prediction and failure probability. Attendance and marks warnings are transparent threshold-based indicators, not presented as trained-model probabilities.
- Student Academic Report now has subject-wise attendance and internal-marks warning panels with their own summaries and action lists, so students can see what to improve in each area independently.
- Added a practical placement-preparation checklist and starter book recommendations to the student report, covering coding practice, portfolio evidence, resume/interview preparation, and professional communication.
