import csv
import io
import os
from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import median

from flask import Flask, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func

from models import Attendance, Mark, Recommendation, Student, Subject, User, db


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "sqlite:///student_analytics.db",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["ATTENDANCE_THRESHOLD"] = float(os.getenv("ATTENDANCE_THRESHOLD", "75"))
app.config["PASS_MARK_PERCENT"] = float(os.getenv("PASS_MARK_PERCENT", "40"))

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def role_required(role):
    def decorator(fn):
        from functools import wraps

        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role != role:
                flash("You do not have permission to open that page.", "danger")
                return redirect(url_for("dashboard"))
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def pct(mark, max_mark=100):
    return round((mark / max_mark) * 100, 1) if max_mark else 0.0


def student_mark_average(student):
    values = [pct(m.marks, m.max_marks) for m in student.marks]
    return round(sum(values) / len(values), 1) if values else 0.0


def attendance_summary(student):
    total = len(student.attendance_records)
    present = sum(1 for a in student.attendance_records if a.status == "Present")
    return present, total, round((present / total) * 100, 1) if total else 0.0


def latest_exam_trend(student):
    grouped = defaultdict(list)
    for m in student.marks:
        grouped[m.exam_type].append(pct(m.marks, m.max_marks))
    if len(grouped) < 2:
        return "Stable", None, None
    ordered = sorted(grouped.keys(), key=lambda k: max((m.date for m in student.marks if m.exam_type == k), default=date.min))
    prev = sum(grouped[ordered[-2]]) / len(grouped[ordered[-2]])
    last = sum(grouped[ordered[-1]]) / len(grouped[ordered[-1]])
    delta = round(last - prev, 1)
    if delta >= 5:
        state = "Improving"
    elif delta <= -5:
        state = "Declining"
    else:
        state = "Stable"
    return state, round(prev, 1), round(last, 1)


def subject_stats(student):
    result = []
    class_students = Student.query.filter_by(department=student.department, semester=student.semester, section=student.section).all()
    for subject in Subject.query.filter_by(semester=student.semester).order_by(Subject.subject_name).all():
        mine = [m for m in student.marks if m.subject_id == subject.id]
        classmates = [m for s in class_students for m in s.marks if m.subject_id == subject.id]
        if not mine and not classmates:
            continue
        my_avg = round(sum(pct(m.marks, m.max_marks) for m in mine) / len(mine), 1) if mine else 0.0
        class_avg = round(sum(pct(m.marks, m.max_marks) for m in classmates) / len(classmates), 1) if classmates else 0.0
        diff = round(my_avg - class_avg, 1)
        result.append({"subject": subject.subject_name, "marks": my_avg, "class_avg": class_avg, "difference": diff})
    return result


def recommendation_payload(student):
    present, total, attendance = attendance_summary(student)
    avg = student_mark_average(student)
    trend, prev, last = latest_exam_trend(student)
    recs = []
    if total and attendance < app.config["ATTENDANCE_THRESHOLD"]:
        recs.append(("Attendance", f"Your attendance is {attendance}%. Aim to improve consistency so you stay above the {app.config['ATTENDANCE_THRESHOLD']:.0f}% threshold.", "high"))
    for row in subject_stats(student):
        if row["marks"] < app.config["PASS_MARK_PERCENT"]:
            recs.append(("Subject", f"{row['subject']} is currently at {row['marks']}%, below the {app.config['PASS_MARK_PERCENT']:.0f}% pass benchmark. Review the latest assessments and target the weakest topics.", "high"))
        elif row["difference"] <= -5:
            recs.append(("Subject", f"{row['subject']} is {abs(row['difference'])} percentage points below the class average. Give this subject additional practice time.", "medium"))
    if trend == "Declining" and prev is not None and last is not None:
        recs.append(("Trend", f"Your average moved from {prev}% to {last}% across the latest two assessment groups. Revisit recent mistakes and adjust your study plan.", "high"))
    if avg >= 80:
        recs.append(("Strength", "You are performing strongly overall. Protect your strengths while focusing on the subjects closest to the class average.", "low"))
    if not recs:
        recs.append(("General", "Your recorded performance is currently stable. Keep your study and attendance routine consistent and monitor subject-level changes.", "low"))
    return recs


