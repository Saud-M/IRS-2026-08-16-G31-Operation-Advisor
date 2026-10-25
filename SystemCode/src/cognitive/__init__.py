"""Cognitive Systems & Multimodal Interaction Module.

Provides:
- NLUParser: Intent detection and slot filling
- WorkingMemory: Short-term active incident context and dialogue manager
- SpeechRecognizer: Pretrained ASR voice report ingestion
- DisplayOCRReader: Gauge and instrument display computer vision reader
- DialogueManager: Central multimodal cognitive orchestrator
"""

from .nlu_parser import NLUParser, TaskIntent, ExtractedSlots, ClarificationPrompt
from .working_memory import WorkingMemory, WorkingMemoryState, DialogueTurn
from .speech_asr import SpeechRecognizer, TranscriptionResult
from .display_ocr import DisplayOCRReader, OCRReadingResult
from .dialogue_manager import DialogueManager, AdvisorResponse

__all__ = [
    "NLUParser",
    "TaskIntent",
    "ExtractedSlots",
    "ClarificationPrompt",
    "WorkingMemory",
    "WorkingMemoryState",
    "DialogueTurn",
    "SpeechRecognizer",
    "TranscriptionResult",
    "DisplayOCRReader",
    "OCRReadingResult",
    "DialogueManager",
    "AdvisorResponse",
]
