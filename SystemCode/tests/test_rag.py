"""Unit and Integration Tests for RAG Engine & Shift Handover Generation (Sprint 6).

Verifies:
1. Document chunking, passage tagging, and metadata extraction.
2. Semantic passage retrieval across SOPs and HAZOP sheets.
3. Citation grounding and anti-hallucination verification.
4. Procedural hypothesis explanations and action rationales.
5. OSHA PSM / API RP 75 compliant Shift Handover Report generation (Markdown & HTML).
6. DialogueManager integration with handover and explanation intents.
"""

import os
import pytest
from src.rag.document_indexer import DocumentIndexer
from src.rag.citation_generator import CitationGenerator
from src.rag.handover_generator import ShiftHandoverGenerator
from src.rag.rag_engine import RAGEngine
from src.cognitive.working_memory import WorkingMemory
from src.cognitive.dialogue_manager import DialogueManager


@pytest.fixture
def rag_engine():
    return RAGEngine()


@pytest.fixture
def sample_wm():
    wm = WorkingMemory(incident_title="Unit Test Overpressure Incident")
    wm.update_telemetry({
        "PT-101": 35.8,
        "LT-101": 52.0,
        "LT-102": 49.5,
        "DPIT-101": 0.025,
        "VT-101": 1.4,
    })
    wm.add_symptoms(["SYM_HIGH_PRESSURE"])
    wm.update_hypotheses([
        {
            "hypothesis_id": "H01",
            "description": "PCV-101 Stuck Closed / Air Failure",
            "posterior_prob": 0.633,
            "likelihood_ratio": 4.22,
        },
        {
            "hypothesis_id": "H06",
            "description": "Wellhead Transient Slug Influx",
            "posterior_prob": 0.180,
            "likelihood_ratio": 1.20,
        },
    ])
    wm.add_check(
        check_id="CHK_01_LOCAL_PCV_STEM",
        name="Inspect Local PCV-101 Valve Stem & Actuator Position",
        target_equipment="PCV-101",
        instructions="Verify physical stem travel indicator against control room command.",
        priority=1,
    )
    wm.add_action({
        "action_id": "ACT_01_SWITCH_MANUAL_BYPASS",
        "name": "Switch PCV-101 to Manual Bypass Valve",
        "target_equipment": "PCV-101",
    })
    return wm


def test_document_chunking_and_metadata(rag_engine):
    """Verify document parser extracts passages with unique IDs and equipment metadata."""
    passages = rag_engine.indexer.passages
    assert len(passages) >= 8

    passage_ids = [p.passage_id for p in passages]
    assert "SOP-V101:SEC-01" in passage_ids
    assert "SOP-K101:SEC-01" in passage_ids
    assert "HAZOP-SEP:NODE-01" in passage_ids

    # Verify equipment metadata extraction
    sop_v101_sec1 = rag_engine.indexer.get_passage_by_id("SOP-V101:SEC-01")
    assert sop_v101_sec1 is not None
    assert "V-101" in sop_v101_sec1.asset_tags
    assert "PCV-101" in sop_v101_sec1.asset_tags


def test_semantic_retrieval_overpressure(rag_engine):
    """Verify retrieval of high pressure procedures and HAZOP nodes."""
    results = rag_engine.query_procedures("high pressure PCV-101 bypass valve", asset_filter="V-101", top_k=3)
    assert len(results) > 0

    top_citation = results[0].citation_tag
    assert top_citation in ("[SOP-V101 Section 1]", "[HAZOP-SEP Node 1]")
    assert results[0].score > 0.20


def test_semantic_retrieval_compressor_surge(rag_engine):
    """Verify retrieval of compressor anti-surge valve procedures."""
    results = rag_engine.query_procedures("compressor aerodynamic surge ASV-101 recycle", asset_filter="K-101", top_k=2)
    assert len(results) > 0

    citations = [r.citation_tag for r in results]
    assert "[SOP-K101 Section 1]" in citations or "[HAZOP-SEP Node 3]" in citations


