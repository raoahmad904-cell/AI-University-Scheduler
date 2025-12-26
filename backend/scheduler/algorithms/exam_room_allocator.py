import math
from typing import Dict, List
from collections import defaultdict
from scheduler.utils.constraints import group_by_department, avoid_same_section_neighbors

class ExamRoomAllocator:
    def __init__(self, rooms: Dict[str, dict], students: Dict[str, dict], exams: Dict[str, dict], *, columns: int = 5, seats_per_column: int = 6):
        self.rooms = rooms
        self.students = students
        self.exams = exams
        self.columns = max(1, columns)
        self.seats_per_column = max(1, seats_per_column)

    def effective_capacity(self, room_id: str) -> int:
        # Capacity is now taken as-is; seat spacing has been removed per updated requirements.
        return max(0, self.rooms[room_id]["capacity"])

    def _build_exam_buckets(self, exam_ids: List[str]) -> Dict[str, List[str]]:
        buckets: Dict[str, List[str]] = {}
        for eid in exam_ids:
            exam = self.exams.get(eid)
            if not exam:
                continue
            sids = exam.get("student_ids", [])
            # Spread sections to reduce adjacency inside buckets.
            buckets[eid] = avoid_same_section_neighbors(sids, self.students)
        return {k: v for k, v in buckets.items() if v}

    def allocate_column_mix(self, exam_ids: List[str]) -> Dict[str, dict]:
        """
        Assign students from multiple exams into room seat grids with column constraint:
        - Each column within a room is homogeneous: all seats in that column carry the same exam.
        - Columns are fixed globally; row count per room expands to use the full room capacity.
        - Fills rooms in descending capacity order until students are exhausted.
        Returns mapping room_id -> {rows: [[{exam_id, student_id, column}]], columns, seats_per_column, assigned_count}.
        Unassigned students (if capacity short) are returned under key "_unassigned".
        """

        buckets = self._build_exam_buckets(exam_ids)
        remaining_counts = {k: len(v) for k, v in buckets.items()}
        rooms_sorted = sorted(self.rooms.keys(), key=lambda r: self.effective_capacity(r), reverse=True)

        allocation: Dict[str, dict] = {}
        columns = self.columns
        # Track which column indices an exam has already occupied (global across rooms)
        exam_column_usage: Dict[str, set] = {eid: set() for eid in remaining_counts.keys()}

        for room_id in rooms_sorted:
            if not any(remaining_counts.values()):
                break

            cap = self.effective_capacity(room_id)
            if cap <= 0:
                continue

            seats_per_column_room = max(1, math.ceil(cap / columns))
            total_seats_per_room = min(cap, columns * seats_per_column_room)

            seats_remaining = cap

            # Build column-wise assignments first to keep each column single-exam.
            column_assignments: List[List[dict]] = []
            for col_idx in range(columns):
                if seats_remaining <= 0:
                    column_assignments.append([])
                    continue
                if not any(remaining_counts.values()):
                    column_assignments.append([])
                    continue
                # Pick exam with highest remaining count that has not used this column index yet.
                eligible = [
                    eid for eid, count in remaining_counts.items()
                    if count > 0 and col_idx not in exam_column_usage[eid]
                ]
                if eligible:
                    eid = max(eligible, key=lambda k: remaining_counts[k])
                else:
                    # Fallback: use the max remaining even if column was used (avoids stranding students).
                    eid = max(remaining_counts.keys(), key=lambda k: remaining_counts[k])
                    if remaining_counts[eid] <= 0:
                        column_assignments.append([])
                        continue
                exam_column_usage[eid].add(col_idx)
                placements = []
                for row_idx in range(seats_per_column_room):
                    if remaining_counts[eid] <= 0 or seats_remaining <= 0:
                        break
                    sid = buckets[eid].pop(0)
                    remaining_counts[eid] -= 1
                    seats_remaining -= 1
                    placements.append({
                        "exam_id": eid,
                        "student_id": sid,
                        "column": chr(ord("A") + col_idx),
                        "row_index": row_idx,
                    })
                column_assignments.append(placements)

            # Convert column-wise placements into row-wise view expected by frontend.
            rows = []
            for row_idx in range(seats_per_column_room):
                row = []
                for col_idx in range(columns):
                    col = column_assignments[col_idx]
                    if row_idx < len(col):
                        row.append(col[row_idx])
                if row:
                    rows.append(row)

            assigned_count = sum(len(r) for r in rows)
            column_view = [
                {
                    "column": chr(ord("A") + idx),
                    "exam_id": col[0]["exam_id"] if col else None,
                    "students": [p["student_id"] for p in col],
                }
                for idx, col in enumerate(column_assignments)
            ]
            allocation[room_id] = {
                "rows": rows,
                "columns": columns,
                "seats_per_column": seats_per_column_room,
                "column_assignments": column_view,
                "assigned_count": assigned_count,
                "capacity": cap,
            }

        # Collect any unassigned students if capacity ran out
        unassigned = {}
        for eid, count in remaining_counts.items():
            if count > 0:
                unassigned[eid] = buckets[eid][:count]

        if unassigned:
            allocation["_unassigned"] = unassigned

        return allocation

    def allocate_room_based(self, exam_id: str) -> Dict[str, List[str]]:
        exam = self.exams[exam_id]
        student_ids = avoid_same_section_neighbors(exam["student_ids"], self.students)
        allocation = defaultdict(list)
        rooms_sorted = sorted(self.rooms.keys(), key=lambda r: self.effective_capacity(r), reverse=True)
        i = 0
        for room_id in rooms_sorted:
            cap = self.effective_capacity(room_id)
            take = student_ids[i:i+cap]
            allocation[room_id].extend(take)
            i += len(take)
            if i >= len(student_ids):
                break
        return dict(allocation)

    def allocate_department_based(self, exam_id: str) -> Dict[str, List[str]]:
        exam = self.exams[exam_id]
        exam_dept = exam.get("department")
        student_ids = exam["student_ids"]
        if exam_dept:
            student_ids = [sid for sid in student_ids if self.students.get(sid, {}).get("department") == exam_dept]
        dep_groups = group_by_department(student_ids, self.students)
        allocation = defaultdict(list)
        room_ids = list(self.rooms.keys())
        dep_order = sorted(dep_groups.items(), key=lambda kv: len(kv[1]), reverse=True)
        used_rooms = set()
        for dep, stu_list in dep_order:
            stu_list = avoid_same_section_neighbors(stu_list, self.students)
            remaining = list(stu_list)
            candidate_rooms = sorted(room_ids, key=lambda r: self.effective_capacity(r), reverse=True)
            for room_id in candidate_rooms:
                if room_id in used_rooms:
                    continue
                cap = self.effective_capacity(room_id)
                take = remaining[:cap]
                if not take:
                    continue
                allocation[room_id].extend(take)
                used_rooms.add(room_id)
                remaining = remaining[len(take):]
                if not remaining:
                    break
            if remaining:
                for room_id in candidate_rooms:
                    if room_id in used_rooms:
                        continue
                    cap = self.effective_capacity(room_id)
                    take = remaining[:cap]
                    if not take:
                        continue
                    allocation[room_id].extend(take)
                    used_rooms.add(room_id)
                    remaining = remaining[len(take):]
                    if not remaining:
                        break
        return dict(allocation)

    def allocate_hybrid(self, exam_id: str) -> Dict[str, List[str]]:
        dep_alloc = self.allocate_department_based(exam_id)
        exam = self.exams[exam_id]
        assigned = set()
        for lst in dep_alloc.values():
            assigned.update(lst)
        remaining = [sid for sid in exam["student_ids"] if sid not in assigned]
        remaining = avoid_same_section_neighbors(remaining, self.students)
        if not remaining:
            return dep_alloc
        rooms_sorted = sorted(self.rooms.keys(), key=lambda r: self.effective_capacity(r), reverse=True)
        used = set(dep_alloc.keys())
        allocation = defaultdict(list, dep_alloc)
        i = 0
        for room_id in rooms_sorted:
            if room_id in used:
                continue
            cap = self.effective_capacity(room_id)
            take = remaining[i:i+cap]
            allocation[room_id].extend(take)
            i += len(take)
            if i >= len(remaining):
                break
        if i < len(remaining):
            used_rooms_sorted = sorted(list(used), key=lambda r: len(allocation[r]))
            for room_id in used_rooms_sorted:
                cap = self.effective_capacity(room_id)
                free = max(0, cap - len(allocation[room_id]))
                if free <= 0:
                    continue
                take = remaining[i:i+free]
                allocation[room_id].extend(take)
                i += len(take)
                if i >= len(remaining):
                    break
        return dict(allocation)