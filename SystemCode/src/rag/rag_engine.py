"""RAG Engine Facade for Industrial Decision Support.

Integrates:
1. Document Indexer (SOPs, HAZOP sheets, technical manuals).
2. Citation Generator (grounded procedural reasoning without hallucination).
3. Shift Handover Generator (OSHA PSM compliant markdown & HTML exports).
"""

from __future__ import annotations
from dataclasses import dataclass
import os
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from src.rag.document_indexer import DocumentIndexer, RetrievalMatch, DocumentPassage
from src.rag.citation_generator import CitationGenerator, GroundedExplanation, GroundedCitation
from src.rag.handover_generator import ShiftHandoverGenerator

if TYPE_CHECKING:
    from src.cognitive.working_memory import WorkingMemory


class RAGEngine:
    """High-level service coordinating document retrieval, grounded citations, and shift handover generation."""

    def __init__(self, documents_dir: Optional[str] = None):
        self.indexer = DocumentIndexer(documents_dir=documents_dir)
        self.citation_gen = CitationGenerator(indexer=self.indexer)
        self.handover_gen = ShiftHandoverGenerator(citation_gen=self.citation_gen)

    def query_procedures(
        self,
        query: str,
        asset_filter: Optional[str] = None,
        top_k: int = 3,
    ) -> List[RetrievalMatch]:
        """Search plant technical corpus for relevant procedural and HAZOP passages."""
        return self.indexer.search(query=query, asset_filter=asset_filter, top_k=top_k)

    def explain_hypothesis(
        self,
        hypothesis_id: str,
        hypothesis_desc: str,
        confidence_pct: Optional[float] = None,
        observed_symptoms: Optional[List[str]] = None,
    ) -> GroundedExplanation:
        """Generate a procedural explanation with strict document citations."""
        return self.citation_gen.explain_hypothesis(
            hypothesis_id=hypothesis_id,
            hypothesis_desc=hypothesis_desc,
            confidence_pct=confidence_pct,
            observed_symptoms=observed_symptoms,
        )

    def explain_action(
        self,
        action_id: str,
        action_name: str,
        target_equipment: str,
    ) -> GroundedExplanation:
        """Generate a grounded rationale for a recommended action."""
        return self.citation_gen.explain_action(
            action_id=action_id,
            action_name=action_name,
            target_equipment=target_equipment,
        )

    def generate_shift_handover(
        self,
        wm: WorkingMemory,
        output_dir: Optional[str] = None,
        outgoing_operator: str = "Lead Console Operator",
        incoming_operator: str = "Incoming Shift Lead",
    ) -> Dict[str, Any]:
        """Generate and save Markdown, HTML, and PDF Shift Handover reports."""
        md = self.handover_gen.generate_markdown(wm, outgoing_operator, incoming_operator)
        html = self.handover_gen.generate_html(wm, outgoing_operator, incoming_operator)
        pdf_bytes = self.handover_gen.generate_pdf(wm, outgoing_operator, incoming_operator)
        paths = self.handover_gen.export_report(wm, output_dir=output_dir)

        return {
            "markdown": md,
            "html": html,
            "pdf_bytes": pdf_bytes,
            "markdown_path": paths["markdown_path"],
            "html_path": paths["html_path"],
            "pdf_path": paths.get("pdf_path"),
        }

    def verify_citations(self, text: str) -> Tuple[bool, List[str]]:
        """Validate all bracketed citations in text against indexed passages."""
        return self.citation_gen.verify_citations(text)