def test_citation_verification_valid_and_invalid(rag_engine):
    """Verify anti-hallucination citation validator."""
    valid_text = "According to [SOP-V101 Section 1] and [HAZOP-SEP Node 1], PCV-101 must be switched to manual bypass."
    is_valid, missing = rag_engine.verify_citations(valid_text)
    assert is_valid is True
    assert len(missing) == 0

    hallucinated_text = "Refer to fictitious document [SOP-NONEXISTENT Section 99] for details."
    is_valid_fake, missing_fake = rag_engine.verify_citations(hallucinated_text)
    assert is_valid_fake is False
    assert "[SOP-NONEXISTENT Section 99]" in missing_fake


def test_grounded_hypothesis_explanation(rag_engine):
    """Verify RAG explanation connects hypothesis to SOP passages with citations."""
    explanation = rag_engine.explain_hypothesis(
        hypothesis_id="H01",
        hypothesis_desc="PCV-101 Stuck Closed / Air Failure",
        confidence_pct=63.3,
        observed_symptoms=["SYM_HIGH_PRESSURE", "SYM_LOW_GAS_FLOW"],
    )

    assert explanation.verified is True
    assert len(explanation.citations) > 0
    assert "H01" in explanation.subject_id
    assert any("[SOP-V101" in cit.citation_tag for cit in explanation.citations)
    assert "PCV-101" in explanation.explanation_text


def test_grounded_action_rationale(rag_engine):
    """Verify RAG action explanation cites procedural safety barrier."""
    explanation = rag_engine.explain_action(
        action_id="ACT_01_SWITCH_MANUAL_BYPASS",
        action_name="Switch PCV-101 to Manual Bypass Valve",
        target_equipment="PCV-101",
    )

    assert explanation.verified is True
    assert len(explanation.citations) > 0
    assert any("[SOP-V101" in cit.citation_tag or "[HAZOP-SEP" in cit.citation_tag for cit in explanation.citations)


def test_shift_handover_generation_and_export(rag_engine, sample_wm, tmp_path):
    """Verify shift handover report generation in Markdown and HTML with file exports."""
    handover = rag_engine.generate_shift_handover(sample_wm, output_dir=str(tmp_path))

    md_content = handover["markdown"]
    html_content = handover["html"]

    # Verify Markdown contents
    assert "OPERATING SHIFT HANDOVER REPORT" in md_content
    assert sample_wm.state.incident_id in md_content
    assert "`PT-101`" in md_content
    assert "35.80 barg" in md_content
    assert "PCV-101 Stuck Closed" in md_content
    assert "63.3% belief" in md_content
    assert "CHK_01_LOCAL_PCV_STEM" in md_content
    assert "ACT_01_SWITCH_MANUAL_BYPASS" in md_content
    assert "[SOP-V101" in md_content

    # Verify HTML contents
    assert "<!DOCTYPE html>" in html_content
    assert "Shift Handover Report" in html_content
    assert "class='report-table'" in html_content

    # Verify file persistence
    assert os.path.exists(handover["markdown_path"])
    assert os.path.exists(handover["html_path"])
    assert os.path.exists(handover["pdf_path"])
    assert os.path.getsize(handover["markdown_path"]) > 500
    assert os.path.getsize(handover["html_path"]) > 1000
    assert os.path.getsize(handover["pdf_path"]) > 1000
    assert handover["pdf_bytes"].startswith(b"%PDF-1.4")


def test_dialogue_manager_handover_intent(sample_wm):
    """Verify DialogueManager generates and returns Shift Handover Report on operator request."""
    mgr = DialogueManager(working_memory=sample_wm)
    resp = mgr.process_text_input("Please prepare the shift handover report for incoming crew")

    assert resp.intent_detected.value == "HANDOVER"
    assert resp.handover_report is not None
    assert "OPERATING SHIFT HANDOVER REPORT" in resp.handover_report
    assert sample_wm.state.incident_id in resp.reply_text