def refresh_recommendations(student):
    Recommendation.query.filter_by(student_id=student.id, category="Auto").delete(synchronize_session=False)
    for category, message, priority in recommendation_payload(student):
        db.session.add(Recommendation(student_id=student.id, category="Auto", message=f"[{category}] {message}", priority=priority))
    db.session.commit()


def grade_for(score):
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B+"
    if score >= 60:
        return "B"
    if score >= 50:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def at_risk_reasons(student):
    present, total, attendance = attendance_summary(student)
    avg = student_mark_average(student)
    trend, prev, last = latest_exam_trend(student)
    failed = 0
    for row in subject_stats(student):
        if row["marks"] < app.config["PASS_MARK_PERCENT"]:
            failed += 1
    reasons = []
    if total and attendance < app.config["ATTENDANCE_THRESHOLD"]:
        reasons.append(f"Attendance below {app.config['ATTENDANCE_THRESHOLD']:.0f}% ({attendance}%)")
    if avg < app.config["PASS_MARK_PERCENT"]:
        reasons.append(f"Average marks below pass benchmark ({avg}%)")
    if trend == "Declining" and prev is not None and last is not None:
        reasons.append(f"Performance declined from {prev}% to {last}%")
    if failed >= 2:
        reasons.append(f"{failed} subjects below passing marks")
    return reasons


def at_risk(student):
    return len(at_risk_reasons(student)) > 0


def teacher_dashboard_data():
    students = Student.query.order_by(Student.name).all()
    attendance_values = [attendance_summary(s)[2] for s in students if s.attendance_records]
    mark_values = [student_mark_average(s) for s in students if s.marks]
    return {
        "total_students": len(students),
        "avg_attendance": round(sum(attendance_values) / len(attendance_values), 1) if attendance_values else 0,
        "avg_marks": round(sum(mark_values) / len(mark_values), 1) if mark_values else 0,
        "at_risk": sum(at_risk(s) for s in students),
        "excellent": sum(student_mark_average(s) >= 85 for s in students),
        "below_attendance": sum(bool(s.attendance_records) and attendance_summary(s)[2] < app.config["ATTENDANCE_THRESHOLD"] for s in students),
    }


@app.context_processor
def inject_globals():
    return {"threshold": app.config["ATTENDANCE_THRESHOLD"], "attendance_summary": attendance_summary, "student_mark_average": student_mark_average, "at_risk": at_risk, "at_risk_reasons": at_risk_reasons, "grade_for": grade_for, "pct": pct, "now_date": date.today().isoformat()}


