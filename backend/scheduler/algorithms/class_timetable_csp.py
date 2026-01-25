from collections import defaultdict
from typing import Dict, List, Tuple
import random

class ClassTimetableCSP:
    """
    Variables: (course_id | section) -> assignment {room, slot, teacher}
    Improved Constraints:
      - Individual Student Overlaps (Fixes the specific student ID issue)
      - Teacher availability & Room capacity
      - No teacher/room/section-group overlaps
    """
    def __init__(self, rooms: Dict[str, dict], teachers: Dict[str, dict], courses: Dict[str, dict], timeslots: Dict[str, dict], students: Dict[str, dict]):
        self.rooms = rooms
        self.teachers = teachers
        self.courses = courses
        self.timeslots = {k: v for k, v in timeslots.items() if v["type"] == "class"}
        self.students = students

        self.room_ids = list(self.rooms.keys())
        self.slot_ids = list(self.timeslots.keys())

        # If labs are explicitly marked, don't schedule them as classes.
        self.has_explicit_labs = any(bool(c.get("lab_required")) for c in self.courses.values() if isinstance(c, dict))

        # --- FIX: Individual Student Mapping ---
        # Track which students are in which course to prevent specific ID overlaps
        self.course_to_students = defaultdict(set)
        for sid, s in self.students.items():
            # If your data has a 'courses' list, use it. 
            # Otherwise, we map them via their section_group in _compute_section_sizes
            enrolled = s.get("courses", [])
            if isinstance(enrolled, list):
                for c_id in enrolled:
                    self.course_to_students[c_id].add(sid)

        self.section_sizes = self._compute_section_sizes()
        self.course_hours = self._derive_course_hours()

        # Trackers for the solver
        self.used_individual_student_slots = set() # (student_id, slot)
        
        # Workload thresholds
        self.max_teacher_week_soft = 30
        self.max_teacher_week_hard = 45
        self.max_teacher_day_soft = 4
        # Hard cap used to prevent extreme daily overload (aligns with coordinator metric)
        self.max_teacher_day_hard = 4

    def _infer_course_program_semester(self, course_id: str, course: dict) -> Tuple[str | None, int | None]:
        if not isinstance(course, dict): return None, None
        prog = course.get("program")
        program = prog.strip().upper() if isinstance(prog, str) and prog.strip() else None
        
        sem_raw = course.get("semester")
        semester = None
        if sem_raw is not None:
            try: semester = int(str(sem_raw).strip())
            except: semester = None

        if program is None or semester is None:
            cid = (course_id or "").strip().upper()
            if "PHD" in cid: program = "PHD"
            elif "MS" in cid: program = "MS"
            elif "BS" in cid: program = "BS"
            
            for i in range(len(cid) - 1):
                if cid[i].isdigit() and cid[i + 1].isdigit():
                    try: 
                        semester = int(cid[i:i+2])
                        break
                    except: pass
        return program, semester

    def _infer_student_program_semester_section(self, student_id: str, student: dict) -> Tuple[str | None, int | None, str | None]:
        if not isinstance(student, dict): return None, None, None
        prog = student.get("program")
        program = prog.strip().upper() if isinstance(prog, str) and prog.strip() else None
        
        sem_raw = student.get("semester")
        semester = None
        if sem_raw is not None:
            try: semester = int(str(sem_raw).strip())
            except: semester = None

        sec_raw = str(student.get("section", "")).upper().strip()
        section_letter = sec_raw[-1] if sec_raw else None
        return program, semester, section_letter

    def _derive_course_hours(self) -> Dict[str, int]:
        hours: Dict[str, int] = {}
        for course_id, course in self.courses.items():
            if not isinstance(course, dict) or course.get("lab_required"): continue
            val = course.get("credits") or course.get("hours_per_week") or 2
            try: value = max(2, min(3, int(float(str(val).strip()))))
            except: value = 2
            hours[course_id] = value
        return hours

    def _compute_section_sizes(self) -> Dict[str, int]:
        sizes: Dict[str, int] = {}
        counts: Dict[str, int] = {}
        for sid, s in self.students.items():
            dept = str(s.get("department", "")).upper().strip()
            program, semester, section_letter = self._infer_student_program_semester_section(sid, s)
            if dept and section_letter and semester is not None:
                group = f"{dept}|{program}|{semester}|{section_letter}"
                counts[group] = counts.get(group, 0) + 1
                # If student-course mapping wasn't in students.json, we infer it here
                # and link this student to all courses belonging to this group
                for cid, c in self.courses.items():
                    c_prog, c_sem = self._infer_course_program_semester(cid, c)
                    if c_prog == program and c_sem == semester:
                        self.course_to_students[cid].add(sid)

        for course_id, course in self.courses.items():
            dept = str(course.get("dept") or course.get("department") or "").upper().strip()
            program, semester = self._infer_course_program_semester(course_id, course)
            for sec in course.get("sections", ["A"]):
                sec_letter = str(sec).upper().strip()
                group = f"{dept}|{program}|{semester}|{sec_letter}"
                sizes[f"{course_id}|{sec_letter}"] = min(50, counts.get(group, 30))
        return sizes

    def _slot_day(self, slot_id: str) -> str:
        label = self.timeslots.get(slot_id, {}).get("label", "")
        raw = label.split()[0] if label else (slot_id.split("_")[0] if "_" in slot_id else "DAY")
        return str(raw).upper()[:3]

    def _teacher_candidates(self, course: dict, dept: str) -> List[str]:
        pref = course.get("teacher_id") or course.get("teacher")
        candidates = [pref] if pref in self.teachers else []
        dept_t = [tid for tid, t in self.teachers.items() if str(t.get("dept") or "").upper() == dept]
        candidates += [t for t in dept_t if t not in candidates]
        overflow = [t for t in self.teachers.keys() if t not in candidates]
        random.shuffle(overflow)
        return candidates + overflow

    def solve(self) -> Dict[str, dict]:
        assignments: Dict[str, dict] = {}
        used_room_slot = set()
        used_teacher_slot = set()
        used_section_slot = set() 
        self.used_individual_student_slots = set() # Reset for new solve

        weekdays = ["MON", "TUE", "WED", "THU", "FRI"]
        section_day_count = {}
        teacher_day_count = {}
        teacher_week_count = {}
        section_days_used = {}
        course_days_used = defaultdict(set)

        tasks = []
        for cid, c in self.courses.items():
            if not isinstance(c, dict) or (self.has_explicit_labs and c.get("lab_required")): continue
            sessions = self.course_hours.get(cid, 2)
            for sec in c.get("sections", ["A"]):
                for sess_idx in range(1, sessions + 1):
                    tasks.append((cid, c, str(sec).upper().strip(), sess_idx))

        tasks.sort(key=lambda t: (-self.course_hours.get(t[0], 2), -len(self.courses[t[0]].get("sections", [])), t[2]))

        def _try_assign(course_id: str, course: dict, section_letter: str, session_idx: int, relax: bool = False) -> bool:
            key_base = f"{course_id}|{section_letter}"
            assign_key = f"{key_base}|S{session_idx}"
            dept = str(course.get("dept") or "").upper().strip()
            program, semester = self._infer_course_program_semester(course_id, course)
            section_group = f"{dept}|{program}|{semester}|{section_letter}"
            
            # --- STUDENT CONFLICT CHECK ---
            current_course_students = self.course_to_students.get(course_id, set())

            teachers = self._teacher_candidates(course, dept)
            # Prefer keeping the course with its preferred/department teacher, while still balancing workload.
            for teacher in teachers:
                # NEW: Prevent same teacher for multiple subjects in same section (unless relax)
                already_assigned = any(
                    assignments.get(f"{other_cid}|{section_letter}|S{other_sess}", {}).get("teacher") == teacher
                    for other_cid, other_course in self.courses.items()
                    if other_cid != course_id and isinstance(other_course, dict) and section_letter in [str(s).upper().strip() for s in other_course.get("sections", ["A"])]
                    for other_sess in range(1, self.course_hours.get(other_cid, 2) + 1)
                )
                if already_assigned and not relax:
                    continue
                # Weekly workload guardrails
                if teacher_week_count.get(teacher, 0) >= self.max_teacher_week_hard:
                    continue
                if not relax and teacher_week_count.get(teacher, 0) >= self.max_teacher_week_soft:
                    continue

                # Build slot candidates preferring lighter teacher days
                slot_candidates = list(self.slot_ids)
                random.shuffle(slot_candidates)
                slot_candidates.sort(
                    key=lambda s: (
                        teacher_day_count.get((teacher, self._slot_day(s)), 0),
                        section_day_count.get((section_group, self._slot_day(s)), 0),
                    )
                )

                for slot in slot_candidates:
                    day = self._slot_day(slot)
                    if not relax and section_day_count.get((section_group, day), 0) >= 3:
                        continue
                    if (section_group, slot) in used_section_slot:
                        continue

                    # Teacher daily workload cap
                    # - Hard: never exceed max_teacher_day_hard
                    # - Soft: in the first pass, avoid hitting the cap early
                    if teacher_day_count.get((teacher, day), 0) >= self.max_teacher_day_hard:
                        continue
                    if not relax and teacher_day_count.get((teacher, day), 0) >= self.max_teacher_day_soft:
                        continue

                    # NEW: Hard Individual Student Check
                    if any((sid, slot) in self.used_individual_student_slots for sid in current_course_students):
                        continue

                    if (teacher, slot) in used_teacher_slot:
                        continue

                    for room_id in self.room_ids:
                        if (room_id, slot) in used_room_slot:
                            continue
                        if self.rooms[room_id]["capacity"] < self.section_sizes.get(key_base, 30):
                            continue

                        # SUCCESS: Assign
                        assignments[assign_key] = {"room": room_id, "slot": slot, "teacher": teacher}
                        used_room_slot.add((room_id, slot))
                        used_teacher_slot.add((teacher, slot))
                        used_section_slot.add((section_group, slot))

                        # Block these students for this slot
                        for sid in current_course_students:
                            self.used_individual_student_slots.add((sid, slot))

                        teacher_week_count[teacher] = teacher_week_count.get(teacher, 0) + 1
                        teacher_day_count[(teacher, day)] = teacher_day_count.get((teacher, day), 0) + 1
                        section_day_count[(section_group, day)] = section_day_count.get((section_group, day), 0) + 1
                        return True
            return False

        for cid, c, sec, s_idx in tasks:
            if not _try_assign(cid, c, sec, s_idx, False):
                _try_assign(cid, c, sec, s_idx, True)

        return assignments