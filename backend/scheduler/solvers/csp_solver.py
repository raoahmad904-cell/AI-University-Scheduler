from collections import defaultdict
from typing import Dict, List, Tuple
import random

class CSPSolver:
    def __init__(self, rooms: Dict, teachers: Dict, courses: Dict, timeslots: Dict, students: Dict):
        self.rooms = rooms
        self.teachers = teachers
        self.courses = courses
        self.timeslots = {k: v for k, v in timeslots.items() if v.get("type") == "class"}
        self.students = students

        # --- FIX 1: Map Student IDs to their actual Enrolled Courses ---
        # This prevents the "wrong output" for specific student IDs
        self.student_enrollments = defaultdict(set)
        for sid, s_data in self.students.items():
            # Extract enrolled_courses if available, else infer from group
            enrolled = s_data.get("enrolled_courses", [])
            for c_id in enrolled:
                self.student_enrollments[sid].add(c_id)

        # Trackers
        self.used_room_slots = set()      # (room_id, slot_id)
        self.used_teacher_slots = set()   # (teacher_id, slot_id)
        self.used_student_slots = set()   # (student_id, slot_id)  <-- NEW TRACKER

    def solve(self) -> Dict[str, dict]:
        assignments = {}
        
        # Build task list: (course_id, section_letter, session_number)
        tasks = []
        for cid, c in self.courses.items():
            sessions = c.get("hours_per_week", 2)
            for sec in c.get("sections", ["A"]):
                for i in range(1, sessions + 1):
                    tasks.append((cid, sec, i))

        # Sort tasks: handle courses with the most students first
        tasks.sort(key=lambda x: len(self._get_students_in_course(x[0])), reverse=True)

        for course_id, section, session_idx in tasks:
            placed = self._try_assign(course_id, section, session_idx, assignments)
            if not placed:
                print(f"Warning: Could not place {course_id} Section {section} Session {session_idx}")

        return assignments

    def _get_students_in_course(self, course_id: str) -> List[str]:
        """Returns list of Student IDs enrolled in a specific course."""
        return [sid for sid, courses in self.student_enrollments.items() if course_id in courses]

    def _try_assign(self, course_id, section, session_idx, assignments) -> bool:
        course = self.courses[course_id]
        enrolled_students = self._get_students_in_course(course_id)
        
        # Shuffle slots to distribute load
        slots = list(self.timeslots.keys())
        random.shuffle(slots)

        for slot_id in slots:
            # --- FIX 2: Individual Student Conflict Check ---
            # If ANY student in this course is already busy in this slot, skip it.
            if any((sid, slot_id) in self.used_student_slots for sid in enrolled_students):
                continue

            # Teacher Conflict Check
            teacher_id = course.get("teacher_id")
            if (teacher_id, slot_id) in self.used_teacher_slots:
                continue

            # Room Conflict & Capacity Check
            suitable_room = None
            for rid, r_data in self.rooms.items():
                if (rid, slot_id) in self.used_room_slots:
                    continue
                if r_data["capacity"] >= len(enrolled_students):
                    suitable_room = rid
                    break
            
            if not suitable_room:
                continue

            # --- SUCCESS: Commit Assignment ---
            assign_key = f"{course_id}|{section}|S{session_idx}"
            assignments[assign_key] = {
                "room": suitable_room,
                "slot": slot_id,
                "teacher": teacher_id
            }

            # Update all trackers
            self.used_room_slots.add((suitable_room, slot_id))
            self.used_teacher_slots.add((teacher_id, slot_id))
            for sid in enrolled_students:
                self.used_student_slots.add((sid, slot_id))
            
            return True
        
        return False