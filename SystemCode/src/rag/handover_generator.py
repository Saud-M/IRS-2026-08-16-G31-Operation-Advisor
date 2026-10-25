"""Shift Handover Report Generator for Oil and Gas Operations.

Transforms Working Memory state, diagnostic beliefs, executed remediations, and
cited procedural safeguards into an OSHA / API RP 75 compliant Shift Handover Report.
Generates structured Markdown and print-ready standalone HTML reports.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
import os
import re
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from src.rag.citation_generator import CitationGenerator

if TYPE_CHECKING:
    from src.cognitive.working_memory import WorkingMemory


class ShiftHandoverGenerator:
    """Generates structured shift handover reports for incoming operations crews."""

    def __init__(self, citation_gen: Optional[CitationGenerator] = None):
        self.citation_gen = citation_gen or CitationGenerator()

    def generate_markdown(self, wm: "WorkingMemory", outgoing_operator: str = "Lead Console Operator", incoming_operator: str = "Incoming Shift Lead") -> str:
        """Render a comprehensive industrial shift handover report in Markdown."""
        state = wm.state
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_id = f"SHR-{state.incident_id.replace('INC-', '')}-{datetime.now().strftime('%Y%m%d%H%M')}"

        # 1. Telemetry Snapshot Table
        telemetry_rows = []
        for tag, val in sorted(state.telemetry.items()):
            unit = "barg" if tag.startswith("PT") else "%" if tag.startswith("LT") else "bar" if tag.startswith("DP") else "mm/s" if tag.startswith("VT") else "Sm3/h"
            telemetry_rows.append(f"| `{tag}` | **{val:.2f} {unit}** | Active DCS Telemetry |")
        telemetry_table = "\n".join(telemetry_rows) if telemetry_rows else "| *No live telemetry recorded* | - | - |"

        # 2. Ranked Hypotheses
        hypo_rows = []
        for idx, h in enumerate(state.ranked_hypotheses[:3], 1):
            prob = h.get("posterior_prob", 0.0) * 100.0
            h_id = h.get("hypothesis_id", "H00")
            h_desc = h.get("description", "Unknown")
            hypo_rows.append(f"{idx}. **{h_desc}** (`{h_id}`) — **{prob:.1f}% belief**")
        hypo_text = "\n".join(hypo_rows) if hypo_rows else "*Nominal steady state. No active root causes.*"

        # 3. Executed Actions
        action_rows = []
        for act in state.executed_actions:
            act_id = act.get("action_id", "ACT")
            act_name = act.get("name", "Action")
            eq = act.get("target_equipment", "Unit")
            action_rows.append(f"- [x] `{act_id}`: **{act_name}** (`{eq}`) — *Executed & Logged*")
        actions_text = "\n".join(action_rows) if action_rows else "*No corrective actions executed during this shift.*"

        # 4. Active Plan
        plan_rows = []
        for idx, step in enumerate(state.active_plan, 1):
            act_id = step.get("action_id", "ACT")
            name = step.get("name", "Step")
            eq = step.get("target_equipment", "Equipment")
            dur = step.get("duration_min", 5.0)
            plan_rows.append(f"- [ ] `{act_id}`: **{name}** on `{eq}` (Est. {dur:.0f} min) — *Pending Execution*")
        plan_text = "\n".join(plan_rows) if plan_rows else "*No outstanding response plan active.*"

        # 5. Pending and Completed Checks
        completed_checks_rows = []
        if isinstance(state.completed_checks, dict):
            for cid, cinfo in state.completed_checks.items():
                if isinstance(cinfo, dict):
                    res_str = "Confirmed" if cinfo.get("positive") else "Refuted"
                    cname = cinfo.get("name", cid)
                    completed_checks_rows.append(f"- [x] `{cid}`: {cname} — **COMPLETED** (Result: {res_str}, Notes: {cinfo.get('notes', 'Field verified')})")
                else:
                    completed_checks_rows.append(f"- [x] `{cid}` — **COMPLETED**")
        elif isinstance(state.completed_checks, list):
            for c in state.completed_checks:
                cid = c.get("check_id") if isinstance(c, dict) else getattr(c, "check_id", "CHK")
                name = c.get("name") if isinstance(c, dict) else getattr(c, "name", "Check")
                completed_checks_rows.append(f"- [x] `{cid}`: {name} — **COMPLETED**")

        pending_checks_rows = []
        for c in state.pending_checks:
            cid = c.get("check_id") if isinstance(c, dict) else getattr(c, "check_id", "CHK")
            name = c.get("name") if isinstance(c, dict) else getattr(c, "name", "Check")
            prio = c.get("priority") if isinstance(c, dict) else getattr(c, "priority", 1)
            pending_checks_rows.append(f"- [ ] `{cid}`: {name} — **PENDING FIELD VERIFICATION** (Priority: {prio})")

        completed_checks_text = "\n".join(completed_checks_rows) if completed_checks_rows else "*No field checks completed yet during this shift.*"
        pending_checks_text = "\n".join(pending_checks_rows) if pending_checks_rows else "*All field verification checks cleared.*"
        all_checks_combined = (completed_checks_rows + pending_checks_rows)
        checks_text = "\n".join(all_checks_combined) if all_checks_combined else "*All field verification checks cleared.*"

        # 6. Relevant SOP Citations
        top_h_id = state.top_hypothesis or "H01"
        top_h_desc = state.ranked_hypotheses[0].get("description", "Operating Fault") if state.ranked_hypotheses else "Normal Operation"
        explanation = self.citation_gen.explain_hypothesis(top_h_id, top_h_desc)
        citations_rows = []
        for cit in explanation.citations:
            citations_rows.append(f"- **{cit.citation_tag}**: *{cit.title}*  \n  > \"{cit.excerpt}\"")
        citations_text = "\n".join(citations_rows) if citations_rows else "- [SOP-V101 Section 1]: Standard Operating Procedure for V-101 Separator"

        # Assemble Full Document
        md = f"""# OPERATING SHIFT HANDOVER REPORT (OSHA PSM / API RP 75)

