"""Self-Contained Local Web Server & API for Operation Advisor Cockpit.

Serves an interactive single-page industrial web dashboard with:
- SVG Process Flow Diagram (PFD) with real-time sensor overlays
- Scenario injection (Nominal, PCV Stiction, Carryover, Surge, Emulsion, Slug)
- Natural language query console with Voice & Dial Gauge OCR integration
- Probabilistic Bayesian belief ranking cards with Shannon entropy
- Dynamic A* plan flowchart and prioritized field checklist
- 1-Click OSHA PSM / API RP 75 Shift Handover Report generation (Markdown/HTML download)
Runs with zero external npm or pip web dependencies via Python's built-in http.server.
"""

from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import os
import urllib.parse
from typing import Dict, Any, Optional

from src.simulation_bridge.scenarios import (
    ScenarioType,
    ScenarioInjector,
    FaultConfig,
)
from src.simulation_bridge.process_model import SeparatorCompressorTrain
from src.cognitive.dialogue_manager import DialogueManager
from src.cognitive.working_memory import WorkingMemory
from src.rag.rag_engine import RAGEngine
from src.cognitive.display_ocr import DisplayOCRReader


class CockpitState:
    """Singleton maintaining live process and cognitive state for the UI."""

    def __init__(self):
        self.wm = WorkingMemory(incident_title="Live Console Operations")
        self.dialogue_mgr = DialogueManager(working_memory=self.wm)
        self.rag = RAGEngine()
        self.ocr = DisplayOCRReader()
        self.current_scenario_name = "NOMINAL"

        # Default nominal steady state readings
        self.telemetry = {
            "PT-101": 31.2,
            "PT-102": 30.5,
            "PT-103": 75.4,
            "LT-101": 50.1,
            "LT-102": 49.8,
            "LT-103": 12.0,
            "FT-101": 68000.0,
            "FT-102": 450.0,
            "DPIT-101": 0.022,
            "VT-101": 1.45,
            "TT-101": 42.0,
            "TT-102": 105.0,
            "PCV_101_POS": 48.0,
            "ASV_101_POS": 0.0,
        }
        self.wm.update_telemetry(self.telemetry)

    def sync_checklist_state(self, completed_item_ids: list):
        """Synchronize operator-selected completed checklist items and actions into working memory."""
        import datetime
        clean_ids = set()
        for cid in completed_item_ids:
            clean = str(cid).replace("chk-", "").replace("step-", "").strip()
            if clean:
                clean_ids.add(clean)

        # 1. Reconcile diagnostic checks
        all_checks = {}
        for chk in self.wm.state.pending_checks:
            cid = chk.get("check_id") if isinstance(chk, dict) else getattr(chk, "check_id", "")
            if cid:
                all_checks[cid] = chk

        for cid, cinfo in self.wm.state.completed_checks.items():
            if cid not in all_checks:
                name = cinfo.get("name") if isinstance(cinfo, dict) else cid
                all_checks[cid] = {"check_id": cid, "name": name, "target_equipment": "Unit", "priority": 1}

        new_pending = []
        new_completed = {}
        for cid, chk in all_checks.items():
            name = chk.get("name", cid) if isinstance(chk, dict) else cid
            if cid in clean_ids:
                new_completed[cid] = {
                    "positive": True,
                    "notes": f"Field verified and completed by operator ({name})",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "name": name,
                    "target_equipment": chk.get("target_equipment", "Unit"),
                }
            else:
                new_pending.append(chk)

        # Add any explicit check ID present in clean_ids
        for cid in clean_ids:
            if cid.startswith("CHK_") and cid not in new_completed:
                new_completed[cid] = {
                    "positive": True,
                    "notes": "Field verified and completed by operator",
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "name": cid,
                }

        self.wm.state.pending_checks = new_pending
        self.wm.state.completed_checks = new_completed

        # 2. Reconcile action steps
        all_actions = {}
        for a in self.wm.state.executed_actions:
            aid = a.get("action_id", "")
            if aid:
                all_actions[aid] = a
        for s in self.wm.state.active_plan_steps:
            aid = s.get("action_id", "")
            if aid:
                all_actions[aid] = s

        new_executed = []
        new_plan = []
        for aid, a in all_actions.items():
            name = a.get("name", "Action")
            eq = a.get("target_equipment", "Unit")
            dur = a.get("duration_min", 5.0)
            if aid in clean_ids:
                new_executed.append({
                    "action_id": aid,
                    "name": name,
                    "target_equipment": eq,
                    "status": "COMPLETED",
                    "executed_at": datetime.datetime.utcnow().isoformat(),
                })
            else:
                new_plan.append({
                    "action_id": aid,
                    "name": name,
                    "target_equipment": eq,
                    "duration_min": dur,
                })

        self.wm.state.executed_actions = new_executed
        self.wm.state.active_plan_steps = new_plan
        self.wm.state.last_updated = datetime.datetime.utcnow().isoformat()

    def load_scenario(self, scenario_key: str):
        """Simulate process telemetry for a given fault scenario."""
        self.current_scenario_name = scenario_key
        # Clean state reset on scenario switch
        self.wm.state.confirmed_symptoms = set()
        self.wm.state.hypothesis_beliefs = {}
        self.wm.state.top_hypothesis = None
        self.wm.state.active_plan_steps = []
        self.wm.state.pending_checks = []
        self.wm.state.completed_checks = {}
        self.wm.state.executed_actions = []
        train = SeparatorCompressorTrain()

        if scenario_key == "PCV_101_STICTION":
            config = FaultConfig(
                scenario_type=ScenarioType.PCV_STICTION,
                start_time_sec=5.0,
                duration_sec=120.0,
                severity=0.9,
                parameters={"stuck_position": 0.08},
            )
            injector = ScenarioInjector(config)
            for _ in range(60):
                injector.apply(train)
                train.step(dt=1.0)
            train.state.shaft_vibration_mms = 1.8
        elif scenario_key == "LIQUID_CARRYOVER":
            config = FaultConfig(
                scenario_type=ScenarioType.LIQUID_CARRYOVER,
                start_time_sec=5.0,
                duration_sec=120.0,
                severity=0.85,
            )
            injector = ScenarioInjector(config)
            for _ in range(60):
                injector.apply(train)
                train.step(dt=1.0)
            train.state.shaft_vibration_mms = 2.1
            train.state.demister_dp_bar = 0.65
        elif scenario_key == "COMPRESSOR_SURGE":
            config = FaultConfig(
                scenario_type=ScenarioType.COMPRESSOR_SURGE,
                start_time_sec=5.0,
                duration_sec=120.0,
                severity=0.85,
            )
            injector = ScenarioInjector(config)
            for _ in range(60):
                injector.apply(train)
                train.step(dt=1.0)
            train.state.shaft_vibration_mms = 5.31
            train.state.demister_dp_bar = 0.022
        elif scenario_key == "EMULSION_DRIFT":
            config = FaultConfig(
                scenario_type=ScenarioType.EMULSION_PAD,
                start_time_sec=5.0,
                duration_sec=120.0,
                severity=0.8,
            )
            injector = ScenarioInjector(config)
            for _ in range(60):
                injector.apply(train)
                train.step(dt=1.0)
            train.state.interface_level_pct = 25.0
            train.state.interface_transmitter_bias_pct = -14.0
            train.state.shaft_vibration_mms = 1.45
            train.state.demister_dp_bar = 0.022
        elif scenario_key == "WELLHEAD_SLUG":
            config = FaultConfig(
                scenario_type=ScenarioType.SLUG_INFLUX,
                start_time_sec=5.0,
                duration_sec=120.0,
                severity=0.85,
            )
            injector = ScenarioInjector(config)
            for _ in range(60):
                injector.apply(train)
                train.step(dt=1.0)
            # In severe wellhead slugging, liquid inventory surges and causes overpressure
            train.state.liquid_level_pct = 75.0
            train.state.pressure_barg = 34.5
            train.state.shaft_vibration_mms = 1.8
            train.state.demister_dp_bar = 0.035
        else:
            for _ in range(60):
                train.step(dt=1.0)
            train.state.demister_dp_bar = 0.022
            train.state.shaft_vibration_mms = 1.45

        snap = train.snapshot()
        p101 = float(snap.get("PT-101", 31.0))
        self.telemetry = {
            "PT-101": round(p101, 2),
            "PT-102": round(p101 - 0.7, 2),
            "PT-103": round(p101 * 2.4, 2),
            "LT-101": round(float(snap.get("LT-101", 50.0)), 2),
            "LT-102": round(float(snap.get("LT-102", 25.0)), 2),
            "LT-103": round(float(snap.get("V102_scrubber_level", 12.0)), 2),
            "FT-101": round(float(snap.get("FT-101", 68000.0)), 1),
            "FT-102": 450.0,
            "DPIT-101": round(float(snap.get("DP-101", 0.022)), 4),
            "VT-101": round(float(snap.get("ST-101", 1.45)), 2),
            "TT-101": round(float(snap.get("TT-101", 42.0)), 1),
            "TT-102": 105.0,
            "PCV_101_POS": round(float(snap.get("PCV-101_pos", 0.48)) * 100.0, 1),
            "ASV_101_POS": round(float(snap.get("ASV-101_pos", 0.0)) * 100.0, 1),
        }
        # Provide aliases for physics reasoning engines
        self.telemetry["DP-101"] = self.telemetry["DPIT-101"]
        self.telemetry["ST-101"] = self.telemetry["VT-101"]
        self.telemetry["V102_scrubber_level"] = self.telemetry["LT-103"]
        self.telemetry["PCV-101_pos"] = round(float(snap.get("PCV-101_pos", 0.48)), 3)
        self.wm.update_telemetry(self.telemetry)


