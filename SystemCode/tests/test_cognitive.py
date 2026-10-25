"""Unit and Integration Tests for Cognitive Systems Module (Sprint 5).
Verifies NLU slot filling, working memory state, speech ASR, OCR display reading, and multimodal dialogue orchestration.
"""

import pytest
from src.cognitive.nlu_parser import NLUParser, TaskIntent
from src.cognitive.working_memory import WorkingMemory
from src.cognitive.speech_asr import SpeechRecognizer
from src.cognitive.display_ocr import DisplayOCRReader
from src.cognitive.dialogue_manager import DialogueManager


@pytest.fixture
def nlu():
    return NLUParser()


@pytest.fixture
def wm():
    return WorkingMemory(incident_title="Unit Test Incident")


@pytest.fixture
def dialogue_mgr():
    return DialogueManager()


def test_nlu_slot_filling_and_intent(nlu):
    """Verify extraction of asset, symptom, unit, scalar value, and task intent."""
    query = "Why is separator V-101 pressure rising past 35.5 barg for the past 15 minutes?"
    slots, clarification = nlu.parse(query)

    assert clarification is None
    assert slots.task_intent == TaskIntent.DIAGNOSE
    assert slots.asset_tag == "V-101"
    assert slots.symptom == "SYM_HIGH_PRESSURE"
    assert slots.observed_value == 35.5
    assert slots.observed_unit == "barg"
    assert "past 15 minute" in slots.timestamp_offset


def test_nlu_clarification_on_ambiguous_input(nlu):
    """Verify clarification request when query has no equipment or symptom."""
    query = "Can you help me diagnose what happened?"
    slots, clarification = nlu.parse(query)

    assert clarification is not None
    assert clarification.missing_slot == "asset_or_symptom"
    assert len(clarification.suggested_options) > 0


def test_working_memory_lifecycle(wm):
    """Verify working memory state transitions, check completions, and audit logging."""
    assert wm.state.active is True
    assert wm.state.incident_id.startswith("INC-")

    # Update telemetry
    wm.update_telemetry({"PT-101": 35.8, "FT-101": 50000.0})
    assert wm.state.telemetry["PT-101"] == 35.8

    # Register pending checks
    wm.register_pending_checks([
        {"check_id": "CHK_01_LOCAL_PCV_STEM", "name": "Inspect PCV stem", "priority": 1}
    ])
    assert len(wm.state.pending_checks) == 1

    # Record check completion
    wm.record_check_feedback("CHK_01_LOCAL_PCV_STEM", positive=True, notes="Stem travel stuck at 15%")
    assert len(wm.state.pending_checks) == 0
    assert "CHK_01_LOCAL_PCV_STEM" in wm.state.completed_checks
    assert wm.state.completed_checks["CHK_01_LOCAL_PCV_STEM"]["positive"] is True

    # Audit logging
    wm.log_audit("TEST_EVENT", {"detail": "All checks verified"})
    assert len(wm.state.audit_events) == 1

    snap = wm.snapshot()
    assert snap["completed_checks"]["CHK_01_LOCAL_PCV_STEM"]["positive"] is True


def test_speech_recognition_transcription():
    """Verify verbal audio report transcription and slot parsing."""
    recognizer = SpeechRecognizer(offline_mode=True)
    res = recognizer.transcribe("sample_vibration_audio.wav", hint_context="vibration")

    assert res.confidence > 0.80
    assert "vibration" in res.transcript.lower()
    assert res.extracted_slots.symptom in ("SYM_HIGH_VIBRATION", "COMPRESSOR_SURGE")
    assert res.extracted_slots.asset_tag == "K-101"


def test_display_ocr_gauge_parsing():
    """Verify parsing of digital meter display text into structured tag and measurement."""
    ocr = DisplayOCRReader()
    text = "TRANSMITTER PT-101 35.8 BARG STATUS NORMAL"
    res = ocr.parse_text_from_display(text)

    assert res is not None
    assert res.detected_tag == "PT-101"
    assert res.numeric_value == 35.8
    assert res.unit == "barg"
    assert res.is_valid_range is True
    assert res.alarm_triggered == "HIGH"


def test_synthetic_gauge_image_generation():
    """Verify synthetic instrument display generation via Pillow."""
    img = DisplayOCRReader.generate_synthetic_gauge_image("ST-101", 5.2, "mm/s")
    assert img.size == (320, 160)
    assert img.mode == "RGB"


