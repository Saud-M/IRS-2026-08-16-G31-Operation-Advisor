"""Multimodal Dialogue Manager & Incident Context Orchestrator.

Coordinates operator inputs across natural language text, voice reports, and gauge images.
Maintains short-term Working Memory, manages clarification dialogues for missing
or conflicting telemetry, and invokes downstream machine reasoning and planning engines.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from .nlu_parser import NLUParser, TaskIntent, ExtractedSlots, ClarificationPrompt
from .working_memory import WorkingMemory
from .speech_asr import SpeechRecognizer, TranscriptionResult
from .display_ocr import DisplayOCRReader, OCRReadingResult
from src.reasoning.forward_chaining import ForwardChainingEngine
from src.learning.bayesian_network import ProcessBayesianNetwork
from src.reasoning.backward_chaining import BackwardChainingEngine
from src.planning.astar_planner import AStarPlanner, PlantPlanState
from src.recommender.action_recommender import ContentGraphRecommender
from src.rag.rag_engine import RAGEngine
from .ollama_client import LocalLLMClient, LLMResponse
from dataclasses import field


@dataclass
class AdvisorResponse:
    reply_text: str
    intent_detected: TaskIntent
    clarification_needed: bool
    clarification_prompt: Optional[ClarificationPrompt]
    top_hypothesis: Optional[str]
    confidence_pct: float
    recommended_checks: List[Dict[str, Any]]
    recommended_actions: List[Dict[str, Any]]
    active_plan: List[Dict[str, Any]]
    incident_id: str
    citations: List[str] = field(default_factory=list)
    handover_report: Optional[str] = None
    llm_source: str = "offline_rag_fallback"
    model_used: str = "deterministic-rag-synthesizer"


class DialogueManager:
    """Central cognitive orchestrator connecting multimodal inputs to reasoning and planning."""

    def __init__(self, working_memory: Optional[WorkingMemory] = None):
        self.wm = working_memory or WorkingMemory()
        self.nlu = NLUParser()
        self.asr = SpeechRecognizer()
        self.ocr = DisplayOCRReader()

        # Core Engines
        self.fwd_engine = ForwardChainingEngine()
        self.bayes_net = ProcessBayesianNetwork()
        self.bwd_engine = BackwardChainingEngine()
        self.planner = AStarPlanner()
        self.recommender = ContentGraphRecommender()
        self.rag = RAGEngine()
        self.llm_client = LocalLLMClient()

    def process_text_input(self, text: str) -> AdvisorResponse:
        """Process typed natural language inquiry or operator field notes."""
        self.wm.add_message(role="operator", content=text)

        slots, clarification = self.nlu.parse(text)

        if clarification:
            reply = f"{clarification.question} (Options: {', '.join(clarification.suggested_options)})"
            self.wm.add_message(role="advisor", content=reply)
            return AdvisorResponse(
                reply_text=reply,
                intent_detected=slots.task_intent,
                clarification_needed=True,
                clarification_prompt=clarification,
                top_hypothesis=self.wm.state.top_hypothesis,
                confidence_pct=0.0,
                recommended_checks=[],
                recommended_actions=[],
                active_plan=[],
                incident_id=self.wm.state.incident_id,
            )

        # Update Working Memory with extracted observation
        if slots.symptoms:
            self.wm.add_symptoms(slots.symptoms)
        elif slots.symptom:
            self.wm.add_symptoms([slots.symptom])

        if slots.observed_value is not None and slots.asset_tag:
            # Map observed value to tag
            tag_map = {"V-101": "PT-101", "K-101": "ST-101", "V-102": "DP-101"}
            sensor_tag = tag_map.get(slots.asset_tag, "PT-101")
            self.wm.update_telemetry({sensor_tag: slots.observed_value})

        # Run multi-engine reasoning cycle
        return self._execute_reasoning_cycle(slots)

    def process_voice_input(self, audio_source: Any, hint_context: str = "") -> AdvisorResponse:
        """Process spoken operator report through ASR then dispatch to dialogue manager."""
        transcription_res = self.asr.transcribe(audio_source, hint_context=hint_context)
        # Log spoken text as operator message
        self.wm.add_message(
            role="operator",
            content=f"[Voice Transcript] {transcription_res.transcript}",
            metadata={"confidence": transcription_res.confidence, "duration_sec": transcription_res.duration_sec},
        )
        return self.process_text_input(transcription_res.transcript)

    def process_gauge_image(self, image_input: Any) -> AdvisorResponse:
        """Process dial gauge or transmitter display image through OCR."""
        ocr_res = self.ocr.process_image(image_input)
        if not ocr_res:
            reply = "Unable to detect valid instrument tag or numeric measurement from image."
            self.wm.add_message(role="advisor", content=reply)
            return AdvisorResponse(
                reply_text=reply,
                intent_detected=TaskIntent.STATUS_QUERY,
                clarification_needed=True,
                clarification_prompt=ClarificationPrompt(
                    missing_slot="image_clarity",
                    question="Please provide a clearer photo of the instrument display or type the reading.",
                    suggested_options=["Type reading manually", "Upload new image"],
                ),
                top_hypothesis=self.wm.state.top_hypothesis,
                confidence_pct=0.0,
                recommended_checks=[],
                recommended_actions=[],
                active_plan=[],
                incident_id=self.wm.state.incident_id,
            )

        # Update Working Memory with extracted measurement
        self.wm.update_telemetry({ocr_res.detected_tag: ocr_res.numeric_value})
        msg = f"[Gauge OCR] Detected {ocr_res.detected_tag} reading: {ocr_res.numeric_value} {ocr_res.unit} (Alarm: {ocr_res.alarm_triggered or 'NORMAL'})"
        self.wm.add_message(role="operator", content=msg)

        # Query diagnosis for the detected instrument
        return self.process_text_input(f"Diagnose abnormal reading on {ocr_res.detected_tag}")

    def _execute_reasoning_cycle(self, slots: ExtractedSlots, generate_narrative: bool = True) -> AdvisorResponse:
        """Run synchronized inference across Forward Chaining, Bayesian Net, Backward Chaining, and A*."""
        telemetry = dict(self.wm.state.telemetry)

        # 1. Forward Chaining (Condition and Symptom Detection)
        fwd_res = self.fwd_engine.infer(telemetry)
        all_symptoms = list(set(fwd_res.active_symptoms) | self.wm.state.confirmed_symptoms)
        self.wm.add_symptoms(all_symptoms)

        for trace in fwd_res.rule_traces:
            self.wm.log_audit("RULE_TRIGGERED", {"rule_id": trace.rule_id, "consequent": trace.consequent})

        # 2. Bayesian Belief Network (Hypothesis Posterior Ranking)
        bayes_evidence = {sym: 1 for sym in all_symptoms}
        bayes_res = self.bayes_net.infer(bayes_evidence)

        # Store rankings in working memory
        ranking_dicts = [
            {
                "hypothesis_id": h.hypothesis_id,
                "description": h.description,
                "posterior_prob": h.posterior_prob,
                "likelihood_ratio": h.likelihood_ratio,
            }
            for h in bayes_res.ranked_hypotheses
        ]
        self.wm.update_hypotheses(ranking_dicts)

        top_hypo = ranking_dicts[0] if ranking_dicts else {"hypothesis_id": "H07", "description": "Nominal", "posterior_prob": 1.0}

        # 3. Backward Chaining (Missing Evidence Gathering)
        bwd_res = self.bwd_engine.evaluate_hypothesis(
            hypothesis_id=top_hypo["hypothesis_id"],
            active_facts=telemetry,
            known_symptoms=set(all_symptoms),
            completed_checks=self.wm.state.completed_checks,
        )

        checks_dicts = [
            {
                "check_id": p.check_id,
                "name": p.name,
                "target_equipment": p.target_equipment,
                "instructions": p.instructions,
                "priority": p.priority,
            }
            for p in bwd_res.prioritized_checks
        ]
        self.wm.register_pending_checks(checks_dicts)

        # 4. Action Recommendations
        beliefs_map = {r["hypothesis_id"]: r["posterior_prob"] for r in ranking_dicts}
        action_recs = self.recommender.recommend_actions(beliefs_map, plant_state=telemetry, top_k=3)
        actions_dicts = [
            {
                "action_id": a.action_id,
                "name": a.name,
                "target_equipment": a.target_equipment,
                "score": a.score,
                "risk_level": a.risk_level.value,
                "eligible": a.eligible,
                "blocking_reasons": a.blocking_reasons,
                "rationale": a.rationale,
            }
            for a in action_recs
        ]

        # 5. A* Response Planning (if fault is active)
        plan_steps_dicts: List[Dict[str, Any]] = []
        if top_hypo["hypothesis_id"] != "H07":
            # Map current working state to PlantPlanState
            p_status = "NORMAL"
            c_status = "RUNNING"
            l_status = "NORMAL"
            pcv_stat = "AUTO"

            if top_hypo["hypothesis_id"] == "H01":
                p_status = "CRITICAL" if telemetry.get("PT-101", 30.0) >= 36.5 else "HIGH"
                pcv_stat = "CLOSED_STUCK"
            elif top_hypo["hypothesis_id"] == "H04":
                c_status = "SURGING"
            elif top_hypo["hypothesis_id"] == "H03":
                l_status = "HIGH"
            elif top_hypo["hypothesis_id"] == "H05":
                l_status = "EMULSION"
            elif top_hypo["hypothesis_id"] == "H06":
                p_status = "HIGH"
                l_status = "HIGH"
            else:
                if telemetry.get("PT-101", 30.0) >= 34.0:
                    p_status = "HIGH"
                if "SYM_HIGH_VIBRATION" in all_symptoms:
                    c_status = "SURGING"
                if "SYM_HIGH_DEMISTER_DP" in all_symptoms or "SYM_HIGH_LEVEL" in all_symptoms:
                    l_status = "HIGH"

            curr_plan_state = PlantPlanState(
                pressure_status=p_status,
                liquid_status=l_status,
                compressor_status=c_status,
                pcv_status=pcv_stat,
                antifoam_active=False,
                permit_granted=telemetry.get("permit_to_work", True),
            )
            plan_res = self.planner.plan(curr_plan_state)
            if plan_res.is_feasible:
                plan_steps_dicts = [
                    {
                        "action_id": s.action_id,
                        "name": s.name,
                        "target_equipment": s.target_equipment,
                        "duration_min": s.estimated_time_min,
                        "cost": s.cost,
                    }
                    for s in plan_res.steps
                ]
                self.wm.set_plan(plan_steps_dicts)

        # 6. RAG Grounding, Local LLM & Procedural Citations
        grounded_info = self.rag.explain_hypothesis(top_hypo["hypothesis_id"], top_hypo["description"])
        active_citations = [c.citation_tag for c in grounded_info.citations]
        handover_report_text: Optional[str] = None
        source_used = "offline_rag_fallback"
        model_name = "deterministic-rag-synthesizer"

        if slots.task_intent == TaskIntent.HANDOVER:
            handover_data = self.rag.generate_shift_handover(self.wm)
            handover_report_text = handover_data["markdown"]
            reply = f"Generated Shift Handover Report for Incident `{self.wm.state.incident_id}` under OSHA PSM / API RP 75 guidelines."
        elif slots.task_intent == TaskIntent.EXPLAIN:
            reply = grounded_info.explanation_text
        elif not generate_narrative:
            # Telemetry status polling cycle - skip heavy LLM generation and WM message history append
            reply = f"Top hypothesis: {top_hypo['description']} ({top_hypo['hypothesis_id']}) with {top_hypo['posterior_prob']*100:.1f}% confidence."
            source_used = "offline_rag_fallback"
            model_name = "deterministic-rag-synthesizer"
        else:
            # Query procedural corpus for query-relevant passages
            search_query = slots.raw_text if slots.raw_text else top_hypo["description"]
            retrieved_matches = self.rag.query_procedures(search_query, top_k=3)
            passages_dict_list = [
                {
                    "citation_tag": m.citation_tag,
                    "doc_id": m.passage.document_id,
                    "section": m.passage.section,
                    "title": m.passage.title,
                    "content": m.passage.content,
                }
                for m in retrieved_matches
            ]

            # Ensure hypothesis citations are present in context
            for c in grounded_info.citations:
                if not any(p["citation_tag"] == c.citation_tag for p in passages_dict_list):
                    passages_dict_list.append({
                        "citation_tag": c.citation_tag,
                        "doc_id": c.passage_id.split("-")[0] if "-" in c.passage_id else "SOP",
                        "section": "1",
                        "title": c.title,
                        "content": c.excerpt,
                    })

            # Generate strictly grounded answer via local Ollama LLM or offline RAG synthesizer
            llm_res = self.llm_client.generate(
                query=slots.raw_text or f"What is the status of {top_hypo['description']}?",
                passages=passages_dict_list,
                telemetry=telemetry,
                hypothesis_info=top_hypo,
                plan_steps=plan_steps_dicts,
                is_query_matched=bool(retrieved_matches),
            )
            reply = llm_res.text
            source_used = llm_res.llm_source
            model_name = llm_res.model_used
            active_citations = list(dict.fromkeys(active_citations + llm_res.citations))

        if generate_narrative:
            self.wm.add_message(role="advisor", content=reply)

        return AdvisorResponse(
            reply_text=reply,
            intent_detected=slots.task_intent,
            clarification_needed=False,
            clarification_prompt=None,
            top_hypothesis=top_hypo["hypothesis_id"],
            confidence_pct=round(top_hypo["posterior_prob"] * 100.0, 1),
            recommended_checks=checks_dicts,
            recommended_actions=actions_dicts,
            active_plan=plan_steps_dicts,
            incident_id=self.wm.state.incident_id,
            citations=active_citations,
            handover_report=handover_report_text,
            llm_source=source_used,
            model_used=model_name,
        )
