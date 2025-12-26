from collections import defaultdict
from typing import List, Dict


def group_by_department(student_ids: List[str], students: Dict[str, dict]) -> Dict[str, List[str]]:
    dep_groups = defaultdict(list)
    for sid in student_ids:
        dep_groups[students[sid]["department"]].append(sid)
    return dep_groups


def group_by_section(student_ids: List[str], students: Dict[str, dict]) -> Dict[str, List[str]]:
    sec_groups = defaultdict(list)
    for sid in student_ids:
        sec_groups[students[sid]["section"]].append(sid)
    return sec_groups


def avoid_same_section_neighbors(order: List[str], students: Dict[str, dict]) -> List[str]:
    by_sec = group_by_section(order, students)
    secs = list(by_sec.keys())
    result = []
    idx = {s: 0 for s in secs}
    done = False
    while not done:
        done = True
        for s in secs:
            if idx[s] < len(by_sec[s]):
                result.append(by_sec[s][idx[s]])
                idx[s] += 1
                done = False
    return result