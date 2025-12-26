from typing import Dict, List, Tuple
import random

class LabTimetableCSP:
    """
    Variables: (course_id | section) -> assignment {room, slot, teacher}
    Constraints:
      - Teacher availability
      - Room capacity >= estimated section size (approx by department or static value)
      - No teacher overlaps
      - No room overlaps
      - Course hours_per_week allocated across slots
      - Combined load: max 1 lab + 2 lectures/day per teacher (if has lab), else max 4 lectures
    Simplified baseline: assign one slot per course-section for demo; extend hours later.
    """
    def __init__(self, rooms: Dict[str, dict], teachers: Dict[str, dict], courses: Dict[str, dict], timeslots: Dict[str, dict], students: Dict[str, dict], class_timetable: Dict[str, dict] = None):
        self.rooms = rooms
        self.teachers = teachers
        self.courses = courses
        self.timeslots = {k: v for k, v in timeslots.items() if v["type"] == "lab"}
        self.students = students
        self.class_timetable = class_timetable or {}

        self.room_ids = list(self.rooms.keys())
        self.slot_ids = list(self.timeslots.keys())

        self.section_sizes = self._compute_section_sizes()
        
        # Precompute teacher lecture counts per day from class timetable
        self.teacher_day_lecture_count = self._compute_teacher_day_lectures()

    def _compute_teacher_day_lectures(self) -> Dict[Tuple[str, str], int]:
        """Count how many lectures each teacher has per day from the class timetable."""
        counts: Dict[Tuple[str, str], int] = {}
        # Get all timeslots (including class timeslots) for label lookup
        all_timeslots = {}
        for k, v in self.timeslots.items():
            all_timeslots[k] = v
        # We need to look up class slots too - they have format like MON_9, TUE_10
        for key, assignment in self.class_timetable.items():
            teacher = assignment.get("teacher")
            slot = assignment.get("slot")
            if not teacher or not slot:
                continue
            # Extract day from slot id (e.g., MON_9 -> MON, TUE_10 -> TUE)
            day = slot.split("_")[0].upper()[:3] if "_" in slot else "MON"
            counts[(teacher, day)] = counts.get((teacher, day), 0) + 1
        return counts

    def _infer_course_program_semester(self, course_id: str, course: dict) -> Tuple[str | None, int | None]:
        if not isinstance(course, dict):
            return None, None

        prog = course.get("program")
        if isinstance(prog, str) and prog.strip():
            program = prog.strip().upper()
        else:
            program = None

        sem_raw = course.get("semester")
        semester: int | None = None
        if sem_raw is not None:
            try:
                semester = int(str(sem_raw).strip())
            except Exception:
                semester = None

        if program is not None and semester is not None:
            return program, semester

        cid = (course_id or "").strip()
        if program is None:
            if "PHD" in cid.upper():
                program = "PHD"
            elif "MS" in cid.upper():
                program = "MS"
            elif "BS" in cid.upper():
                program = "BS"

        if semester is None:
            digits = ""
            for i in range(len(cid) - 1):
                if cid[i].isdigit() and cid[i + 1].isdigit():
                    digits = cid[i] + cid[i + 1]
                    break
            if digits:
                try:
                    semester = int(digits)
                except Exception:
                    semester = None
        return program, semester

    def _infer_student_program_semester_section(self, student_id: str, student: dict) -> Tuple[str | None, int | None, str | None]:
        if not isinstance(student, dict):
            return None, None, None
        prog = student.get("program")
        program = prog.strip().upper() if isinstance(prog, str) and prog.strip() else None

        sem_raw = student.get("semester")
        semester: int | None = None
        if sem_raw is not None:
            try:
                semester = int(str(sem_raw).strip())
            except Exception:
                semester = None

        sec_raw = str(student.get("section", "")).upper().strip()
        section_letter = sec_raw[-1] if sec_raw else None

        sid = (student_id or "").upper().strip()
        parts = sid.split("_")
        if len(parts) >= 5:
            if program is None and parts[2] in {"BS", "MS", "PHD"}:
                program = parts[2]
            if semester is None:
                try:
                    semester = int(parts[3][:2])
                except Exception:
                    pass
            if section_letter is None and len(parts[3]) >= 3:
                section_letter = parts[3][2]
        return program, semester, section_letter

    def _compute_section_sizes(self) -> Dict[str, int]:
        sizes: Dict[str, int] = {}
        counts: Dict[str, int] = {}
        for sid, s in self.students.items():
            if not isinstance(s, dict):
                continue
            dept = str(s.get("department", "")).upper().strip()
            program, semester, section_letter = self._infer_student_program_semester_section(sid, s)
            if not dept or not program or semester is None or not section_letter:
                continue
            group = f"{dept}|{program}|{semester}|{section_letter}"
            counts[group] = counts.get(group, 0) + 1

        for course_id, course in self.courses.items():
            if not isinstance(course, dict):
                continue
            dept = str(course.get("dept") or course.get("department") or "").upper().strip()
            program, semester = self._infer_course_program_semester(course_id, course)
            for sec in course.get("sections", ["A"]):
                section_letter = str(sec).upper().strip()
                group = f"{dept}|{program}|{semester}|{section_letter}"
                key = f"{course_id}|{section_letter}"
                count = counts.get(group, 0)
                sizes[key] = min(50, count if count > 0 else 30)
        return sizes

    def _slot_day(self, slot_id: str) -> str:
        label = self.timeslots.get(slot_id, {}).get("label", "")
        if label:
            return label.split()[0]
        return slot_id.split("_")[0] if "_" in slot_id else "DAY"

    def solve(self) -> Dict[str, dict]:
        """Schedule ALL lab courses. Each lab is 1 CR = 1 session per week (3-hour block)."""
        assignments: Dict[str, dict] = {}
        used_room_slot = set()
        used_teacher_slot = set()
        used_group_slot = set()  # (section_group, slot)

        weekdays = ["MON", "TUE", "WED", "THU", "FRI"]

        teacher_day_lab_count: Dict[Tuple[str, str], int] = {}
        teacher_week_lab_count: Dict[str, int] = {}
        group_day_count: Dict[Tuple[str, str], int] = {}
        group_days_used: Dict[str, set] = {}

        # Build lab rooms list
        lab_rooms = [rid for rid in self.room_ids if "lab" in self.rooms.get(rid, {}).get("tags", [])]
        if not lab_rooms or not self.slot_ids:
            return {}

        has_explicit_labs = any(bool(c.get("lab_required")) for c in self.courses.values() if isinstance(c, dict))

        # Build flat task list: each (course_id, course, section) = 1 lab session per week
        tasks: List[Tuple[str, dict, str]] = []
        for course_id, course in self.courses.items():
            if not isinstance(course, dict):
                continue
            if has_explicit_labs and not course.get("lab_required"):
                continue
            dept = str(course.get("dept") or course.get("department") or "").upper().strip()
            program, semester = self._infer_course_program_semester(course_id, course)
            for section in course.get("sections", ["A"]):
                section_letter = str(section).upper().strip()
                group = f"{dept}|{program}|{semester}|{section_letter}"
                group_days_used.setdefault(group, set())
                tasks.append((course_id, course, section_letter))

        if not tasks:
            return {}

        # Shuffle tasks to distribute scheduling fairly
        random.shuffle(tasks)

        def _slot_day_key(slot_id: str) -> Tuple[str, str]:
            day = self._slot_day(slot_id)
            day_key = day[:3].upper()
            return day, day_key

        def _teacher_candidates_for_course(course_obj: dict) -> List[str]:
            t0 = course_obj.get("teacher_id") or course_obj.get("teacher")
            dept_raw = course_obj.get("dept") or course_obj.get("department")
            dept_teachers = [tid for tid, t in self.teachers.items() if (t.get("dept") or t.get("department")) == dept_raw]
            candidates = [t for t in [t0, *dept_teachers] if t and t in self.teachers]
            # Add cross-department teachers as overflow
            overflow = [tid for tid in self.teachers.keys() if tid not in candidates]
            random.shuffle(overflow)
            return candidates + overflow if candidates else overflow

        def _try_schedule_lab(course_id: str, course: dict, section_letter: str, relax: bool = False) -> bool:
            base_key = f"{course_id}|{section_letter}"
            dept = str(course.get("dept") or course.get("department") or "").upper().strip()
            program, semester = self._infer_course_program_semester(course_id, course)
            section_group = f"{dept}|{program}|{semester}|{section_letter}"

            missing_days = [d for d in weekdays if d not in group_days_used.get(section_group, set())]
            preferred_slots = [s for s in self.slot_ids if _slot_day_key(s)[1] in missing_days]
            other_slots = [s for s in self.slot_ids if s not in preferred_slots]
            random.shuffle(preferred_slots)
            random.shuffle(other_slots)
            slot_candidates = preferred_slots + other_slots

            required = self.section_sizes.get(base_key, 30)
            teachers_for_task = _teacher_candidates_for_course(course)

            for slot in slot_candidates:
                day, day_key = _slot_day_key(slot)
                if day_key not in weekdays:
                    continue
                # Max 2 labs per day per section group (soft constraint, relax if needed)
                if not relax and group_day_count.get((section_group, day), 0) >= 2:
                    continue
                if (section_group, slot) in used_group_slot:
                    continue

                for teacher in teachers_for_task:
                    if (teacher, slot) in used_teacher_slot:
                        continue
                    # Combined daily load constraint (aligns with coordinator metric):
                    # - At most 1 lab per day per teacher
                    # - Do not schedule a lab if it would push total (lectures + labs) above 4 for that day
                    if teacher_day_lab_count.get((teacher, day), 0) >= 1:
                        continue
                    lecture_count = self.teacher_day_lecture_count.get((teacher, day_key), 0)
                    if lecture_count + 1 > 4:
                        continue
                    if teacher_week_lab_count.get(teacher, 0) >= 30:
                        continue

                    # Find suitable lab room
                    room_order = [r for r in lab_rooms if self.rooms.get(r, {}).get("capacity", 0) >= required]
                    if not room_order:
                        room_order = list(lab_rooms)
                    else:
                        room_order += [r for r in lab_rooms if r not in room_order]

                    for room_id in room_order:
                        if (room_id, slot) in used_room_slot:
                            continue
                        # Assign this lab
                        assignments[base_key] = {"room": room_id, "slots": [slot], "teacher": teacher}
                        used_room_slot.add((room_id, slot))
                        used_teacher_slot.add((teacher, slot))
                        used_group_slot.add((section_group, slot))
                        group_day_count[(section_group, day)] = group_day_count.get((section_group, day), 0) + 1
                        teacher_week_lab_count[teacher] = teacher_week_lab_count.get(teacher, 0) + 1
                        teacher_day_lab_count[(teacher, day)] = teacher_day_lab_count.get((teacher, day), 0) + 1
                        group_days_used.setdefault(section_group, set()).add(day_key)
                        return True
            return False

        # Schedule all labs - first pass with constraints, second pass relaxed
        unscheduled: List[Tuple[str, dict, str]] = []
        for course_id, course, section_letter in tasks:
            if not _try_schedule_lab(course_id, course, section_letter, relax=False):
                unscheduled.append((course_id, course, section_letter))

        # Retry unscheduled with relaxed constraints
        for course_id, course, section_letter in unscheduled:
            _try_schedule_lab(course_id, course, section_letter, relax=True)

        return assignments