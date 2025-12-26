import csv
import json
import random
from pathlib import Path

# Deterministic output for repeatability
random.seed(42)

BASE_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BASE_DIR.parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# Pakistan-style BS curricula (semester-wise)
# -----------------------------------------------------------------------------

departments = {
    "CS": {"name": "Computer Science", "programs": ["BS"]},
    "SE": {"name": "Software Engineering", "programs": ["BS"]},
    "EE": {"name": "Electrical Engineering", "programs": ["BS"]},
}

# BSCS
bscs_curriculum = {
    1: {
        "theory": [
            "Programming Fundamentals",
            "ICT",
            "Calculus",
            "English Composition",
            "Applied Physics",
        ],
        "labs": [
            "Programming Fundamentals Lab",
            "ICT Lab",
        ],
    },
    2: {
        "theory": [
            "Object Oriented Programming",
            "Discrete Structures",
            "Linear Algebra",
            "Communication Skills",
            "Pakistan Studies / Islamic Studies",
        ],
        "labs": [
            "OOP Lab",
        ],
    },
    3: {
        "theory": [
            "Data Structures & Algorithms",
            "Digital Logic Design",
            "Probability & Statistics",
            "Technical Writing",
            "Computer Organization & Assembly",
        ],
        "labs": [
            "Data Structures Lab",
            "Digital Logic Design Lab",
        ],
    },
    4: {
        "theory": [
            "Operating Systems",
            "Database Systems",
            "Design & Analysis of Algorithms",
            "Software Engineering",
            "Differential Equations",
        ],
        "labs": [
            "Operating Systems Lab",
            "Database Systems Lab",
        ],
    },
    5: {
        "theory": [
            "Computer Networks",
            "Theory of Automata",
            "Artificial Intelligence",
            "Web Engineering",
            "Professional Practices",
        ],
        "labs": [
            "Computer Networks Lab",
            "Web Engineering Lab",
            "AI Lab",
        ],
    },
    6: {
        "theory": [
            "Compiler Construction",
            "Information Security",
            "Parallel & Distributed Computing",
            "Mobile App Development",
            "Research Methodology",
        ],
        "labs": [
            "Compiler Construction Lab",
            "Information Security Lab",
            "Mobile App Development Lab",
        ],
    },
    7: {
        "theory": [
            "Final Year Project I",
            "Machine Learning",
            "Cloud Computing",
            "Software Quality Assurance",
            "Elective I",
        ],
        "labs": [
            "Machine Learning Lab",
            "Cloud Computing Lab",
        ],
    },
    8: {
        "theory": [
            "Final Year Project II",
            "Data Science",
            "Internet of Things",
            "Elective II",
        ],
        "labs": [
            "Data Science Lab",
            "IoT Lab",
        ],
    },
}

# BS Software Engineering
bsse_curriculum = {
    1: {
        "theory": [
            "Programming Fundamentals",
            "ICT",
            "Calculus",
            "English Composition",
            "Applied Physics",
        ],
        "labs": ["Programming Fundamentals Lab", "ICT Lab"],
    },
    2: {
        "theory": [
            "Object Oriented Programming",
            "Discrete Structures",
            "Linear Algebra",
            "Communication Skills",
            "Pakistan Studies / Islamic Studies",
        ],
        "labs": ["OOP Lab"],
    },
    3: {
        "theory": [
            "Data Structures",
            "Software Requirements Engineering",
            "Probability & Statistics",
            "Technical Writing",
            "Digital Logic Design",
        ],
        "labs": ["Data Structures Lab", "Software Requirements Lab"],
    },
    4: {
        "theory": [
            "Database Systems",
            "Software Design & Architecture",
            "Operating Systems",
            "Software Construction",
            "Differential Equations",
        ],
        "labs": ["Database Systems Lab", "Software Construction Lab"],
    },
    5: {
        "theory": [
            "Software Quality Assurance",
            "Human Computer Interaction",
            "Computer Networks",
            "Web Engineering",
            "Professional Practices",
        ],
        "labs": ["SQA Lab", "HCI Lab", "Web Engineering Lab"],
    },
    6: {
        "theory": [
            "Software Project Management",
            "DevOps & Cloud Fundamentals",
            "Information Security",
            "Mobile App Development",
            "Research Methodology",
        ],
        "labs": ["DevOps Lab", "Information Security Lab", "Mobile App Development Lab"],
    },
    7: {
        "theory": [
            "Final Year Project I",
            "Software Testing",
            "Software Evolution & Maintenance",
            "Elective I",
            "Elective II",
        ],
        "labs": ["Testing Lab"],
    },
    8: {
        "theory": [
            "Final Year Project II",
            "Entrepreneurship / Innovation",
            "Elective III",
            "Elective IV",
        ],
        "labs": [],
    },
}

