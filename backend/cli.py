import argparse
from scheduler.utils.loader import load_all_data
from scheduler.algorithms.exam_room_allocator import ExamRoomAllocator
from scheduler.algorithms.exam_timetable_ga import ExamTimetableGA
from scheduler.algorithms.class_timetable_csp import ClassTimetableCSP
from scheduler.algorithms.lab_timetable_csp import LabTimetableCSP
from scheduler.utils.reporting import print_allocation, print_exam_timetable, print_class_timetable, print_lab_timetable

def main():
    parser = argparse.ArgumentParser(description="AI University Scheduler CLI")
    parser.add_argument("--task", choices=["allocate-exam-rooms", "exam-timetable", "class-timetable", "lab-timetable"], required=True)
    parser.add_argument("--mode", choices=["room", "department", "hybrid"])
    parser.add_argument("--exam_id")
    parser.add_argument("--population", type=int, default=60)
    parser.add_argument("--generations", type=int, default=100)
    args = parser.parse_args()

    # 1. Load Data (Includes the 'enrolled_courses' fix from loader.py)
    rooms, students, exams, teachers, courses, timeslots = load_all_data()

    if args.task == "allocate-exam-rooms":
        if not args.exam_id or not args.mode:
            raise SystemExit("Please provide --exam_id and --mode")
        allocator = ExamRoomAllocator(rooms=rooms, students=students, exams=exams)
        if args.mode == "room":
            allocation = allocator.allocate_room_based(args.exam_id)
        elif args.mode == "department":
            allocation = allocator.allocate_department_based(args.exam_id)
        else:
            allocation = allocator.allocate_hybrid(args.exam_id)
        print_allocation(allocation, rooms, students)

    elif args.task == "exam-timetable":
        # Pass students to GA so it can check for individual conflicts
        ga = ExamTimetableGA(exams=exams, students=students, timeslots=timeslots)
        best = ga.run(population_size=args.population, generations=args.generations)
        print_exam_timetable(best, exams, timeslots)

    elif args.task == "class-timetable":
        # Pass students to CSP so it can block occupied slots
        solver = ClassTimetableCSP(rooms=rooms, teachers=teachers, courses=courses, timeslots=timeslots, students=students)
        solution = solver.solve()
        print_class_timetable(solution, courses, rooms, timeslots)

    elif args.task == "lab-timetable":
        # Pass students to CSP
        solver = LabTimetableCSP(rooms=rooms, teachers=teachers, courses=courses, timeslots=timeslots, students=students)
        solution = solver.solve()
        print_lab_timetable(solution, courses, rooms, timeslots)

if __name__ == "__main__":
    main()