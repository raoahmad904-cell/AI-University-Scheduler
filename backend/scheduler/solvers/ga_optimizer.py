from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Tuple
import random


Chromosome = Dict[str, Any]
FitnessFn = Callable[[Chromosome], float]
InitFn = Callable[[], Chromosome]
CrossoverFn = Callable[[Chromosome, Chromosome], Chromosome]
MutationFn = Callable[[Chromosome], Chromosome]


@dataclass
class GAConfig:
    population_size: int = 100
    generations: int = 200
    mutation_rate: float = 0.15
    tournament_size: int = 5
    elitism_count: int = 5
    random_seed: int = 42


class GAOptimizer:
    def __init__(
        self,
        init_fn: InitFn,
        fitness_fn: FitnessFn,
        crossover_fn: CrossoverFn,
        mutation_fn: MutationFn,
        config: GAConfig | None = None,
    ) -> None:
        self.init_fn = init_fn
        self.fitness_fn = fitness_fn
        self.crossover_fn = crossover_fn
        self.mutation_fn = mutation_fn
        self.config = config or GAConfig()
        random.seed(self.config.random_seed)

    def _evaluate_population(
        self, population: List[Chromosome]
    ) -> List[Tuple[float, Chromosome]]:
        return [(self.fitness_fn(c), c) for c in population]

    def _tournament_select(
        self, scored: List[Tuple[float, Chromosome]]
    ) -> Chromosome:
        k = min(self.config.tournament_size, len(scored))
        contenders = random.sample(scored, k=k)
        return max(contenders, key=lambda x: x[0])[1]

    def run(self) -> Dict[str, Any]:
        population = [self.init_fn() for _ in range(self.config.population_size)]
        scored = self._evaluate_population(population)
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0]

        history: List[float] = [best[0]]

        for _ in range(self.config.generations):
            elite = [chrom for _, chrom in scored[:self.config.elitism_count]]
            new_pop: List[Chromosome] = list(elite)

            while len(new_pop) < self.config.population_size:
                parent1 = self._tournament_select(scored)
                parent2 = self._tournament_select(scored)
                child = self.crossover_fn(parent1, parent2)

                if random.random() < self.config.mutation_rate:
                    child = self.mutation_fn(child)

                new_pop.append(child)

            scored = self._evaluate_population(new_pop)
            scored.sort(key=lambda x: x[0], reverse=True)

            if scored[0][0] > best[0]:
                best = scored[0]

            history.append(best[0])

        return {
            "best_fitness": best[0],
            "best_chromosome": best[1],
            "fitness_history": history,
        }
