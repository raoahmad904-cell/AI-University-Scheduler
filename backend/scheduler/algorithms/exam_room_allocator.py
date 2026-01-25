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
        return max(0, self.rooms[room_id]["capacity"])  

#Prepares student lists for each exam, arranged to minimize adjacent same-section students.
    def _build_exam_buckets(self, exam_ids: List[str]) -> Dict[str, List[str]]:
        buckets: Dict[str, List[str]] = {}
        for eid in exam_ids:
            exam = self.exams.get(eid)
            if not exam:
                continue
            sids = exam.get("student_ids", [])
            #Arranges students to avoid adjacent same-section students. and add in the buckets dict
            buckets[eid] = avoid_same_section_neighbors(sids, self.students)
        return {k: v for k, v in buckets.items() if v}  

    def allocate_column_mix(self, exam_ids: List[str]) -> Dict[str, dict]:

        buckets = self._build_exam_buckets(exam_ids)
        remaining_counts = {k: len(v) for k, v in buckets.items()}
        #Rooms sorted by size largest to smallest
        rooms_sorted = sorted(self.rooms.keys(), key=lambda r: self.effective_capacity(r), reverse=True)

        allocation: Dict[str, dict] = {}
        columns = self.columns
        # Tracking column usage per exam {"MATH101": {0, 2}, "PHY101": {1}}
        exam_column_usage: Dict[str, set] = {eid: set() for eid in remaining_counts.keys()}
        #For each room: Skip if no students lef , Skip if room has 0 capacity
        for room_id in rooms_sorted:
            if not any(remaining_counts.values()):
                break
            cap = self.effective_capacity(room_id) 
            if cap <= 0:
                continue

            #check rows
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
                # Pick exam with highest remaining student that has not used this column index yet.
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
                    #seating assignment Takes next student, Reduces remaining count
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
            #final room data
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

