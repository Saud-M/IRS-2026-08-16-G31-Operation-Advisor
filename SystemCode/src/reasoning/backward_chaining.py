"""Backward Chaining Goal-Driven Diagnostic Engine.

Given a candidate hypothesis as a diagnostic goal, backward-chains through
the dependency tree to identify missing evidentiary facts, unresolved symptoms,
and prioritized physical checks required from the operator.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set
from .knowledge_graph import KnowledgeGraph


class GoalStatus(str, Enum):
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"
    PENDING_EVIDENCE = "PENDING_EVIDENCE"


@dataclass
class DiagnosticCheckPrompt:
    """Prioritized check request to display to the control room operator."""
    check_id: str
    name: str
    target_equipment: str
    instructions: str
    priority: int  # 1 = highest priority
    expected_outcome_for_hypothesis: str


@dataclass
class BackwardChainingResult:
    """Diagnostic assessment of a goal hypothesis."""
    hypothesis_id: str
    hypothesis_name: str
    status: GoalStatus
    verification_score: float # [0.0, 1.0]
    verified_evidence: List[str]
    missing_evidence: List[str]
    refuting_evidence: List[str]
    prioritized_checks: List[DiagnosticCheckPrompt]
    mitigating_actions: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]


class BackwardChainingEngine:
    """Goal-directed reasoning engine verifying or eliminating diagnostic hypotheses."""

    def __init__(self, knowledge_graph: Optional[KnowledgeGraph] = None):
        self.kg = knowledge_graph or KnowledgeGraph()

    def evaluate_hypothesis(
        self,
        hypothesis_id: str,
        active_facts: Dict[str, Any],
        known_symptoms: Optional[Set[str]] = None,
        completed_checks: Optional[Dict[str, Any]] = None,
    ) -> BackwardChainingResult:
        """Goal evaluation: prove, refute, or request missing evidence for hypothesis_id."""
        if not self.kg.graph.has_node(hypothesis_id):
            raise ValueError(f"Unknown hypothesis ID: {hypothesis_id}")

        hypo_data = self.kg.graph.nodes[hypothesis_id]
        h_name = hypo_data.get("name", hypothesis_id)

        known_symptoms = known_symptoms or set()
        completed_checks = completed_checks or {}

        primary_syms = hypo_data.get("primary_symptoms", [])
        secondary_syms = hypo_data.get("secondary_symptoms", [])
        required_checks = hypo_data.get("required_checks", [])

        verified_evidence: List[str] = []
        missing_evidence: List[str] = []
        refuting_evidence: List[str] = []

        # 1. Evaluate Primary Symptoms
        primary_satisfied = 0
        for s_id in primary_syms:
            if s_id in known_symptoms:
                verified_evidence.append(f"Confirmed primary symptom: {s_id}")
                primary_satisfied += 1
            else:
                missing_evidence.append(f"Unobserved primary symptom: {s_id}")

        # 2. Evaluate Secondary Symptoms
        for s_id in secondary_syms:
            if s_id in known_symptoms:
                verified_evidence.append(f"Corroborating secondary symptom: {s_id}")

        # 3. Evaluate Physical Operator Checks
        checks_satisfied = 0
        for chk_id in required_checks:
            if chk_id in completed_checks:
                check_result = completed_checks[chk_id]
                if check_result.get("positive", False):
                    verified_evidence.append(f"Positive field check: {chk_id}")
                    checks_satisfied += 1
                else:
                    refuting_evidence.append(f"Negative field check refuting hypothesis: {chk_id}")
            else:
                missing_evidence.append(f"Pending physical verification: {chk_id}")

        # 4. Formulate Verification Score
        # Primary symptoms provide up to 60%, physical checks provide up to 40%
        w_primary = (primary_satisfied / len(primary_syms)) if primary_syms else 1.0
        w_checks = (checks_satisfied / len(required_checks)) if required_checks else 0.5
        score = 0.60 * w_primary + 0.40 * w_checks

        # 5. Determine Goal Status
        if refuting_evidence:
            status = GoalStatus.REFUTED
            score = 0.05
        elif primary_satisfied == len(primary_syms) and (checks_satisfied > 0 or not required_checks):
            status = GoalStatus.VERIFIED
        else:
            status = GoalStatus.PENDING_EVIDENCE

        # 6. Fetch Prioritized Checks from Knowledge Graph
        raw_checks = self.kg.get_checks_for_hypothesis(hypothesis_id)
        prompts: List[DiagnosticCheckPrompt] = []
        p_rank = 1
        for rc in raw_checks:
            c_id = rc.get("id", "")
            if c_id not in completed_checks:
                prompts.append(
                    DiagnosticCheckPrompt(
                        check_id=c_id,
                        name=rc.get("name", c_id),
                        target_equipment=rc.get("target_equipment", ""),
                        instructions=rc.get("instructions", ""),
                        priority=p_rank,
                        expected_outcome_for_hypothesis=f"Confirms root cause for {h_name}",
                    )
                )
                p_rank += 1

        mitigations = self.kg.get_mitigations_for_hypothesis(hypothesis_id)
        citations = self.kg.get_citations_for_hypothesis(hypothesis_id)

        return BackwardChainingResult(
            hypothesis_id=hypothesis_id,
            hypothesis_name=h_name,
            status=status,
            verification_score=round(score, 3),
            verified_evidence=verified_evidence,
            missing_evidence=missing_evidence,
            refuting_evidence=refuting_evidence,
            prioritized_checks=prompts,
            mitigating_actions=mitigations,
            citations=citations,
        )
