"""Natural Language Understanding (NLU) Intent Detection & Slot Filling.

Captures four mandatory operational slots from operator natural text or voice transcriptions:
1. Asset Tag (e.g. V-101, K-101, PCV-101, V-102)
2. Symptom / Observation (e.g. HIGH_PRESSURE, SURGE, VIBRATION, CARRYOVER, EMULSION)
3. Timestamp / Offset (e.g. past 15 minutes, since 08:00, just now)
4. Requested Task (DIAGNOSE, PLAN, VERIFY, EXPLAIN, HANDOVER, STATUS)

Detects missing or ambiguous slots and generates structured ClarificationPrompts.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Dict, Any, List, Optional, Set, Tuple


class TaskIntent(str, Enum):
    DIAGNOSE = "DIAGNOSE"                  # "Why has this condition changed?", "Root cause"
    PLAN = "PLAN"                          # "What is the response sequence?", "How to resolve?"
    VERIFY_CHECK = "VERIFY_CHECK"          # "I checked PCV-101 stem, it is stuck"
    EXPLAIN = "EXPLAIN"                    # "Explain why H01 is ranked #1"
    HANDOVER = "HANDOVER"                  # "Generate shift handover summary"
    STATUS_QUERY = "STATUS_QUERY"          # "What is the status of V-101?"
    UNKNOWN = "UNKNOWN"


@dataclass
class ExtractedSlots:
    task_intent: TaskIntent
    asset_tag: Optional[str] = None
    symptom: Optional[str] = None
    symptoms: List[str] = field(default_factory=list)
    timestamp_offset: Optional[str] = None
    observed_value: Optional[float] = None
    observed_unit: Optional[str] = None
    raw_text: str = ""
    confidence: float = 0.90


@dataclass
class ClarificationPrompt:
    missing_slot: str
    question: str
    suggested_options: List[str]


class NLUParser:
    """Extracts operational slots and task intents from natural language reports."""

    # Canonical dictionary of equipment tags and aliases
    ASSET_SYNONYMS = {
        "V-101": ["v-101", "v101", "separator", "hp separator", "3-phase separator", "three phase separator"],
        "V-102": ["v-102", "v102", "scrubber", "suction scrubber", "knockout drum", "ko drum"],
        "K-101": ["k-101", "k101", "compressor", "stage 1 compressor", "first stage compressor"],
        "K-102": ["k-102", "k102", "stage 2 compressor", "second stage compressor"],
        "PCV-101": ["pcv-101", "pcv101", "gas valve", "gas export valve", "pressure control valve"],
        "LCV-101": ["lcv-101", "lcv101", "oil valve", "oil level control valve"],
        "LCV-102": ["lcv-102", "lcv102", "water valve", "interface valve"],
        "ASV-101": ["asv-101", "asv101", "anti-surge valve", "recycle valve", "anti surge"],
    }

    # Canonical dictionary of symptoms
    SYMPTOM_PATTERNS = {
        "SYM_HIGH_PRESSURE": [r"high pressure", r"overpressure", r"pressure rising", r"pressure high", r"pressure spike", r"p > 34", r"pressure alarm"],
        "SYM_LOW_PRESSURE": [r"low pressure", r"pressure low", r"depressuriz", r"pressure drop", r"pressure falling"],
        "SYM_HIGH_LEVEL": [r"high level", r"level rising", r"level high", r"liquid accumulation", r"flooding"],
        "SYM_LOW_INTERFACE": [r"low interface", r"interface low", r"interface reading low", r"emulsion", r"rag layer"],
        "SYM_HIGH_DEMISTER_DP": [r"high dp", r"demister dp", r"carryover", r"differential pressure", r"foaming"],
        "SYM_HIGH_VIBRATION": [r"high vibration", r"vibration rising", r"vibration spike", r"shaking", r"rattle", r"surge vibration", r"compressor surge", r"\bsurge\b", r"surging", r"aerodynamic surge"],
        "SYM_LOW_GAS_FLOW": [r"low flow", r"low gas flow", r"gas flow low", r"flow drop", r"flow starved"],
    }

    TASK_PATTERNS = {
        TaskIntent.DIAGNOSE: [r"why", r"root cause", r"diagnos", r"what happened", r"what is wrong", r"reason"],
        TaskIntent.PLAN: [r"plan", r"action", r"how to fix", r"how to resolve", r"response sequence", r"what should i do", r"which check"],
        TaskIntent.VERIFY_CHECK: [r"i checked", r"verified", r"field check", r"stem position", r"sample result", r"\bcheck\b"],
        TaskIntent.HANDOVER: [r"handover", r"shift handover", r"incident summary", r"shift report", r"log incident"],
        TaskIntent.STATUS_QUERY: [r"status", r"how is", r"readings", r"current state", r"telemetry"],
        TaskIntent.EXPLAIN: [r"explain", r"justification", r"why did you recommend", r"cite", r"citation"],
    }

    def parse(self, text: str) -> Tuple[ExtractedSlots, Optional[ClarificationPrompt]]:
        """Parse natural text into structured slots and return any clarification requirement."""
        clean_text = text.strip()
        lower_text = clean_text.lower()

        # 1. Identify Task Intent
        detected_task = TaskIntent.UNKNOWN
        for intent, patterns in self.TASK_PATTERNS.items():
            if any(re.search(pat, lower_text) for pat in patterns):
                detected_task = intent
                break

        # Default to DIAGNOSE if symptoms are stated but task is unstated
        if detected_task == TaskIntent.UNKNOWN:
            if any(any(re.search(pat, lower_text) for pat in pats) for pats in self.SYMPTOM_PATTERNS.values()):
                detected_task = TaskIntent.DIAGNOSE

        # 2. Extract Asset Tag (with regex boundary checks to avoid substring collisions e.g. v-101 inside pcv-101)
        extracted_asset: Optional[str] = None
        for canonical_tag, aliases in sorted(self.ASSET_SYNONYMS.items(), key=lambda item: max(len(a) for a in item[1]), reverse=True):
            if any(re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lower_text) for alias in aliases):
                extracted_asset = canonical_tag
                break

        # 3. Extract Symptoms (can extract multiple symptoms from one utterance)
        extracted_symptoms: List[str] = []
        for canonical_sym, patterns in self.SYMPTOM_PATTERNS.items():
            if any(re.search(pat, lower_text) for pat in patterns):
                extracted_symptoms.append(canonical_sym)

        primary_symptom = extracted_symptoms[0] if extracted_symptoms else None

        # 4. Extract Numeric Value and Unit (e.g. "36.2 barg", "5.1 mm/s", "85 %")
        extracted_val: Optional[float] = None
        extracted_unit: Optional[str] = None
        val_unit_match = re.search(r"(\d+(?:\.\d+)?)\s*(barg|bar|psi|mm/s|°c|deg c|%|sm3/h)", lower_text)
        if val_unit_match:
            try:
                extracted_val = float(val_unit_match.group(1))
                extracted_unit = val_unit_match.group(2)
            except ValueError:
                pass

        # 5. Extract Timestamp / Offset
        extracted_time: Optional[str] = None
        time_match = re.search(r"(past \d+ (?:minutes?|mins?|hours?)|since \d+:\d+|just now|for the last \d+ (?:minutes?|mins?))", lower_text)
        if time_match:
            extracted_time = time_match.group(1)
        else:
            extracted_time = "current"

        slots = ExtractedSlots(
            task_intent=detected_task,
            asset_tag=extracted_asset,
            symptom=primary_symptom,
            symptoms=extracted_symptoms,
            timestamp_offset=extracted_time,
            observed_value=extracted_val,
            observed_unit=extracted_unit,
            raw_text=clean_text,
            confidence=0.88 if (extracted_asset and primary_symptom) else 0.70,
        )

        # 6. Check for Clarification Needs
        clarification: Optional[ClarificationPrompt] = None

        if detected_task in (TaskIntent.DIAGNOSE, TaskIntent.PLAN):
            if not extracted_asset and not primary_symptom:
                clarification = ClarificationPrompt(
                    missing_slot="asset_or_symptom",
                    question="Which equipment or abnormal condition are you asking about?",
                    suggested_options=["V-101 Separator Overpressure", "K-101 Compressor Surge / Vibration", "V-102 Scrubber Carryover"],
                )
            elif primary_symptom in ("SYM_HIGH_PRESSURE", "SYM_LOW_PRESSURE") and not extracted_asset:
                # Infer default asset V-101 for pressure
                slots.asset_tag = "V-101"
            elif primary_symptom == "SYM_HIGH_VIBRATION" and not extracted_asset:
                # Infer default compressor K-101
                slots.asset_tag = "K-101"

        return slots, clarification
