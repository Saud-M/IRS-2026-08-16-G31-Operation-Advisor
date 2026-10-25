"""Genetic Algorithm (GA) Operating Setpoint Optimizer.

Optimizes steady-state operating parameters:
1. Separator Pressure Setpoint (PT-101): [27.0, 33.0] barg
2. Compressor Anti-Surge Minimum Margin: [15.0, 35.0] %
3. Hydrocarbon Liquid Level Setpoint (LT-101): [45.0, 55.0] %

Balances gas export throughput, compressor electrical power consumption,
flaring risk penalties, and surge safety margins.
"""

from dataclasses import dataclass, field
import random
from typing import Dict, Any, List, Tuple, Optional


@dataclass
class OperatingSetpoints:
    separator_pressure_barg: float
    anti_surge_margin_pct: float
    liquid_level_pct: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "separator_pressure_barg": round(self.separator_pressure_barg, 2),
            "anti_surge_margin_pct": round(self.anti_surge_margin_pct, 2),
            "liquid_level_pct": round(self.liquid_level_pct, 2),
        }


@dataclass
class OptimizationResult:
    best_setpoints: OperatingSetpoints
    best_fitness: float
    baseline_fitness: float
    improvement_pct: float
    fitness_history: List[float]
    metrics: Dict[str, float]


