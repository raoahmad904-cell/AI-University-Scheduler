# FILE: backend/scheduler/scripts/check_constraints.py
from __future__ import annotations

import re
from collections import defaultdict

from scheduler.algorithms.class_timetable_csp import ClassTimetableCSP
from scheduler.algorithms.lab_timetable_csp import LabTimetableCSP
from scheduler.utils.loader import load_all_data


def infer_program(course_id: str) -> str | None:
    u = (course_id or "").upper()
    if "PHD" in u:
        return "PHD"
    if "MS" in u:
        return "MS"
    if "BS" in u:
        return "BS"
    return None


def infer_semester(course_id: str, course_obj: dict) -> int | None:
    if isinstance(course_obj, dict) and course_obj.get("semester") is not None:
        try:
            return int(str(course_obj.get("semester")).strip())
        except Exception:
            pass

    cid = str(course_id or "")
    for i in range(len(cid) - 1):
        if cid[i].isdigit() and cid[i + 1].isdigit():
            try:
                return int(cid[i] + cid[i + 1])
            except Exception:
                return None

    name = str((course_obj or {}).get("name") or (course_obj or {}).get("title") or "")
    m = re.search(r"\(Sem\s*(\d+)\)", name, re.I)
    return int(m.group(1)) if m else None


def main() -> None:
    # 1. Load Data
    rooms, students, exams, teachers, courses, timeslots = load_all_data()
    
    # 2. Run Solvers
    print("Running CSP Solvers...")
    class_tt = ClassTimetableCSP(rooms, teachers, courses, timeslots, students).solve()
    lab_tt = LabTimetableCSP(rooms, teachers, courses, timeslots, students).solve()

    # --- PART A: EXISTING RESOURCE CHECKS (Teacher, Room, Section Group) ---
    section_slot = set()
    teacher_slot = set()
    room_slot = set()
    conf_section = conf_teacher = conf_room = 0

    # Check Class Timetable
    for key, val in (class_tt or {}).items():
        parts = key.split("|")
        if len(parts) < 2:
            continue
        course_id, sec = parts[0], parts[1]
        course = courses.get(course_id, {})
        dept = str(course.get("dept") or course.get("department") or "").upper()
        prog = infer_program(course_id)
        sem = infer_semester(course_id, course)
        group = f"{dept}|{prog}|{sem}|{sec.upper()}"
        slot = val.get("slot")
        t = val.get("teacher")
        r = val.get("room")

        if (group, slot) in section_slot:
            conf_section += 1
        else:
            section_slot.add((group, slot))

        if (t, slot) in teacher_slot:
            conf_teacher += 1
        else:
            teacher_slot.add((t, slot))

        if (r, slot) in room_slot:
            conf_room += 1
        else:
            room_slot.add((r, slot))

    # Check Lab Timetable
    section_slot_lab = set()
    teacher_slot_lab = set()
    room_slot_lab = set()
    conf_section_lab = conf_teacher_lab = conf_room_lab = 0

    for key, val in (lab_tt or {}).items():
        parts = key.split("|")
        if len(parts) < 2:
            continue
        course_id, sec = parts[0], parts[1]
        course = courses.get(course_id, {})
        dept = str(course.get("dept") or course.get("department") or "").upper()
        prog = infer_program(course_id)
        sem = infer_semester(course_id, course)
        group = f"{dept}|{prog}|{sem}|{sec.upper()}"
        slots = val.get("slots") or []
        t = val.get("teacher")
        r = val.get("room")

        for slot in slots:
            if (group, slot) in section_slot_lab:
                conf_section_lab += 1
            else:
                section_slot_lab.add((group, slot))

            if (t, slot) in teacher_slot_lab:
                conf_teacher_lab += 1
            else:
                teacher_slot_lab.add((t, slot))

            if (r, slot) in room_slot_lab:
                conf_room_lab += 1
            else:
                room_slot_lab.add((r, slot))

    # --- PART B: NEW INDIVIDUAL STUDENT CONFLICT CHECK ---
    print("\n--- Checking Individual Student Schedules ---")
    student_conflicts = 0
    
    # student_id -> set of occupied slot_ids
    student_schedule_map = defaultdict(list)

    def check_assignment(course_id, slot):
        nonlocal student_conflicts
        # Find which students are in this course using 'enrolled_courses'
        enrolled_sids = []
        
        # A. Check explicit enrollment (Preferred)
        for sid, s in students.items():
            # Ensure we check the list properly (loader fix handles the type)
            enrolled = s.get("enrolled_courses", [])
            if course_id in enrolled:
                enrolled_sids.append(sid)
        
        # B. Fallback: If no explicit enrollments found, assume Section Group logic
        # (Only strictly necessary if data generation didn't run correctly)
        if not enrolled_sids:
             # Basic fallback matching logic could go here, but with correct data
             # this list should be populated.
             pass

        for sid in enrolled_sids:
            if slot in student_schedule_map[sid]:
                # Conflict found!
                print(f"❌ CONFLICT: Student {sid} has multiple classes at {slot} (Course: {course_id})")
                student_conflicts += 1
            student_schedule_map[sid].append(slot)

    # 1. Iterate Class Timetable for Student Checks
    for key, val in (class_tt or {}).items():
        course_id = key.split("|")[0]
        slot = val.get("slot")
        if slot:
            check_assignment(course_id, slot)

    # 2. Iterate Lab Timetable for Student Checks
    for key, val in (lab_tt or {}).items():
        course_id = key.split("|")[0]
        slots = val.get("slots", [])
        for slot in slots:
             check_assignment(course_id, slot)

    # --- PART C: FINAL REPORTING ---
    lab_in_class = sum(
        1 for k in (class_tt or {}).keys() if bool(courses.get(k.split("|")[0], {}).get("lab_required"))
    )

    print("-" * 40)
    print("SUMMARY REPORT")
    print("-" * 40)
    print(f"Class Assignments Generated: {len(class_tt or {})}")
    print(f"Lab Assignments Generated:   {len(lab_tt or {})}")
    print("-" * 40)
    print("GROUP-BASED CONFLICTS (Sections/Teachers/Rooms):")
    print(f"  > Sections: {conf_section}")
    print(f"  > Teachers: {conf_teacher}")
    print(f"  > Rooms:    {conf_room}")
    print("\nLAB CONFLICTS:")
    print(f"  > Sections: {conf_section_lab}")
    print(f"  > Teachers: {conf_teacher_lab}")
    print(f"  > Rooms:    {conf_room_lab}")
    print(f"  > Labs scheduled as Classes: {lab_in_class}")
    print("-" * 40)
    
    if student_conflicts == 0:
        print("✅ SUCCESS: No individual student conflicts found.")
    else:
        print(f"❌ FAILED: Found {student_conflicts} individual student conflicts.")
    print("-" * 40)


if __name__ == "__main__":
    main()