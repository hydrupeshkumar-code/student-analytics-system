from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

RoleT = Literal["admin", "faculty", "student"]
ComponentT = Literal["quiz", "assignment", "practical", "attendance", "other"]
StatusT = Literal["draft", "in_progress", "completed", "finalized"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ auth

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshIn(BaseModel):
    refresh_token: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class StudentProfileOut(ORM):
    roll_no: str
    program_id: int | None
    batch: str | None
    semester: int | None
    section: str | None


class UserOut(ORM):
    id: int
    name: str
    email: str
    role: RoleT
    department: str | None
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None
    student_profile: StudentProfileOut | None = None


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


# ------------------------------------------------------------------ users

class StudentProfileIn(BaseModel):
    roll_no: str = Field(min_length=1, max_length=40)
    program_id: int | None = None
    batch: str | None = Field(default=None, max_length=20)
    semester: int | None = Field(default=None, ge=1, le=12)
    section: str | None = Field(default=None, max_length=10)


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    role: RoleT
    department: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    student_profile: StudentProfileIn | None = None

    @model_validator(mode="after")
    def student_needs_profile(self):
        if self.role == "student" and not self.student_profile:
            raise ValueError("Students need a roll number")
        return self


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    role: RoleT | None = None
    department: str | None = None
    is_active: bool | None = None
    student_profile: StudentProfileIn | None = None


class UserCreated(BaseModel):
    user: UserOut
    temporary_password: str | None = None


# ------------------------------------------------------------------ programs

class OutcomeIn(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    description: str = Field(min_length=1, max_length=2000)


class OutcomeOut(ORM):
    id: int
    code: str
    description: str


class ProgramIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=160)
    department: str | None = Field(default=None, max_length=120)


class ProgramOut(ORM):
    id: int
    code: str
    name: str
    department: str | None
    outcomes: list[OutcomeOut] = []


# ------------------------------------------------------------------ courses

class CourseConfig(BaseModel):
    cp_weight: float | None = Field(default=None, ge=0, le=100)
    ncp_weight: float | None = Field(default=None, ge=0, le=100)
    ncp_max_marks: float | None = Field(default=None, gt=0, le=1000)
    co_target_pct: float | None = Field(default=None, ge=0, le=100)
    level1_pct: float | None = Field(default=None, ge=0, le=100)
    level2_pct: float | None = Field(default=None, ge=0, le=100)
    level3_pct: float | None = Field(default=None, ge=0, le=100)
    target_level: float | None = Field(default=None, ge=0, le=3)


class CourseIn(CourseConfig):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=160)
    program_id: int | None = None
    faculty_id: int | None = None
    semester: int = Field(ge=1, le=12)
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$")
    section: str = Field(default="A", min_length=1, max_length=10)
    credits: float = Field(default=3, ge=0, le=30)


class CourseUpdate(CourseConfig):
    code: str | None = Field(default=None, min_length=1, max_length=30)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    program_id: int | None = None
    faculty_id: int | None = None
    semester: int | None = Field(default=None, ge=1, le=12)
    academic_year: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    section: str | None = Field(default=None, max_length=10)
    credits: float | None = Field(default=None, ge=0, le=30)
    is_archived: bool | None = None
    ncp_published: bool | None = None


class CourseOut(ORM):
    id: int
    code: str
    name: str
    program_id: int | None
    faculty_id: int | None
    semester: int
    academic_year: str
    section: str
    credits: float
    cp_weight: float
    ncp_weight: float
    ncp_max_marks: float
    ncp_published: bool
    co_target_pct: float
    level1_pct: float
    level2_pct: float
    level3_pct: float
    target_level: float
    is_archived: bool
    faculty_name: str | None = None
    program_name: str | None = None
    student_count: int = 0


class CoPoCell(BaseModel):
    co_id: int
    po_id: int
    strength: int | None = Field(default=None, ge=1, le=3)


class EnrollIn(BaseModel):
    student_ids: list[int] = []
    roll_nos: list[str] = []