class GeneticAlgorithmOptimizer:
    """Evolutionary algorithm optimizing continuous operating setpoints."""

    def __init__(
        self,
        population_size: int = 40,
        generations: int = 35,
        mutation_rate: float = 0.20,
        crossover_rate: float = 0.85,
        random_seed: int = 42,
    ):
        self.pop_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        random.seed(random_seed)

        # Optimization Parameter Bounds: (min, max)
        self.bounds = {
            "pressure": (27.5, 33.0),
            "surge_margin": (16.0, 35.0),
            "liquid_level": (45.0, 55.0),
        }

    def evaluate_fitness(self, ind: OperatingSetpoints) -> Tuple[float, Dict[str, float]]:
        """Evaluate multi-objective fitness function under process physics constraints."""
        p = ind.separator_pressure_barg
        sm = ind.anti_surge_margin_pct
        ll = ind.liquid_level_pct

        # 1. Gas throughput increases with higher separator pressure (less pressure drop across export valve)
        # Baseline 90,000 Sm3/h at 30.0 barg
        throughput_sm3h = 90000.0 * (1.0 + 0.015 * (p - 30.0))

        # 2. Compressor power consumption (kW)
        # Power increases if suction pressure drops, or if recycle margin is excessive (unnecessary gas recycle)
        recycle_penalty_kw = max(0.0, (sm - 20.0) * 45.0)  # Excess recycle wastes power
        base_power_kw = 3250.0 * (30.0 / p) ** 0.35
        total_power_kw = base_power_kw + recycle_penalty_kw

        # 3. Flaring Penalty (Severe if pressure approaches safety relief 34.0 barg)
        flaring_penalty = 0.0
        if p > 32.5:
            flaring_penalty = 350.0 * ((p - 32.5) ** 2)

        # 4. Surge Risk Penalty (Severe if margin drops near minimum surge boundary 15%)
        surge_penalty = 0.0
        if sm < 18.0:
            surge_penalty = 500.0 * ((18.0 - sm) ** 2)

        # 5. Liquid Carryover Penalty (If liquid level is too high, vapor space shrinks)
        level_penalty = 0.0
        if ll > 52.0:
            level_penalty = 80.0 * (ll - 52.0)

        # Objective Function: Maximize Throughput Revenue - Power Costs - Operational Penalties
        # Normalized to a dimensionless operational index
        fitness = (
            (throughput_sm3h / 1000.0) * 1.5
            - (total_power_kw / 100.0) * 0.8
            - flaring_penalty
            - surge_penalty
            - level_penalty
        )

        metrics = {
            "throughput_sm3h": round(throughput_sm3h, 1),
            "compressor_power_kw": round(total_power_kw, 1),
            "flaring_penalty": round(flaring_penalty, 2),
            "surge_penalty": round(surge_penalty, 2),
        }

        return fitness, metrics

    def optimize(self) -> OptimizationResult:
        """Execute Genetic Algorithm evolution cycle."""
        # Initialize population randomly within bounds
        population: List[OperatingSetpoints] = [
            OperatingSetpoints(
                separator_pressure_barg=random.uniform(*self.bounds["pressure"]),
                anti_surge_margin_pct=random.uniform(*self.bounds["surge_margin"]),
                liquid_level_pct=random.uniform(*self.bounds["liquid_level"]),
            )
            for _ in range(self.pop_size)
        ]

        # Evaluate default baseline (30.0 barg, 25.0% margin, 50.0% level)
        baseline = OperatingSetpoints(30.0, 25.0, 50.0)
        baseline_fitness, _ = self.evaluate_fitness(baseline)

        history: List[float] = []
        best_overall = population[0]
        best_fitness_overall = float("-inf")
        best_metrics_overall: Dict[str, float] = {}

        for gen in range(self.generations):
            scores_and_metrics = [self.evaluate_fitness(ind) for ind in population]
            fitness_scores = [item[0] for item in scores_and_metrics]

            # Elitism: find best in generation
            gen_best_idx = int(max(range(len(fitness_scores)), key=lambda i: fitness_scores[i]))
            if fitness_scores[gen_best_idx] > best_fitness_overall:
                best_fitness_overall = fitness_scores[gen_best_idx]
                best_overall = population[gen_best_idx]
                best_metrics_overall = scores_and_metrics[gen_best_idx][1]

            history.append(round(best_fitness_overall, 3))

            # Tournament Selection (size k=3)
            def tournament() -> OperatingSetpoints:
                candidates = random.sample(range(self.pop_size), 3)
                winner_idx = max(candidates, key=lambda i: fitness_scores[i])
                return population[winner_idx]

            # Breed next generation
            next_pop: List[OperatingSetpoints] = [best_overall]  # Elitism keeps #1

            while len(next_pop) < self.pop_size:
                p1 = tournament()
                p2 = tournament()

                # Blend Crossover (BLX-alpha with alpha=0.3)
                if random.random() < self.crossover_rate:
                    alpha = 0.3
                    gamma_p = random.uniform(-alpha, 1.0 + alpha)
                    gamma_sm = random.uniform(-alpha, 1.0 + alpha)
                    gamma_ll = random.uniform(-alpha, 1.0 + alpha)

                    child_p = p1.separator_pressure_barg + gamma_p * (p2.separator_pressure_barg - p1.separator_pressure_barg)
                    child_sm = p1.anti_surge_margin_pct + gamma_sm * (p2.anti_surge_margin_pct - p1.anti_surge_margin_pct)
                    child_ll = p1.liquid_level_pct + gamma_ll * (p2.liquid_level_pct - p1.liquid_level_pct)
                else:
                    child_p, child_sm, child_ll = p1.separator_pressure_barg, p1.anti_surge_margin_pct, p1.liquid_level_pct

                # Mutation (Gaussian perturbation)
                if random.random() < self.mutation_rate:
                    child_p += random.gauss(0.0, 0.35)
                if random.random() < self.mutation_rate:
                    child_sm += random.gauss(0.0, 0.8)
                if random.random() < self.mutation_rate:
                    child_ll += random.gauss(0.0, 0.4)

                # Boundary clipping
                child_p = max(self.bounds["pressure"][0], min(self.bounds["pressure"][1], child_p))
                child_sm = max(self.bounds["surge_margin"][0], min(self.bounds["surge_margin"][1], child_sm))
                child_ll = max(self.bounds["liquid_level"][0], min(self.bounds["liquid_level"][1], child_ll))

                next_pop.append(OperatingSetpoints(child_p, child_sm, child_ll))

            population = next_pop

        improvement = ((best_fitness_overall - baseline_fitness) / abs(baseline_fitness)) * 100.0

        return OptimizationResult(
            best_setpoints=best_overall,
            best_fitness=round(best_fitness_overall, 3),
            baseline_fitness=round(baseline_fitness, 3),
            improvement_pct=round(improvement, 2),
            fitness_history=history,
            metrics=best_metrics_overall,
        )
