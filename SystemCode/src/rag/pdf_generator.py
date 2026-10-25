import io
import math
from datetime import datetime
from typing import List, Dict, Any, Optional

class HandoverPDFBuilder:
    """Zero-dependency pure-Python PDF generator for Shift Handover Reports."""

    def __init__(self, page_width=595.28, page_height=841.89):
        self.width = page_width
        self.height = page_height
        self.margin_x = 40.0
        self.margin_top = 45.0
        self.margin_bottom = 50.0
        self.content_width = self.width - (2 * self.margin_x)

        self.pages: List[str] = []
        self.stream: List[str] = []
        self.cursor_y = self.height - self.margin_top
        self.page_num = 1

    def _start_new_page(self):
        if self.stream:
            self.pages.append("".join(self.stream))
            self.stream = []
        self.page_num += 1
        self.cursor_y = self.height - self.margin_top
        self._draw_page_decorations()

    def _ensure_space(self, needed_pt: float):
        if self.cursor_y - needed_pt < self.margin_bottom:
            self._start_new_page()

    def _draw_page_decorations(self):
        # Top banner on subsequent pages
        top_y = self.height - 30.0
        self._rect(self.margin_x, top_y, self.content_width, 1.5, fill=(0.12, 0.25, 0.45))
        self._text("OSHA PSM 1910.119 / API RP 75 SHIFT HANDOVER REPORT", self.margin_x, top_y + 4, font="F2", size=8, color=(0.3, 0.4, 0.5))
        self._text("DECISION SUPPORT COCKPIT", self.margin_x + self.content_width - 120, top_y + 4, font="F1", size=8, color=(0.4, 0.5, 0.6))

        # Bottom footer
        foot_y = 30.0
        self._rect(self.margin_x, foot_y + 12, self.content_width, 0.8, fill=(0.8, 0.85, 0.9))
        self._text("CPF TRAIN 1 — LEVEL-2 READ-ONLY SUPERVISORY ADVISOR", self.margin_x, foot_y, font="F1", size=8, color=(0.45, 0.5, 0.55))
        self._text(f"Page {self.page_num}", self.margin_x + self.content_width - 45, foot_y, font="F2", size=8, color=(0.3, 0.4, 0.5))

    def _escape(self, text: str) -> str:
        res = ""
        for ch in text:
            code = ord(ch)
            if ch in "\\()":
                res += "\\" + ch
            elif ch in "•✓☑":
                res += "-"
            elif ch in "→":
                res += "->"
            elif ch in "↑":
                res += "^"
            elif ch in "↓":
                res += "v"
            elif 32 <= code <= 126 or 160 <= code <= 255:
                res += ch
            else:
                res += " "
        return res

    def _rect(self, x, y, w, h, fill=None, stroke=None, line_width=1.0):
        cmd = ["q"]
        if fill:
            cmd.append(f"{fill[0]:.3f} {fill[1]:.3f} {fill[2]:.3f} rg")
        if stroke:
            cmd.append(f"{line_width:.2f} w")
            cmd.append(f"{stroke[0]:.3f} {stroke[1]:.3f} {stroke[2]:.3f} RG")
        cmd.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill and stroke:
            cmd.append("B")
        elif fill:
            cmd.append("f")
        else:
            cmd.append("s")
        cmd.append("Q\n")
        self.stream.append(" ".join(cmd))

    def _text(self, text: str, x: float, y: float, font="F1", size=10, color=(0.1, 0.1, 0.1)):
        escaped = self._escape(text)
        cmd = [
            "BT",
            f"/{font} {size} Tf",
            f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg",
            f"1 0 0 1 {x:.2f} {y:.2f} Tm",
            f"({escaped}) Tj",
            "ET\n"
        ]
        self.stream.append(" ".join(cmd))

    def add_title_header(self, report_id: str, incident_id: str, now_str: str):
        # Draw main corporate banner
        banner_h = 56.0
        self._rect(self.margin_x, self.cursor_y - banner_h, self.content_width, banner_h, fill=(0.06, 0.16, 0.32))
        self._text("OSHA PSM 1910.119 / API RP 75 SHIFT HANDOVER REPORT", self.margin_x + 14, self.cursor_y - 22, font="F2", size=14, color=(1, 1, 1))
        self._text(f"Central Processing Facility — Train 1 (V-101 Separator & K-101 Compressor)", self.margin_x + 14, self.cursor_y - 38, font="F1", size=10, color=(0.75, 0.88, 1.0))
        self._text(f"Report Ref: {report_id}  |  Incident: {incident_id}  |  Generated: {now_str}", self.margin_x + 14, self.cursor_y - 50, font="F3", size=8, color=(0.58, 0.72, 0.88))
        self.cursor_y -= (banner_h + 16.0)

    def add_metadata_grid(self, meta: Dict[str, str]):
        self._ensure_space(60.0)
        box_h = 48.0
        self._rect(self.margin_x, self.cursor_y - box_h, self.content_width, box_h, fill=(0.95, 0.97, 0.99), stroke=(0.8, 0.86, 0.92))

        col1_x = self.margin_x + 10
        col2_x = self.margin_x + (self.content_width / 2.0) + 10
        y1 = self.cursor_y - 16
        y2 = self.cursor_y - 32
        y3 = self.cursor_y - 44

        self._text("Outgoing Shift Lead:", col1_x, y1, font="F2", size=9, color=(0.15, 0.25, 0.35))
        self._text(meta.get("outgoing", "Lead Console Operator"), col1_x + 110, y1, font="F1", size=9)

        self._text("Incoming Shift Lead:", col2_x, y1, font="F2", size=9, color=(0.15, 0.25, 0.35))
        self._text(meta.get("incoming", "Incoming Shift Lead"), col2_x + 110, y1, font="F1", size=9)

        self._text("Operational Status:", col1_x, y2, font="F2", size=9, color=(0.15, 0.25, 0.35))
        status_txt = meta.get("status", "ACTIVE INCIDENT")
        self._text(status_txt, col1_x + 110, y2, font="F2", size=9, color=(0.8, 0.2, 0.1) if "ACTIVE" in status_txt else (0.1, 0.6, 0.2))

        self._text("Supervisory Mode:", col2_x, y2, font="F2", size=9, color=(0.15, 0.25, 0.35))
        self._text("Level-2 Advisory (Zero DCS Write)", col2_x + 110, y2, font="F1", size=9)

        self.cursor_y -= (box_h + 16.0)

    def add_section_header(self, title: str):
        self._ensure_space(32.0)
        self._rect(self.margin_x, self.cursor_y - 18, self.content_width, 18, fill=(0.92, 0.95, 0.98))
        self._rect(self.margin_x, self.cursor_y - 18, 4, 18, fill=(0.08, 0.35, 0.72))
        self._text(title, self.margin_x + 10, self.cursor_y - 13, font="F2", size=10, color=(0.06, 0.2, 0.4))
        self.cursor_y -= 26.0

    def add_paragraph(self, text: str, font="F1", size=9, color=(0.15, 0.15, 0.15)):
        self._ensure_space(16.0)
        self._text(text, self.margin_x + 4, self.cursor_y, font=font, size=size, color=color)
        self.cursor_y -= (size + 5.0)

    def add_telemetry_table(self, telemetry: Dict[str, float]):
        self._ensure_space(40.0)
        row_h = 16.0
        header_h = 18.0

        # Header
        self._rect(self.margin_x, self.cursor_y - header_h, self.content_width, header_h, fill=(0.12, 0.25, 0.42))
        col_x = [self.margin_x + 10, self.margin_x + 130, self.margin_x + 260, self.margin_x + 390]
        self._text("Instrument Tag", col_x[0], self.cursor_y - 13, font="F2", size=9, color=(1, 1, 1))
        self._text("Current Reading", col_x[1], self.cursor_y - 13, font="F2", size=9, color=(1, 1, 1))
        self._text("Operating Envelope", col_x[2], self.cursor_y - 13, font="F2", size=9, color=(1, 1, 1))
        self._text("Alarm State", col_x[3], self.cursor_y - 13, font="F2", size=9, color=(1, 1, 1))
        self.cursor_y -= header_h

        envelopes = {
            "PT-101": ("28.0 - 34.0 barg", 34.0, 36.5),
            "PT-102": ("27.0 - 33.0 barg", 33.0, 35.5),
            "PT-103": ("70.0 - 80.0 barg", 80.0, 85.0),
            "LT-101": ("40.0 - 65.0 %", 65.0, 75.0),
            "LT-102": ("40.0 - 65.0 %", 65.0, 75.0),
            "LT-103": ("5.0 - 20.0 %", 20.0, 30.0),
            "DPIT-101": ("0.010 - 0.050 bar", 0.050, 0.080),
            "VT-101": ("0.50 - 3.80 mm/s", 3.80, 4.50),
            "FT-101": ("50,000 - 80,000 Sm3/h", 85000, 95000),
            "PCV_101_POS": ("30.0 - 70.0 %", 80.0, 90.0),
            "ASV_101_POS": ("0.0 % (Closed)", 20.0, 50.0),
        }

        row_idx = 0
        for tag, val in sorted(telemetry.items()):
            if tag not in envelopes:
                continue
            self._ensure_space(row_h + 4)
            fill_bg = (0.97, 0.98, 0.99) if row_idx % 2 == 0 else (1.0, 1.0, 1.0)
            self._rect(self.margin_x, self.cursor_y - row_h, self.content_width, row_h, fill=fill_bg, stroke=(0.88, 0.91, 0.94), line_width=0.5)

            unit = "barg" if tag.startswith("PT") else "%" if (tag.startswith("LT") or "POS" in tag) else "bar" if tag.startswith("DP") else "mm/s" if tag.startswith("VT") else "Sm3/h"
            env_str, alarm_lim, trip_lim = envelopes[tag]

            alarm_status = "NORMAL"
            alarm_col = (0.1, 0.55, 0.2)
            if val >= trip_lim:
                alarm_status = "TRIP (HIGH-HIGH)"
                alarm_col = (0.8, 0.1, 0.1)
            elif val >= alarm_lim:
                alarm_status = "HIGH ALARM"
                alarm_col = (0.85, 0.5, 0.0)

            self._text(tag, col_x[0], self.cursor_y - 12, font="F2", size=8.5, color=(0.15, 0.2, 0.3))
            self._text(f"{val:.2f} {unit}", col_x[1], self.cursor_y - 12, font="F3", size=8.5, color=(0.1, 0.1, 0.1))
            self._text(env_str, col_x[2], self.cursor_y - 12, font="F1", size=8.5, color=(0.35, 0.4, 0.45))
            self._text(alarm_status, col_x[3], self.cursor_y - 12, font="F2", size=8.5, color=alarm_col)

            self.cursor_y -= row_h
            row_idx += 1

        self.cursor_y -= 12.0

    def add_checklist_item(self, checked: bool, text: str, meta_str: str = ""):
        self._ensure_space(22.0)
        box_y = self.cursor_y - 12.0

        if checked:
            self._rect(self.margin_x + 6, box_y, 11, 11, fill=(0.1, 0.65, 0.3), stroke=(0.08, 0.5, 0.22))
            self._text("X", self.margin_x + 9, box_y + 2, font="F2", size=8, color=(1, 1, 1))
            self._text(text, self.margin_x + 24, box_y + 2, font="F2", size=9, color=(0.1, 0.35, 0.2))
        else:
            self._rect(self.margin_x + 6, box_y, 11, 11, fill=(1, 1, 1), stroke=(0.7, 0.75, 0.8))
            self._text(text, self.margin_x + 24, box_y + 2, font="F1", size=9, color=(0.2, 0.25, 0.3))

        if meta_str:
            self.cursor_y -= 14.0
            self._text(meta_str, self.margin_x + 24, self.cursor_y, font="F1", size=8, color=(0.45, 0.5, 0.55))
            self.cursor_y -= 8.0
        else:
            self.cursor_y -= 18.0

    def add_signoff_section(self, now_str: str, outgoing: str, incoming: str):
        self._ensure_space(85.0)
        box_w = (self.content_width / 2.0) - 8.0
        box_h = 75.0

        # Outgoing Box
        x1 = self.margin_x
        y = self.cursor_y - box_h
        self._rect(x1, y, box_w, box_h, fill=(0.98, 0.99, 1.0), stroke=(0.75, 0.82, 0.9))
        self._text("OUTGOING SHIFT OPERATOR", x1 + 10, y + box_h - 14, font="F2", size=8.5, color=(0.1, 0.25, 0.45))
        self._text(f"Name / Role: {outgoing}", x1 + 10, y + box_h - 28, font="F1", size=8.5)
        self._text("Signature: __________________________", x1 + 10, y + box_h - 48, font="F1", size=8.5)
        self._text(f"Timestamp: {now_str}", x1 + 10, y + box_h - 62, font="F3", size=8, color=(0.4, 0.45, 0.5))

        # Incoming Box
        x2 = self.margin_x + box_w + 16.0
        self._rect(x2, y, box_w, box_h, fill=(0.98, 0.99, 1.0), stroke=(0.75, 0.82, 0.9))
        self._text("INCOMING SHIFT SUPERVISOR", x2 + 10, y + box_h - 14, font="F2", size=8.5, color=(0.1, 0.25, 0.45))
        self._text(f"Name / Role: {incoming}", x2 + 10, y + box_h - 28, font="F1", size=8.5)
        self._text("Signature: __________________________", x2 + 10, y + box_h - 48, font="F1", size=8.5)
        self._text("Timestamp: _____-_____-_____  ____:____", x2 + 10, y + box_h - 62, font="F3", size=8, color=(0.4, 0.45, 0.5))

        self.cursor_y -= (box_h + 16.0)

    def build_pdf_bytes(self) -> bytes:
        if self.stream:
            self.pages.append("".join(self.stream))
            self.stream = []

        if not self.pages:
            self._draw_page_decorations()
            self.pages.append("".join(self.stream))

        num_pages = len(self.pages)
        objects: List[Any] = []

        catalog_id = 1
        pages_id = 2
        font_regular_id = 3
        font_bold_id = 4
        font_mono_id = 5

        first_page_obj_id = 6
        page_obj_ids = [first_page_obj_id + 2 * i for i in range(num_pages)]

        # 1: Catalog
        objects.append(f"{catalog_id} 0 obj\n<< /Type /Catalog /Pages {pages_id} 0 R >>\nendobj\n")

        # 2: Pages tree
        kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
        objects.append(f"{pages_id} 0 obj\n<< /Type /Pages /Kids [ {kids_str} ] /Count {num_pages} >>\nendobj\n")

        # 3: Helvetica
        objects.append(f"{font_regular_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n")

        # 4: Helvetica-Bold
        objects.append(f"{font_bold_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n")

        # 5: Courier
        objects.append(f"{font_mono_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>\nendobj\n")

        # Page objects and Content streams
        for i, page_content in enumerate(self.pages):
            p_id = page_obj_ids[i]
            c_id = p_id + 1
            content_bytes = page_content.encode("latin-1", errors="replace")
            page_dict = (
                f"{p_id} 0 obj\n"
                f"<< /Type /Page /Parent {pages_id} 0 R "
                f"/MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R /F3 {font_mono_id} 0 R >> >> "
                f"/Contents {c_id} 0 R >>\nendobj\n"
            )
            objects.append(page_dict)

            stream_dict = (
                f"{c_id} 0 obj\n"
                f"<< /Length {len(content_bytes)} >>\n"
                f"stream\n"
            )
            objects.append(stream_dict)
            objects.append(content_bytes)
            objects.append("\nendstream\nendobj\n")

        header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        out = io.BytesIO()
        out.write(header)

        total_objs = 5 + 2 * num_pages
        offsets = [0] * (total_objs + 1)
        obj_counter = 1

        for item in objects:
            if isinstance(item, str):
                if f"{obj_counter} 0 obj" in item:
                    offsets[obj_counter] = out.tell()
                    obj_counter += 1
                b = item.encode("latin-1", errors="replace")
            else:
                b = item
            out.write(b)

        xref_offset = out.tell()
        out.write(f"xref\n0 {total_objs + 1}\n".encode("latin-1"))
        out.write(b"0000000000 65535 f \r\n")
        for o in range(1, total_objs + 1):
            out.write(f"{offsets[o]:010d} 00000 n \r\n".encode("latin-1"))

        trailer = (
            f"trailer\n"
            f"<< /Size {total_objs + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n"
            f"%%EOF\n"
        )
        out.write(trailer.encode("latin-1"))
        return out.getvalue()

