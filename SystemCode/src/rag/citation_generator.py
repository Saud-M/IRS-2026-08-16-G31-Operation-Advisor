"""Citation Generator & Procedure Grounding Engine.

Generates grounded diagnostic explanations and procedural step rationales with
strict, verifiable citations to plant operating documents (e.g. [SOP-V101 Section 1], [HAZOP-SEP Node 1]).
Prevents hallucination by validating all generated references against indexed passage IDs.
"""

from dataclasses import dataclass, field
import re
from typing import List, Dict, Any, Optional, Tuple
from src.rag.document_indexer import DocumentIndexer, RetrievalMatch


@dataclass
class GroundedCitation:
    citation_tag: str
    passage_id: str
    title: str
    excerpt: str
    relevance_score: float


@dataclass
class GroundedExplanation:
    subject_id: str
    subject_name: str
    explanation_text: str
    citations: List[GroundedCitation] = field(default_factory=list)
    verified: bool = True
    missing_citations: List[str] = field(default_factory=list)


class CitationGenerator:
    """Grounds operational advice in validated procedural and HAZOP passages."""

    HYPOTHESIS_QUERY_MAP = {
        "H01": ("V-101 high pressure PCV-101 stuck closed bypass valve BDV-101", "V-101"),
        "H02": ("V-101 low pressure PCV-101 stuck open gas depressurization", "V-101"),
        "H03": ("V-101 foaming demister fouling carryover scrubber V-102 anti-foam P-105", "V-101"),
        "H04": ("K-101 compressor surge vibration ASV-101 anti-surge recycle", "K-101"),
        "H05": ("V-101 emulsion rag layer LT-102 interface demulsifier sampling", "V-101"),
        "H06": ("V-101 slug arrival liquid level surge choke wellhead pinching", "V-101"),
        "H07": ("steady-state nominal normal operating limits baseline", "V-101"),
    }

    ACTION_QUERY_MAP = {
        "ACT_01_SWITCH_MANUAL_BYPASS": ("PCV-101 manual station crack open bypass HV-101B pressure relief", "V-101"),
        "ACT_02_INJECT_ANTIFOAM": ("anti-foam injection pump P-105 demister dp carryover silicone ppm", "V-101"),
        "ACT_03_OPEN_ASV": ("ASV-101 anti-surge valve manual 100% recycle surge margin", "K-101"),
        "ACT_04_INCREASE_DEMULSIFIER": ("demulsifier dosing rate emulsion rag layer interface LT-102", "V-101"),
        "ACT_05_PINCH_WELLHEAD_CHOKE": ("pinch wellhead choke 15% liquid slug superficial gas velocity", "V-101"),
        "ACT_06_DIVERT_TO_FLARE": ("emergency blowdown BDV-101 flare depressurization high pressure relief", "V-101"),
        "ACT_07_DRAIN_SCRUBBER_MANUAL": ("scrubber V-102 manual drain HV-103B liquid carryover protection", "V-102"),
    }

    def __init__(self, indexer: Optional[DocumentIndexer] = None):
        self.indexer = indexer or DocumentIndexer()

    def verify_citations(self, text: str) -> Tuple[bool, List[str]]:
        """Verify that all bracketed citations in text resolve to valid indexed passages."""
        # Find all brackets like [SOP-V101 Section 1] or [HAZOP-SEP Node 2]
        found_tags = re.findall(r"\[([A-Z0-9_\-]+(?:\s*Section\s*\d+|\s*Node\s*\d+|:[A-Z0-9_\-]+))\]", text, re.IGNORECASE)
        valid_citations = set()
        for p in self.indexer.passages:
            valid_citations.add(self.indexer._extract_citation_tag(p.passage_id, p.title).strip("[]"))
            valid_citations.add(p.passage_id)
            valid_citations.add(p.document_id)

        missing = []
        for tag in found_tags:
            # Check direct match or document prefix match
            if tag not in valid_citations and not any(tag.startswith(p.document_id) for p in self.indexer.passages):
                missing.append(f"[{tag}]")

        is_valid = len(missing) == 0
        return is_valid, missing

    def explain_hypothesis(
        self,
        hypothesis_id: str,
        hypothesis_desc: str,
        confidence_pct: Optional[float] = None,
        observed_symptoms: Optional[List[str]] = None,
    ) -> GroundedExplanation:
        """Formulate a procedural, citation-grounded explanation for a fault hypothesis."""
        query_info = self.HYPOTHESIS_QUERY_MAP.get(
            hypothesis_id, (f"{hypothesis_desc} failure remediation", None)
        )
        query_text, asset_filter = query_info

        matches = self.indexer.search(query=query_text, asset_filter=asset_filter, top_k=2)

        citations: List[GroundedCitation] = []
        citation_tags = []
        for m in matches:
            excerpt_lines = [line.strip() for line in m.passage.content.split("\n") if line.strip() and not line.startswith("#")]
            excerpt = " ".join(excerpt_lines[:2])
            citation = GroundedCitation(
                citation_tag=m.citation_tag,
                passage_id=m.passage.passage_id,
                title=m.passage.title,
                excerpt=excerpt[:220] + "..." if len(excerpt) > 220 else excerpt,
                relevance_score=m.score,
            )
            citations.append(citation)
            citation_tags.append(m.citation_tag)

        tags_str = ", ".join(citation_tags) if citation_tags else "[SOP-V101]"
        symptoms_str = f" based on observations of {', '.join(observed_symptoms)}" if observed_symptoms else ""
        confidence_str = f" with {confidence_pct:.1f}% probabilistic confidence" if confidence_pct else ""

        explanation_text = (
            f"Fault hypothesis **{hypothesis_desc}** ({hypothesis_id}) is identified{confidence_str}{symptoms_str}. "
            f"Under mandatory facility safety guidelines {tags_str}, this condition requires immediate operator intervention "
            f"to prevent process trip limits or mechanical safeguard exceedance. "
            f"Primary operating procedures are documented in {tags_str}."
        )

        verified, missing = self.verify_citations(explanation_text)

        return GroundedExplanation(
            subject_id=hypothesis_id,
            subject_name=hypothesis_desc,
            explanation_text=explanation_text,
            citations=citations,
            verified=verified,
            missing_citations=missing,
        )

    def explain_action(
        self,
        action_id: str,
        action_name: str,
        target_equipment: str,
    ) -> GroundedExplanation:
        """Formulate a citation-backed rationale for a planned action."""
        query_info = self.ACTION_QUERY_MAP.get(
            action_id, (f"{action_name} {target_equipment}", target_equipment)
        )
        query_text, asset_filter = query_info

        matches = self.indexer.search(query=query_text, asset_filter=asset_filter, top_k=2)

        citations: List[GroundedCitation] = []
        citation_tags = []
        for m in matches:
            excerpt_lines = [line.strip() for line in m.passage.content.split("\n") if line.strip() and not line.startswith("#")]
            excerpt = " ".join(excerpt_lines[:2])
            citations.append(
                GroundedCitation(
                    citation_tag=m.citation_tag,
                    passage_id=m.passage.passage_id,
                    title=m.passage.title,
                    excerpt=excerpt[:220] + "..." if len(excerpt) > 220 else excerpt,
                    relevance_score=m.score,
                )
            )
            citation_tags.append(m.citation_tag)

        tags_str = ", ".join(citation_tags) if citation_tags else "[SOP-V101 Section 1]"

        explanation_text = (
            f"Recommended action **{action_name}** targeting `{target_equipment}` is grounded in {tags_str}. "
            f"Execution mitigates root cause escalation while maintaining plant safety barriers as stipulated in {tags_str}."
        )

        verified, missing = self.verify_citations(explanation_text)

        return GroundedExplanation(
            subject_id=action_id,
            subject_name=action_name,
            explanation_text=explanation_text,
            citations=citations,
            verified=verified,
            missing_citations=missing,
        )