# BS Electrical Engineering
bsee_curriculum = {
    1: {
        "theory": [
            "Applied Physics",
            "Calculus",
            "English Composition",
            "ICT",
            "Engineering Drawing",
        ],
        "labs": ["Applied Physics Lab", "ICT Lab"],
    },
    2: {
        "theory": [
            "Linear Algebra",
            "Circuit Analysis I",
            "Communication Skills",
            "Pakistan Studies / Islamic Studies",
            "Programming Fundamentals",
        ],
        "labs": ["Circuits Lab I", "Programming Lab"],
    },
    3: {
        "theory": [
            "Differential Equations",
            "Circuit Analysis II",
            "Digital Logic Design",
            "Signals & Systems",
            "Probability & Statistics",
        ],
        "labs": ["Circuits Lab II", "Digital Logic Design Lab"],
    },
    4: {
        "theory": [
            "Electronics I",
            "Electromagnetics",
            "Control Systems",
            "Electrical Machines I",
            "Technical Writing",
        ],
        "labs": ["Electronics Lab", "Control Systems Lab"],
    },
    5: {
        "theory": [
            "Power Systems I",
            "Communication Systems",
            "Electronics II",
            "Microprocessors & Interfacing",
            "Professional Ethics / Practices",
        ],
        "labs": ["Communication Systems Lab", "Microprocessors Lab"],
    },
    6: {
        "theory": [
            "Power Electronics",
            "Power Systems II",
            "Instrumentation & Measurements",
            "Digital Signal Processing",
            "Research Methodology",
        ],
        "labs": ["Power Electronics Lab", "Instrumentation Lab", "DSP Lab"],
    },
    7: {
        "theory": [
            "Final Year Project I",
            "Embedded Systems",
            "Renewable Energy Systems",
            "Elective I",
            "Elective II",
        ],
        "labs": ["Embedded Systems Lab"],
    },
    8: {
        "theory": [
            "Final Year Project II",
            "Engineering Management / Entrepreneurship",
            "Elective III",
        ],
        "labs": [],
    },
}

# Map dept -> curriculum
curricula = {
    "CS": bscs_curriculum,
    "SE": bsse_curriculum,
    "EE": bsee_curriculum,
}

# Sections per semester
DEFAULT_SECTIONS = "A;B;C"

# Keep teacher availability aligned with the project's configured class timeslots
availability_slots = [
    "MON_9", "MON_10", "MON_11",
    "TUE_9", "TUE_10", "TUE_11",
    "WED_9", "WED_10", "WED_11",
    "THU_9", "THU_10", "THU_11",
    "FRI_9", "FRI_10", "FRI_11",
]

# --- Helpers -----------------------------------------------------------------

def choose_unique(pool, k):
    if k <= len(pool):
        return random.sample(pool, k)
    return [random.choice(pool) for _ in range(k)]

def is_lab_course(name: str) -> bool:
    n = name.lower()
    return " lab" in n or n.endswith("lab")

def infer_credits(course_name: str) -> int:
    if is_lab_course(course_name):
        return 1
    if "final year project" in course_name.lower():
        return 3
    return 3

def normalize_curriculum(curr: dict) -> dict:
    """Ensures semesters 1..8 exist and each has 'theory' and 'labs' keys."""
    out = {}
    for sem in range(1, 9):
        sem_obj = curr.get(sem, {})
        out[sem] = {
            "theory": list(sem_obj.get("theory", [])),
            "labs": list(sem_obj.get("labs", [])),
        }
    return out

