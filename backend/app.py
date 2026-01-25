from collections import Counter
import json
from pathlib import Path
from typing import Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from scheduler.utils.loader import load_all_data
from scheduler.algorithms.exam_room_allocator import ExamRoomAllocator
from scheduler.algorithms.exam_timetable_ga import ExamTimetableGA
from scheduler.algorithms.class_timetable_csp import ClassTimetableCSP
from scheduler.algorithms.lab_timetable_csp import LabTimetableCSP
from scheduler.solvers.evaluator import exam_timetable_metrics
from scheduler.utils.csv_loader import UPLOAD_DIR, parse_csv_text, save_csv_and_json

app = FastAPI(title="AI University Scheduler")


# ---------------- Timetable cache (stability) ----------------
_TIMETABLE_CACHE: dict[str, Any] | None = None
_TIMETABLE_CACHE_PATH = Path(UPLOAD_DIR) / "generated_timetable.json"
_TIMETABLE_CACHE_VERSION = 5


def _clear_timetable_cache() -> None:
    global _TIMETABLE_CACHE
    _TIMETABLE_CACHE = None
    try:
        if _TIMETABLE_CACHE_PATH.exists():
            _TIMETABLE_CACHE_PATH.unlink()
    except Exception:
        pass


def _load_timetable_cache_from_disk() -> dict[str, Any] | None:
    try:
        if _TIMETABLE_CACHE_PATH.exists():
            return json.loads(_TIMETABLE_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _save_timetable_cache_to_disk(payload: dict[str, Any]) -> None:
    try:
        _TIMETABLE_CACHE_PATH.write_text(json.dumps(payload), encoding="utf-8")
    except Exception:
        pass


def _get_or_generate_full_timetable() -> dict[str, Any]:
    global _TIMETABLE_CACHE
    if isinstance(_TIMETABLE_CACHE, dict):
        return _TIMETABLE_CACHE

    disk = _load_timetable_cache_from_disk()
    if (
        isinstance(disk, dict)
        and disk.get("cache_version") == _TIMETABLE_CACHE_VERSION
        and disk.get("class_timetable")
        and disk.get("lab_timetable")
    ):
        _TIMETABLE_CACHE = disk
        return _TIMETABLE_CACHE

    rooms, students, exams, teachers, courses, timeslots = load_all_data()
    class_solver = ClassTimetableCSP(
        rooms=rooms,
        teachers=teachers,
        courses=courses,
        timeslots=timeslots,
        students=students,
    )
    class_tt = class_solver.solve()
    
    lab_solver = LabTimetableCSP(
        rooms=rooms,
        teachers=teachers,
        courses=courses,
        timeslots=timeslots,
        students=students,
        class_timetable=class_tt,
    )
    lab_tt = lab_solver.solve()

    _TIMETABLE_CACHE = {
        "cache_version": _TIMETABLE_CACHE_VERSION,
        "class_timetable": class_tt,
        "lab_timetable": lab_tt,
        "rooms": rooms,
        "teachers": teachers,
        "courses": courses,
        "timeslots": timeslots,
    }
    _save_timetable_cache_to_disk(_TIMETABLE_CACHE)
    return _TIMETABLE_CACHE

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5180",
        "http://127.0.0.1:5180",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------  user store ----------------
USERS = [
    {
        "email": "student@uni.edu",
        "password": "student@123",
        "role": "student",
        "name": "Student",
        "sections": ["CS101|A", "BBA201|A"],
    },
    {
        "email": "teacher@uni.edu",
        "password": "teacher@123",
        "role": "teacher",
        "name": "Faculty",
        "sections": [],
    },
    {
        "email": "coord@uni.edu",
        "password": "coord@123",
        "role": "coordinator",
        "name": "Mr Shehroz",
        "sections": [],
    },
]

# ---------------- Models ----------------
class AllocateRoomsRequest(BaseModel):
    exam_id: str
    mode: str
    exam_ids: Optional[List[str]] = None

class TimetableRequest(BaseModel):
    population: int = 60
    generations: int = 100

class CSVUploadRequest(BaseModel):
    csv_text: str

class LoginRequest(BaseModel):
    email: str
    password: str

# ---------------- Health ----------------
@app.get("/api/status")
def status():
    return {"status": "ok", "service": "AI University Scheduler"}


# ---------------- Auth (demo) ----------------
@app.post("/api/login")
def login(req: LoginRequest):
    user = next((u for u in USERS if u["email"] == req.email and u["password"] == req.password), None)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = f"demo-token-{user['email']}"
    return {
        "token": token,
        "role": user["role"],
        "name": user["name"],
        "email": user["email"],
        "sections": user.get("sections", []),
    }

# ---------------- Upload with persistence ----------------
@app.post("/api/upload/rooms")
def upload_rooms(req: CSVUploadRequest):
    rows = parse_csv_text(req.csv_text)
    if not rows: raise HTTPException(status_code=400, detail="No rows found")
    save_csv_and_json("rooms", req.csv_text, rows)
    _clear_timetable_cache()
    return {"count": len(rows), "rows": rows}

@app.post("/api/upload/teachers")
def upload_teachers(req: CSVUploadRequest):
    rows = parse_csv_text(req.csv_text)
    if not rows: raise HTTPException(status_code=400, detail="No rows found")
    save_csv_and_json("teachers", req.csv_text, rows)
    _clear_timetable_cache()
    return {"count": len(rows), "rows": rows}

@app.post("/api/upload/courses")
def upload_courses(req: CSVUploadRequest):
    rows = parse_csv_text(req.csv_text)
    if not rows: raise HTTPException(status_code=400, detail="No rows found")
    save_csv_and_json("courses", req.csv_text, rows)
    _clear_timetable_cache()
    return {"count": len(rows), "rows": rows}

@app.post("/api/upload/students")
def upload_students(req: CSVUploadRequest):
    rows = parse_csv_text(req.csv_text)
    if not rows: raise HTTPException(status_code=400, detail="No rows found")
    save_csv_and_json("students", req.csv_text, rows)
    _clear_timetable_cache()
    return {"count": len(rows), "rows": rows}

@app.post("/api/upload/exams")
def upload_exams(req: CSVUploadRequest):
    rows = parse_csv_text(req.csv_text)
    if not rows: raise HTTPException(status_code=400, detail="No rows found")
    save_csv_and_json("exams", req.csv_text, rows)
    return {"count": len(rows), "rows": rows}

# ---------------- Exam Room Allocation ----------------
@app.post("/api/allocate_rooms")
def allocate_rooms(req: AllocateRoomsRequest):
    try:
        rooms, students, exams, teachers, courses, timeslots = load_all_data()

        if req.exam_id not in exams:
            raise HTTPException(status_code=404, detail=f"Exam {req.exam_id} not found")

        exam = exams[req.exam_id]
        student_ids = exam.get("student_ids", [])
        missing_students = [sid for sid in student_ids if sid not in students]
        if missing_students:
            exam["student_ids"] = [sid for sid in student_ids if sid in students]
            if not exam["student_ids"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"No valid students found for exam {req.exam_id}.",
                )

        room_pool = rooms
        allocator = ExamRoomAllocator(rooms=room_pool, students=students, exams=exams)

        exam_ids = req.exam_ids or [req.exam_id]
        exam_ids = [eid for eid in exam_ids if eid in exams]
        if not exam_ids:
            raise HTTPException(status_code=400, detail="No valid exams for column mode")
        allocation = allocator.allocate_column_mix(exam_ids)
        mode_used = "column"

        explanation = []
        heatmap = {}

        if mode_used == "column":
            for rid, payload in allocation.items():
                if rid == "_unassigned": continue
                cap = room_pool[rid]["capacity"]
                used = payload.get("assigned_count", 0)
                util = used / cap if cap > 0 else 0.0
                heatmap[rid] = util
                explanation.append({
                    "room": rid,
                    "room_name": room_pool[rid].get("name", rid),
                    "capacity": cap,
                    "assigned_count": used,
                    "utilization": round(util, 3),
                    "columns": payload.get("columns"),
                    "seats_per_column": payload.get("seats_per_column"),
                    "comment": "Column-mix layout",
                })
        else:
            for rid, sids in allocation.items():
                cap = room_pool[rid]["capacity"]
                used = len(sids)
                util = used / cap if cap > 0 else 0.0
                heatmap[rid] = util
                deps = [students[s]["department"] for s in sids if s in students]
                dep_counter = Counter(deps)
                dominant_dep, dominant_count = dep_counter.most_common(1)[0] if dep_counter else (None, 0)
                mixed = len(dep_counter) > 1

                explanation.append({
                    "room": rid,
                    "room_name": room_pool[rid].get("name", rid),
                    "capacity": cap,
                    "assigned_count": used,
                    "utilization": round(util, 3),
                    "dominant_department": dominant_dep,
                    "is_mixed_departments": mixed,
                    "comment": "Mixed departments" if mixed else "Single department",
                })

        response = {
            "mode": mode_used,
            "exam_id": req.exam_id,
            "allocation": allocation,
            "explanation": explanation,
            "room_utilization_heatmap": heatmap,
        }

        if mode_used == "column" and "_unassigned" in allocation:
            response.setdefault("warnings", {})["unassigned"] = allocation["_unassigned"]

        if missing_students:
            response.setdefault("warnings", {})["missing_students"] = missing_students

        return response
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Allocation failed: {exc}")


@app.get("/api/exams")
def list_exams():
    _, _, exams, _, _, _ = load_all_data()
    return {"exams": list(exams.values())}

@app.post("/api/generate/exam_timetable")
def generate_exam_timetable(req: TimetableRequest):
    rooms, students, exams, teachers, courses, timeslots = load_all_data()
    ga = ExamTimetableGA(exams=exams, students=students, timeslots=timeslots)
    result = ga.run(population_size=req.population, generations=req.generations)

    chrom = result["best_chromosome"]
    metrics = exam_timetable_metrics(chrom, exams)

    slot_exam_list = {}
    slot_department_counts = {}
    for eid, slot in chrom.items():
        slot_exam_list.setdefault(slot, []).append(eid)

    for slot, exam_ids in slot_exam_list.items():
        deps = [exams[eid].get("department", "GEN") for eid in exam_ids]
        slot_department_counts[slot] = dict(Counter(deps))

    return {
        "chromosome": chrom,
        "best_fitness": result["best_fitness"],
        "fitness_history": result["fitness_history"],
        "metrics": metrics,
        "slot_exam_list": slot_exam_list,
        "slot_department_counts": slot_department_counts,
        "timeslots": timeslots,
    }

@app.post("/api/generate/timetable")
def generate_full_timetable():
    global _TIMETABLE_CACHE
    rooms, students, exams, teachers, courses, timeslots = load_all_data()
    class_solver = ClassTimetableCSP(
        rooms=rooms,
        teachers=teachers,
        courses=courses,
        timeslots=timeslots,
        students=students,
    )
    class_tt = class_solver.solve()
    
    lab_solver = LabTimetableCSP(
        rooms=rooms,
        teachers=teachers,
        courses=courses,
        timeslots=timeslots,
        students=students,
        class_timetable=class_tt,
    )
    lab_tt = lab_solver.solve()

    payload = {
        "class_timetable": class_tt,
        "lab_timetable": lab_tt,
        "rooms": rooms,
        "teachers": teachers,
        "courses": courses,
        "timeslots": timeslots,
    }

    _TIMETABLE_CACHE = payload
    _save_timetable_cache_to_disk(payload)
    return payload


# ---------------- Student timetable lookup (FIXED) ----------------
@app.get("/api/student/{student_id}/timetable")
def student_timetable(student_id: str, department: str | None = None, section: str | None = None):
    # Load cached data
    cached = _get_or_generate_full_timetable()
    rooms = cached.get("rooms") or {}
    teachers = cached.get("teachers") or {}
    courses = cached.get("courses") or {}
    timeslots = cached.get("timeslots")

    # Load fresh student data (in case uploads happened)
    students = load_all_data()[1]
    student_key = (student_id or "").strip().upper()
    
    # Case-insensitive lookup
    student = None
    for sid, s in students.items():
        if sid.upper() == student_key:
            student = s
            break
            
    if not student:
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found")

    # Helper for Section Matching
    student_section = str(section or student.get("section", "")).upper().strip()
    def _alpha_section(sec: str) -> str:
        return "".join(ch for ch in sec if ch.isalpha()).upper()
    
    student_section_alpha = _alpha_section(student_section)
    student_section_letter = student_section_alpha[-1] if student_section_alpha else ""
    
    # Helper for Filters
    student_department = str(department or student.get("department", "")).upper().strip()
    
    # Check explicit enrollment (This fixes the "wrong output/gaps")
    # 'enrolled_courses' is now a LIST thanks to loader.py
    enrolled_courses_list = student.get("enrolled_courses", [])
    has_enrollment_data = bool(enrolled_courses_list)

    # ---------------------------------------------------------
    # Inferred details (Legacy fallback only)
    # ---------------------------------------------------------
    student_program = None
    prog_raw = student.get("program")
    if isinstance(prog_raw, str) and prog_raw.strip():
        student_program = prog_raw.strip().upper()
    
    student_semester: int | None = None
    try:
        sem_raw = student.get("semester")
        if sem_raw is not None:
            student_semester = int(str(sem_raw).strip())
    except Exception:
        pass

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------
    class_tt = cached.get("class_timetable") or {}
    lab_tt = cached.get("lab_timetable") or {}
    
    if isinstance(timeslots, list):
        timeslot_map = {t.get("id"): t for t in timeslots if isinstance(t, dict)}
    else:
        timeslot_map = timeslots or {}

    def label(slot_id: str) -> str:
        ts = timeslot_map.get(slot_id, {})
        return ts.get("label", slot_id)

    # ---------------------------------------------------------
    # Logic: Collect Classes
    # ---------------------------------------------------------
    def _collect() -> tuple[list[dict], list[dict]]:
        classes_out: list[dict] = []
        
        # 1. Classes
        for key, val in class_tt.items():
            parts = key.split("|")
            if len(parts) < 2: continue
            course_id = parts[0]
            sec_val = parts[1].upper()
            
            # --- FILTERING LOGIC ---
            is_enrolled = course_id in enrolled_courses_list
            
            if has_enrollment_data:
                # STRICT MODE: Only show if explicitly enrolled
                if not is_enrolled:
                    continue
                
                # SECTION MATCH: Even if enrolled, check section letter
                # (Matches 5A to CS101|A)
                sec_alpha = _alpha_section(sec_val)
                if student_section:
                    match = (
                        sec_val == student_section or 
                        sec_alpha == student_section_alpha or 
                        sec_alpha == student_section_letter or
                        sec_val == student_section_letter
                    )
                    if not match: continue
            else:
                # LEGACY MODE (Fallbacks)
                # Filter by Department / Program / Semester
                course = courses.get(course_id, {})
                c_dept = str(course.get("dept") or "").upper()
                c_sem = course.get("semester")
                
                if student_department and c_dept and c_dept != student_department: continue
                if student_semester and c_sem and c_sem != student_semester: continue
                
                # Check section match
                sec_alpha = _alpha_section(sec_val)
                if student_section:
                    match = (
                        sec_val == student_section or 
                        sec_alpha == student_section_alpha or 
                        sec_alpha == student_section_letter or
                        sec_val == student_section_letter
                    )
                    if not match: continue

            # --- ADD TO OUTPUT ---
            course = courses.get(course_id, {})
            teacher_id = val.get("teacher")
            room_id = val.get("room")
            
            classes_out.append({
                "course_id": course_id,
                "course_title": course.get("title") or course.get("name") or course_id,
                "semester": course.get("semester"),
                "section": sec_val,
                "teacher_id": teacher_id,
                "teacher_name": (teachers.get(teacher_id, {}) or {}).get("name", teacher_id),
                "room_id": room_id,
                "room_name": (rooms.get(room_id, {}) or {}).get("name", room_id),
                "timeslot_id": val.get("slot"),
                "timeslot_label": label(val.get("slot")),
                "type": "class",
            })

        # 2. Labs
        labs_out: list[dict] = []
        for key, val in lab_tt.items():
            parts = key.split("|")
            if len(parts) < 2: continue
            course_id = parts[0]
            sec_val = parts[1].upper()

            # --- FILTERING LOGIC (Same as above) ---
            is_enrolled = course_id in enrolled_courses_list
            
            if has_enrollment_data:
                if not is_enrolled: continue
                sec_alpha = _alpha_section(sec_val)
                if student_section:
                    match = (
                        sec_val == student_section or 
                        sec_alpha == student_section_alpha or 
                        sec_alpha == student_section_letter or
                        sec_val == student_section_letter
                    )
                    if not match: continue
            else:
                course = courses.get(course_id, {})
                c_dept = str(course.get("dept") or "").upper()
                c_sem = course.get("semester")
                if student_department and c_dept and c_dept != student_department: continue
                if student_semester and c_sem and c_sem != student_semester: continue
                
                sec_alpha = _alpha_section(sec_val)
                if student_section:
                    match = (
                        sec_val == student_section or 
                        sec_alpha == student_section_alpha or 
                        sec_alpha == student_section_letter or
                        sec_val == student_section_letter
                    )
                    if not match: continue

            teacher_id = val.get("teacher")
            room_id = val.get("room")
            slot_ids = val.get("slots", [])
            
            labs_out.append({
                "course_id": course_id,
                "course_title": courses.get(course_id, {}).get("name", course_id),
                "semester": courses.get(course_id, {}).get("semester"),
                "section": sec_val,
                "teacher_id": teacher_id,
                "teacher_name": (teachers.get(teacher_id, {}) or {}).get("name", teacher_id),
                "room_id": room_id,
                "room_name": (rooms.get(room_id, {}) or {}).get("name", room_id),
                "timeslot_ids": slot_ids,
                "timeslot_labels": [label(sid) for sid in slot_ids],
                "type": "lab",
            })
            
        return classes_out, labs_out

    classes, labs = _collect()
    
    return {
        "student": {
            "id": student_id,
            "department": student_department,
            "section": student_section,
            "semester": student_semester,
            "program": student_program,
        },
        "classes": classes,
        "labs": labs,
        "timeslots": timeslot_map,
    }