import pytest
from scheduler.algorithms.exam_room_allocator import ExamRoomAllocator

rooms = {
    "A": {"name": "A", "capacity": 10, "tags": []},
    "B": {"name": "B", "capacity": 8, "tags": []},
    "C": {"name": "C", "capacity": 6, "tags": []},
}
students = {
    f"S{i}": {"department": "CS" if i <= 10 else "BBA", "section": "A" if i % 2 == 0 else "B"}
    for i in range(1, 21)
}
exams = {
    "E1": {"id": "E1", "course_code": "X", "title": "T", "student_ids": [f"S{i}" for i in range(1, 13)], "department": "CS"}
}