def ensure_min_labs(curr: dict, *, dept_code: str, min_labs: int = 2) -> dict:
    """Ensure each semester has at least `min_labs` lab courses."""
    out = {}
    for sem, sem_obj in curr.items():
        theory = list(sem_obj.get("theory", []))
        labs = list(sem_obj.get("labs", []))
        while len(labs) < min_labs:
            idx = len(labs) + 1
            labs.append(f"{dept_code} Practice {sem}-{idx} Lab")
        out[sem] = {"theory": theory, "labs": labs}
    return out

# --- Generators --------------------------------------------------------------

def generate_courses():
    rows = []
    for dept_code, info in departments.items():
        program_list = info["programs"]
        curriculum = normalize_curriculum(curricula.get(dept_code, {}))
        curriculum = ensure_min_labs(curriculum, dept_code=dept_code, min_labs=2)

        for program in program_list:
            for sem in range(1, 9):
                sections = DEFAULT_SECTIONS

                # Theory courses
                for idx, name in enumerate(curriculum[sem]["theory"], start=1):
                    cid = f"{dept_code}{program}{sem:02d}T{idx:02d}"
                    rows.append({
                        "id": cid,
                        "name": f"{name} (Sem {sem})",
                        "dept": dept_code,
                        "program": program,
                        "semester": sem,
                        "sections": sections,
                        "credits": infer_credits(name),
                        "lab_required": "false",
                    })

                # Lab courses
                for idx, name in enumerate(curriculum[sem]["labs"], start=1):
                    cid = f"{dept_code}{program}{sem:02d}L{idx:02d}"
                    rows.append({
                        "id": cid,
                        "name": f"{name} (Sem {sem})",
                        "dept": dept_code,
                        "program": program,
                        "semester": sem,
                        "sections": sections,
                        "credits": 1,
                        "lab_required": "true",
                    })
    return rows

def generate_teachers():
    rows = []
    for dept_code in departments.keys():
        for i in range(1, 13):  # 12 teachers per department
            tid = f"T_{dept_code}_{i:02d}"
            name = f"Dr. {dept_code} Faculty {i}"
            avail = ";".join(choose_unique(availability_slots, 10))
            preference = random.choice(["morning", "mixed", "evening"])
            rows.append({
                "id": tid,
                "name": name,
                "dept": dept_code,
                "availability": avail,
                "preferences": preference,
            })
    return rows

def generate_rooms():
    rows = []
    room_id = 1
    # lecture rooms
    for capacity in [40, 45, 50, 55, 60] * 2:
        rows.append({
            "id": f"R{room_id:03d}",
            "capacity": capacity,
            "type": "lecture",
            "building": "Main",
            "floor": str((room_id % 3) + 1),
            "equipment": "projector",
        })
        room_id += 1
    # labs
    for _ in range(36):
        rows.append({
            "id": f"R{room_id:03d}",
            "capacity": random.randint(25, 30),
            "type": "lab",
            "building": "CS-Block",
            "floor": str((room_id % 3) + 1),
            "equipment": "computers",
        })
        room_id += 1
    # exam halls
    for _ in range(4):
        rows.append({
            "id": f"R{room_id:03d}",
            "capacity": random.randint(120, 180),
            "type": "exam",
            "building": "Auditorium",
            "floor": "0",
            "equipment": "projector",
        })
        room_id += 1
    return rows

def generate_students(courses_list):
    """
    Generates students AND assigns their 'enrolled_courses' based on the
    generated courses list.
    """
    rows = []
    
    # 1. Index courses by (Dept, Program, Semester) for fast lookup
    courses_by_group = {} # key: (dept, prog, sem) -> list of course IDs
    for c in courses_list:
        key = (c['dept'], c['program'], c['semester'])
        if key not in courses_by_group:
            courses_by_group[key] = []
        courses_by_group[key].append(c['id'])

    for dept_code, info in departments.items():
        for program in info["programs"]:
            for sem in range(1, 9):
                for section in ["A", "B", "C"]:
                    count = random.randint(35, 50)
                    for idx in range(1, count + 1):
                        sid = f"S_{dept_code}_{program}_{sem:02d}{section}{idx:03d}"
                        
                        # 2. Find courses for this student (Exact semester match)
                        my_courses = courses_by_group.get((dept_code, program, sem), [])
                        
                        # 3. Create the student record with 'enrolled_courses'
                        rows.append({
                            "id": sid,
                            "department": dept_code,
                            "program": program,
                            "semester": sem,
                            "section": f"{sem}{section}",
                            "enrolled_courses": ";".join(my_courses) # Save as ; separated string
                        })
    return rows