def test_dialogue_manager_end_to_end(dialogue_mgr):
    """Verify full end-to-end cognitive loop: operator input -> reasoning -> advisor response."""
    report = "Why is separator V-101 pressure high at 36.0 barg with low gas flow?"
    resp = dialogue_mgr.process_text_input(report)

    assert resp.clarification_needed is False
    assert resp.top_hypothesis == "H01"
    assert resp.confidence_pct > 60.0
    assert len(resp.recommended_checks) > 0
    assert len(resp.recommended_actions) > 0
    assert len(resp.active_plan) > 0
    assert "H01" in resp.reply_text or "PCV-101" in resp.reply_text


def test_ollama_client_cross_platform_setup():
    """Verify LocalLLMClient initializes on Windows, macOS (Intel/ARM), and Linux."""
    from src.cognitive.ollama_client import LocalLLMClient
    client = LocalLLMClient(host="http://localhost:11434", default_model="llama3.2")

    assert client.host == "http://localhost:11434"
    assert client.model == "llama3.2"
    assert len(client.platform_info) > 0
    # Offline check should return boolean without throwing unhandled exceptions
    is_avail = client.is_available()
    assert isinstance(is_avail, bool)


def test_ollama_client_strict_prompt_and_grounding():
    """Verify context-only prompt construction enforcing negative constraints and citations."""
    from src.cognitive.ollama_client import LocalLLMClient
    client = LocalLLMClient()

    passages = [
        {
            "citation_tag": "[SOP-V101 Section 2]",
            "title": "PCV-101 Stiction Response",
            "content": "Crack open manual bypass valve HV-101B immediately upon overpressure.",
        }
    ]
    telemetry = {"PT-101": 36.5, "FT-101": 42000.0}
    context_str = client.build_grounded_context(
        passages=passages,
        telemetry=telemetry,
        hypothesis_info={"description": "PCV-101 Stuck Closed", "posterior_prob": 0.63},
        plan_steps=[{"name": "Switch PCV-101 to Manual Bypass Valve", "target_equipment": "PCV-101", "duration_min": 5.0}],
    )

    assert "[SOP-V101 Section 2]" in context_str
    assert "PT-101: 36.50" in context_str
    assert "PCV-101 Stuck Closed" in context_str
    assert "Switch PCV-101 to Manual Bypass Valve" in context_str
    # Verify strict negative constraints in system prompt
    assert "Answer ONLY using the facts" in client.SYSTEM_PROMPT
    assert "Do NOT use outside knowledge" in client.SYSTEM_PROMPT


def test_ollama_client_out_of_domain_negative_constraint():
    """Verify that ungrounded, out-of-domain queries return strict refusal rather than hallucinations."""
    from src.cognitive.ollama_client import LocalLLMClient
    client = LocalLLMClient()

    # Query with zero procedural match
    resp = client.generate(
        query="What is the weather in Singapore today?",
        passages=[],
        telemetry={"PT-101": 30.0},
        hypothesis_info={"hypothesis_id": "H07", "description": "Nominal"},
        is_query_matched=False,
    )

    assert resp.is_grounded is True
    assert "do not contain information" in resp.text
    assert len(resp.citations) == 0


def test_ollama_client_offline_procedural_synthesis():
    """Verify intelligent offline RAG synthesis answering specific procedural queries with exact citations."""
    from src.cognitive.ollama_client import LocalLLMClient
    client = LocalLLMClient()

    passages = [
        {
            "citation_tag": "[SOP-K101 Section 2]",
            "doc_id": "SOP-K101",
            "section": "2",
            "title": "Anti-Surge Protection & Shaft Vibration Control",
            "content": "Compressor K-101 nominal shaft vibration envelope is 1.2 to 2.8 mm/s. Exceeding 4.5 mm/s requires opening ASV-101.",
        }
    ]
    resp = client.generate(
        query="What is the vibration limit on compressor K-101?",
        passages=passages,
        telemetry={"ST-101": 2.1},
        hypothesis_info={"hypothesis_id": "H07", "description": "Nominal"},
        is_query_matched=True,
    )

    assert resp.is_grounded is True
    assert "[SOP-K101 Section 2]" in resp.text
    assert "ST-101" in resp.text or "vibration" in resp.text.lower()

