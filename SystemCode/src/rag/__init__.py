"""Retrieval-Augmented Generation (RAG) module: Vector store, retriever, cited handover."""

from src.rag.document_indexer import DocumentIndexer, DocumentPassage, RetrievalMatch
from src.rag.citation_generator import CitationGenerator, GroundedCitation, GroundedExplanation
from src.rag.handover_generator import ShiftHandoverGenerator
from src.rag.rag_engine import RAGEngine

__all__ = [
    "DocumentIndexer",
    "DocumentPassage",
    "RetrievalMatch",
    "CitationGenerator",
    "GroundedCitation",
    "GroundedExplanation",
    "ShiftHandoverGenerator",
    "RAGEngine",
]
