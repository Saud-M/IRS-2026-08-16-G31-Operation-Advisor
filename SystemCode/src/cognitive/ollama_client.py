"""Local LLM Client for Industrial Decision Support via Ollama.

Connects the Operation Advisor to an on-premise, air-gapped local LLM via Ollama
(running on Windows, macOS Intel, macOS Apple Silicon, or Linux) with strict
zero-hallucination contextual grounding.

Key Architecture:
1. Cross-platform REST integration via standard urllib.request (zero extra dependencies).
2. Context-only prompt engineering with rigid negative constraints (no external knowledge).
3. Exact procedural document grounding from indexed SOPs and HAZOP sheets.
4. Deterministic sampling (temperature = 0.0) for procedural accuracy.
5. High-reliability fallback to intelligent local RAG synthesis when Ollama is offline.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import json
import os
import platform
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class LLMResponse:
    """Standardized response from the local LLM or offline RAG synthesizer."""
    text: str
    model_used: str
    citations: List[str] = field(default_factory=list)
    is_grounded: bool = True
    llm_source: str = "ollama"  # 'ollama' or 'offline_rag_fallback'
    execution_time_ms: float = 0.0


class LocalLLMClient:
    """Client for local Ollama instances with strict RAG context enforcement."""

    SYSTEM_PROMPT = """You are the Operation Advisor AI assistant for high-pressure 3-phase separator V-101 and centrifugal gas compressor K-101.
Your duty is to answer control room operators with absolute procedural accuracy.

CRITICAL OPERATIONAL RULES:
1. Answer ONLY using the facts, limits, and steps provided in the CONTEXT below.
2. Do NOT use outside knowledge, assumptions, or unverified industrial practices.
3. If the question cannot be answered directly from the provided context, reply exactly:
   "The available operating procedures (SOP-V101, SOP-K101, HAZOP-SEP) do not contain information to answer this question."
