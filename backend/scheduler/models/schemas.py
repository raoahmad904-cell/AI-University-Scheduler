from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class Room:
    id: str
    name: str
    capacity: int
    tags: List[str]  # e.g., ["near-CS", "lab", "ground-floor"]

@dataclass
class Student:
    id: str
    department: str
    section: str  # e.g., "A", "B"

@dataclass
class Exam:
    id: str
    course_code: str
    title: str
    student_ids: List[str]
    department: Optional[str] = None

@dataclass
class Teacher:
    id: str
    name: str
    availability: List[str]  # timeslot ids

@dataclass
class Course:
    id: str
    title: str
    department: str
    sections: List[str]
    teacher_id: str
    hours_per_week: int
    is_lab: bool = False
    lab_room_tags: Optional[List[str]] = None

@dataclass
class Timeslot:
    id: str
    label: str  # e.g., "Mon 9-10", "Tue 10-11" or "2025-12-16 Morning"
    type: str   # "class" | "lab" | "exam"