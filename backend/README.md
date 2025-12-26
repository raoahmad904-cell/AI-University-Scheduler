# AI-Based University Timetable, Exam Scheduling & Room Allocation Optimization System

This project provides AI-powered scheduling for:
- Part 1: Class Timetable (CSP + heuristics)
- Part 2: Lab Timetable (CSP with contiguous slots)
- Part 3: Exam Timetable (Genetic Algorithm)
- Part 4: Exam Room Allocation (Room/Department/Hybrid)
- Part 5: Frontend (React + API)

## Prerequisites
- Python 3.10+ and pip
- Node.js 18+ (for frontend)

## 1) Backend Setup

```bash
cd ai-university-scheduler/backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Validate algorithms with sample data:

```bash
# Room allocation
python cli.py --task allocate-exam-rooms --mode room --exam_id EXAM1
python cli.py --task allocate-exam-rooms --mode department --exam_id EXAM1
python cli.py --task allocate-exam-rooms --mode hybrid --exam_id EXAM1

# Exam timetable GA
python cli.py --task exam-timetable --population 60 --generations 100

# Class timetable CSP
python cli.py --task class-timetable

# Lab timetable CSP
python cli.py --task lab-timetable

# Run tests
pytest -q
```

Run API:

```bash
uvicorn app:app --reload
# API docs: http://127.0.0.1:8000/docs
```

## 2) Frontend Setup

```bash
cd ../frontend
npm install
npm run dev
# open: http://localhost:5173
```

By default, frontend calls backend at http://127.0.0.1:8000. You can change it in `src/api.ts`.

## 3) Docker Compose (optional)

```bash
cd ..
docker-compose up --build
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

## Data Files

Located in `backend/scheduler/data/`:
- rooms.yaml
- students.yaml
- exams.yaml
- teachers.yaml
- courses.yaml
- timeslots.yaml

You can replace these with your real data.

## Notes

- This is a working baseline with simple heuristics and GA designed for clarity and extensibility.
- You can tune GA parameters and CSP strategies for larger datasets.