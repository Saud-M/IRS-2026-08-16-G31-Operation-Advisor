"""Document Indexer & Semantic Passage Retriever for Oil & Gas Technical Corpus.

Indexes Standard Operating Procedures (SOPs), HAZOP sheets, and equipment manuals.
Features:
1. Strict passage chunking preserving unique passage IDs (e.g. [SOP-V101:SEC-01]).
2. Metadata tagging (equipment assets, symptom keywords, document source).
3. Hybrid semantic retrieval (TF-IDF vector space + keyword/tag boost), with ChromaDB
   support if available.
4. Offline, air-gapped industrial capability with zero network dependencies.
"""

from dataclasses import dataclass, field
import os
import re
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class DocumentPassage:
    passage_id: str
    document_id: str
    title: str
    section: str
    content: str
    asset_tags: List[str] = field(default_factory=list)
    symptom_keys: List[str] = field(default_factory=list)


@dataclass
class RetrievalMatch:
    passage: DocumentPassage
    score: float
    citation_tag: str  # e.g., "[SOP-V101 Section 1]" or "[HAZOP-SEP Node 1]"


class DocumentIndexer:
    """Parses, indexes, and retrieves passages from plant technical documents."""

    EQUIPMENT_KEYWORDS = {
        "V-101": ["v-101", "separator", "hp separator", "3-phase"],
        "K-101": ["k-101", "compressor", "first stage", "centrifugal"],
        "V-102": ["v-102", "scrubber", "suction scrubber", "knockout"],
        "PCV-101": ["pcv-101", "pressure control valve", "gas valve"],
        "ASV-101": ["asv-101", "anti-surge", "anti surge", "recycle valve"],
        "BDV-101": ["bdv-101", "blowdown", "flare valve"],
        "HV-101B": ["hv-101b", "bypass valve", "manual bypass"],
        "LCV-101": ["lcv-101", "oil valve"],
        "LCV-102": ["lcv-102", "water valve", "interface valve"],
    }

    SYMPTOM_KEYWORDS = {
        "SYM_HIGH_PRESSURE": ["high pressure", "overpressure", "pressure spike", "p > 34"],
        "SYM_LOW_PRESSURE": ["low pressure", "depressuriz", "pressure drop"],
        "SYM_HIGH_LEVEL": ["high level", "flooding", "liquid accumulation"],
        "SYM_LOW_INTERFACE": ["low interface", "interface reading low", "emulsion", "rag layer"],
        "SYM_HIGH_DEMISTER_DP": ["high dp", "demister dp", "carryover", "foaming"],
        "SYM_HIGH_VIBRATION": ["high vibration", "vibration spike", "vibration danger"],
        "SYM_LOW_GAS_FLOW": ["low flow", "low gas flow", "flow starved"],
        "COMPRESSOR_SURGE": ["surge", "aerodynamic surge", "surge limit", "scl"],
    }

    def __init__(self, documents_dir: Optional[str] = None):
        self.documents_dir = documents_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "documents"
        )
        self.passages: List[DocumentPassage] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix: Optional[np.ndarray] = None
        self._build_index()

    def _extract_citation_tag(self, passage_id: str, title: str) -> str:
        """Derive standard human-readable citation label like [SOP-V101 Section 1]."""
        doc = passage_id.split(":")[0] if ":" in passage_id else passage_id
        sec_match = re.search(r"(?:Section\s*|Sec\s*)(\d+)", title, re.IGNORECASE)
        node_match = re.search(r"Node\s*(\d+)", title, re.IGNORECASE)

        if sec_match:
            return f"[{doc} Section {sec_match.group(1)}]"
        elif node_match:
            return f"[{doc} Node {node_match.group(1)}]"
        return f"[{passage_id}]"

    def _parse_markdown_file(self, file_path: str) -> List[DocumentPassage]:
        """Split a technical Markdown file into distinct referenced passages."""
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        if base_name == "README":
            return []

        # Split on section headings containing bracketed passage IDs: ## [DOC_ID:SEC_ID]
        sections = re.split(r"\n(?=##\s+\[)", text)
        passages: List[DocumentPassage] = []

        for sec in sections:
            m = re.match(r"##\s+\[([a-zA-Z0-9_\-]+:[a-zA-Z0-9_\-]+)\]\s*(.+)", sec)
            if m:
                p_id = m.group(1)
                title_line = m.group(2).strip()
                content = sec[m.end():].strip()
            else:
                # If header doesn't have bracketed ID, look for generic header
                header_match = re.match(r"##\s+(.+)", sec)
                if not header_match:
                    continue
                title_line = header_match.group(1).strip()
                p_id = f"{base_name}:SEC-{len(passages) + 1:02d}"
                content = sec[header_match.end():].strip()

            content_lower = content.lower() + " " + title_line.lower()

            # Detect matching assets
            matched_assets = []
            for asset, syns in self.EQUIPMENT_KEYWORDS.items():
                if any(syn in content_lower for syn in syns):
                    matched_assets.append(asset)

            # Detect matching symptoms
            matched_symptoms = []
            for sym, syns in self.SYMPTOM_KEYWORDS.items():
                if any(syn in content_lower for syn in syns):
                    matched_symptoms.append(sym)

            passage = DocumentPassage(
                passage_id=p_id,
                document_id=base_name,
                title=title_line,
                section=title_line,
                content=content,
                asset_tags=matched_assets,
                symptom_keys=matched_symptoms,
            )
            passages.append(passage)

        return passages

    def _build_index(self):
        """Load and index all Markdown files from data/documents."""
        self.passages = []
        if os.path.exists(self.documents_dir):
            for fname in sorted(os.listdir(self.documents_dir)):
                if fname.endswith(".md"):
                    fpath = os.path.join(self.documents_dir, fname)
                    file_passages = self._parse_markdown_file(fpath)
                    self.passages.extend(file_passages)

        if not self.passages:
            return

        corpus = [f"{p.title}\n{p.content}" for p in self.passages]
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            stop_words="english",
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def search(
        self,
        query: str,
        asset_filter: Optional[str] = None,
        top_k: int = 3,
        threshold: float = 0.05,
    ) -> List[RetrievalMatch]:
        """Search indexed technical passages with hybrid TF-IDF and metadata boosting."""
        if not self.passages or self.vectorizer is None or self.tfidf_matrix is None:
            return []

        query_lower = query.lower()
        query_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        matches: List[RetrievalMatch] = []
        for idx, passage in enumerate(self.passages):
            score = float(sims[idx])

            # Metadata boost for exact asset match
            if asset_filter and asset_filter in passage.asset_tags:
                score += 0.25
            elif any(asset.lower() in query_lower for asset in passage.asset_tags):
                score += 0.15

            # Metadata boost for exact symptom match
            if any(sym.lower() in query_lower for sym in passage.symptom_keys):
                score += 0.20

            if score >= threshold:
                citation = self._extract_citation_tag(passage.passage_id, passage.title)
                matches.append(RetrievalMatch(passage=passage, score=round(score, 4), citation_tag=citation))

        # Sort descending by composite score
        matches.sort(key=lambda m: m.score, reverse=True)
        return matches[:top_k]

    def get_passage_by_id(self, passage_id: str) -> Optional[DocumentPassage]:
        """Fetch passage directly by unique ID."""
        for p in self.passages:
            if p.passage_id == passage_id:
                return p
        return None