# ------------------------------------------------------------------ rubrics

class LevelIn(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    points: float = Field(ge=0, le=1000)


class CriterionIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    weight: float = Field(gt=0, le=1000)
    descriptors: list[str] | None = None


class RubricIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    levels: list[LevelIn]
    criteria: list[CriterionIn]


class LevelOut(ORM):
    id: int
    label: str
    points: float
    position: int


class CriterionOut(ORM):
    id: int
    name: str
    description: str | None
    weight: float
    descriptors: list[str] | None
    position: int


class RubricOut(ORM):
    id: int
    title: str
    description: str | None
    owner_id: int | None
    created_at: datetime
    updated_at: datetime
    levels: list[LevelOut]
    criteria: list[CriterionOut]
    in_use: bool = False
    owner_name: str | None = None


# ------------------------------------------------------------------ assessments & scores

class AssessmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    component: ComponentT
    max_marks: float = Field(gt=0, le=1000)
    weightage: float = Field(ge=0, le=100)
    rubric_id: int | None = None
    sessions_held: int | None = Field(default=None, ge=1, le=1000)
    due_date: date | None = None
    co_ids: list[int] = []

    @model_validator(mode="after")
    def attendance_sessions(self):
        if self.component == "attendance":
            if not self.sessions_held:
                raise ValueError("Attendance components need the number of sessions held")
            if self.rubric_id:
                raise ValueError("Attendance cannot be rubric-scored")
        return self


class AssessmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    max_marks: float | None = Field(default=None, gt=0, le=1000)
    weightage: float | None = Field(default=None, ge=0, le=100)
    rubric_id: int | None = None
    sessions_held: int | None = Field(default=None, ge=1, le=1000)
    due_date: date | None = None
    co_ids: list[int] | None = None


class AssessmentOut(ORM):
    id: int
    course_id: int
    title: str
    component: ComponentT
    max_marks: float
    weightage: float
    rubric_id: int | None
    sessions_held: int | None
    due_date: date | None
    status: StatusT
    created_at: datetime
    co_ids: list[int] = []
    graded_count: int = 0


class StatusIn(BaseModel):
    status: StatusT


class ScoreIn(BaseModel):
    student_id: int
    marks: float | None = Field(default=None, ge=0)
    attended: int | None = Field(default=None, ge=0)
    is_absent: bool = False
    feedback: str | None = Field(default=None, max_length=4000)
    criteria: dict[int, int] | None = None  # criterion_id -> level_id

    @field_validator("criteria", mode="before")
    @classmethod
    def int_keys(cls, v):
        if isinstance(v, dict):
            return {int(k): int(val) for k, val in v.items() if val not in (None, "")}
        return v


class ScoresIn(BaseModel):
    scores: list[ScoreIn]


class NcpIn(BaseModel):
    student_id: int
    marks: float | None = Field(default=None, ge=0)
    is_absent: bool = False


class NcpBulkIn(BaseModel):
    results: list[NcpIn]


# ------------------------------------------------------------------ settings / ml

class GradeBand(BaseModel):
    grade: str = Field(min_length=1, max_length=4)
    min: float = Field(ge=0, le=100)
    points: float = Field(ge=0, le=10)


class SettingsIn(BaseModel):
    grade_bands: list[GradeBand] | None = None
    pass_mark_pct: float | None = Field(default=None, ge=0, le=100)
    ncp_min_pct: float | None = Field(default=None, ge=0, le=100)
    attendance_min_pct: float | None = Field(default=None, ge=0, le=100)
    component_alert_pct: float | None = Field(default=None, ge=0, le=100)
    risk_high: float | None = Field(default=None, gt=0, lt=1)
    risk_medium: float | None = Field(default=None, gt=0, lt=1)


class TrainIn(BaseModel):
    algorithm: Literal["auto", "logistic_regression", "decision_tree"] = "auto"


class ModelVersionOut(ORM):
    id: int
    algorithm: str
    metrics: dict
    feature_names: list
    n_samples: int
    is_active: bool
    created_at: datetime
