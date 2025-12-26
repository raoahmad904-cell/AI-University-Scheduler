"""
Heuristic (A* / greedy) seeding for timetables.
Here we provide a simple greedy constructor that can be used to seed GA.
"""

from typing import Dict, Any, List, Tuple, Optional
from collections import defaultdict
from scheduler.utils.loader import load_all_data


def _get_slot_day(slot_id: str) -> str:
    """Extract day from slot ID: EXAM_D1_M -> D1"""
    if "_" in slot_id:
        parts = slot_id.split("_")
        if len(parts) > 1:
            return parts[1]
    return slot_id


def greedy_exam_seed(
    exams: Optional[Dict[str, dict]] = None,
    timeslots: Optional[Dict[str, dict]] = None,
) -> Dict[str, str]:
    """
    Greedy builder that minimizes:
      1. Student conflicts (same student in 2 exams at same slot) - CRITICAL
      2. Same-day conflicts (same student with 2+ exams on same day) - IMPORTANT
    
    Sort exams by number of students descending, then assign to best slot.
    """
    if exams is None or timeslots is None:
        _, _, loaded_exams, _, _, loaded_timeslots = load_all_data()
        exams = loaded_exams
        timeslots = loaded_timeslots

    exam_ids = list(exams.keys())
    exam_ids.sort(key=lambda eid: len(exams[eid].get("student_ids", [])), reverse=True)

    exam_slots = {k: v for k, v in timeslots.items() if v.get("type") == "exam"}
    slot_ids = list(exam_slots.keys())

    chrom: Dict[str, str] = {}
    # Track students assigned to each slot
    slot_students: Dict[str, set] = {s: set() for s in slot_ids}
    # Track students assigned to each day (for same-day penalty)
    day_students: Dict[str, set] = defaultdict(set)

    for eid in exam_ids:
        best_slot = None
        best_score = float('inf')
        
        for slot in slot_ids:
            day = _get_slot_day(slot)
            
            # Count conflicts for this slot
            slot_conflicts = 0
            same_day_conflicts = 0
            
            for sid in exams[eid]["student_ids"]:
                if sid in slot_students[slot]:
                    slot_conflicts += 1
                elif sid in day_students[day]:
                    same_day_conflicts += 1
            
            # Score: slot conflicts are critical, same-day is important but less severe
            score = 1000 * slot_conflicts + 10 * same_day_conflicts
            
            if score < best_score:
                best_score = score
                best_slot = slot

        if best_slot is None:
            best_slot = slot_ids[0]
        
        chrom[eid] = best_slot
        day = _get_slot_day(best_slot)
        for sid in exams[eid]["student_ids"]:
            slot_students[best_slot].add(sid)
            day_students[day].add(sid)

    return chrom