@app.route("/")
def index():
    return redirect(url_for("dashboard")) if current_user.is_authenticated else redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter(func.lower(User.email) == email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "teacher":
        return render_template("teacher_dashboard.html", stats=teacher_dashboard_data())
    student = current_user.student
    refresh_recommendations(student)
    return render_template(
        "student_dashboard.html",
        student=student,
        overall=student_mark_average(student),
        attendance=attendance_summary(student)[2],
        grade=grade_for(student_mark_average(student)),
        trend=latest_exam_trend(student)[0],
        subjects=subject_stats(student),
        recommendations=Recommendation.query.filter_by(student_id=student.id, category="Auto").order_by(Recommendation.created_at.desc()).all(),
    )


@app.route("/students", methods=["GET", "POST"])
@role_required("teacher")
def students():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        sid = request.form.get("student_id", "").strip()
        if not name or not email or not sid:
            flash("Name, email, and student ID are required.", "warning")
        elif Student.query.filter((Student.email == email) | (Student.student_id == sid)).first():
            flash("A student with that email or ID already exists.", "danger")
        else:
            user = User(name=name, email=email, role="student")
            user.set_password(request.form.get("password", "student123"))
            student = Student(student_id=sid, name=name, email=email, department=request.form.get("department", "CSE"), semester=int(request.form.get("semester", 5)), section=request.form.get("section", "A"), roll_number=request.form.get("roll_number", sid), user=user)
            db.session.add(user)
            db.session.add(student)
            db.session.commit()
            flash(f"Student {name} added successfully.", "success")
        return redirect(url_for("students"))

    q = request.args.get("q", "").strip()
    department = request.args.get("department", "").strip()
    semester = request.args.get("semester", "").strip()
    query = Student.query
    if q:
        pattern = f"%{q}%"
        query = query.filter((Student.name.ilike(pattern)) | (Student.student_id.ilike(pattern)) | (Student.email.ilike(pattern)))
    if department:
        query = query.filter_by(department=department)
    if semester:
        query = query.filter_by(semester=int(semester))
    students_list = query.order_by(Student.name).all()
    departments = [d[0] for d in db.session.query(Student.department).distinct().order_by(Student.department).all()]
    return render_template("students.html", students=students_list, departments=departments)


@app.route("/students/<int:student_id>/delete", methods=["POST"])
@role_required("teacher")
def delete_student(student_id):
    student = db.get_or_404(Student, student_id)
    if student.user:
        db.session.delete(student.user)
    db.session.delete(student)
    db.session.commit()
    flash("Student deleted.", "info")
    return redirect(url_for("students"))


@app.route("/attendance", methods=["GET", "POST"])
@role_required("teacher")
def attendance():
    students = Student.query.order_by(Student.name).all()
    subjects = Subject.query.order_by(Subject.subject_name).all()
    if request.method == "POST":
        subject_id = int(request.form["subject_id"])
        record_date = date.fromisoformat(request.form["date"])
        for student in students:
            status = request.form.get(f"status_{student.id}")
            if status not in {"Present", "Absent"}:
                continue
            existing = Attendance.query.filter_by(student_id=student.id, subject_id=subject_id, date=record_date).first()
            if existing:
                existing.status = status
            else:
                db.session.add(Attendance(student_id=student.id, subject_id=subject_id, date=record_date, status=status))
        db.session.commit()
        flash("Attendance saved for the selected class and date.", "success")
        return redirect(url_for("attendance", subject_id=subject_id, date=record_date.isoformat()))
    return render_template("attendance.html", students=students, subjects=subjects, selected_subject=request.args.get("subject_id", type=int), selected_date=request.args.get("date", date.today().isoformat()))


@app.route("/marks", methods=["GET", "POST"])
@role_required("teacher")
def marks():
    students = Student.query.order_by(Student.name).all()
    subjects = Subject.query.order_by(Subject.subject_name).all()
    if request.method == "POST":
        student_id = int(request.form["student_id"])
        subject_id = int(request.form["subject_id"])
        exam_type = request.form["exam_type"].strip()
        marks_value = float(request.form["marks"])
        max_marks = float(request.form["max_marks"])
        mark_date = date.fromisoformat(request.form["date"])
        if marks_value < 0 or max_marks <= 0 or marks_value > max_marks:
            flash("Marks must be between 0 and the maximum marks.", "danger")
        else:
            db.session.add(Mark(student_id=student_id, subject_id=subject_id, exam_type=exam_type, marks=marks_value, max_marks=max_marks, date=mark_date))
            db.session.commit()
            flash("Marks recorded.", "success")
        return redirect(url_for("marks"))
    recent = Mark.query.order_by(Mark.date.desc(), Mark.id.desc()).limit(80).all()
    return render_template("marks.html", students=students, subjects=subjects, recent=recent)


@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@role_required("teacher")
def edit_student(student_id):
    student = db.get_or_404(Student, student_id)
    if request.method == "POST":
        student.name = request.form.get("name", "").strip()
        student.email = request.form.get("email", "").strip().lower()
        student.department = request.form.get("department", "CSE").strip()
        student.semester = int(request.form.get("semester", 5))
        student.section = request.form.get("section", "A").strip()
        student.roll_number = request.form.get("roll_number", "").strip()
        student.user.name = student.name
        student.user.email = student.email
        new_password = request.form.get("password", "").strip()
        if new_password:
            student.user.set_password(new_password)
        db.session.commit()
        flash("Student details updated.", "success")
        return redirect(url_for("students"))
    return render_template("student_edit.html", student=student)


@app.route("/marks/<int:mark_id>/edit", methods=["GET", "POST"])
@role_required("teacher")
def edit_mark(mark_id):
    mark = db.get_or_404(Mark, mark_id)
    if request.method == "POST":
        mark.student_id = int(request.form["student_id"])
        mark.subject_id = int(request.form["subject_id"])
        mark.exam_type = request.form["exam_type"].strip()
        mark.marks = float(request.form["marks"])
        mark.max_marks = float(request.form["max_marks"])
        mark.date = date.fromisoformat(request.form["date"])
        if mark.marks < 0 or mark.max_marks <= 0 or mark.marks > mark.max_marks:
            flash("Invalid marks values.", "danger")
        else:
            db.session.commit()
            flash("Mark updated.", "success")
        return redirect(url_for("marks"))
    return render_template("mark_edit.html", mark=mark, students=Student.query.order_by(Student.name).all(), subjects=Subject.query.order_by(Subject.subject_name).all())


@app.route("/marks/<int:mark_id>/delete", methods=["POST"])
@role_required("teacher")
def delete_mark(mark_id):
    mark = db.get_or_404(Mark, mark_id)
    db.session.delete(mark)
    db.session.commit()
    flash("Mark deleted.", "info")
    return redirect(url_for("marks"))


@app.route("/api/attendance/status")
@role_required("teacher")
def attendance_status_api():
    subject_id = request.args.get("subject_id", type=int)
    record_date = request.args.get("date", date.today().isoformat())
    try:
        record_date = date.fromisoformat(record_date)
    except ValueError:
        return jsonify({"error": "Invalid date"}), 400
    records = Attendance.query.filter_by(subject_id=subject_id, date=record_date).all()
    return jsonify({str(r.student_id): r.status for r in records})


@app.route("/analytics")
@role_required("teacher")
def analytics():
    subjects = Subject.query.order_by(Subject.subject_name).all()
    departments = [d[0] for d in db.session.query(Student.department).distinct().order_by(Student.department).all()]
    return render_template("analytics.html", subjects=subjects, departments=departments)


@app.route("/api/analytics")
@role_required("teacher")
def analytics_api():
    dept = request.args.get("department", "").strip()
    semester = request.args.get("semester", type=int)
    section = request.args.get("section", "").strip()
    subject_id = request.args.get("subject_id", type=int)
    query = Student.query
    if dept:
        query = query.filter_by(department=dept)
    if semester:
        query = query.filter_by(semester=semester)
    if section:
        query = query.filter_by(section=section)
    students = query.all()
    if subject_id:
        subjects = [db.get_or_404(Subject, subject_id)]
    else:
        subjects = Subject.query.order_by(Subject.subject_name).all()

    subject_labels, subject_avgs, attendance_by_subject = [], [], []
    for subject in subjects:
        mark_values = [pct(m.marks, m.max_marks) for s in students for m in s.marks if m.subject_id == subject.id]
        attend = [1 if a.status == "Present" else 0 for s in students for a in s.attendance_records if a.subject_id == subject.id]
        if mark_values:
            subject_labels.append(subject.subject_name)
            subject_avgs.append(round(sum(mark_values) / len(mark_values), 1))
            attendance_by_subject.append(round((sum(attend) / len(attend)) * 100, 1) if attend else 0)
    student_points = []
    for s in students:
        att = attendance_summary(s)[2]
        avg = student_mark_average(s)
        if s.marks or s.attendance_records:
            student_points.append({"name": s.name, "attendance": att, "marks": avg})

    all_marks = [pct(m.marks, m.max_marks) for s in students for m in s.marks]
    grade_distribution = {g: 0 for g in ["A+", "A", "B+", "B", "C", "D", "F"]}
    for value in all_marks:
        grade_distribution[grade_for(value)] += 1
    exam_groups = defaultdict(list)
    for s in students:
        for m in s.marks:
            exam_groups[m.exam_type].append(pct(m.marks, m.max_marks))
    ordered_exams = sorted(exam_groups.keys())
    exam_avgs = [round(sum(exam_groups[e]) / len(exam_groups[e]), 1) for e in ordered_exams]
    avg = round(sum(all_marks) / len(all_marks), 1) if all_marks else 0
    passed = sum(v >= app.config["PASS_MARK_PERCENT"] for v in all_marks)
    return jsonify({
        "subject_labels": subject_labels,
        "subject_avgs": subject_avgs,
        "attendance_labels": subject_labels,
        "attendance_values": attendance_by_subject,
        "scatter": student_points,
        "grade_labels": list(grade_distribution.keys()),
        "grade_values": list(grade_distribution.values()),
        "exam_labels": ordered_exams,
        "exam_values": exam_avgs,
        "class_average": avg,
        "median": round(median(all_marks), 1) if all_marks else 0,
        "highest": round(max(all_marks), 1) if all_marks else 0,
        "lowest": round(min(all_marks), 1) if all_marks else 0,
        "pass_percentage": round((passed / len(all_marks)) * 100, 1) if all_marks else 0,
    })


@app.route("/student/performance")
@role_required("student")
def student_performance():
    student = current_user.student
    refresh_recommendations(student)
    return render_template("student_performance.html", student=student, subjects=subject_stats(student), overall=student_mark_average(student), trend=latest_exam_trend(student))


@app.route("/student/attendance")
@role_required("student")
def student_attendance():
    student = current_user.student
    per_subject = []
    for subject in Subject.query.filter_by(semester=student.semester).order_by(Subject.subject_name).all():
        records = [a for a in student.attendance_records if a.subject_id == subject.id]
        if records:
            present = sum(a.status == "Present" for a in records)
            per_subject.append({"subject": subject.subject_name, "present": present, "total": len(records), "percentage": round((present / len(records)) * 100, 1)})
    return render_template("student_attendance.html", student=student, per_subject=per_subject, total=attendance_summary(student)[1], present=attendance_summary(student)[0], overall=attendance_summary(student)[2])


@app.route("/student/marks")
@role_required("student")
def student_marks():
    student = current_user.student
    return render_template("student_marks.html", student=student, marks=sorted(student.marks, key=lambda x: (x.date, x.id), reverse=True))


@app.route("/student/improvement")
@role_required("student")
def improvement():
    student = current_user.student
    refresh_recommendations(student)
    rows = subject_stats(student)
    strengths = [r for r in rows if r["marks"] >= 80]
    improve = [r for r in rows if r["marks"] < 70 or r["difference"] <= -5]
    return render_template("improvement.html", student=student, recommendations=Recommendation.query.filter_by(student_id=student.id, category="Auto").order_by(Recommendation.priority.desc()).all(), strengths=strengths, improve=improve)


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user, student=current_user.student)


