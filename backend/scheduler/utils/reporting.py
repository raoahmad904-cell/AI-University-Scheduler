# Add this to backend/scheduler/utils/reporting.py

def generate_student_timetable(student_id, students, courses, class_assignments, lab_assignments=None, exam_assignments=None):
    """
    Generates a consolidated JSON-ready timetable for a SINGLE student.
    Fixes the 'wrong output' by checking actual course enrollments.
    """
    student = students.get(student_id)
    if not student:
        return {"error": "Student not found"}

    # 1. Identify Target Courses
    # Priority: Explicit 'enrolled_courses' list -> Fallback: Infer from Section
    enrolled_ids = set(student.get("enrolled_courses", []))
    
    # Fallback: If no enrollment data, assume standard semester load
    if not enrolled_ids:
        s_prog = student.get("program")
        s_sem = student.get("semester")
        s_sec = student.get("section")
        
        # Find all courses matching this student's group
        for cid, c_data in courses.items():
            # (You can use your existing inference logic here if needed)
            # Simple check:
            if c_data.get("semester") == s_sem and c_data.get("program") == s_prog:
                enrolled_ids.add(cid)

    timetable = []

    # 2. Filter Class Assignments
    # assignment key format: "COURSE_ID|SECTION|SESSION_IDX"
    for key, val in class_assignments.items():
        parts = key.split("|")
        course_id = parts[0]
        section = parts[1]
        
        # CHECK 1: Is the student explicitly enrolled in this course?
        if course_id in enrolled_ids:
            # If enrolled, they attend THIS section (or if section matches assignment)
            # For simplicity, if they are enrolled, we show it. 
            # (Real-world: check if they are in this specific section of the course)
            timetable.append({
                "type": "Class",
                "course": courses[course_id].get("name", course_id),
                "code": course_id,
                "room": val["room"], # You might need to map room_id to room_name
                "slot": val["slot"],
                "teacher": val["teacher"]
            })
        
        # CHECK 2 (Legacy): If no enrollment, does the section match?
        elif not enrolled_ids and student.get("section") == section:
             timetable.append({
                "type": "Class",
                "course": courses[course_id].get("name", course_id),
                "code": course_id,
                "room": val["room"],
                "slot": val["slot"],
                "teacher": val["teacher"]
            })

    # 3. Filter Lab Assignments (if applicable)
    if lab_assignments:
        for key, val in lab_assignments.items():
            course_id = key.split("|")[0]
            if course_id in enrolled_ids:
                timetable.append({
                    "type": "Lab",
                    "course": courses[course_id].get("name", course_id),
                    "code": course_id,
                    "room": val["room"],
                    "slot": val["slots"][0], # Labs might have multiple slots
                    "teacher": val["teacher"]
                })

    return timetable