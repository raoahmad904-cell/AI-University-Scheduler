import csv
import json
from pathlib import Path
import yaml
from .csv_loader import UPLOAD_DIR, parse_csv_text

DATA_DIR = Path(__file__).parent.parent / "data"

# Programs that should be excluded from the project entirely.
_DISABLED_PROGRAMS = {"MS", "PHD"}

def _norm_program(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip().upper()
    return s or None

def _infer_program_from_course_id(course_id: str) -> str | None:
    cid = (course_id or "").strip().upper()
    if not cid: return None
    if "PHD" in cid: return "PHD"
    if "MS" in cid: return "MS"
    if "BS" in cid: return "BS"
    return None

def _infer_program_from_student_id(student_id: str) -> str | None:
    sid = (student_id or "").strip().upper()
    if not sid: return None
    parts = sid.split("_")
    if len(parts) >= 3 and parts[2] in {"BS", "MS", "PHD"}:
        return parts[2]
    if "_PHD_" in sid or "PHD" in sid: return "PHD"
    if "_MS_" in sid or "MS" in sid: return "MS"
    if "_BS_" in sid or "BS" in sid: return "BS"
    return None

def _filter_disabled_programs(*, rooms, students, exams, teachers, courses, disabled_programs=_DISABLED_PROGRAMS):
    disabled = {p.strip().upper() for p in disabled_programs if str(p).strip()}
    if not disabled:
        return rooms, students, exams, teachers, courses

    filtered_students = {}
    for sid, s in students.items():
        program = _norm_program(s.get("program")) if isinstance(s, dict) else None
        program = program or _infer_program_from_student_id(sid)
        if program in disabled: continue
        filtered_students[sid] = s

    filtered_courses = {}
    for cid, c in courses.items():
        program = _norm_program(c.get("program")) if isinstance(c, dict) else None
        program = program or _infer_program_from_course_id(cid)
        if program in disabled: continue
        filtered_courses[cid] = c

    filtered_exams = {}
    for eid, e in exams.items():
        if not isinstance(e, dict): continue
        student_ids = e.get("student_ids") or []
        if not isinstance(student_ids, list): student_ids = []
        student_ids = [sid for sid in student_ids if sid in filtered_students]
        if not student_ids: continue
        e2 = dict(e)
        e2["student_ids"] = student_ids
        filtered_exams[eid] = e2

    return rooms, filtered_students, filtered_exams, teachers, filtered_courses

def load_yaml(path: Path):
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f)

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

def _rows_to_dict(rows):
    data = {}
    for idx, row in enumerate(rows):
        key = row.get("id", str(idx)) if isinstance(row, dict) else str(idx)
        data[key] = row
    return data

def _split_semicolon(value):
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace("|", ";").split(";") if p.strip()]
        return parts
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []

# --- NEW FUNCTION: NORMALIZE STUDENTS ---
def _normalize_students(students: dict) -> dict:
    fixed = {}
    for key, s in students.items():
        if not isinstance(s, dict): continue
        sid = s.get("id") or key
        
        # FIX: Ensure enrolled_courses is a LIST, not a string
        enrolled_raw = s.get("enrolled_courses")
        if enrolled_raw:
            enrolled = _split_semicolon(enrolled_raw)
        else:
            enrolled = []
            
        fixed[sid] = {
            **s, 
            "id": sid, 
            "enrolled_courses": enrolled
        }
    return fixed

def _normalize_courses(courses: dict) -> dict:
    fixed = {}
    for key, c in courses.items():
        if not isinstance(c, dict): continue
        cid = c.get("id") or key
        sections = c.get("sections")
        sections_list = _split_semicolon(sections) if sections else ["A"]
        lab_required_raw = c.get("lab_required")
        if isinstance(lab_required_raw, str):
            lab_required = lab_required_raw.strip().lower() in {"true", "1", "yes", "y"}
        else:
            lab_required = bool(lab_required_raw)
        
        credits_raw = c.get("credits") or c.get("credit_hours")
        hours_raw = c.get("hours_per_week")
        try: credits = int(float(str(credits_raw).strip())) if credits_raw is not None else None
        except: credits = None
        try: hours = int(float(str(hours_raw).strip())) if hours_raw is not None else None
        except: hours = None
        
        fixed[cid] = {**c, "id": cid, "sections": sections_list, "lab_required": lab_required, "credits": credits, "hours_per_week": hours}
    return fixed

