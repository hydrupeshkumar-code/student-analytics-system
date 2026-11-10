from app.services.student_guidance import internship_feedback_for_course, student_risk_signals


def test_attendance_and_internals_are_separate_signals():
    cfg = {"attendance_min_pct": 75.0, "component_alert_pct": 40.0, "pass_mark_pct": 40.0}
    result = student_risk_signals(
        {"attendance": 62.0, "quiz": 48.0, "assignment": 55.0, "practical": 35.0}, cfg
    )

    assert result["attendance"]["risk_level"] == "high"
    assert result["attendance"]["value_pct"] == 62.0
    assert result["internals"]["risk_level"] in {"medium", "high"}
    assert result["internals_pct"] == 46.0
    assert result["attendance"] is not result["internals"]


def test_missing_marks_are_not_misreported_as_low_risk():
    cfg = {"attendance_min_pct": 75.0, "component_alert_pct": 40.0, "pass_mark_pct": 40.0}
    result = student_risk_signals({"attendance": None, "quiz": None, "assignment": None, "practical": None}, cfg)
    assert result["attendance"]["risk_level"] is None
    assert result["internals"]["risk_level"] is None
    assert result["internals_pct"] is None


def test_python_subject_gets_internship_project_advice():
    feedback = internship_feedback_for_course(
        "CS303", "Python Programming",
        {"quiz": 55.0, "assignment": 62.0, "practical": 45.0}, 54.0,
    )
    assert feedback
    assert feedback[0]["skill"] == "Keep practising"
    python_advice = next(item for item in feedback if item["skill"] == "Python problem-solving and portfolio")
    assert "GitHub" in python_advice["action"]
    assert feedback[0]["recommended_books"]
    assert feedback[0]["recommended_books"][0] == "Python Crash Course"
    assert "internship" in feedback[0]["internship_link"].lower()


def test_professional_communication_gets_interview_focused_advice():
    feedback = internship_feedback_for_course(
        "PC301", "Professional Communication",
        {"quiz": 62.0, "assignment": 58.0, "practical": 70.0}, 63.0,
    )
    communication_advice = next(item for item in feedback if item["skill"] == "Professional communication")
    assert "self-introduction" in communication_advice["action"]
    assert feedback[0]["priority"] == "medium"


def test_data_structures_and_networking_receive_subject_specific_resources():
    ds = internship_feedback_for_course("CS304", "Data Structures", {"quiz": 82, "assignment": 80, "practical": 85}, 82)
    cn = internship_feedback_for_course("CS305", "Computer Networks", {"quiz": 35, "assignment": 40, "practical": 38}, 38)
    assert ds[0]["priority"] == "low"
    assert "Grokking Algorithms" in ds[0]["recommended_books"]
    assert cn[0]["priority"] == "high"
    assert "Computer Networking: A Top-Down Approach" in cn[0]["recommended_books"]


def test_unmapped_course_does_not_get_unrelated_book_recommendations():
    feedback = internship_feedback_for_course(
        "HS101", "History", {"quiz": 70, "assignment": 72}, 71,
    )
    assert feedback
    assert all(not item.get("recommended_books") for item in feedback)