COCKPIT_STATE = CockpitState()


class CockpitHandler(BaseHTTPRequestHandler):
    """Handles HTTP requests for the Operation Advisor Cockpit."""

    def _set_headers(self, content_type="application/json"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._serve_html_dashboard()
        elif path == "/api/status":
            self._handle_api_status()
        elif path == "/api/handover":
            params = urllib.parse.parse_qs(parsed.query)
            fmt = params.get("format", ["pdf"])[0]
            completed_str = params.get("completed", [""])[0]
            completed_items = [c.strip() for c in completed_str.split(",") if c.strip()] if completed_str else None
            self._handle_api_handover(completed_items, format_type=fmt)
        elif path == "/api/citation":
            params = urllib.parse.parse_qs(parsed.query)
            tag = params.get("tag", [""])[0]
            self._handle_api_citation(tag)
        elif path.startswith("/static/"):
            self._serve_static(path)
        else:
            self.send_error(404, "Endpoint Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        body = json.loads(post_data.decode("utf-8")) if post_data else {}

        if path == "/api/scenario":
            sc_key = body.get("scenario", "NOMINAL")
            COCKPIT_STATE.load_scenario(sc_key)
            self._handle_api_status()
        elif path == "/api/query":
            text = body.get("text", "")
            resp = COCKPIT_STATE.dialogue_mgr.process_text_input(text)
            self._set_headers("application/json")
            self.wfile.write(json.dumps({
                "reply": resp.reply_text,
                "intent": resp.intent_detected.value,
                "top_hypothesis": resp.top_hypothesis,
                "confidence_pct": resp.confidence_pct,
                "recommended_checks": resp.recommended_checks,
                "recommended_actions": resp.recommended_actions,
                "active_plan": resp.active_plan,
                "citations": resp.citations,
                "handover_report": resp.handover_report,
                "llm_source": resp.llm_source,
                "model_used": resp.model_used,
            }).encode("utf-8"))
        elif path == "/api/telemetry":
            new_telemetry = body.get("telemetry", {})
            COCKPIT_STATE.telemetry.update(new_telemetry)
            COCKPIT_STATE.wm.update_telemetry(new_telemetry)
            self._handle_api_status()
        elif path == "/api/handover":
            params = urllib.parse.parse_qs(parsed.query)
            fmt = params.get("format", [body.get("format", "pdf")])[0]
            completed_items = body.get("completed_items", None)
            self._handle_api_handover(completed_items, format_type=fmt)
        elif path == "/api/checklist":
            completed_items = body.get("completed_items", [])
            COCKPIT_STATE.sync_checklist_state(completed_items)
            self._set_headers("application/json")
            self.wfile.write(json.dumps({
                "status": "ok",
                "completed_count": len(completed_items),
            }).encode("utf-8"))
        else:
            self.send_error(404, "Endpoint Not Found")

    def _handle_api_status(self):
        """Return combined live telemetry and reasoning state."""
        state = COCKPIT_STATE.wm.state
        tel = dict(COCKPIT_STATE.telemetry)

        # Trigger reasoning cycle to refresh beliefs without invoking slow conversational narrative
        slots, _ = COCKPIT_STATE.dialogue_mgr.nlu.parse("Diagnose current operational telemetry")
        advisor_res = COCKPIT_STATE.dialogue_mgr._execute_reasoning_cycle(slots, generate_narrative=False)

        # Build comprehensive checklist: keep both completed and pending checks visible
        all_checks = []
        seen_check_ids = set()

        for cid, cinfo in state.completed_checks.items():
            seen_check_ids.add(cid)
            all_checks.append({
                "check_id": cid,
                "name": cinfo.get("name", cid) if isinstance(cinfo, dict) else cid,
                "target_equipment": cinfo.get("target_equipment", "Unit") if isinstance(cinfo, dict) else "Unit",
                "instructions": cinfo.get("instructions", "Completed & field verified by operator.") if isinstance(cinfo, dict) else "",
                "priority": cinfo.get("priority", 1) if isinstance(cinfo, dict) else 1,
                "completed": True,
            })

        for chk in advisor_res.recommended_checks:
            cid = chk.get("check_id") if isinstance(chk, dict) else getattr(chk, "check_id", "")
            if cid and cid not in seen_check_ids:
                seen_check_ids.add(cid)
                item = dict(chk) if isinstance(chk, dict) else {
                    "check_id": chk.check_id,
                    "name": chk.name,
                    "target_equipment": chk.target_equipment,
                    "instructions": chk.instructions,
                    "priority": chk.priority,
                }
                item["completed"] = False
                all_checks.append(item)

        # Reconcile plan steps with executed actions
        executed_ids = {a.get("action_id", "") for a in state.executed_actions}
        plan_steps = []
        for step in advisor_res.active_plan:
            step_dict = dict(step)
            step_dict["completed"] = step_dict.get("action_id") in executed_ids
            plan_steps.append(step_dict)

        resp_payload = {
            "incident_id": state.incident_id,
            "scenario": COCKPIT_STATE.current_scenario_name,
            "telemetry": tel,
            "confirmed_symptoms": list(state.confirmed_symptoms),
            "top_hypothesis": advisor_res.top_hypothesis,
            "confidence_pct": advisor_res.confidence_pct,
            "ranked_hypotheses": state.ranked_hypotheses[:5],
            "recommended_checks": all_checks,
            "recommended_actions": advisor_res.recommended_actions,
            "active_plan": plan_steps,
            "citations": advisor_res.citations,
            "ollama_available": COCKPIT_STATE.dialogue_mgr.llm_client.is_available(),
            "ollama_model": COCKPIT_STATE.dialogue_mgr.llm_client.model,
        }

        resp_bytes = json.dumps(resp_payload).encode("utf-8")
        self._set_headers("application/json")
        self.wfile.write(resp_bytes)

    def _handle_api_handover(self, completed_items=None, format_type="pdf"):
        """Export shift handover report and return PDF, HTML, or JSON metadata."""
        if completed_items is not None:
            COCKPIT_STATE.sync_checklist_state(completed_items)
        handover = COCKPIT_STATE.rag.generate_shift_handover(COCKPIT_STATE.wm)

        if format_type == "pdf":
            pdf_bytes = handover.get("pdf_bytes")
            if not pdf_bytes:
                pdf_bytes = COCKPIT_STATE.rag.handover_gen.generate_pdf(COCKPIT_STATE.wm)
            inc_id = COCKPIT_STATE.wm.state.incident_id.replace("INC-", "")
            filename = f"Shift_Handover_INC_{inc_id}.pdf"
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(pdf_bytes)))
            self.end_headers()
            self.wfile.write(pdf_bytes)
        elif format_type == "html":
            html_content = handover.get("html", "")
            html_bytes = html_content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)
        else:
            resp_copy = {k: v for k, v in handover.items() if k != "pdf_bytes"}
            data_bytes = json.dumps(resp_copy).encode("utf-8")
            self._set_headers("application/json")
            self.wfile.write(data_bytes)

    def _handle_api_citation(self, tag: str):
        """Return excerpt and full text for a given citation tag."""
        norm_tag = tag.strip("[] ").lower()
        matched = None
        for p in COCKPIT_STATE.rag.indexer.passages:
            tag_sop = f"{p.document_id} section {p.section}".lower()
            tag_node = f"{p.document_id} node {p.section}".lower()
            tag_alt = f"{p.document_id} {p.section}".lower()
            if (norm_tag in tag_sop) or (norm_tag in tag_node) or (norm_tag in tag_alt) or (p.passage_id.lower() in norm_tag):
                matched = p
                break

        if not matched and COCKPIT_STATE.rag.indexer.passages:
            # Fallback to search query
            results = COCKPIT_STATE.rag.query_procedures(norm_tag, top_k=1)
            if results:
                matched = results[0].passage

        if matched:
            payload = {
                "tag": tag,
                "title": matched.title,
                "document_id": matched.document_id,
                "section": matched.section,
                "content": matched.content,
                "asset_tags": matched.asset_tags,
            }
        else:
            payload = {"error": f"Citation reference '{tag}' not found in active SOP corpus."}

        self._set_headers("application/json")
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _serve_html_dashboard(self):
        """Serve the single-page responsive Cockpit UI."""
        html_path = os.path.join(os.path.dirname(__file__), "index.html")
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
            self._set_headers("text/html")
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_error(404, "index.html not found")

    def _serve_static(self, path: str):
        """Serve static files if needed."""
        self.send_error(404, "Static file not found")


def start_cockpit_server(port: int = 8501, host: str = "127.0.0.1") -> ThreadingHTTPServer:
    """Launch the Operation Advisor Cockpit HTTP Server."""
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, CockpitHandler)
    httpd.daemon_threads = True
    return httpd
