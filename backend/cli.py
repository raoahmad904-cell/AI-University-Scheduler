#aapke project ka command-line interface (CLI) hai. Is file ka role hai:
#User ko terminal/command prompt se direct commands dene ki facility dena.
#User yahan se different tasks run kar sakta hai, jaise:
#Exam rooms allocate karna
#Exam timetable banana (Genetic Algorithm se)
#Class timetable banana (CSP se)
#Lab timetable banana (CSP se)
#Ye file user ke input (arguments) ko parse karti hai, data load karti hai, 
# aur relevant algorithm ko call karti hai.
#Output ko readable format me print karti hai.
import argparse
# argparse CLI (command line interface) arguments lene ke liye use hota hai

from scheduler.utils.loader import load_all_data
# Ye function saara required data load karta hai
# (rooms, students, exams, teachers, courses, timeslots)

from scheduler.algorithms.exam_room_allocator import ExamRoomAllocator
# Exam ke liye rooms allocate karne wali algorithm

from scheduler.algorithms.exam_timetable_ga import ExamTimetableGA
# Exam timetable banane ke liye Genetic Algorithm

from scheduler.algorithms.class_timetable_csp import ClassTimetableCSP
# Class timetable ke liye CSP (Constraint Satisfaction Problem)

from scheduler.algorithms.lab_timetable_csp import LabTimetableCSP
# Lab timetable ke liye CSP solver

from scheduler.utils.reporting import (
    print_allocation,
    print_exam_timetable,
    print_class_timetable,
    print_lab_timetable
)
# Results ko readable format mein print karne ke liye utilities


def main():
    # Argument parser create karo
    parser = argparse.ArgumentParser(description="AI University Scheduler CLI")

    # User se task lena (kaunsa kaam karna hai)
    parser.add_argument(
        "--task",
        choices=[
            "allocate-exam-rooms",
            "exam-timetable",
            "class-timetable",
            "lab-timetable"
        ],
        required=True
    )

    # Allocation mode (future extensibility)
    parser.add_argument("--mode", choices=["column"], default="column")

    # Exam ID (sirf exam room allocation ke liye)
    parser.add_argument("--exam_id")

    # GA population size (exam timetable ke liye)
    parser.add_argument("--population", type=int, default=60)

    # GA generations count
    parser.add_argument("--generations", type=int, default=100)

    # CLI arguments parse karo
    args = parser.parse_args()

    # ---------------------------------------
    # 1. Load all required data
    # ---------------------------------------
    # Ye saara university data load karega
    rooms, students, exams, teachers, courses, timeslots = load_all_data()

    # ---------------------------------------
    # TASK 1: Allocate Exam Rooms
    # ---------------------------------------
    if args.task == "allocate-exam-rooms":

        # Exam ID mandatory hai
        if not args.exam_id:
            raise SystemExit("Please provide --exam_id")

        # Exam room allocator initialize karo
        allocator = ExamRoomAllocator(
            rooms=rooms,
            students=students,
            exams=exams
        )

        # Selected exam ke liye room allocation
        allocation = allocator.allocate_column_mix([args.exam_id])

        # Allocation result print karo
        print_allocation(allocation, rooms, students)

    # ---------------------------------------
    # TASK 2: Exam Timetable (GA)
    # ---------------------------------------
    elif args.task == "exam-timetable":

        # Genetic Algorithm initialize karo
        # Students pass kiye jaate hain taake conflicts check ho saken
        ga = ExamTimetableGA(
            exams=exams,
            students=students,
            timeslots=timeslots
        )

        # GA run karo with given population & generations
        best = ga.run(
            population_size=args.population,
            generations=args.generations
        )

        # Best exam timetable print karo
        print_exam_timetable(best, exams, timeslots)

    # ---------------------------------------
    # TASK 3: Class Timetable (CSP)
    # ---------------------------------------
    elif args.task == "class-timetable":

        # CSP solver initialize karo
        solver = ClassTimetableCSP(
            rooms=rooms,
            teachers=teachers,
            courses=courses,
            timeslots=timeslots,
            students=students
        )

        # CSP solve karo
        solution = solver.solve()

        # Class timetable print karo
        print_class_timetable(solution, courses, rooms, timeslots)

    # ---------------------------------------
    # TASK 4: Lab Timetable (CSP)
    # ---------------------------------------
    elif args.task == "lab-timetable":

        # Lab CSP solver
        solver = LabTimetableCSP(
            rooms=rooms,
            teachers=teachers,
            courses=courses,
            timeslots=timeslots,
            students=students
        )

        # Solve lab timetable
        solution = solver.solve()

        # Lab timetable print karo
        print_lab_timetable(solution, courses, rooms, timeslots)


# Program ka entry point
if __name__ == "__main__":
    main()
