from __future__ import annotations

from collections import defaultdict

from scheduler.algorithms.class_timetable_csp import ClassTimetableCSP
from scheduler.algorithms.lab_timetable_csp import LabTimetableCSP
from scheduler.utils.loader import load_all_data


def main() -> None:
    rooms, students, _exams, teachers, courses, timeslots = load_all_data()

    class_tt = ClassTimetableCSP(rooms, teachers, courses, timeslots, students).solve()
    lab_tt = LabTimetableCSP(rooms, teachers, courses, timeslots, students, class_tt).solve()

    # Count daily sessions per teacher:
    # - each class assignment counts 1
    # - each lab counts 1 per day (not per lab slot)
    teacher_day: dict[tuple[str, str], int] = defaultdict(int)

    for assignment in (class_tt or {}).values():
        teacher = assignment.get("teacher")
        slot = assignment.get("slot")
        if not teacher or not slot:
            continue
        day_key = str(slot).split("_")[0].upper()[:3]
        teacher_day[(teacher, day_key)] += 1

    for assignment in (lab_tt or {}).values():
        teacher = assignment.get("teacher")
        slots = assignment.get("slots") or []
        if not teacher:
            continue

        days: set[str] = set()
        for s in slots:
            if not isinstance(s, str) or not s:
                continue
            parts = s.split("_")
            # examples: LAB_MON_9 or MON_9
            if parts and parts[0].upper() == "LAB" and len(parts) >= 2:
                days.add(parts[1].upper()[:3])
            else:
                days.add(parts[0].upper()[:3])

        for day_key in days:
            teacher_day[(teacher, day_key)] += 1

    overload = [(t, d, c) for (t, d), c in teacher_day.items() if c > 4]
    overload.sort(key=lambda x: (-x[2], x[1], x[0]))

    print("CLASS_ASSIGNMENTS", len(class_tt or {}))
    print("LAB_ASSIGNMENTS", len(lab_tt or {}))
    print("OVERLOAD_CASES", len(overload))
    print("OVERLOAD_TOP10", overload[:10])


if __name__ == "__main__":
    main()