@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


@app.route("/reports")
@login_required
def reports():
    if current_user.role == "teacher":
        students = Student.query.order_by(Student.name).all()
        return render_template("reports.html", students=students)
    return render_template("reports.html", students=[current_user.student])


@app.route("/reports/student/<int:student_id>/pdf")
@role_required("teacher")
def student_pdf(student_id):
    student = db.get_or_404(Student, student_id)
    return build_student_pdf(student)


@app.route("/student/report.pdf")
@role_required("student")
def own_pdf():
    return build_student_pdf(current_user.student)


def build_student_pdf(student):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    elements = [Paragraph("Student Academic Performance Report", styles["Title"]), Spacer(1, 12)]
    attendance = attendance_summary(student)[2]
    overall = student_mark_average(student)
    elements.append(Paragraph(f"<b>{student.name}</b> — {student.student_id} — {student.department} — Semester {student.semester} — Section {student.section}", styles["BodyText"]))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(f"Overall Percentage: {overall}% &nbsp;&nbsp;&nbsp; Grade: {grade_for(overall)} &nbsp;&nbsp;&nbsp; Attendance: {attendance}%", styles["BodyText"]))
    elements.append(Spacer(1, 12))
    rows = [["Subject", "Marks %", "Class Avg", "Difference", "Status"]]
    for r in subject_stats(student):
        status = "Excellent" if r["marks"] >= 80 else "Good" if r["difference"] >= 0 else "Improve"
        rows.append([r["subject"], r["marks"], r["class_avg"], r["difference"], status])
    table = Table(rows, repeatRows=1, colWidths=[150, 65, 65, 65, 70])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e9eefc")), ("GRID", (0,0), (-1,-1), 0.4, colors.grey), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"), ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f9fbff")])]))
    elements.append(table)
    elements.append(Spacer(1, 12))
    trend = latest_exam_trend(student)[0]
    elements.append(Paragraph(f"Performance trend: <b>{trend}</b>", styles["BodyText"]))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Improvement suggestions", styles["Heading2"]))
    for _, message, _ in recommendation_payload(student):
        elements.append(Paragraph("• " + message, styles["BodyText"]))
        elements.append(Spacer(1, 4))
    doc.build(elements)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f"{student.student_id}_report.pdf", mimetype="application/pdf")


