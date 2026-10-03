from datetime import date, datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    student = db.relationship("Student", back_populates="user", uselist=False)

    def set_password(self, raw_password: str):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password, raw_password)


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False)
    department = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    section = db.Column(db.String(20), nullable=False)
    roll_number = db.Column(db.String(30), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, unique=True)
    user = db.relationship("User", back_populates="student")
    attendance_records = db.relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    marks = db.relationship("Mark", back_populates="student", cascade="all, delete-orphan")
    recommendations = db.relationship("Recommendation", back_populates="student", cascade="all, delete-orphan")


class Subject(db.Model):
    __tablename__ = "subjects"
    id = db.Column(db.Integer, primary_key=True)
    subject_name = db.Column(db.String(120), nullable=False)
    subject_code = db.Column(db.String(30), unique=True, nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    attendance_records = db.relationship("Attendance", back_populates="subject", cascade="all, delete-orphan")
    marks = db.relationship("Mark", back_populates="subject", cascade="all, delete-orphan")


class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    status = db.Column(db.String(10), nullable=False)
    student = db.relationship("Student", back_populates="attendance_records")
    subject = db.relationship("Subject", back_populates="attendance_records")
    __table_args__ = (db.UniqueConstraint("student_id", "subject_id", "date", name="uq_attendance_day"),)


class Mark(db.Model):
    __tablename__ = "marks"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False, index=True)
    exam_type = db.Column(db.String(60), nullable=False)
    marks = db.Column(db.Float, nullable=False)
    max_marks = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    student = db.relationship("Student", back_populates="marks")
    subject = db.relationship("Subject", back_populates="marks")


class Recommendation(db.Model):
    __tablename__ = "recommendations"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False, index=True)
    category = db.Column(db.String(40), nullable=False)
    message = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), nullable=False, default="medium")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    student = db.relationship("Student", back_populates="recommendations")
