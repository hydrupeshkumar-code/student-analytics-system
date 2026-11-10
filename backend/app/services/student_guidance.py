"""Student-facing, explainable risk signals and internship-readiness guidance.

These checks complement (and do not replace) the platform's trained overall
failure-risk model. Attendance and internal-assessment signals are calculated
independently so students can see exactly what to improve.
"""
from __future__ import annotations

from statistics import mean


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 1)


def _level(index: float | None) -> str | None:
    if index is None:
        return None
    if index >= 70:
        return "high"
    if index >= 40:
        return "medium"
    return "low"


def student_risk_signals(components: dict, cfg: dict) -> dict:
    """Create distinct threshold-based attendance and internal risk indicators.

    The displayed number is a *risk index*, not a statistical probability. It is
    intentionally transparent because the system does not train separate models
    for attendance and internal marks.
    """
    attendance = components.get("attendance")
    minimum = float(cfg.get("attendance_min_pct", 75.0))
    if attendance is None:
        attendance_signal = {
            "risk_level": None,
            "risk_index": None,
            "value_pct": None,
            "target_pct": minimum,
            "summary": "Attendance data is not available yet.",
            "actions": ["Check with your faculty that attendance has been entered and released."],
        }
    else:
        attendance = float(attendance)
        if attendance < minimum:
            index = _clip(35 + (minimum - attendance) * 5)
            summary = f"Attendance is {attendance:.1f}%, below the {minimum:.0f}% requirement."
            actions = [
                "Attend every remaining class and avoid preventable absences.",
                "Meet your faculty mentor to confirm the number of classes remaining and the recovery plan.",
            ]
        else:
            index = _clip(35 - (attendance - minimum) * 2, 5, 35)
            summary = (f"Attendance is {attendance:.1f}%, meeting the {minimum:.0f}% requirement. "
                       "Keep a buffer by attending upcoming classes.")
            actions = ["Maintain attendance above the minimum; do not rely on the current margin alone."]
        attendance_signal = {
            "risk_level": _level(index),
            "risk_index": index,
            "value_pct": round(attendance, 1),
            "target_pct": minimum,
            "summary": summary,
            "actions": actions,
        }

    internal_keys = ("quiz", "assignment", "practical")
    available = {key: components.get(key) for key in internal_keys if components.get(key) is not None}
    internal_pct = round(mean(float(v) for v in available.values()), 1) if available else None
    # 60% is an improvement/readiness target, not an institution pass rule.
    internal_target = 60.0
    if internal_pct is None:
        internal_signal = {
            "risk_level": None,
            "risk_index": None,
            "value_pct": None,
            "target_pct": internal_target,
            "based_on": [],
            "components": available,
            "summary": "Internal-assessment marks are not available yet.",
            "actions": ["Complete the first released quiz, assignment or practical so progress can be assessed."],
        }
    else:
        if internal_pct < internal_target:
            index = _clip(35 + (internal_target - internal_pct) * 2)
            weak = sorted(available.items(), key=lambda item: float(item[1]))
            weakest = weak[0][0] if weak else "internal assessments"
            summary = (f"Internal-assessment average is {internal_pct:.1f}%, below the "
                       f"{internal_target:.0f}% improvement target. Weakest available area: {weakest}.")
            actions = [
                f"Prioritise {weakest} in your next study session; review faculty feedback and redo missed questions.",
                "Set a weekly target: two focused practice sessions and one review of mistakes before each assessment.",
            ]
        else:
            index = _clip(35 - (internal_pct - internal_target) * 1.5, 5, 35)
            summary = (f"Internal-assessment average is {internal_pct:.1f}%, meeting the "
                       f"{internal_target:.0f}% improvement target. Keep practising to build internship-ready evidence.")
            actions = ["Maintain your results and turn the strongest topic into a small portfolio project or worked example."]
        internal_signal = {
            "risk_level": _level(index),
            "risk_index": index,
            "value_pct": internal_pct,
            "target_pct": internal_target,
            "based_on": list(available.keys()),
            "components": available,
            "summary": summary,
            "actions": actions,
        }

    return {"attendance": attendance_signal, "internals": internal_signal, "internals_pct": internal_pct}


