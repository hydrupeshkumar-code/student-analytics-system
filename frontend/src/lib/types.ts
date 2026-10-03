export type Role = "admin" | "faculty" | "student";
export type Component = "quiz" | "assignment" | "practical" | "attendance" | "other";
export type AStatus = "draft" | "in_progress" | "completed" | "finalized";
export type RiskLevel = "high" | "medium" | "low";

export interface StudentProfile {
  roll_no: string;
  program_id: number | null;
  batch: string | null;
  semester: number | null;
  section: string | null;
}

export interface User {
  id: number;
  name: string;
  email: string;
  role: Role;
  department: string | null;
  is_active: boolean;
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
  student_profile: StudentProfile | null;
}

export interface Outcome { id: number; code: string; description: string }
export interface Program { id: number; code: string; name: string; department: string | null; outcomes: Outcome[] }

export interface Course {
  id: number;
  code: string;
  name: string;
  program_id: number | null;
  faculty_id: number | null;
  semester: number;
  academic_year: string;
  section: string;
  credits: number;
  cp_weight: number;
  ncp_weight: number;
  ncp_max_marks: number;
  ncp_published: boolean;
  co_target_pct: number;
  level1_pct: number;
  level2_pct: number;
  level3_pct: number;
  target_level: number;
  is_archived: boolean;
  faculty_name: string | null;
  program_name: string | null;
  student_count: number;
}

export interface RubricLevel { id: number; label: string; points: number; position: number }
export interface RubricCriterion { id: number; name: string; description: string | null; weight: number; descriptors: string[] | null; position: number }
export interface Rubric {
  id: number;
  title: string;
  description: string | null;
  owner_id: number | null;
  owner_name: string | null;
  created_at: string;
  updated_at: string;
  levels: RubricLevel[];
  criteria: RubricCriterion[];
  in_use: boolean;
}

export interface Assessment {
  id: number;
  course_id: number;
  title: string;
  component: Component;
  max_marks: number;
  weightage: number;
  rubric_id: number | null;
  sessions_held: number | null;
  due_date: string | null;
  status: AStatus;
  created_at: string;
  co_ids: number[];
  graded_count: number;
}

export interface GradebookCell { marks: number | null; pct: number | null; absent: boolean; attended: number | null; feedback: string | null }
export interface GradebookStudent {
  student_id: number;
  name: string;
  email: string;
  roll_no: string | null;
  assessments: Record<string, GradebookCell>;
  components: Record<Component, number | null>;
  cp_pct: number | null;
  cp_weight_covered: number;
  ncp_marks: number | null;
  ncp_pct: number | null;
  ncp_absent: boolean;
  final_pct: number | null;
  grade: string | null;
  grade_points: number | null;
  passed: boolean | null;
  flags: string[];
}
export interface Gradebook {
  course_id: number;
  assessments: (Pick<Assessment, "id" | "title" | "component" | "max_marks" | "weightage" | "status" | "rubric_id" | "sessions_held" | "due_date"> & { co_ids: number[] })[];
  students: GradebookStudent[];
  cp_weight: number;
  ncp_weight: number;
  ncp_max_marks: number;
  ncp_published: boolean;
}

export interface RiskRow {
  student_id: number;
  name: string;
  roll_no: string | null;
  probability: number;
  risk_level: RiskLevel;
  method: "ml" | "rules";
  features: Record<string, number | null>;
  reasons: string[];
  generated_at: string;
}

export interface Metrics { accuracy: number; precision: number; recall: number; f1: number; roc_auc: number; confusion_matrix?: number[][]; test_size?: number }
export interface ModelVersion {
  id: number;
  algorithm: string;
  metrics: { cv: Record<string, Metrics>; cv_folds: number; threshold?: number; holdout: Metrics; selected: string; positive_rate: number; explain: { type: string; values: Record<string, number> } };
  feature_names: string[];
  n_samples: number;
  is_active: boolean;
  created_at: string;
}

export interface Settings {
  grade_bands: { grade: string; min: number; points: number }[];
  pass_mark_pct: number;
  ncp_min_pct: number;
  attendance_min_pct: number;
  component_alert_pct: number;
  risk_high: number;
  risk_medium: number;
}

export interface Paged<T> { total: number; page?: number; page_size?: number; items: T[] }
