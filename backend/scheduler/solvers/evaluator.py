"""
Evaluation metrics and fitness combination for timetables and allocations.
"""

from typing import Dict, Any, List, Tuple
from collections import defaultdict


def _slot_day(slot_id: str) -> str:
    # Attempt to extract a day token; for EXAM_D1_M -> D1
    if "_" in slot_id:
        parts = slot_id.split("_")
        if len(parts) > 1:
            return parts[1]
        return parts[0]
    return slot_id


def exam_timetable_metrics(
    chrom: Dict[str, str],
    exams: Dict[str, dict],
) -> Dict[str, Any]:
    """
    Compute:
      - student_conflicts: same student overlapping in same slot (HARD - must be 0)
      - student_same_day_conflicts: same student with >1 exam on same day (soft)
      - slot_overload: count of exams per slot (for spreading)
    
    Note: Department clashes are OK if students are from different semesters.
    The student_conflicts metric already handles the real constraint.
    """
    # student -> exams
    student_to_exams: Dict[str, List[str]] = {}
    for eid, e in exams.items():
        for sid in e["student_ids"]:
            student_to_exams.setdefault(sid, []).append(eid)

    # conflicts: same student with multiple exams in same slot
    conflicts = 0
    same_day_conflicts = 0
    for sid, eids in student_to_exams.items():
        slots = [chrom[eid] for eid in eids]
        conflicts += len(slots) - len(set(slots))

        # one exam per day: count extra exams on same day
        days = [_slot_day(slot) for slot in slots]
        same_day_conflicts += len(days) - len(set(days))

    # slot usage for spreading
    slot_counts: Dict[str, int] = defaultdict(int)
    slot_to_deps: Dict[str, List[str]] = defaultdict(list)
    for eid, slot in chrom.items():
        dep = exams[eid].get("department", "GEN")
        slot_to_deps[slot].append(dep)
        slot_counts[slot] += 1

    # dept_clashes: informational only (not penalized if student_conflicts=0)
    dept_clash_count = 0
    for slot, deps in slot_to_deps.items():
        for d in set(deps):
            dept_clash_count += deps.count(d) - 1

    # Encourage spreading exams across available slots.
    slot_overload = sum(max(0, count - 1) for count in slot_counts.values())

    return {
        "student_conflicts": conflicts,
        "student_same_day_conflicts": same_day_conflicts,
        "department_clashes": dept_clash_count,  # informational
        "slot_overload": slot_overload,
    }


def build_exam_eval_index(exams: Dict[str, dict]) -> Dict[str, Any]:
    """Precompute structures reused across GA fitness evaluations."""
    student_to_exams: Dict[str, List[str]] = {}
    exam_dept: Dict[str, str] = {}
    for eid, e in exams.items():
        exam_dept[eid] = e.get("department", "GEN")
        for sid in e.get("student_ids", []):
            student_to_exams.setdefault(sid, []).append(eid)
    return {"student_to_exams": student_to_exams, "exam_dept": exam_dept, "exam_count": len(exams)}


def exam_timetable_metrics_indexed(chrom: Dict[str, str], index: Dict[str, Any]) -> Dict[str, Any]:
    student_to_exams: Dict[str, List[str]] = index["student_to_exams"]
    exam_dept: Dict[str, str] = index["exam_dept"]

    conflicts = 0
    same_day_conflicts = 0
    for _, eids in student_to_exams.items():
        slots = [chrom[eid] for eid in eids]
        conflicts += len(slots) - len(set(slots))
        days = [_slot_day(slot) for slot in slots]
        same_day_conflicts += len(days) - len(set(days))

    slot_to_deps: Dict[str, List[str]] = defaultdict(list)
    slot_counts: Dict[str, int] = defaultdict(int)
    for eid, slot in chrom.items():
        slot_to_deps[slot].append(exam_dept.get(eid, "GEN"))
        slot_counts[slot] += 1

    # dept_clashes: informational only
    dept_clash_count = 0
    for deps in slot_to_deps.values():
        for d in set(deps):
            dept_clash_count += deps.count(d) - 1

    slot_overload = sum(max(0, count - 1) for count in slot_counts.values())

    return {
        "student_conflicts": conflicts,
        "student_same_day_conflicts": same_day_conflicts,
        "department_clashes": dept_clash_count,  # informational
        "slot_overload": slot_overload,
    }


def exam_timetable_fitness_indexed(chrom: Dict[str, str], index: Dict[str, Any]) -> float:
    m = exam_timetable_metrics_indexed(chrom, index)
    conflicts = m["student_conflicts"]
    same_day = m["student_same_day_conflicts"]
    slot_overload = m["slot_overload"]

    # HARD CONSTRAINT: student_conflicts must be 0 (same student can't have 2 exams at same time)
    # Same-day is soft (students prefer not having 2 exams same day but it's allowed)
    # Dept clashes are OK if different semesters (student_conflicts handles the real constraint)
    penalty = 10000.0 * conflicts + 10.0 * same_day + 1.0 * slot_overload
    base = max(100000.0, 1000.0 * float(index.get("exam_count", 0) or 0))
    return max(0.0, base - penalty)


def exam_timetable_fitness(chrom: Dict[str, str], exams: Dict[str, dict]) -> float:
    m = exam_timetable_metrics(chrom, exams)
    conflicts = m["student_conflicts"]
    same_day = m["student_same_day_conflicts"]
    slot_overload = m["slot_overload"]

    # HARD CONSTRAINT: student_conflicts must be 0 (same student can't have 2 exams at same time)
    # Same-day is soft (students prefer not having 2 exams same day but it's allowed)
    # Dept clashes are OK if different semesters (student_conflicts handles the real constraint)
    penalty = 10000.0 * conflicts + 10.0 * same_day + 1.0 * slot_overload

    # Scale the baseline with problem size so typical schedules score positive
    # and improvements are visible in UI (no "always 0" collapse).
    base = max(100000.0, 1000.0 * float(len(exams)))
    return max(0.0, base - penalty)