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

def test_room_based_capacity_respected():
    alloc = ExamRoomAllocator(rooms, students, exams).allocate_room_based("E1")
    assert sum(len(v) for v in alloc.values()) == 12
    assert len(alloc["A"]) <= 10

def test_department_based_no_mix_rooms():
    alloc = ExamRoomAllocator(rooms, students, exams).allocate_department_based("E1")
    for room, stu_list in alloc.items():
        assert all(students[s]["department"] == "CS" for s in stu_list)

def test_hybrid_fills_remaining():
    alloc = ExamRoomAllocator(rooms, students, exams).allocate_hybrid("E1")
    total_assigned = sum(len(v) for v in alloc.values())
    assert total_assigned == 12