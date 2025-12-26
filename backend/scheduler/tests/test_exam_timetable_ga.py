from scheduler.algorithms.exam_timetable_ga import ExamTimetableGA

def test_ga_runs():
    exams = {
        "E1": {"student_ids": ["S1", "S2"], "department": "CS"},
        "E2": {"student_ids": ["S2", "S3"], "department": "CS"},
        "E3": {"student_ids": ["S3"], "department": "EE"},
    }
    students = {"S1": {}, "S2": {}, "S3": {}}
    timeslots = {
        "EXAM_D1_M": {"type": "exam", "label": "D1 M"},
        "EXAM_D1_E": {"type": "exam", "label": "D1 E"},
        "EXAM_D2_M": {"type": "exam", "label": "D2 M"},
    }
    ga = ExamTimetableGA(exams, students, timeslots)
    best = ga.run(population_size=20, generations=20)
    assert isinstance(best["chromosome"], dict)
    assert len(best["chromosome"]) == 3