@app.route("/reports/class.csv")
@role_required("teacher")
def class_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student ID", "Name", "Department", "Semester", "Section", "Attendance %", "Average Marks %", "Grade", "Status"])
    for s in Student.query.order_by(Student.name).all():
        avg = student_mark_average(s)
        writer.writerow([s.student_id, s.name, s.department, s.semester, s.section, attendance_summary(s)[2], avg, grade_for(avg), "Needs Attention" if at_risk(s) else "On Track"])
    return send_file(io.BytesIO(output.getvalue().encode("utf-8")), as_attachment=True, download_name="class_report.csv", mimetype="text/csv")


@app.route("/reports/class.xlsx")
@role_required("teacher")
def class_xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = "Class Report"
    ws.append(["Student ID", "Name", "Department", "Semester", "Section", "Attendance %", "Average Marks %", "Grade", "Status"])
    for s in Student.query.order_by(Student.name).all():
        avg = student_mark_average(s)
        ws.append([s.student_id, s.name, s.department, s.semester, s.section, attendance_summary(s)[2], avg, grade_for(avg), "Needs Attention" if at_risk(s) else "On Track"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="class_report.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def seed_demo_data():
    if User.query.filter_by(email="teacher@demo.com").first():
        return
    teacher = User(name="Demo Teacher", email="teacher@demo.com", role="teacher")
    teacher.set_password("teacher123")
    db.session.add(teacher)
    subjects = [
        Subject(subject_name="Database Management", subject_code="DBMS", semester=5),
        Subject(subject_name="Operating Systems", subject_code="OS", semester=5),
        Subject(subject_name="Computer Networks", subject_code="CN", semester=5),
        Subject(subject_name="Data Structures", subject_code="DS", semester=5),
        Subject(subject_name="Mathematics", subject_code="MATH", semester=5),
        Subject(subject_name="Web Technologies", subject_code="WT", semester=5),
    ]
    db.session.add_all(subjects)
    db.session.flush()
    profiles = [
        ("STU001", "Rahul", 62, [48, 42, 55, 51, 46, 49]),
        ("STU002", "Ananya", 93, [91, 88, 95, 90, 87, 92]),
        ("STU003", "Vikram", 78, [72, 69, 65, 76, 71, 74]),
        ("STU004", "Priya", 86, [88, 84, 91, 83, 79, 87]),
        ("STU005", "Arjun", 74, [61, 58, 66, 70, 64, 67]),
        ("STU006", "Sneha", 88, [84, 77, 86, 90, 81, 88]),
        ("STU007", "Kiran", 69, [73, 64, 59, 68, 62, 61]),
        ("STU008", "Meera", 96, [94, 92, 96, 91, 90, 95]),
        ("STU009", "Rohit", 82, [80, 74, 79, 85, 76, 83]),
        ("STU010", "Divya", 71, [68, 63, 72, 66, 70, 65]),
        ("STU011", "Manoj", 76, [75, 71, 73, 77, 69, 74]),
        ("STU012", "Ishita", 90, [89, 85, 88, 93, 87, 91]),
    ]
    exam_names = ["Internal 1", "Quiz 1", "Midterm", "Internal 2"]
    rng_start = date.today() - timedelta(days=75)
    for idx, (sid, name, att_target, subject_scores) in enumerate(profiles, start=1):
        email = f"{sid.lower()}@demo.com" if sid != "STU001" else "student@demo.com"
        u = User(name=name, email=email, role="student")
        u.set_password("student123")
        s = Student(student_id=sid, name=name, email=email, department="CSE", semester=5, section="A", roll_number=str(100 + idx), user=u)
        db.session.add_all([u, s])
        db.session.flush()
        for sub_i, subject in enumerate(subjects):
            base = subject_scores[sub_i]
            for exam_i, exam in enumerate(exam_names):
                # STU001 intentionally declines toward recent exams for demo analytics.
                if sid == "STU001":
                    values = [base + 10, base + 4, base - 2, max(0, base - 8)]
                    score = values[exam_i]
                else:
                    score = max(0, min(100, base + ((exam_i - 1) * 1.5)))
                db.session.add(Mark(student_id=s.id, subject_id=subject.id, exam_type=exam, marks=score, max_marks=100, date=rng_start + timedelta(days=exam_i * 22 + sub_i)))
            for d in range(6):
                status = "Present" if ((d + sub_i + idx) % 7) < max(1, round(att_target / 100 * 7)) else "Absent"
                db.session.add(Attendance(student_id=s.id, subject_id=subject.id, date=rng_start + timedelta(days=sub_i * 2 + d), status=status))
        db.session.flush()
        for category, message, priority in recommendation_payload(s):
            db.session.add(Recommendation(student_id=s.id, category="Auto", message=f"[{category}] {message}", priority=priority))
    db.session.commit()


def bootstrap_database():
    db.create_all()
    seed_demo_data()


if __name__ == "__main__":
    with app.app_context():
        bootstrap_database()
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
