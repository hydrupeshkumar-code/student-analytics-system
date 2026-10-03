"""Unified CP–NCP data model (Objective O1).

CP  = Continuous Process components (quizzes, assignments, practicals, attendance) -> Assessment/Score
NCP = Non-Continuous Process (semester-end examination)                           -> NcpResult
"""
from datetime import date, datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Role(str, Enum):
    admin = "admin"
    faculty = "faculty"
    student = "student"


class Component(str, Enum):
    quiz = "quiz"
    assignment = "assignment"
    practical = "practical"
    attendance = "attendance"
    other = "other"


class AssessmentStatus(str, Enum):
    draft = "draft"            # created, not visible to students, no marking
    in_progress = "in_progress"  # marking open
    completed = "completed"    # marking done, visible to students
    finalized = "finalized"    # locked


# ---------------------------------------------------------------- users

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), index=True)
    department: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)

    student_profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan")


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    roll_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id", ondelete="SET NULL"))
    batch: Mapped[str | None] = mapped_column(String(20))
    semester: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(10))

    user: Mapped[User] = relationship(back_populates="student_profile")
    program: Mapped["Program | None"] = relationship()


# ---------------------------------------------------------------- programs & outcomes

class Program(Base):
    __tablename__ = "programs"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    department: Mapped[str | None] = mapped_column(String(120))

    outcomes: Mapped[list["ProgramOutcome"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", order_by="ProgramOutcome.id")


class ProgramOutcome(Base):
    __tablename__ = "program_outcomes"
    __table_args__ = (UniqueConstraint("program_id", "code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)

    program: Mapped[Program] = relationship(back_populates="outcomes")


# ---------------------------------------------------------------- courses

class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("code", "academic_year", "section"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), index=True)
    name: Mapped[str] = mapped_column(String(160))
    program_id: Mapped[int | None] = mapped_column(ForeignKey("programs.id", ondelete="SET NULL"))
    faculty_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    semester: Mapped[int] = mapped_column(Integer, default=1)
    academic_year: Mapped[str] = mapped_column(String(20))
    section: Mapped[str] = mapped_column(String(10), default="A")
    credits: Mapped[float] = mapped_column(Float, default=3)

    # CP/NCP split of the final mark (must sum to 100)
    cp_weight: Mapped[float] = mapped_column(Float, default=50)
    ncp_weight: Mapped[float] = mapped_column(Float, default=50)
    ncp_max_marks: Mapped[float] = mapped_column(Float, default=100)
    ncp_published: Mapped[bool] = mapped_column(Boolean, default=False)

    # CO attainment configuration (NBA style)
    co_target_pct: Mapped[float] = mapped_column(Float, default=60)   # student "attains" a CO at >= this %
    level1_pct: Mapped[float] = mapped_column(Float, default=50)      # % of students attaining -> level 1
    level2_pct: Mapped[float] = mapped_column(Float, default=60)
    level3_pct: Mapped[float] = mapped_column(Float, default=70)
    target_level: Mapped[float] = mapped_column(Float, default=2.0)   # CO considered attained at >= this level

    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    program: Mapped[Program | None] = relationship()
    faculty: Mapped[User | None] = relationship()
    outcomes: Mapped[list["CourseOutcome"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="CourseOutcome.code")
    assessments: Mapped[list["Assessment"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Assessment.id")
    enrollments: Mapped[list["Enrollment"]] = relationship(back_populates="course", cascade="all, delete-orphan")


class CourseOutcome(Base):
    __tablename__ = "course_outcomes"
    __table_args__ = (UniqueConstraint("course_id", "code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)

    course: Mapped[Course] = relationship(back_populates="outcomes")
    po_links: Mapped[list["CoPoMapping"]] = relationship(back_populates="co", cascade="all, delete-orphan")


class CoPoMapping(Base):
    __tablename__ = "co_po_mappings"
    __table_args__ = (UniqueConstraint("co_id", "po_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    co_id: Mapped[int] = mapped_column(ForeignKey("course_outcomes.id", ondelete="CASCADE"))
    po_id: Mapped[int] = mapped_column(ForeignKey("program_outcomes.id", ondelete="CASCADE"))
    strength: Mapped[int] = mapped_column(Integer)  # 1 low, 2 medium, 3 high

    co: Mapped[CourseOutcome] = relationship(back_populates="po_links")
    po: Mapped[ProgramOutcome] = relationship()


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("course_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    course: Mapped[Course] = relationship(back_populates="enrollments")
    student: Mapped[User] = relationship()


# ---------------------------------------------------------------- rubric engine

class Rubric(Base):
    __tablename__ = "rubrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    owner: Mapped[User | None] = relationship()
    levels: Mapped[list["RubricLevel"]] = relationship(
        back_populates="rubric", cascade="all, delete-orphan", order_by="RubricLevel.position")
    criteria: Mapped[list["RubricCriterion"]] = relationship(
        back_populates="rubric", cascade="all, delete-orphan", order_by="RubricCriterion.position")


class RubricLevel(Base):
    __tablename__ = "rubric_levels"
    id: Mapped[int] = mapped_column(primary_key=True)
    rubric_id: Mapped[int] = mapped_column(ForeignKey("rubrics.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(60))
    points: Mapped[float] = mapped_column(Float)
    position: Mapped[int] = mapped_column(Integer, default=0)

    rubric: Mapped[Rubric] = relationship(back_populates="levels")


class RubricCriterion(Base):
    __tablename__ = "rubric_criteria"
    id: Mapped[int] = mapped_column(primary_key=True)
    rubric_id: Mapped[int] = mapped_column(ForeignKey("rubrics.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float)  # relative weightage (%)
    # performance-level descriptors, aligned with rubric.levels order
    descriptors: Mapped[list | None] = mapped_column(JSON)
    position: Mapped[int] = mapped_column(Integer, default=0)

    rubric: Mapped[Rubric] = relationship(back_populates="criteria")


# ---------------------------------------------------------------- CP assessments

class AssessmentCO(Base):
    __tablename__ = "assessment_cos"
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), primary_key=True)
    co_id: Mapped[int] = mapped_column(ForeignKey("course_outcomes.id", ondelete="CASCADE"), primary_key=True)


class Assessment(Base):
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    component: Mapped[str] = mapped_column(String(20))
    max_marks: Mapped[float] = mapped_column(Float)
    weightage: Mapped[float] = mapped_column(Float)  # % of the CP total
    rubric_id: Mapped[int | None] = mapped_column(ForeignKey("rubrics.id", ondelete="RESTRICT"))
    sessions_held: Mapped[int | None] = mapped_column(Integer)  # attendance only
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default=AssessmentStatus.draft.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    course: Mapped[Course] = relationship(back_populates="assessments")
    rubric: Mapped[Rubric | None] = relationship()
    cos: Mapped[list[CourseOutcome]] = relationship(secondary="assessment_cos")
    scores: Mapped[list["Score"]] = relationship(back_populates="assessment", cascade="all, delete-orphan")


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("assessment_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    marks: Mapped[float | None] = mapped_column(Float)
    attended: Mapped[int | None] = mapped_column(Integer)
    is_absent: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback: Mapped[str | None] = mapped_column(Text)
    graded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    assessment: Mapped[Assessment] = relationship(back_populates="scores")
    criteria: Mapped[list["ScoreCriterion"]] = relationship(back_populates="score", cascade="all, delete-orphan")


class ScoreCriterion(Base):
    __tablename__ = "score_criteria"
    __table_args__ = (UniqueConstraint("score_id", "criterion_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    score_id: Mapped[int] = mapped_column(ForeignKey("scores.id", ondelete="CASCADE"))
    criterion_id: Mapped[int] = mapped_column(ForeignKey("rubric_criteria.id", ondelete="CASCADE"))
    level_id: Mapped[int] = mapped_column(ForeignKey("rubric_levels.id", ondelete="CASCADE"))

    score: Mapped[Score] = relationship(back_populates="criteria")


# ---------------------------------------------------------------- NCP

class NcpResult(Base):
    __tablename__ = "ncp_results"
    __table_args__ = (UniqueConstraint("course_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    marks: Mapped[float | None] = mapped_column(Float)
    is_absent: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------- analytics / ML

class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    algorithm: Mapped[str] = mapped_column(String(40))
    metrics: Mapped[dict] = mapped_column(JSON)
    feature_names: Mapped[list] = mapped_column(JSON)
    n_samples: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str | None] = mapped_column(String(255))
    # serialized estimator, kept in the database so it survives redeploys on ephemeral hosts
    model_blob: Mapped[bytes | None] = mapped_column(LargeBinary().with_variant(LONGBLOB(), "mysql"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    trained_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("course_id", "student_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    probability: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(10))
    method: Mapped[str] = mapped_column(String(10))  # ml | rules
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id", ondelete="SET NULL"))
    features: Mapped[dict] = mapped_column(JSON)
    reasons: Mapped[list] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class HistoricalRecord(Base):
    """Anonymised CP–NCP outcomes used to train the at-risk model. No personal identifiers."""
    __tablename__ = "historical_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(20))  # import | harvest | synthetic
    cohort: Mapped[str | None] = mapped_column(String(40))
    course_code: Mapped[str | None] = mapped_column(String(30))
    quiz_pct: Mapped[float | None] = mapped_column(Float)
    assignment_pct: Mapped[float | None] = mapped_column(Float)
    practical_pct: Mapped[float | None] = mapped_column(Float)
    attendance_pct: Mapped[float | None] = mapped_column(Float)
    cp_pct: Mapped[float] = mapped_column(Float)
    ncp_pct: Mapped[float | None] = mapped_column(Float)
    passed: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


# ---------------------------------------------------------------- system

class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict | list | float | str] = mapped_column(JSON)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str | None] = mapped_column(String(60))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)

    user: Mapped[User | None] = relationship()