def _normalize_teachers(teachers: dict) -> dict:
    fixed = {}
    for key, t in teachers.items():
        if not isinstance(t, dict): continue
        tid = t.get("id") or key
        avail_raw = t.get("availability")
        avail = _split_semicolon(avail_raw) if avail_raw else []
        fixed[tid] = {**t, "id": tid, "availability": avail or t.get("availability", [])}
    return fixed

def _normalize_rooms(rooms: dict) -> dict:
    fixed = {}
    for key, r in rooms.items():
        if not isinstance(r, dict): continue
        rid = r.get("id") or key
        tags = list(r.get("tags", [])) if isinstance(r.get("tags"), list) else []
        if "lab" in (r.get("type") or "").lower() and "lab" not in tags: tags.append("lab")
        try: cap = int(r.get("capacity"))
        except: cap = 0
        fixed[rid] = {**r, "id": rid, "capacity": cap, "tags": tags}
    return fixed

def _normalize_exams(exams: dict) -> dict:
    fixed = {}
    for key, exam in exams.items():
        if not isinstance(exam, dict): continue
        eid = exam.get("id") or exam.get("exam_id") or key
        raw_s = exam.get("student_ids") or exam.get("student_id") or exam.get("students") or ""
        s_ids = _split_semicolon(raw_s) if isinstance(raw_s, str) else (raw_s if isinstance(raw_s, list) else [])
        fixed[eid] = {**exam, "id": eid, "student_ids": s_ids}
    return fixed

def load_with_override(kind: str, default_filename: str):
    upload_json = UPLOAD_DIR / f"{kind}.json"
    upload_csv = UPLOAD_DIR / f"{kind}.csv"
    
    data = {}
    if upload_json.exists():
        try: data = _rows_to_dict(load_json(upload_json))
        except: pass
    elif upload_csv.exists():
        try: data = _rows_to_dict(parse_csv_text(upload_csv.read_text(encoding="utf-8")))
        except: pass
    else:
        data = load_yaml(DATA_DIR / default_filename)

    # Normalize data immediately after loading
    if kind == "exams": return _normalize_exams(data)
    elif kind == "courses": return _normalize_courses(data)
    elif kind == "teachers": return _normalize_teachers(data)
    elif kind == "rooms": return _normalize_rooms(data)
    elif kind == "students": return _normalize_students(data) # <-- Added this!
    return data

def load_all_data():
    rooms = load_with_override("rooms", "rooms.yaml")
    students = load_with_override("students", "students.yaml")
    exams = load_with_override("exams", "exams.yaml")
    teachers = load_with_override("teachers", "teachers.yaml")
    courses = load_with_override("courses", "courses.yaml")
    timeslots = load_yaml(DATA_DIR / "timeslots.yaml")
    
    rooms, students, exams, teachers, courses = _filter_disabled_programs(
        rooms=rooms, students=students, exams=exams, teachers=teachers, courses=courses
    )

    # Inject explicit start/end times for exams
    for tid, slot in timeslots.items():
        if slot.get("type") == "exam":
            # Default fallback
            slot["start_time"] = "09:00"
            slot["end_time"] = "12:00"
            
            if tid.endswith("_M"):
                slot["start_time"] = "09:00"
                slot["end_time"] = "12:00"
            elif tid.endswith("_E"):
                slot["start_time"] = "14:00"
                slot["end_time"] = "17:00"

    return rooms, students, exams, teachers, courses, timeslots