from app.models import HistoricalRecord
from app.services import prediction
from tests.conftest import login


def _assessment(client, h, cid, **kw):
    body = {"title": "Quiz", "component": "quiz", "max_marks": 20, "weightage": 50, **kw}
    r = client.post(f"/api/courses/{cid}/assessments", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _open(client, h, aid):
    assert client.post(f"/api/assessments/{aid}/status", headers=h, json={"status": "in_progress"}).status_code == 200


# ------------------------------------------------------------------ auth & security

def test_login_throttle_and_bad_password(client, world):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "fac@x.edu", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "fac@x.edu", "password": "Passw0rd!"}).status_code == 429


def test_password_change_revokes_old_tokens(client, world):
    old = world["F"]
    r = client.post("/api/auth/change-password", headers=old,
                    json={"current_password": "Passw0rd!", "new_password": "NewPassw0rd"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=old).status_code == 401
    assert login(client, "fac@x.edu", "NewPassw0rd")


def test_refresh_token(client, world):
    r = client.post("/api/auth/login", json={"email": "fac@x.edu", "password": "Passw0rd!"}).json()
    r2 = client.post("/api/auth/refresh", json={"refresh_token": r["refresh_token"]})
    assert r2.status_code == 200
    # an access token cannot be used as a refresh token
    assert client.post("/api/auth/refresh", json={"refresh_token": r["access_token"]}).status_code == 401


def test_role_and_object_permissions(client, world):
    cid = world["course"]["id"]
    assert client.get("/api/admin/overview", headers=world["F"]).status_code == 403
    assert client.get(f"/api/courses/{cid}/gradebook", headers=world["O"]).status_code == 403   # other faculty
    assert client.get(f"/api/courses/{cid}/gradebook", headers=world["S1"]).status_code == 403  # student
    assert client.get(f"/api/me/courses/{cid}", headers=world["S1"]).status_code == 200
    assert client.post("/api/courses", headers=world["F"], json={}).status_code in (403, 422)
    # faculty may change weights but not reassign the course
    assert client.patch(f"/api/courses/{cid}", headers=world["F"], json={"faculty_id": None}).status_code == 403


# ------------------------------------------------------------------ rubric engine & CP aggregation

def test_rubric_scoring_and_gradebook(client, world):
    F, cid = world["F"], world["course"]["id"]
    s1, s2, s3 = (s.id for s in world["students"])
    rub = client.post("/api/rubrics", headers=F, json={
        "title": "R", "levels": [{"label": "Good", "points": 4}, {"label": "Poor", "points": 1}],
        "criteria": [{"name": "A", "weight": 75}, {"name": "B", "weight": 25}]}).json()
    good, poor = rub["levels"][0]["id"], rub["levels"][1]["id"]
    ca, cb = rub["criteria"][0]["id"], rub["criteria"][1]["id"]

    quiz = _assessment(client, F, cid, weightage=40)
    asg = _assessment(client, F, cid, title="Asg", component="assignment", max_marks=40, weightage=40, rubric_id=rub["id"])
    att = _assessment(client, F, cid, title="Att", component="attendance", max_marks=10, weightage=20, sessions_held=40)
    for a in (quiz, asg, att):
        _open(client, F, a["id"])

    # marks cannot exceed maximum
    r = client.put(f"/api/assessments/{quiz['id']}/scores", headers=F, json={"scores": [{"student_id": s1, "marks": 25}]})
    assert r.status_code == 422
    client.put(f"/api/assessments/{quiz['id']}/scores", headers=F, json={"scores": [
        {"student_id": s1, "marks": 18}, {"student_id": s2, "marks": 6}, {"student_id": s3, "is_absent": True}]})
    # A good (75 * 4/4) + B poor (25 * 1/4) = 81.25% of 40 = 32.5
    r = client.put(f"/api/assessments/{asg['id']}/scores", headers=F, json={"scores": [
        {"student_id": s1, "criteria": {str(ca): good, str(cb): poor}, "feedback": "ok"}]})
    row = next(x for x in r.json()["rows"] if x["student_id"] == s1)
    assert row["marks"] == 32.5
    # incomplete rubric is rejected
    r = client.put(f"/api/assessments/{asg['id']}/scores", headers=F, json={"scores": [
        {"student_id": s2, "criteria": {str(ca): good}}]})
    assert r.status_code == 422
    r = client.put(f"/api/assessments/{att['id']}/scores", headers=F, json={"scores": [
        {"student_id": s1, "attended": 30}, {"student_id": s2, "attended": 20}]})
    assert r.status_code == 200

    gb = client.get(f"/api/courses/{cid}/gradebook", headers=F).json()
    st = {s["student_id"]: s for s in gb["students"]}
    # s1: quiz 90% *40 + asg 81.25% *40 + att 75% *20 = 83.5
    assert st[s1]["cp_pct"] == 83.5
    assert st[s1]["components"]["attendance"] == 75.0
    # s2: quiz 30% (w40) + att 50% (w20), assignment not yet scored -> (1200+1000)/60
    assert st[s2]["cp_pct"] == round(2200 / 60, 2)
    assert any("Attendance" in f for f in st[s2]["flags"])
    assert st[s3]["assessments"][str(quiz["id"])]["absent"] is True

    # students see nothing until the assessment is completed
    me = client.get(f"/api/me/courses/{cid}", headers=world["S1"]).json()
    assert me["assessments"] == []
    client.post(f"/api/assessments/{asg['id']}/status", headers=F, json={"status": "completed"})
    me = client.get(f"/api/me/courses/{cid}", headers=world["S1"]).json()
    assert me["assessments"][0]["marks"] == 32.5
    assert me["assessments"][0]["rubric"]["criteria"][0]["selected_level_id"] == good

    # weightage cap and lifecycle rules
    assert client.post(f"/api/courses/{cid}/assessments", headers=F, json={
        "title": "X", "component": "quiz", "max_marks": 10, "weightage": 5}).status_code == 422
    assert client.post(f"/api/assessments/{asg['id']}/status", headers=F, json={"status": "draft"}).status_code == 409
    client.post(f"/api/assessments/{asg['id']}/status", headers=F, json={"status": "finalized"})
    assert client.post(f"/api/assessments/{asg['id']}/status", headers=F, json={"status": "in_progress"}).status_code == 403
    assert client.post(f"/api/assessments/{asg['id']}/status", headers=world["A"], json={"status": "in_progress"}).status_code == 200


# ------------------------------------------------------------------ NCP, final result and CO/PO attainment

def test_ncp_final_and_attainment(client, world):
    F, cid = world["F"], world["course"]["id"]
    s1, s2, s3 = (s.id for s in world["students"])
    co1 = client.post(f"/api/courses/{cid}/outcomes", headers=F, json={"code": "CO1", "description": "x"}).json()
    co2 = client.post(f"/api/courses/{cid}/outcomes", headers=F, json={"code": "CO2", "description": "y"}).json()
    pos = client.get(f"/api/courses/{cid}/co-po", headers=F).json()["pos"]
    client.put(f"/api/courses/{cid}/co-po", headers=F, json=[
        {"co_id": co1["id"], "po_id": pos[0]["id"], "strength": 3},
        {"co_id": co2["id"], "po_id": pos[0]["id"], "strength": 1}])

    q = _assessment(client, F, cid, weightage=100, co_ids=[co1["id"]])
    _open(client, F, q["id"])
    client.put(f"/api/assessments/{q['id']}/scores", headers=F, json={"scores": [
        {"student_id": s1, "marks": 16}, {"student_id": s2, "marks": 14}, {"student_id": s3, "marks": 4}]})
    r = client.put(f"/api/courses/{cid}/ncp", headers=F, json={"results": [
        {"student_id": s1, "marks": 70}, {"student_id": s2, "marks": 30}, {"student_id": s3, "is_absent": True}]})
    assert r.status_code == 200
    assert client.put(f"/api/courses/{cid}/ncp", headers=F, json={"results": [
        {"student_id": s1, "marks": 170}]}).status_code == 422

    gb = {s["student_id"]: s for s in client.get(f"/api/courses/{cid}/gradebook", headers=F).json()["students"]}
    assert gb[s1]["final_pct"] == 75.0 and gb[s1]["passed"] is True and gb[s1]["grade"] == "A"
    # s2: final = (70 + 30)/2 = 50 but NCP 30% < 35% minimum -> fail
    assert gb[s2]["final_pct"] == 50.0 and gb[s2]["passed"] is False and gb[s2]["grade"] == "F"
    assert gb[s3]["passed"] is False

    att = client.get(f"/api/courses/{cid}/attainment", headers=F).json()
    c1 = next(c for c in att["cos"] if c["code"] == "CO1")
    # CP: 2/3 students >= 60% -> 66.7% -> level 2; NCP: 1/3 -> 33% -> level 0; CO = (2*50 + 0*50)/100 = 1.0
    assert c1["cp"]["level"] == 2 and c1["ncp"]["level"] == 0 and c1["attainment"] == 1.0
    c2 = next(c for c in att["cos"] if c["code"] == "CO2")
    assert c2["basis"] == "NCP only" and c2["attainment"] == 0.0
    po1 = next(p for p in att["pos"] if p["code"] == "PO1")
    assert po1["attainment"] == round((1.0 * 3 + 0.0 * 1) / 4, 2)

    for ext, magic in (("pdf", b"%PDF"), ("xlsx", b"PK")):
        r = client.get(f"/api/courses/{cid}/attainment.{ext}", headers=F)
        assert r.status_code == 200 and r.content.startswith(magic)

    # student cannot see NCP until published
    me = client.get(f"/api/me/courses/{cid}", headers=world["S1"]).json()
    assert me["ncp_pct"] is None
    client.patch(f"/api/courses/{cid}", headers=F, json={"ncp_published": True})
    me = client.get(f"/api/me/courses/{cid}", headers=world["S1"]).json()
    # quiz marking still open -> NCP visible but no final grade yet
    assert me["ncp_pct"] == 70.0 and me["grade"] is None and me["result_pending"] is True
    client.post(f"/api/assessments/{q['id']}/status", headers=F, json={"status": "completed"})
    me = client.get(f"/api/me/courses/{cid}", headers=world["S1"]).json()
    assert me["final_pct"] == 75.0 and me["grade"] == "A" and me["result_pending"] is False
    assert client.get("/api/me/report.pdf", headers=world["S1"]).content.startswith(b"%PDF")


# ------------------------------------------------------------------ predictive early warning

def test_training_and_prediction(client, world, db):
    db.add_all(prediction.synthetic_history(400))
    db.commit()
    r = client.post("/api/ml/train", headers=world["A"], json={"algorithm": "auto"})
    assert r.status_code == 200, r.text
    m = r.json()["metrics"]
    assert m["holdout"]["roc_auc"] > 0.75
    assert set(m["cv"]) == {"logistic_regression", "decision_tree"}

    F, cid = world["F"], world["course"]["id"]
    s1, s2, _ = (s.id for s in world["students"])
    q = _assessment(client, F, cid, weightage=60)
    att = _assessment(client, F, cid, title="Att", component="attendance", max_marks=10, weightage=40, sessions_held=40)
    _open(client, F, q["id"])
    _open(client, F, att["id"])
    client.put(f"/api/assessments/{q['id']}/scores", headers=F, json={"scores": [
        {"student_id": s1, "marks": 19}, {"student_id": s2, "marks": 3}]})
    client.put(f"/api/assessments/{att['id']}/scores", headers=F, json={"scores": [
        {"student_id": s1, "attended": 39}, {"student_id": s2, "attended": 18}]})
    rows = {r["student_id"]: r for r in client.post(f"/api/courses/{cid}/risk/recompute", headers=F).json()["students"]}
    assert rows[s2]["risk_level"] == "high" and rows[s2]["method"] == "ml"
    assert rows[s1]["risk_level"] == "low"
    assert rows[s2]["probability"] > rows[s1]["probability"]
    assert rows[s2]["reasons"]

    me = client.get(f"/api/me/courses/{cid}", headers=login(client, "s2@x.edu")).json()
    assert me["risk"]["risk_level"] == "high" and me["risk"]["suggestions"]


def test_training_requires_data(client, world, db):
    assert client.post("/api/ml/train", headers=world["A"], json={}).status_code == 422
    db.add_all([HistoricalRecord(source="import", cp_pct=50, passed=True) for _ in range(60)])
    db.commit()
    # only one class present
    assert client.post("/api/ml/train", headers=world["A"], json={}).status_code == 422


# ------------------------------------------------------------------ admin

def test_user_import_and_audit(client, world):
    csv = ("name,email,role,roll_no,program_code\n"
           "New One,new1@x.edu,student,N1,BT\n"
           "New Two,new2@x.edu,faculty,,\n").encode()
    r = client.post("/api/users/import", headers=world["A"], files={"file": ("u.csv", csv, "text/csv")})
    assert r.status_code == 200 and r.json()["created"] == 2
    temp = r.json()["credentials"][1][3]
    me = client.post("/api/auth/login", json={"email": "new1@x.edu", "password": temp}).json()
    assert me["user"]["must_change_password"] is True
    # duplicate import is rejected atomically
    r = client.post("/api/users/import", headers=world["A"], files={"file": ("u.csv", csv, "text/csv")})
    assert r.json()["created"] == 0 and r.json()["errors"]
    log = client.get("/api/audit", headers=world["A"]).json()
    assert any(i["action"] == "users_imported" for i in log["items"])


def test_csv_formula_injection_is_neutralised(client, world):
    from app.utils import _safe
    assert _safe("=HYPERLINK(1)").startswith("'")
    assert _safe("-5") == "-5"
