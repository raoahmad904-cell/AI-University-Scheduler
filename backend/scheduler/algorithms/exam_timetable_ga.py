import random
from typing import Dict, Any, List
from collections import defaultdict
from scheduler.solvers.ga_optimizer import GAOptimizer, GAConfig
from scheduler.solvers.evaluator import build_exam_eval_index, exam_timetable_fitness_indexed
from scheduler.solvers.heuristic_builder import greedy_exam_seed


class ExamTimetableGA:
    def __init__(self, exams: Dict[str, dict], students: Dict[str, dict], timeslots: Dict[str, dict]):
        self.exams = exams
        self.students = students
        self.timeslots = {k: v for k, v in timeslots.items() if v["type"] == "exam"}
        self.exam_ids = list(exams.keys())
        self.slot_ids = list(self.timeslots.keys())
        self._eval_index = build_exam_eval_index(exams)
        
        # Pre-compute student-to-exams mapping for smart mutation
        self._student_to_exams: Dict[str, List[str]] = {}
        for eid, e in exams.items():
            for sid in e.get("student_ids", []):
                self._student_to_exams.setdefault(sid, []).append(eid)

    def random_chromosome(self) -> Dict[str, str]:
        return {eid: random.choice(self.slot_ids) for eid in self.exam_ids}

    def crossover(self, a: Dict[str, str], b: Dict[str, str]) -> Dict[str, str]:
        child: Dict[str, str] = {}
        for eid in self.exam_ids:
            child[eid] = a[eid] if random.random() < 0.5 else b[eid]
        return child

    def mutate(self, chrom: Dict[str, str]) -> Dict[str, str]:
        """Smart mutation that tries to reduce same-day conflicts."""
        # Find exams causing same-day conflicts
        student_day_exams: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        for sid, eids in self._student_to_exams.items():
            for eid in eids:
                slot = chrom[eid]
                day = slot.split('_')[1] if '_' in slot else slot  # EXAM_D1_M -> D1
                student_day_exams[sid][day].append(eid)
        
        # Find problematic exams (causing same-day conflicts)
        problem_exams = set()
        for sid, days in student_day_exams.items():
            for day, eids in days.items():
                if len(eids) > 1:
                    # All but one are problems
                    problem_exams.update(eids[1:])
        
        for eid in self.exam_ids:
            # Higher mutation rate for problematic exams
            mutation_chance = 0.4 if eid in problem_exams else 0.08
            
            if random.random() < mutation_chance:
                chrom[eid] = random.choice(self.slot_ids)
        
        return chrom

    def run(self, population_size: int = 100, generations: int = 200) -> Dict[str, Any]:
        # Compute greedy seed once (not per chromosome) to avoid repeated disk loads.
        base_seed = greedy_exam_seed(exams=self.exams, timeslots=self.timeslots)

        # Seed function: mix greedy seed with some randomization for diversity
        def init_fn():
            chrom = {}
            for eid in self.exam_ids:
                # 70% use greedy seed, 30% random for diversity
                if random.random() < 0.7:
                    chrom[eid] = base_seed.get(eid, random.choice(self.slot_ids))
                else:
                    chrom[eid] = random.choice(self.slot_ids)
            return chrom

        def fitness_fn(chrom: Dict[str, str]) -> float:
            return exam_timetable_fitness_indexed(chrom, self._eval_index)

        optimizer = GAOptimizer(
            init_fn=init_fn,
            fitness_fn=fitness_fn,
            crossover_fn=self.crossover,
            mutation_fn=self.mutate,
            config=GAConfig(
                population_size=population_size,
                generations=generations,
                mutation_rate=0.2,
                tournament_size=5,
                elitism_count=5,
                random_seed=random.randint(1, 10000),  # Different seed each run for variety
            ),
        )
        result = optimizer.run()
        # Provide legacy key expected by tests/consumers
        result["chromosome"] = result.get("best_chromosome")
        return result