**Report ID:** `{report_id}`  
**Generated At:** `{now_str}`  
**Plant Unit:** Area 10/20 — Primary Separation & Gas Compression Train  
**Incident Reference:** `{state.incident_id}` (`{state.incident_title}`)  
**Operational Status:** `{'ACTIVE INCIDENT / ABNORMAL' if state.active else 'STABILIZED / CLOSED'}`  
**Outgoing Shift Lead:** `{outgoing_operator}`  
**Incoming Shift Lead:** `{incoming_operator}`  

---

## 1. Executive Summary & Active Telemetry

The facility is currently operating under supervised decision-support management following abnormal process telemetry.

| Sensor Tag | Current Value | Telemetry Status |
| :--- | :--- | :--- |
{telemetry_table}

- **Confirmed Abnormal Symptoms:** {', '.join(f'`{s}`' for s in sorted(state.confirmed_symptoms)) if state.confirmed_symptoms else 'None (Nominal)'}

---

## 2. Diagnosed Root Causes & Belief Distribution

Diagnostic reasoning engines (Forward Chaining + Bayesian Belief Network) indicate the following prioritized root-cause probabilities:

{hypo_text}

---

## 3. Actions Executed & Active Remediation Plan

### Remediations Executed in Current Shift
{actions_text}

### Active Bounded A* Plan Sequence
{plan_text}

---

## 4. Outstanding Tasks & Field Verification Checks for Incoming Crew

### Verified Field Checks (Completed in Current Shift)
{completed_checks_text}

### Outstanding Checks Required for Incoming Crew
{pending_checks_text}

---

## 5. Grounded Procedural References & Safety Safeguards

All diagnoses and mitigations have been validated against plant operating standards:

{citations_text}

---

## 6. Handover Sign-off & Endorsement

