"""Script to generate a comprehensive, professionally styled Word Document (.docx)
User Guide for the Operation Advisor system.
"""

import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    """Set the background color of a table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set inner padding of a table cell in dxa (1 pt = 20 dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def add_callout(doc, text, title="NOTE", callout_type="NOTE"):
    """Add a shaded callout alert box with colored left border."""
    border_color = "0A2540" # Navy default
    bg_color = "F1F5F9"     # Light slate
    title_color = RGBColor(10, 37, 64)

    if callout_type == "IMPORTANT":
        border_color = "B91C1C" # Crimson
        bg_color = "FEF2F2"
        title_color = RGBColor(185, 28, 28)
    elif callout_type == "TIP":
        border_color = "0D9488" # Teal
        bg_color = "F0FDFA"
        title_color = RGBColor(13, 148, 136)
    elif callout_type == "WARNING":
        border_color = "D97706" # Amber
        bg_color = "FFFBEB"
        title_color = RGBColor(217, 119, 6)

    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, bg_color)
    set_cell_margins(cell, top=140, bottom=140, left=180, right=180)

    # Left border only
    tcPr = cell._tc.get_or_add_tcPr()
    borders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'<w:top w:val="none"/>'
        f'<w:left w:val="single" w:sz="36" w:space="0" w:color="{border_color}"/>'
        f'<w:bottom w:val="none"/>'
        f'<w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(borders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run_title = p.add_run(f"[{title}] ")
    run_title.bold = True
    run_title.font.name = "Segoe UI"
    run_title.font.size = Pt(10)
    run_title.font.color.rgb = title_color

    run_text = p.add_run(text)
    run_text.font.name = "Segoe UI"
    run_text.font.size = Pt(9.5)
    run_text.font.color.rgb = RGBColor(51, 65, 85)

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

def format_table(tbl, col_widths, headers, data_rows, header_bg="0A2540"):
    """Format a table with industrial styling, alternating row shading, and proper padding."""
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False

    # Header Row
    hdr_cells = tbl.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].width = Inches(col_widths[i])
        set_cell_background(hdr_cells[i], header_bg)
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=140, right=140)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        run = p.add_run(title)
        run.bold = True
        run.font.name = "Segoe UI"
        run.font.size = Pt(9.5)
        run.font.color.rgb = RGBColor(255, 255, 255)

    # Data Rows
    for row_idx, row_data in enumerate(data_rows):
        row = tbl.add_row()
        bg_color = "F8FAFC" if (row_idx % 2 == 1) else "FFFFFF"
        for col_idx, val in enumerate(row_data):
            cell = row.cells[col_idx]
            cell.width = Inches(col_widths[col_idx])
            set_cell_background(cell, bg_color)
            set_cell_margins(cell, top=90, bottom=90, left=130, right=130)
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            run = p.add_run(str(val))
            run.font.name = "Segoe UI"
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(30, 41, 59)

            # Set thin horizontal grid line
            tcPr = cell._tc.get_or_add_tcPr()
            borders = parse_xml(
                f'<w:tcBorders {nsdecls("w")}>'
                f'<w:top w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
                f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>'
                f'<w:left w:val="none"/>'
                f'<w:right w:val="none"/>'
                f'</w:tcBorders>'
            )
            tcPr.append(borders)

    doc_p = tbl._element.getparent()
    # Add spacing after table
    p_after = docx.text.paragraph.Paragraph(parse_xml(f'<w:p {nsdecls("w")}/>'), doc_p)
    p_after.paragraph_format.space_after = Pt(8)

def build_user_guide():
    doc = Document()

    # Configure Margins
    for section in doc.sections:
        section.top_margin = Inches(0.85)
        section.bottom_margin = Inches(0.85)
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)

    # Base Styles
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Segoe UI'
    style_normal.font.size = Pt(10)
    style_normal.font.color.rgb = RGBColor(30, 41, 59) # Slate 800

    # ==========================================
    # COVER / TITLE PAGE HEADER
    # ==========================================
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(24)
    title_p.paragraph_format.space_after = Pt(4)
    run_sup = title_p.add_run("CPF TRAIN 1 AUTOMATION & SAFETY SYSTEM\n")
    run_sup.font.size = Pt(11)
    run_sup.font.bold = True
    run_sup.font.color.rgb = RGBColor(14, 116, 144) # Cyan 700

    run_title = title_p.add_run("OPERATION ADVISOR")
    run_title.font.size = Pt(26)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(10, 37, 64) # Deep Navy

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(18)
    run_sub = sub_p.add_run("Control Room Operator Manual & Industrial Cockpit User Guide")
    run_sub.font.size = Pt(13)
    run_sub.font.color.rgb = RGBColor(71, 85, 105)

    # Document Metadata Table
    meta_tbl = doc.add_table(rows=1, cols=4)
    meta_widths = [1.6, 1.6, 1.6, 1.7]
    meta_headers = ["Document Reference", "System Version", "Operating Target", "Regulatory Standard"]
    meta_data = [
        ["MNL-OA-TR1-2026", "Version 4.2 Production", "Area 10/20 (V-101 / K-101)", "OSHA 1910.119 / API RP 75"]
    ]
    format_table(meta_tbl, meta_widths, meta_headers, meta_data, header_bg="1E293B")

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    add_callout(
        doc,
        "Level-2 Supervisory Advisory Architecture: Operation Advisor operates strictly as a read-only decision support system. "
        "It provides probabilistic fault diagnosis, prioritized field verification checklists, and optimal remediation plans. "
        "Operation Advisor NEVER directly writes setpoint changes or overrides Distributed Control System (DCS) safety interlocks. "
        "All physical valves and control stations must be executed by certified panel or field operators.",
        title="OPERATIONAL SAFETY MANDATE",
        callout_type="IMPORTANT"
    )

    # ==========================================
    # SECTION 1: EXECUTIVE OVERVIEW
    # ==========================================
    h1 = doc.add_heading("1. Executive Summary & System Purpose", level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)

    p = doc.add_paragraph(
        "Modern hydrocarbon separation and compression trains operate under dynamic multiphase conditions where rapid process upsets "
        "(such as control valve stiction, liquid carryover foaming, wellhead slugging, and aerodynamic compressor surge) can escalate within "
        "seconds into emergency flaring, mechanical trip, or environmental release. "
        "Operation Advisor (Group 31) is an industrial-grade cognitive artificial intelligence system engineered specifically for Central Processing "
        "Facility (CPF) Train 1, monitoring High-Pressure 3-Phase Separator V-101 and Centrifugal Gas Compressor K-101."
    )
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "By fusing live sensor telemetry with a dynamic first-principles physical model, forward-chaining rules, exact Bayesian Belief Networks, "
        "heuristic A* state-space planning, and retrieval-augmented SOP generation, Operation Advisor provides control room console operators with "
        "unmatched situational awareness and mathematically grounded operational guidance."
    )

    # Key Capabilities Bullet List
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    bullets = [
        ("Real-Time Telemetry & Visual Mimics: ", "Continuous tracking of 14 key plant sensors with intuitive normal, alarm, and trip thresholds and dynamic rate-of-change trend vectors."),
        ("Physics-Driven Scenario Injection: ", "Full simulation bridge providing dynamic scenario testing for 6 operational conditions without endangering physical assets."),
        ("Probabilistic Bayesian Diagnosis: ", "Computes exact posterior belief distributions across competing failure hypotheses, quantified with Shannon Entropy in bits."),
        ("Backward-Chaining Field Checklists: ", "Generates prioritized, targeted physical verification checklists that isolate root causes and guide field operators."),
        ("Bounded A* Remediation Planning: ", "Computes mathematically admissible, cost-optimal procedural response sequences guaranteed to restore plant stability."),
        ("Verifiable SOP & HAZOP Grounding: ", "Cites verbatim standard operating procedures (e.g., [SOP-V101 Section 1], [HAZOP-SEP Node 1]) with two-way anti-hallucination verification."),
        ("OSHA PSM / API RP 75 Shift Handover Export: ", "Instantly compiles and exports structured Shift Handover Dossiers into clean, standardized PDF documents with a single click.")
    ]
    for b_title, b_desc in bullets:
        bp = doc.add_paragraph(style='List Bullet')
        bp.paragraph_format.space_after = Pt(3)
        r_b = bp.add_run(b_title)
        r_b.bold = True
        r_b.font.color.rgb = RGBColor(15, 23, 42)
        r_t = bp.add_run(b_desc)
        r_t.font.color.rgb = RGBColor(51, 65, 85)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ==========================================
    # SECTION 2: SYSTEM ARCHITECTURE
    # ==========================================
    h1 = doc.add_heading("2. Core Multi-Pillar Architecture", level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)

    p = doc.add_paragraph(
        "Operation Advisor is structured into five cohesive architectural pillars working in strict real-time synchronization:"
    )
    p.paragraph_format.space_after = Pt(8)

    arch_tbl = doc.add_table(rows=1, cols=3)
    arch_widths = [1.5, 2.2, 2.8]
    arch_headers = ["Pillar", "Component / Engine", "Operational Responsibility"]
    arch_data = [
        ["Pillar 1: Physics", "SeparatorCompressorTrain & ScenarioInjector", "Dynamic differential equations of state modeling gas pressure, liquid accumulation, demister fouling, scrubber carryover, and compressor surge aerodynamics."],
        ["Pillar 2: Logic", "ForwardChainingEngine & BackwardChainingEngine", "Evaluates operational limits to deduce active symptoms; backtracks through plant Knowledge Graph to identify required physical field checks."],
        ["Pillar 3: Uncertainty", "ProcessBayesianNetwork (pgmpy + NumPy)", "Computes posterior probability distributions P(Fault | Evidence) across 7 hypotheses with Shannon Entropy diagnostic ambiguity scoring."],
        ["Pillar 4: Planning", "AStarPlanner & GA Optimizer", "State-space heuristic search finding shortest-duration, lowest-risk sequence of remedial actions; genetic setpoint optimization."],
        ["Pillar 5: Cognitive", "LocalLLMClient, RAGEngine, & HandoverGenerator", "Strictly grounded natural language Q&A, two-way citation verification, dial gauge OCR simulation, and PDF Shift Handover report compiling."]
    ]
    format_table(arch_tbl, arch_widths, arch_headers, arch_data, header_bg="0A2540")

    add_callout(
        doc,
        "Deterministic Grounding Guarantee: When operating with local Ollama LLMs or offline RAG synthesizers, "
        "the system rejects any generated statement that lacks verifiable grounding in the indexed document corpus. "
        "Hallucinated procedures or non-existent document numbers are strictly blocked by the citation verification gateway.",
        title="ANTI-HALLUCINATION ENFORCEMENT",
        callout_type="TIP"
    )

    # ==========================================
    # SECTION 3: COCKPIT INTERFACE GUIDE
    # ==========================================
    h1 = doc.add_heading("3. Cockpit User Interface Guide", level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "The Operation Advisor Cockpit is accessible via any modern web browser at http://localhost:8080. "
        "Its human-centered industrial design is optimized for high-pressure control room environments with low visual fatigue."
    )

    h2 = doc.add_heading("3.1 Top Navigation & Action Header", level=2)
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "The top header bar provides instant global plant status and primary controls:\n"
        "• Plant Status Orb: Glowing indicator reflecting real-time Train 1 state (Green = Nominal, Amber = Warning/Alarm, Red = ESD/Trip Limit Exceeded).\n"
        "• Incident ID Badge: Unique incident tracking tag (e.g. INC-BBD0724B) tied to the active working memory and cryptographic audit trail.\n"
        "• Inject Scenario Dropdown: Allows instant injection of 6 calibrated dynamic operating scenarios for training, drift testing, and diagnosis verification.\n"
        "• Export Handover (PDF) Button: Automatically generates a formal OSHA PSM / API RP 75 compliant Shift Handover Report and prompts browser download."
    )

    h2 = doc.add_heading("3.2 Interactive Plant Schematic Mimic", level=2)
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "The central SVG schematic represents the physical layout of CPF Train 1:\n"
        "• Separator V-101: Features dynamic animated liquid hold-up level that rises or drops in real-time according to telemetry.\n"
        "• Compressor K-101: Visualizes suction and discharge streams, showing stage 1 compression and anti-surge loop ASV-101.\n"
        "• Interactive Sensor Badges: Clicking directly on sensor callouts (such as PT-101 or ST-101) automatically queries the AI assistant for operating limits and troubleshooting instructions."
    )

    h2 = doc.add_heading("3.3 Live Sensor Telemetry Suite", level=2)
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "The telemetry panel displays 8 core transmitters with color-coded alarm limits, progress bars, and directional trend arrows:"
    )

    sensor_tbl = doc.add_table(rows=1, cols=5)
    sensor_widths = [1.2, 1.4, 1.3, 1.3, 1.3]
    sensor_headers = ["Tag ID", "Description", "Normal Range", "Alarm Warning", "ESD Trip Limit"]
    sensor_data = [
        ["PT-101", "Separator V-101 Pressure", "28.0 - 32.0 barg", "PAH >= 34.0 barg", "PAHH >= 36.5 barg"],
        ["LT-101", "Hydrocarbon Liquid Level", "45.0 - 55.0 %", "LAH >= 65.0 %", "LAHH >= 75.0 %"],
        ["LT-102", "Oil-Water Interface Level", "20.0 - 35.0 %", "LAL <= 15.0 %", "LAAL <= 10.0 %"],
        ["DPIT-101", "Demister Pad Differential Pressure", "0.015 - 0.035 bar", "DPAH >= 0.080 bar", "Risk Limit > 0.120 bar"],
        ["VT-101", "Compressor K-101 Shaft Vibration", "1.0 - 2.5 mm/s", "VAH >= 3.8 mm/s", "VAHH >= 4.5 mm/s"],
        ["FT-101", "Dry Gas Export Flow Rate", "80,000 - 95,000 Sm3/h", "FAL <= 65,000 Sm3/h", "Surge Line <= 52,000 Sm3/h"],
        ["PCV-101", "Gas Outlet Control Valve Position", "40.0 - 60.0 %", "Sluggish < 20.0 %", "Stuck / Fail Closed"],
        ["ASV-101", "Anti-Surge Recycle Valve Position", "0.0 % (Fully Closed)", "Modulating > 15.0 %", "Manual 100% Full Recycle"]
    ]
    format_table(sensor_tbl, sensor_widths, sensor_headers, sensor_data, header_bg="1E293B")

    h2 = doc.add_heading("3.4 Cognitive Dialogue Assistant & Quick Suggestion Chips", level=2)
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "Console operators can interact in plain English with the Operation Advisor through the chatbox or by clicking one of the quick chips:\n"
        "• V-101 Pressure Inquiry: Rapidly diagnoses why pressure is rising and evaluates PCV-101 status.\n"
        "• K-101 Surge Margin: Queries compressor operating point relative to the Surge Control Line (SCL).\n"
        "• SOP-V101 Limits: Retrieves formal technical operating envelopes from indexed engineering documents.\n"
        "• PCV-101 Verification: Returns step-by-step mechanical and instrument air checks.\n"
        "• Shift Handover Dossier: Summarizes operational events and compiles formal sign-off report."
    )

    h2 = doc.add_heading("3.5 Probabilistic Fault Hypotheses (Bayesian Net)", level=2)
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "This panel presents the real-time posterior probability distribution over all competing operational hypotheses. "
        "The top hypothesis is highlighted in bright cyan with a probability progress bar. "
        "The header displays the live Shannon Entropy H(X) in bits (e.g. 2.73 bits indicates maximum ambiguity under nominal conditions; "
        "values below 1.20 bits indicate high diagnostic certainty under an active fault)."
    )

    h2 = doc.add_heading("3.6 Bounded A* Response Plan & Field Checklist", level=2)
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "Combines backward-chaining physical field checks with forward-looking A* remediation steps:\n"
        "• Interactive Verification Checkboxes: Checking an item marks it COMPLETED in the UI and immediately synchronizes "
        "with the WorkingMemory backend via POST /api/checklist, updating the diagnostic certainty score.\n"
        "• Planned Remediation Steps: Displays optimal action sequences, target equipment tags, and duration estimates (e.g. 'Step 1: Switch PCV-101 to Manual Bypass Valve - Est: 5.0 min')."
    )

    h2 = doc.add_heading("3.7 Grounded Technical References (SOPs & HAZOP)", level=2)
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "Displays clickable citation pills (such as [SOP-V101 Section 1] and [HAZOP-SEP Node 1]). "
        "Clicking any citation pill opens the Verbatim Procedural Inspector Modal, showing the exact standard text, document ID, revision date, "
        "and applicable asset boundaries."
    )

    # ==========================================
    # SECTION 4: FAULT SCENARIO PLAYBOOKS
    # ==========================================
    h1 = doc.add_heading("4. Operational Scenario Playbooks", level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "The Operation Advisor includes 6 standard operational scenarios designed to validate plant safety protocols and operator training:"
    )

    scenarios_data = [
        ("Scenario 1: Nominal Steady-State", "H07: Nominal Operation",
         "Process variables remain within baseline tolerances (PT-101 = 30.0 barg, LT-101 = 50%, VT-101 = 1.45 mm/s).",
         "No remediation plan required. Bayesian net shows uniform prior distribution (25% nominal, Shannon Entropy ~2.73 bits).",
         "None (System stable). Cites [SOP-V101 Section 1] for baseline operation."),

        ("Scenario 2: PCV-101 Stiction (Overpressure)", "H01: PCV-101 Stuck Closed",
         "PCV-101 actuator sticks at 8% stroke. Gas outlet flow FT-101 drops to 25,000 Sm3/h; vessel pressure PT-101 surges past 37.5 barg.",
         "1. Inspect local PCV-101 valve stem & actuator position.\n2. Check instrument air supply regulator (4.5 barg setpoint).",
         "Switch PCV-101 to DCS Manual Station and modulate manual bypass valve HV-101B to stabilize vessel between 31.0 and 32.5 barg per [SOP-V101 Section 1]."),

        ("Scenario 3: Demister Fouling & Carryover", "H03: Foaming & Carryover",
         "Heavy crude foaming blinds the wire mesh demister pad. DPIT-101 differential pressure rises past 0.65 bar; liquid carries over into suction scrubber V-102 (LT-103 > 13%).",
         "1. Check demister differential pressure transmitter lines.\n2. Verify suction scrubber V-102 auto-drain valve LCV-103 operation.",
         "Start chemical injection pump P-105 to dose silicone-based antifoam at 25-45 ppm. Pinch upstream choke manifold by 15% to lower gas superficial velocity per [SOP-V101 Section 2]."),

        ("Scenario 4: Compressor K-101 Surge", "H04: Aerodynamic Surge",
         "Driver speed fluctuation or flow restriction forces operating point across the Surge Control Line (SCL). Shaft vibration VT-101 violently spikes to 5.3 mm/s (exceeding trip limit 4.5 mm/s).",
         "1. Inspect anti-surge recycle valve ASV-101 fast-stroke actuator.\n2. Check compressor suction strainer differential pressure.",
         "Immediately switch ASV-101 controller to MANUAL and step open to 100% full recycle back to scrubber V-102 per [SOP-K101 Section 1]."),

        ("Scenario 5: Emulsion Pad & LT-102 Drift", "H05: Emulsion Rag Layer & Drift",
         "Accumulation of tight emulsion / rag layer at oil-water interface causes capacitive transmitter LT-102 to drift down to 11% while true interface is at 25%.",
         "1. Take physical thief sample from V-101 interface try-cocks (LG-102) to verify true emulsion pad thickness.",
         "Isolate and flush external level bridle LT-102. Increase demulsifier injection rate by 20% at upstream manifold per [SOP-V101 Section 3]."),

        ("Scenario 6: Severe Wellhead Slug Influx", "H06: Wellhead Slug Influx",
         "A massive transient multiphase liquid slug arrives from gathering lines. Vessel liquid level LT-101 surges to 75% and vapor space compression drives PT-101 to 34.5 barg.",
         "1. Verify PCV-101 valve stem position.\n2. Check demister differential pressure gauge.",
         "Pinch upstream wellhead production chokes by 15-20% and fully open oil/water dump valves LCV-101 / LCV-102 to evacuate liquid into surge vessels per [SOP-V101 Section 4].")
    ]

    for title, hypo, dynamics, checks, actions in scenarios_data:
        h2 = doc.add_heading(title, level=2)
        h2.paragraph_format.space_before = Pt(12)
        h2.paragraph_format.space_after = Pt(4)

        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(f"Diagnostic Root Cause: {hypo}\n")
        r.bold = True
        r.font.color.rgb = RGBColor(10, 37, 64)

        sc_tbl = doc.add_table(rows=1, cols=2)
        sc_widths = [1.8, 4.7]
        sc_headers = ["Phase", "Operational Sequence & Protocol"]
        sc_rows = [
            ["Process Dynamics", dynamics],
            ["Field Verification Checks", checks],
            ["Response Plan & SOP Action", actions]
        ]
        format_table(sc_tbl, sc_widths, sc_headers, sc_rows, header_bg="334155")

    # ==========================================
    # SECTION 5: SHIFT HANDOVER & PDF EXPORT
    # ==========================================
    h1 = doc.add_heading("5. Shift Handover Dossier & PDF Export", level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)

    doc.add_paragraph(
        "A critical safety requirement under OSHA PSM 1910.119 and API RP 75 is the formal transmission of operational integrity data between "
        "outgoing and incoming console leads. Miscommunication during shift rotations is historically one of the leading causes of major industrial accidents."
    )

    doc.add_paragraph(
        "Operation Advisor automates shift handover report compilation through its zero-dependency pure-Python PDF generator "
        "(src/rag/pdf_generator.py), ensuring clean, regulatory-compliant documentation without requiring external system libraries."
    )

    h2 = doc.add_heading("5.1 Standard Report Contents", level=2)
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(4)

    handover_items = [
        ("Section 1: Incident & Facility Header: ", "Unique Incident ID, plant area, operational status, timestamp, and shift lead identities."),
        ("Section 2: Critical Process Telemetry Snapshot: ", "Table detailing PT-101, LT-101, LT-102, FT-101, DPIT-101, VT-101, PCV-101, and ASV-101 with alarm statuses."),
        ("Section 3: Probabilistic Fault Diagnostics: ", "Ranked Bayesian net beliefs showing assessed root cause and confidence percentage."),
        ("Section 4: Field Verification & Response Progress: ", "Itemized list of physical checks and planned remediation actions explicitly marked as COMPLETED or PENDING."),
        ("Section 5: Grounded Technical References: ", "Verbatim SOP and HAZOP standard excerpts governing the shift operational state."),
        ("Section 6: Formal Regulatory Endorsement: ", "Physical signature and date lines for Outgoing Shift Supervisor and Incoming Shift Lead.")
    ]
    for h_title, h_desc in handover_items:
        bp = doc.add_paragraph(style='List Bullet')
        bp.paragraph_format.space_after = Pt(3)
        r_b = bp.add_run(h_title)
        r_b.bold = True
        r_t = bp.add_run(h_desc)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ==========================================
    # SECTION 6: ADMINISTRATION & TROUBLESHOOTING
    # ==========================================
    h1 = doc.add_heading("6. System Administration & Troubleshooting", level=1)
    h1.paragraph_format.space_before = Pt(16)
    h1.paragraph_format.space_after = Pt(6)

    h2 = doc.add_heading("6.1 Launching the Cockpit Server", level=2)
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(4)

    doc.add_paragraph(
        "To start the Operation Advisor Cockpit, launch the Windows PowerShell terminal in the project directory and run:"
    )
    code_p = doc.add_paragraph()
    code_p.paragraph_format.space_before = Pt(4)
    code_p.paragraph_format.space_after = Pt(8)
    r_code = code_p.add_run(".\\venv_win\\Scripts\\python.exe src/ui/app.py --port 8080")
    r_code.font.name = "Consolas"
    r_code.font.size = Pt(9.5)
    r_code.bold = True
    r_code.font.color.rgb = RGBColor(14, 116, 144)

    doc.add_paragraph("Open your web browser and navigate to: http://localhost:8080")

    h2 = doc.add_heading("6.2 Frequently Asked Questions & Troubleshooting", level=2)
    h2.paragraph_format.space_before = Pt(10)
    h2.paragraph_format.space_after = Pt(4)

    faq_tbl = doc.add_table(rows=1, cols=3)
    faq_widths = [1.8, 2.2, 2.5]
    faq_headers = ["Issue / Symptom", "Probable Cause", "Recommended Resolution"]
    faq_data = [
        ["Port 8080 already in use", "A prior instance of python.exe is still bound to port 8080.", "Run Stop-Process -Id (Get-NetTCPConnection -LocalPort 8080).OwningProcess -Force in PowerShell."],
        ["LLM Badge shows 'RAG (Zero-Hallucination)' instead of Ollama", "Local Ollama daemon is offline or OLLAMA_HOST is unreachable.", "Start Ollama desktop service or run 'ollama serve'. The system automatically operates in high-precision offline deterministic RAG mode."],
        ["Scenario numbers reset upon page reload", "Web browser re-queries /api/status which polls the active server state.", "Select the desired scenario from the dropdown to restore its simulated physics snapshot."],
        ["Checklist items are cleared", "Injecting a new scenario intentionally resets working memory to prevent cross-contamination.", "Complete verification checks sequentially for the active incident scenario."]
    ]
    format_table(faq_tbl, faq_widths, faq_headers, faq_data, header_bg="1E293B")

    # Final signoff
    doc.add_paragraph().paragraph_format.space_after = Pt(12)
    p_end = doc.add_paragraph()
    p_end.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_end = p_end.add_run("--- End of Operation Advisor User Guide (Document Ref: MNL-OA-TR1-2026) ---")
    r_end.font.size = Pt(9)
    r_end.font.color.rgb = RGBColor(148, 163, 184)

    # Save to docs and root
    os.makedirs("docs", exist_ok=True)
    doc_path = os.path.join("docs", "Operation_Advisor_User_Guide.docx")
    root_path = "USER_GUIDE.docx"
    doc.save(doc_path)
    doc.save(root_path)
    print(f"User guide successfully generated at:\n  - {doc_path}\n  - {root_path}")

if __name__ == "__main__":
    build_user_guide()