def generate_exams(*, courses: list[dict], students: list[dict]) -> list[dict]:
    """Generate exam definitions consistent with generated courses/students."""
    
    # Index theory courses
    theory_by_key: dict[tuple[str, str, int], list[dict]] = {}
    for c in courses:
        try:
            lab_required = str(c.get("lab_required", "")).strip().lower() in {"true", "1", "yes", "y"}
        except Exception:
            lab_required = False
        if lab_required:
            continue
        dept = (c.get("dept") or "").strip()
        program = (c.get("program") or "").strip()
        try:
            sem = int(c.get("semester"))
        except Exception:
            continue
        if not dept or not program or not sem:
            continue
        theory_by_key.setdefault((dept, program, sem), []).append(c)

    # Index students
    students_by_group: dict[tuple[str, str, int], list[str]] = {}
    for s in students:
        sid = (s.get("id") or "").strip()
        dept = (s.get("department") or "").strip()
        program = (s.get("program") or "").strip()
        try:
            sem = int(s.get("semester"))
        except Exception:
            continue
        if not sid or not dept or not program or not sem:
            continue
        students_by_group.setdefault((dept, program, sem), []).append(sid)

    exams: list[dict] = []
    for (dept, program, sem), sids in sorted(students_by_group.items()):
        theory_courses = sorted(theory_by_key.get((dept, program, sem), []), key=lambda x: str(x.get("id", "")))
        if not theory_courses:
            continue
        for course in theory_courses:
            cid = str(course.get("id") or "").strip()
            if not cid:
                continue
            exam_id = f"EX_{cid}"
            exams.append({
                "id": exam_id,
                "course_code": cid,
                "title": str(course.get("name") or f"{dept} {program} Sem {sem} {cid} Exam"),
                "department": dept,
                "student_ids": list(sids),
            })
    return exams

# --- Writers -----------------------------------------------------------------

def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def write_json(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(rows), indent=2), encoding="utf-8")

def main():
    # 1. Generate Courses
    courses = generate_courses()
    
    teachers = generate_teachers()
    rooms = generate_rooms()
    
    # 2. Generate Students (Passing courses to link enrollments)
    students = generate_students(courses)
    
    # 3. Generate Exams
    exams = generate_exams(courses=courses, students=students)

    # Write Outputs
    write_csv(
        UPLOAD_DIR / "courses.csv",
        ["id", "name", "dept", "program", "semester", "sections", "credits", "lab_required"],
        courses,
    )
    write_json(UPLOAD_DIR / "courses.json", courses)
    
    write_csv(
        UPLOAD_DIR / "teachers.csv",
        ["id", "name", "dept", "availability", "preferences"],
        teachers,
    )
    write_json(UPLOAD_DIR / "teachers.json", teachers)
    
    write_csv(
        UPLOAD_DIR / "rooms.csv",
        ["id", "capacity", "type", "building", "floor", "equipment"],
        rooms,
    )
    write_json(UPLOAD_DIR / "rooms.json", rooms)
    
    # NOTE: "enrolled_courses" is now included in the fieldnames
    write_csv(
        UPLOAD_DIR / "students.csv",
        ["id", "department", "program", "semester", "section", "enrolled_courses"],
        students,
    )
    write_json(UPLOAD_DIR / "students.json", students)

    # Exams
    exams_csv_rows = []
    for e in exams:
        e2 = dict(e)
        if isinstance(e2.get("student_ids"), list):
            e2["student_ids"] = ";".join(e2["student_ids"])
        exams_csv_rows.append(e2)

    write_csv(
        UPLOAD_DIR / "exams.csv",
        ["id", "course_code", "title", "department", "student_ids"],
        exams_csv_rows,
    )
    write_json(UPLOAD_DIR / "exams.json", exams)

    print(f"Generated {len(courses)} courses, {len(students)} students with valid enrollments.")

if __name__ == "__main__":
    main()