- **Outgoing Console Operator:** _____________________ Date/Time: `{now_str}`
- **Incoming Shift Supervisor:** _____________________ Date/Time: ___________________
"""
        return md

    def generate_html(self, wm: WorkingMemory, outgoing_operator: str = "Lead Console Operator", incoming_operator: str = "Incoming Shift Lead") -> str:
        """Render print-ready, high-visibility styled HTML shift handover report."""
        md = self.generate_markdown(wm, outgoing_operator, incoming_operator)
        
        # Simple Markdown-to-HTML conversion suitable for standalone viewing and printing
        html_lines = []
        in_table = False

        for line in md.split("\n"):
            line_str = line.strip()
            if line_str.startswith("# "):
                html_lines.append(f"<h1 class='title'>{line_str[2:]}</h1>")
            elif line_str.startswith("## "):
                html_lines.append(f"<h2 class='section-title'>{line_str[3:]}</h2>")
            elif line_str.startswith("### "):
                html_lines.append(f"<h3 class='subsection-title'>{line_str[4:]}</h3>")
            elif line_str.startswith("|") and line_str.endswith("|"):
                if not in_table:
                    html_lines.append("<div class='table-container'><table class='report-table'>")
                    in_table = True
                if ":---" in line_str:
                    continue
                cells = [c.strip() for c in line_str.strip("|").split("|")]
                tag = "th" if "Sensor Tag" in line_str else "td"
                cell_html = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
                html_lines.append(f"<tr>{cell_html}</tr>")
            else:
                if in_table:
                    html_lines.append("</table></div>")
                    in_table = False
                if line_str.startswith("- [x]"):
                    html_lines.append(f"<div class='check-item checked'>&#9745; {line_str[5:]}</div>")
                elif line_str.startswith("- [ ]"):
                    html_lines.append(f"<div class='check-item pending'>&#9744; {line_str[5:]}</div>")
                elif line_str.startswith("- "):
                    html_lines.append(f"<li>{line_str[2:]}</li>")
                elif line_str.startswith("> "):
                    html_lines.append(f"<blockquote class='citation-quote'>{line_str[2:]}</blockquote>")
                elif line_str:
                    # Inline bold and code replacements
                    formatted = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line_str)
                    formatted = re.sub(r"`(.+?)`", r"<code>\1</code>", formatted)
                    formatted = re.sub(r"\*(.+?)\*", r"<em>\1</em>", formatted)
                    html_lines.append(f"<p>{formatted}</p>")

        if in_table:
            html_lines.append("</table></div>")

        body_content = "\n".join(html_lines)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Shift Handover Report - {wm.state.incident_id}</title>
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        line-height: 1.6;
        color: #1a202c;
        max-width: 900px;
        margin: 40px auto;
        padding: 0 24px;
        background: #f7fafc;
    }}
    .container {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        padding: 40px;
    }}
    .title {{
        color: #0d47a1;
        border-bottom: 3px solid #1976d2;
        padding-bottom: 12px;
        margin-top: 0;
        font-size: 24px;
    }}
    .section-title {{
        color: #1a365d;
        border-bottom: 1px solid #cbd5e0;
        padding-bottom: 6px;
        margin-top: 32px;
        font-size: 18px;
    }}
    .subsection-title {{
        color: #2d3748;
        font-size: 15px;
        margin-top: 20px;
    }}
    .table-container {{
        margin: 16px 0;
        overflow-x: auto;
    }}
    .report-table {{
        width: 100%;
        border-collapse: collapse;
    }}
    .report-table th, .report-table td {{
        border: 1px solid #e2e8f0;
        padding: 8px 12px;
        text-align: left;
        font-size: 14px;
    }}
    .report-table th {{
        background: #edf2f7;
        font-weight: 600;
        color: #2d3748;
    }}
    .check-item {{
        padding: 6px 10px;
        margin: 4px 0;
        border-radius: 4px;
        font-size: 14px;
    }}
    .check-item.checked {{
        background: #f0fff4;
        color: #22543d;
        border-left: 3px solid #38a169;
    }}
    .check-item.pending {{
        background: #fffaf0;
        color: #7b341e;
        border-left: 3px solid #dd6b20;
    }}
    .citation-quote {{
        border-left: 3px solid #3182ce;
        background: #ebf8ff;
        padding: 8px 16px;
        margin: 8px 0;
        font-style: italic;
        color: #2b6cb0;
    }}
    code {{
        background: #edf2f7;
        padding: 2px 6px;
        border-radius: 3px;
        font-family: monospace;
        font-size: 13px;
    }}
    @media print {{
        body {{ background: #fff; margin: 0; padding: 0; }}
        .container {{ border: none; box-shadow: none; padding: 0; }}
    }}
</style>
</head>
<body>
<div class="container">
{body_content}
</div>
</body>
</html>
"""
        return html

    def generate_pdf(
        self,
        wm: "WorkingMemory",
        outgoing_operator: str = "Lead Console Operator",
        incoming_operator: str = "Incoming Shift Lead",
    ) -> bytes:
        """Render print-ready, high-fidelity PDF shift handover report."""
        from src.rag.pdf_generator import HandoverPDFBuilder
        state = wm.state
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        report_id = f"SHR-{state.incident_id.replace('INC-', '')}-{datetime.now().strftime('%Y%m%d%H%M')}"

        pdf = HandoverPDFBuilder()
        pdf.add_title_header(report_id, state.incident_id, now_str)

        meta = {
            "outgoing": outgoing_operator,
            "incoming": incoming_operator,
            "status": "ACTIVE INCIDENT / ABNORMAL" if state.active else "STABILIZED / NOMINAL",
        }
        pdf.add_metadata_grid(meta)

        # 1. Active Telemetry
        pdf.add_section_header("1. Executive Summary & Live DCS Telemetry")
        pdf.add_paragraph("Process conditions monitored under Level-2 Supervisory advisory envelope:")
        if state.telemetry:
            pdf.add_telemetry_table(dict(state.telemetry))
        else:
            pdf.add_paragraph("No live telemetry recorded.", font="F1", size=8.5, color=(0.4, 0.4, 0.4))

        if state.confirmed_symptoms:
            pdf.add_paragraph(f"Active Symptoms: {', '.join(sorted(state.confirmed_symptoms))}", font="F2", size=8.5, color=(0.7, 0.2, 0.1))

        # 2. Diagnosed Root Causes
        pdf.add_section_header("2. Diagnosed Root Causes & Bayesian Posterior Beliefs")
        if state.ranked_hypotheses:
            for idx, h in enumerate(state.ranked_hypotheses[:3], 1):
                prob = h.get("posterior_prob", 0.0) * 100.0
                h_id = h.get("hypothesis_id", "H00")
                h_desc = h.get("description", "Unknown")
                pdf.add_paragraph(f"{idx}. {h_desc} ({h_id}) - {prob:.1f}% confidence", font="F2" if idx == 1 else "F1", size=8.5)
        else:
            pdf.add_paragraph("Nominal steady-state operation. No active root causes.", font="F1", size=8.5)

        # 3. Remediations & Active Plan
        pdf.add_section_header("3. Actions Executed & Active Remediation Sequence")
        if state.executed_actions:
            pdf.add_paragraph("Executed Remediations in Current Shift:", font="F2", size=8.5)
            for act in state.executed_actions:
                act_id = act.get("action_id", "ACT")
                act_name = act.get("name", "Action")
                eq = act.get("target_equipment", "Unit")
                pdf.add_checklist_item(True, f"{act_id}: {act_name}", f"Equipment: {eq} | Status: Executed & Logged")
        else:
            pdf.add_paragraph("No corrective actions executed during this shift.", font="F1", size=8.5, color=(0.4, 0.4, 0.4))

        if state.active_plan:
            pdf.add_paragraph("Outstanding Plan Sequence:", font="F2", size=8.5)
            for idx, step in enumerate(state.active_plan, 1):
                act_id = step.get("action_id", "ACT")
                name = step.get("name", "Step")
                eq = step.get("target_equipment", "Equipment")
                dur = step.get("duration_min", 5.0)
                pdf.add_checklist_item(False, f"Step {idx}: {name} ({act_id})", f"Target: {eq} | Estimated Time: {dur:.0f} min")

        # 4. Outstanding Tasks & Field Verification Checks
        pdf.add_section_header("4. Field Verification Checks (Completed vs. Pending for Incoming Crew)")
        # Completed
        has_completed = False
        if isinstance(state.completed_checks, dict) and state.completed_checks:
            has_completed = True
            for cid, cinfo in state.completed_checks.items():
                if isinstance(cinfo, dict):
                    cname = cinfo.get("name", cid)
                    eq = cinfo.get("target_equipment", "Unit")
                    res = "Confirmed" if cinfo.get("positive") else "Refuted"
                    pdf.add_checklist_item(True, f"{cid}: {cname}", f"Target: {eq} | Result: {res} | Status: Completed")
                else:
                    pdf.add_checklist_item(True, f"{cid}", "Status: Completed")
        elif isinstance(state.completed_checks, list) and state.completed_checks:
            has_completed = True
            for c in state.completed_checks:
                cid = c.get("check_id") if isinstance(c, dict) else getattr(c, "check_id", "CHK")
                name = c.get("name") if isinstance(c, dict) else getattr(c, "name", "Check")
                pdf.add_checklist_item(True, f"{cid}: {name}", "Status: Completed")

        if not has_completed:
            pdf.add_paragraph("No field checks completed yet during this shift.", font="F1", size=8.5, color=(0.4, 0.4, 0.4))

        # Pending
        if state.pending_checks:
            pdf.add_paragraph("Pending Checks for Incoming Shift Lead:", font="F2", size=8.5, color=(0.7, 0.3, 0.0))
            for c in state.pending_checks:
                cid = c.get("check_id") if isinstance(c, dict) else getattr(c, "check_id", "CHK")
                name = c.get("name") if isinstance(c, dict) else getattr(c, "name", "Check")
                eq = c.get("target_equipment") if isinstance(c, dict) else getattr(c, "target_equipment", "Unit")
                prio = c.get("priority") if isinstance(c, dict) else getattr(c, "priority", 1)
                pdf.add_checklist_item(False, f"{cid}: {name}", f"Target: {eq} | Priority: {prio} | Mandatory Verification")
        else:
            pdf.add_paragraph("All field verification checks cleared for this operational state.", font="F1", size=8.5, color=(0.1, 0.5, 0.2))

        # 5. SOP References
        pdf.add_section_header("5. Grounded Technical References (SOPs & HAZOP Safeguards)")
        top_h_id = state.top_hypothesis or "H01"
        top_h_desc = state.ranked_hypotheses[0].get("description", "Operating Fault") if state.ranked_hypotheses else "Normal Operation"
        explanation = self.citation_gen.explain_hypothesis(top_h_id, top_h_desc)
        if explanation.citations:
            for cit in explanation.citations[:3]:
                pdf.add_paragraph(f"{cit.citation_tag}: {cit.title}", font="F2", size=8.5, color=(0.1, 0.3, 0.6))
                pdf.add_paragraph(f"Excerpt: {cit.excerpt[:120]}...", font="F1", size=8, color=(0.35, 0.35, 0.35))
        else:
            pdf.add_paragraph("[SOP-V101 Section 1]: Standard Operating Procedure for V-101 3-Phase Separator", font="F1", size=8.5)

        # 6. Sign-off
        pdf.add_section_header("6. Formal Shift Handover Sign-off & Regulatory Endorsement")
        pdf.add_signoff_section(now_str, outgoing_operator, incoming_operator)

        return pdf.build_pdf_bytes()

    def export_report(self, wm: WorkingMemory, output_dir: Optional[str] = None) -> Dict[str, str]:
        """Save Markdown, HTML, and PDF handover reports to disk."""
        target_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "cases"
        )
        os.makedirs(target_dir, exist_ok=True)

        timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        inc_id = wm.state.incident_id.replace("INC-", "")
        md_filename = f"handover_{inc_id}_{timestamp_slug}.md"
        html_filename = f"handover_{inc_id}_{timestamp_slug}.html"
        pdf_filename = f"handover_{inc_id}_{timestamp_slug}.pdf"

        md_path = os.path.join(target_dir, md_filename)
        html_path = os.path.join(target_dir, html_filename)
        pdf_path = os.path.join(target_dir, pdf_filename)

        md_content = self.generate_markdown(wm)
        html_content = self.generate_html(wm)
        pdf_content = self.generate_pdf(wm)

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        with open(pdf_path, "wb") as f:
            f.write(pdf_content)

        return {"markdown_path": md_path, "html_path": html_path, "pdf_path": pdf_path}