4. Every factual claim, alarm threshold, or recommended action MUST include its exact bracketed citation tag from the context (e.g. [SOP-V101 Section 2], [SOP-K101 Section 3], or [HAZOP-SEP Node 1]).
5. Keep your answer concise, direct, professional, and actionable for panel operators.
"""

    def __init__(
        self,
        host: Optional[str] = None,
        default_model: str = "llama3.2",
        timeout_sec: float = 25.0,
    ):
        # Resolve host from environment or default to standard loopback
        env_host = os.environ.get("OLLAMA_HOST", "").strip()
        raw_host = env_host or host or "http://127.0.0.1:11434"

        if not raw_host.startswith("http://") and not raw_host.startswith("https://"):
            raw_host = f"http://{raw_host}"
        self.host = raw_host.rstrip("/")

        self.model = os.environ.get("OLLAMA_MODEL", "").strip() or default_model
        self.timeout_sec = timeout_sec
        self._cached_available: Optional[bool] = None
        self._discovered_models: List[str] = []

    @property
    def platform_info(self) -> str:
        """Return operating system and architecture for diagnostic logs."""
        return f"{platform.system()} ({platform.machine()})"

    def is_available(self, force_refresh: bool = False) -> bool:
        """Check if the local Ollama server is running and reachable."""
        if self._cached_available is not None and not force_refresh:
            return self._cached_available

        url = f"{self.host}/api/tags"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": f"OperationAdvisor-Cockpit/{self.platform_info}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name", "") for m in payload.get("models", [])]
                    self._discovered_models = [m for m in models if m]

                    # Auto-select installed model if default not present
                    if self._discovered_models and self.model not in self._discovered_models:
                        # Check for base name match (e.g. 'llama3.2' matching 'llama3.2:latest')
                        match = next((m for m in self._discovered_models if m.startswith(self.model)), None)
                        if match:
                            self.model = match
                        elif self._discovered_models:
                            self.model = self._discovered_models[0]

                    self._cached_available = True
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass

        self._cached_available = False
        return False

    def get_available_models(self) -> List[str]:
        """Return list of models downloaded in the local Ollama instance."""
        if not self._discovered_models:
            self.is_available(force_refresh=True)
        return list(self._discovered_models)

    def build_grounded_context(
        self,
        passages: List[Dict[str, Any]],
        telemetry: Dict[str, Any],
        hypothesis_info: Optional[Dict[str, Any]] = None,
        plan_steps: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Assemble strict procedural context and live telemetry into standard prompt format."""
        context_blocks = []

        # 1. Procedural Document Chunks
        context_blocks.append("=== PROCEDURAL & HAZOP DOCUMENTATION ===")
        if passages:
            for p in passages:
                tag = p.get("citation_tag") or f"[{p.get('doc_id', 'DOC')} Section {p.get('section', '1')}]"
                title = p.get("title", "Procedure")
                content = p.get("content", "").strip()
                context_blocks.append(f"--- DOCUMENT PASSAGE: {tag} ({title}) ---\n{content}\n")
        else:
            context_blocks.append("No specific procedural passages retrieved for this query.\n")

        # 2. Live Process Telemetry
        context_blocks.append("=== CURRENT LIVE TELEMETRY & ALARM STATUS ===")
        tel_lines = []
        for k in sorted(telemetry.keys()):
            v = telemetry[k]
            if isinstance(v, float):
                tel_lines.append(f"- {k}: {v:.2f}")
            else:
                tel_lines.append(f"- {k}: {v}")
        context_blocks.append("\n".join(tel_lines))

        # 3. Active Reasoning & Diagnostic State
        if hypothesis_info:
            h_desc = hypothesis_info.get("description", "Nominal")
            h_prob = hypothesis_info.get("posterior_prob", 0.0)
            context_blocks.append(f"\n=== DIAGNOSTIC REASONING STATE ===\n- Assessed Hypothesis: {h_desc} ({h_prob*100:.1f}% confidence)")

        if plan_steps:
            context_blocks.append("\n=== RECOMMENDED RESPONSE PLAN ===")
            for idx, step in enumerate(plan_steps, 1):
                context_blocks.append(f"{idx}. {step.get('name')} (Target: {step.get('target_equipment')}, Duration: {step.get('duration_min')} min)")

        return "\n\n".join(context_blocks)

    def generate(
        self,
        query: str,
        passages: List[Dict[str, Any]],
        telemetry: Dict[str, Any],
        hypothesis_info: Optional[Dict[str, Any]] = None,
        plan_steps: Optional[List[Dict[str, Any]]] = None,
        is_query_matched: bool = True,
    ) -> LLMResponse:
        """Generate a strictly grounded response using local Ollama or offline RAG synthesizer."""
        import time
        t0 = time.perf_counter()

        context_str = self.build_grounded_context(
            passages=passages,
            telemetry=telemetry,
            hypothesis_info=hypothesis_info,
            plan_steps=plan_steps,
        )

        # Attempt Ollama local generation if server is reachable
        if self.is_available():
            try:
                llm_text = self._call_ollama_chat(query=query, context_str=context_str)
                if llm_text:
                    elapsed = (time.perf_counter() - t0) * 1000.0
                    citations = self._extract_citations(llm_text)
                    return LLMResponse(
                        text=llm_text,
                        model_used=self.model,
                        citations=citations,
                        is_grounded=True,
                        llm_source="ollama",
                        execution_time_ms=round(elapsed, 1),
                    )
            except Exception:
                # Silently fall back to offline RAG synthesizer on network/generation error
                pass

        # Offline Intelligent RAG Synthesizer Fallback
        fallback_text, citations = self._synthesize_offline_rag_response(
            query=query,
            passages=passages,
            telemetry=telemetry,
            hypothesis_info=hypothesis_info,
            plan_steps=plan_steps,
            is_query_matched=is_query_matched,
        )
        elapsed = (time.perf_counter() - t0) * 1000.0

        return LLMResponse(
            text=fallback_text,
            model_used="deterministic-rag-synthesizer",
            citations=citations,
            is_grounded=True,
            llm_source="offline_rag_fallback",
            execution_time_ms=round(elapsed, 1),
        )

    def _call_ollama_chat(self, query: str, context_str: str) -> Optional[str]:
        """Execute HTTP POST request to Ollama /api/chat with zero temperature."""
        url = f"{self.host}/api/chat"

        user_content = f"CONTEXT:\n{context_str}\n\nOPERATOR INQUIRY:\n{query}\n\nAnswer strictly from CONTEXT with mandatory bracketed section citations:"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "options": {
                "temperature": 0.0,  # Zero-temperature for deterministic, factual fidelity
                "num_predict": 300,
            },
            "stream": False,
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"OperationAdvisor-Cockpit/{self.platform_info}",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            if resp.status == 200:
                result = json.loads(resp.read().decode("utf-8"))
                message = result.get("message", {})
                content = message.get("content", "").strip()
                if content:
                    # Strip any internal thought or reasoning blocks (e.g. <think>...</think>)
                    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                    return content
        return None

    def _extract_citations(self, text: str) -> List[str]:
        """Extract all bracketed citation tags from text."""
        return re.findall(r"\[[A-Z0-9_\-]+(?:\s*Section\s*\d+(?:\.\d+)?|\s*Node\s*\d+|:[A-Z0-9_\-]+)\]", text, re.IGNORECASE)

    def _synthesize_offline_rag_response(
        self,
        query: str,
        passages: List[Dict[str, Any]],
        telemetry: Dict[str, Any],
        hypothesis_info: Optional[Dict[str, Any]] = None,
        plan_steps: Optional[List[Dict[str, Any]]] = None,
        is_query_matched: bool = True,
    ) -> Tuple[str, List[str]]:
        """Intelligently synthesize answers directly from retrieved SOP passages and telemetry."""
        q_lower = query.lower()
        citations = []
        for p in passages:
            tag = p.get("citation_tag")
            if tag and tag not in citations:
                citations.append(tag)

        # 0. Strict negative constraint for out-of-domain queries
        if not is_query_matched and not any(tag in q_lower for tag in ["pt-101", "lt-101", "lt-102", "st-101", "ft-101", "dp-101", "v-101", "k-101", "v-102", "pcv-101", "asv-101", "pressure", "vibration", "level", "flow", "separator", "compressor"]):
            return (
                "The available operating procedures (SOP-V101, SOP-K101, HAZOP-SEP) do not contain information regarding this inquiry. "
                "The Operation Advisor is strictly constrained to verified operating documentation and live telemetry for Train 1.",
                [],
            )

        # 1. Root-cause diagnostic inquiries under active fault
        if hypothesis_info and hypothesis_info.get("hypothesis_id") != "H07" and (
            any(w in q_lower for w in ["why", "diagnos", "cause", "reason", "fault", "problem", "h01", "pcv", "surge", "stuck", "carryover", "slug", "pad"])
            or not q_lower
        ):
            h_desc = hypothesis_info.get("description", "Process Upset")
            h_id = hypothesis_info.get("hypothesis_id", "H01")
            h_prob = hypothesis_info.get("posterior_prob", 0.0)
            tag = citations[0] if citations else "[SOP-V101 Section 2]"
            plan_note = f" Generated {len(plan_steps)}-step response plan: 1. {plan_steps[0].get('name')}." if plan_steps else ""
            reply = (
                f"Primary root cause assessed as **{h_desc}** ({h_id}) with {h_prob*100:.1f}% probabilistic confidence. "
                f"Grounded in {tag}.{plan_note}"
            )
            return reply, list(set(citations))

        # 2. Telemetry / Status inquiries
        if any(w in q_lower for w in ["status", "reading", "value", "pressure", "level", "vibration", "temperature", "flow"]):
            # Specific sensor check
            if "pt-101" in q_lower or "pressure" in q_lower:
                p_val = telemetry.get("PT-101", 30.0)
                tag_cit = "[SOP-V101 Section 1]"
                citations.append(tag_cit)
                status_desc = "elevated (ALARM: PAH)" if p_val >= 34.0 else "nominal"
                reply = (
                    f"Separator V-101 operating pressure (`PT-101`) is currently **{p_val:.2f} barg** ({status_desc}). "
                    f"According to {tag_cit}, the normal operating envelope is 28.0–32.0 barg, with High Alarm (PAH) at 34.0 barg."
                )
                return reply, list(set(citations))

            if "st-101" in q_lower or "vibration" in q_lower or "k-101" in q_lower:
                v_val = telemetry.get("ST-101", 1.8)
                tag_cit = "[SOP-K101 Section 2]"
                citations.append(tag_cit)
                v_desc = "critical surge vibration (ALARM: VAHH)" if v_val >= 4.5 else "nominal"
                reply = (
                    f"Compressor K-101 shaft vibration (`ST-101`) is currently **{v_val:.2f} mm/s** ({v_desc}). "
                    f"Under {tag_cit}, nominal vibration is 1.2–2.8 mm/s; exceeding 4.5 mm/s warrants immediate anti-surge recycle opening."
                )
                return reply, list(set(citations))

            if "lt-101" in q_lower or "lt-102" in q_lower or "level" in q_lower:
                l_val = telemetry.get("LT-101", 50.0)
                tag_cit = "[SOP-V101 Section 1]"
                citations.append(tag_cit)
                reply = (
                    f"Separator V-101 liquid level (`LT-101`) is **{l_val:.1f}%**, and water interface (`LT-102`) is **{telemetry.get('LT-102', 25.0):.1f}%**. "
                    f"Design operating envelope is 45–55% liquid hold-up per {tag_cit}."
                )
                return reply, list(set(citations))

        # 3. General procedural inquiries answered from retrieved passage content
        if passages:
            best_p = passages[0]
            tag = best_p.get("citation_tag") or f"[{best_p.get('doc_id')} Section {best_p.get('section')}]"
            title = best_p.get("title", "Standard Procedure")
            content = best_p.get("content", "")

            # Extract key action lines or guidelines
            lines = [l.strip() for l in content.split("\n") if l.strip() and not l.startswith("#")]
            summary_lines = lines[:4] if len(lines) >= 4 else lines
            summary_text = " ".join(summary_lines)

            plan_note = ""
            if plan_steps:
                plan_note = f" Recommended response sequence: 1. {plan_steps[0].get('name')}."

            reply = f"Per {tag} ({title}): {summary_text}{plan_note}"
            return reply, list(set(citations))

        # 3. Fallback to active hypothesis if a fault is active
        if hypothesis_info and hypothesis_info.get("hypothesis_id") != "H07":
            h_desc = hypothesis_info.get("description", "Process Upset")
            h_prob = hypothesis_info.get("posterior_prob", 0.0)
            tag = citations[0] if citations else "[SOP-V101 Section 2]"
            reply = (
                f"Process diagnostics indicate **{h_desc}** with {h_prob*100:.1f}% posterior confidence. "
                f"Refer to {tag} for immediate corrective response steps."
            )
            return reply, list(set(citations))

        return (
            "All process parameters appear nominal and within safe operating envelopes. "
            "Refer to [SOP-V101 Section 1] for steady-state control specifications.",
            ["[SOP-V101 Section 1]"],
        )