def internship_feedback_for_course(code: str, name: str, components: dict, internals_pct: float | None) -> list[dict]:
    """Return practical, course-aware internship preparation suggestions."""
    subject = f"{code} {name}".lower()
    quiz = components.get("quiz")
    assignment = components.get("assignment")
    practical = components.get("practical")
    feedback: list[dict] = []

    # Performance-tiered guidance combines course performance with concrete, credible
    # learning resources. This is coaching guidance, not a placement guarantee.
    resources = {
        "pc": ("The Pyramid Principle", "Talk Like TED"),
        "ds": ("Grokking Algorithms", "Cracking the Coding Interview"),
        "cn": ("Computer Networking: A Top-Down Approach", "Networking All-in-One For Dummies"),
        "python": ("Python Crash Course", "Automate the Boring Stuff with Python"),
        "sql": ("Learning SQL", "SQL Queries for Mere Mortals"),
        "web": ("HTML and CSS: Design and Build Websites", "Eloquent JavaScript"),
        "os": ("Operating Systems: Three Easy Pieces",),
        "ml": ("Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow",),
    }
    if "professional communication" in subject or "communication skills" in subject or code.upper().startswith("PC"):
        key = "pc"
    elif "data structure" in subject or code.upper().startswith("DS") or code.upper().startswith("CS304"):
        key = "ds"
    elif "computer network" in subject or code.upper().startswith("CN") or code.upper().startswith("CS305"):
        key = "cn"
    elif any(term in subject for term in ("python", "programming", "coding")):
        key = "python"
    elif any(term in subject for term in ("database", "sql")):
        key = "sql"
    elif any(term in subject for term in ("web development", "web technology", "web programming")):
        key = "web"
    elif "operating system" in subject:
        key = "os"
    elif any(term in subject for term in ("machine learning", "artificial intelligence")):
        key = "ml"
    else:
        key = "general"
    if internals_pct is not None:
        if internals_pct >= 75:
            tier, priority = "Good progress", "low"
            why = f"Your assessment average is {internals_pct:.0f}%, which is a strong start. Use what you learned in a small project."
            action = (f"Read {resources[key][0]} and then {resources[key][-1]}. Build a small project for this subject, explain how it works in a README, and practise showing it to someone." if key != "general" else "Choose a harder topic from this course, build a small project, and practise explaining how it works.")
        elif internals_pct >= 50:
            tier, priority = "Keep practising", "medium"
            why = f"Your assessment average is {internals_pct:.0f}%. Review topics you found difficult and practise them each week."
            action = (f"Review the two topics you found hardest. Use {resources[key][0]} to help, practise three related tasks each week, and explain what you learned." if key != "general" else "Review the two topics you found hardest. Practise three related tasks each week and explain what you learned.")
        else:
            tier, priority = "Ask for extra help", "high"
            why = f"Your assessment average is {internals_pct:.0f}%. Spend time on the basic topics first. This is a sign to get support, not a judgement of your ability."
            action = (f"Start with the first chapters of {resources[key][0]}. Ask your teacher for help, review one topic at a time, and redo questions you got wrong." if key != "general" else "Ask your teacher for help with the basic topics. Review one topic at a time and redo questions you got wrong.")
        feedback.append({
            "skill": tier,
            "priority": priority,
            "why": why,
            "action": action,
            "internship_link": "Build demonstrable skills for internship screening, technical interviews and project discussions.",
            "recommended_books": list(resources[key]) if key != "general" else [],
        })

    is_pc = "professional communication" in subject or "communication skills" in subject or code.upper().startswith("PC")
    is_python = "python" in subject or "programming" in subject or "coding" in subject

    if is_pc:
        signal = assignment if assignment is not None else internals_pct
        detail = f"Your writing/assignment score is {signal:.0f}%" if signal is not None else "Communication marks are not released yet"
        feedback.append({
            "skill": "Professional communication",
            "priority": "high" if signal is not None and signal < 60 else "medium",
            "why": detail + "; communication is used in recruiter messages, interviews and team hand-offs.",
            "action": "Each week, write one concise professional email, practise a 60-second self-introduction, and record a 3-minute explanation of a project. Ask a peer to review clarity and structure.",
            "internship_link": "Recruiter communication, interviews, presentations and teamwork.",
        })
    elif is_python:
        signal = practical if practical is not None else internals_pct
        detail = f"Your practical score is {signal:.0f}%" if signal is not None else "Practical marks are not released yet"
        feedback.append({
            "skill": "Python problem-solving and portfolio",
            "priority": "high" if signal is not None and signal < 60 else "medium",
            "why": detail + "; internship tasks often require turning a problem into working, testable code.",
            "action": "Build a small task list, a tool that reads a data file, and a simple web service in Python. Put each project on GitHub with a short guide and a few tests. Practise explaining how your code works.",
            "internship_link": "Python development, automation, data handling and entry-level software roles.",
        })
    elif key == "ds":
        signal = practical if practical is not None else internals_pct
        feedback.append({
            "skill": "Data structures and coding interviews",
            "priority": "high" if signal is not None and signal < 50 else "medium",
            "why": f"Current practical/overall signal: {signal:.0f}%" if signal is not None else "Practical marks are not released yet; build your skills with a repeatable practice routine.",
            "action": "Practise common topics such as lists, queues, trees and maps. For each problem, write down your first idea, improve it, and test unusual cases. Share a few finished examples with clear notes.",
            "internship_link": "DSA screening rounds and entry-level software engineering internships.",
        })
    elif key == "cn":
        signal = practical if practical is not None else internals_pct
        feedback.append({
            "skill": "Networking fundamentals and troubleshooting",
            "priority": "high" if signal is not None and signal < 50 else "medium",
            "why": f"Current practical/overall signal: {signal:.0f}%" if signal is not None else "Practical marks are not released yet; build confidence with small network labs.",
            "action": "Review IP addresses, DNS, HTTP and routing. Build a small network in Packet Tracer, use its tools to find one connection problem, and save a short report with screenshots.",
            "internship_link": "Network support, cloud support, cybersecurity and infrastructure internships.",
        })
    elif not any(value is not None for value in (quiz, assignment, practical)):
        feedback.append({
            "skill": "Start building internship evidence",
            "priority": "medium",
            "why": "Subject marks are not available yet, so this is a starter suggestion rather than a judgement about your performance.",
            "action": "Choose one topic from this course and practise it with a small task. Write what you did and how you checked your work. Save it so you can improve it later.",
            "internship_link": "Building a portfolio habit and showing how you learn independently.",
        })
    elif practical is not None and practical < 60:
        feedback.append({
            "skill": "Hands-on problem solving",
            "priority": "high",
            "why": f"Your practical component is {practical:.0f}%; applied skills need more practice before you can demonstrate them confidently.",
            "action": "Complete one small hands-on exercise each week, document the steps and outcome, and practise explaining how you tested and debugged it.",
            "internship_link": "Demonstrating practical ability in technical internship interviews and assignments.",
        })
    elif assignment is not None and assignment < 60:
        feedback.append({
            "skill": "Deliverables and documentation",
            "priority": "high",
            "why": f"Your assignment component is {assignment:.0f}%; employers value complete, readable deliverables as well as correct answers.",
            "action": "Before submitting work, use a checklist for requirements, correctness, formatting and explanation. Keep a short project log and add screenshots or examples that prove the result.",
            "internship_link": "Reliable task delivery, documentation and hand-off to teammates.",
        })
    elif quiz is not None and quiz < 60:
        feedback.append({
            "skill": "Core concepts and interview practice",
            "priority": "medium",
            "why": f"Your quiz average is {quiz:.0f}%; stronger fundamentals make technical interview questions easier to explain.",
            "action": "Create a one-page summary for each topic, solve five practice questions a week, and explain one solution aloud without notes.",
            "internship_link": "Technical screening tests and clear reasoning during interviews.",
        })
    else:
        feedback.append({
            "skill": "Turn coursework into evidence",
            "priority": "medium",
            "why": "Your visible course data does not show a single urgent weakness; the next step is to demonstrate what you can do.",
            "action": "Choose one concept from this subject and create a concise portfolio artefact: a worked example, short presentation, mini-project or case study. Include what you learned and how you validated the result.",
            "internship_link": "A portfolio that helps you discuss real work in applications and interviews.",
        })

    # Add a focused action when one of the other internal components is a clear weakness.
    weak_components = [("quiz", quiz), ("assignment", assignment), ("practical", practical)]
    weak_components = [(k, float(v)) for k, v in weak_components if v is not None and float(v) < 45]
    if weak_components and feedback:
        weakest, value = min(weak_components, key=lambda pair: pair[1])
        if not (is_python and weakest == "practical"):
            labels = {"quiz": "topic revision", "assignment": "assignment quality", "practical": "hands-on practice"}
            feedback.append({
                "skill": labels[weakest].capitalize(),
                "priority": "high",
                "why": f"The {weakest} component is currently {value:.0f}% and is a specific area to improve.",
                "action": f"Review the feedback for your {weakest}, identify the first two mistakes, then redo the questions or task and compare the new result.",
                "internship_link": "Showing that you can accept feedback and improve your work.",
            })
    return feedback


def aggregate_internship_feedback(course_items: list[dict]) -> list[dict]:
    """Pick the most actionable student-specific items without flooding the report."""
    all_items = []
    seen = set()
    for course in course_items:
        for item in course.get("internship_feedback", []):
            key = (item.get("skill"), item.get("action"))
            if key in seen:
                continue
            seen.add(key)
            all_items.append({**item, "course_code": course.get("code"), "course_name": course.get("name")})
    # High-priority gaps first, keep the personal plan short enough to act on.
    all_items.sort(key=lambda x: (0 if x.get("priority") == "high" else 1, x.get("skill", "")))
    return all_items[:6]
