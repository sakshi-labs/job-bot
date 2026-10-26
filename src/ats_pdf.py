"""
Pure-Python ATS-Compliant PDF Generator.
Zero external dependencies. Generates valid PDF 1.4 documents optimized for
Applicant Tracking Systems (Greenhouse, Lever, Workday, Taleo).
"""
import os
import re
from typing import List, Tuple
from .models import TailoredResume

def escape_pdf_text(text: str) -> str:
    """Escape special characters for PDF text streams."""
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    # Replace unicode dashes / bullets with safe ASCII / standard equivalents
    text = text.replace("—", "-").replace("–", "-").replace("“", "\"").replace("”", "\"")
    text = text.replace("’", "'").replace("‘", "'").replace("•", "*")
    return text

def wrap_text(text: str, max_chars: int) -> List[str]:
    """Simple greedy word-wrapping."""
    words = text.split()
    lines = []
    curr = []
    curr_len = 0
    for w in words:
        if curr_len + len(w) + (1 if curr else 0) <= max_chars:
            curr.append(w)
            curr_len += len(w) + (1 if curr else 0)
        else:
            if curr:
                lines.append(" ".join(curr))
            curr = [w]
            curr_len = len(w)
    if curr:
        lines.append(" ".join(curr))
    return lines

class ATSPdfGenerator:
    def __init__(self, page_width: float = 612.0, page_height: float = 792.0):
        # Letter size (612 x 792 points)
        self.width = page_width
        self.height = page_height
        self.margin_x = 40.0
        self.margin_top = 40.0
        self.margin_bottom = 40.0
        self.content_width = self.width - (2 * self.margin_x)

    def generate(self, resume: TailoredResume, output_path: str) -> str:
        """Generates the PDF file and writes it to output_path."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        pages_content: List[List[str]] = []
        current_page_ops: List[str] = []
        y = self.height - self.margin_top

        def check_page_break(needed_space: float):
            nonlocal y, current_page_ops, pages_content
            if y - needed_space < self.margin_bottom:
                pages_content.append(current_page_ops)
                current_page_ops = []
                y = self.height - self.margin_top

        def draw_text(text: str, x: float, y_pos: float, font: str = "/F1", size: float = 10.0, r: float = 0.0, g: float = 0.0, b: float = 0.0):
            safe = escape_pdf_text(text)
            current_page_ops.append(
                f"BT {r:.2f} {g:.2f} {b:.2f} rg {font} {size} Tf 1 0 0 1 {x:.2f} {y_pos:.2f} Tm ({safe}) Tj ET"
            )

        def draw_line(x1: float, y1: float, x2: float, y2: float, line_width: float = 0.75):
            current_page_ops.append(
                f"{line_width} w 0.2 0.2 0.2 RG {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S"
            )

        # 1. Candidate Name (Header)
        draw_text(resume.full_name, self.margin_x, y, font="/F2", size=18.0, r=0.1, g=0.1, b=0.15)
        y -= 16.0

        # 2. Contact details line
        contacts = [resume.email, resume.phone, resume.location]
        if resume.linkedin:
            contacts.append(resume.linkedin.replace("https://", ""))
        if resume.github:
            contacts.append(resume.github.replace("https://", ""))
        contact_str = " | ".join(contacts)
        draw_text(contact_str, self.margin_x, y, font="/F1", size=8.5, r=0.3, g=0.3, b=0.3)
        y -= 14.0

        # Section Header Helper
        def add_section_header(title: str):
            nonlocal y
            check_page_break(28.0)
            y -= 6.0
            draw_text(title.upper(), self.margin_x, y, font="/F2", size=10.5, r=0.05, g=0.25, b=0.55)
            y -= 4.0
            draw_line(self.margin_x, y, self.width - self.margin_x, y, line_width=0.6)
            y -= 10.0

        # 3. Professional Summary
        add_section_header("Professional Summary")
        summary_lines = wrap_text(resume.tailored_summary, 98)
        for sline in summary_lines:
            check_page_break(12.0)
            draw_text(sline, self.margin_x, y, font="/F1", size=9.0)
            y -= 12.0
        y -= 4.0

        # 4. Technical Skills
        add_section_header("Technical Skills")
        for category, skills in resume.categorized_skills.items():
            if not skills:
                continue
            check_page_break(13.0)
            cat_label = f"{category}: "
            skills_str = ", ".join(skills)
            full_line = cat_label + skills_str
            wrapped = wrap_text(full_line, 95)
            
            for idx, wline in enumerate(wrapped):
                check_page_break(12.0)
                if idx == 0:
                    draw_text(cat_label, self.margin_x, y, font="/F2", size=9.0)
                    # Offset for category name approximation
                    offset_x = self.margin_x + (len(cat_label) * 4.6)
                    rest_text = wline[len(cat_label):]
                    draw_text(rest_text, offset_x, y, font="/F1", size=9.0)
                else:
                    draw_text(wline, self.margin_x + 12.0, y, font="/F1", size=9.0)
                y -= 12.0
        y -= 4.0

        # 5. Work Experience
        add_section_header("Professional Experience")
        for exp in resume.experiences:
            check_page_break(45.0)
            # Role & Dates
            role_header = f"{exp.role} — {exp.company}"
            date_loc = f"{exp.start_date} – {exp.end_date} | {exp.location}"
            draw_text(role_header, self.margin_x, y, font="/F2", size=9.5)
            
            # Align dates to the right roughly
            date_x = self.width - self.margin_x - (len(date_loc) * 4.8)
            draw_text(date_loc, max(date_x, 360.0), y, font="/F3", size=8.5, r=0.3, g=0.3, b=0.3)
            y -= 13.0

            # Bullets
            for bullet in exp.bullets:
                bullet_lines = wrap_text(bullet, 92)
                for b_idx, bline in enumerate(bullet_lines):
                    check_page_break(12.0)
                    if b_idx == 0:
                        draw_text("•", self.margin_x + 6.0, y, font="/F2", size=9.0)
                        draw_text(bline, self.margin_x + 18.0, y, font="/F1", size=8.8)
                    else:
                        draw_text(bline, self.margin_x + 18.0, y, font="/F1", size=8.8)
                    y -= 11.5
            y -= 4.0

        # 6. Projects (if present)
        if resume.projects:
            add_section_header("Key Projects")
            for proj in resume.projects:
                check_page_break(28.0)
                p_name = proj.get("name", "")
                p_tech = ", ".join(proj.get("technologies", []))
                header = f"{p_name} ({p_tech})" if p_tech else p_name
                draw_text(header, self.margin_x, y, font="/F2", size=9.0)
                y -= 12.0
                
                desc = proj.get("description", "")
                d_lines = wrap_text(desc, 92)
                for dline in d_lines:
                    check_page_break(11.0)
                    draw_text(f"• {dline}", self.margin_x + 10.0, y, font="/F1", size=8.5)
                    y -= 11.0
                y -= 3.0

        # 7. Education
        if resume.education:
            add_section_header("Education")
            for edu in resume.education:
                check_page_break(25.0)
                degree_inst = f"{edu.get('degree', '')} — {edu.get('institution', '')}"
                grad = edu.get("graduation_date", "")
                draw_text(degree_inst, self.margin_x, y, font="/F2", size=9.0)
                if grad:
                    draw_text(grad, self.width - self.margin_x - 70.0, y, font="/F1", size=8.5, r=0.3, g=0.3, b=0.3)
                y -= 12.0
                if edu.get("highlights"):
                    draw_text(f"Details: {edu.get('highlights')}", self.margin_x + 10.0, y, font="/F3", size=8.2, r=0.2, g=0.2, b=0.2)
                    y -= 11.0

        # 8. Certifications
        if resume.certifications:
            add_section_header("Certifications")
            check_page_break(14.0)
            cert_str = " • ".join(resume.certifications)
            draw_text(cert_str, self.margin_x, y, font="/F1", size=8.8)
            y -= 12.0

        if current_page_ops:
            pages_content.append(current_page_ops)

        # Build raw PDF document structure
        self._write_pdf_file(pages_content, output_path)
        return output_path

    def _write_pdf_file(self, pages_content: List[List[str]], output_path: str):
        objects = []
        def add_object(content: str) -> int:
            objects.append(content)
            return len(objects)

        # 1: Catalog
        catalog_id = add_object("<< /Type /Catalog /Pages 2 0 R >>")
        
        # 2: Pages (placeholder, updated later)
        pages_id = add_object("")
        
        # 3, 4, 5: Fonts (Helvetica, Helvetica-Bold, Helvetica-Oblique)
        f1_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
        f2_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
        f3_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>")

        page_ids = []
        for p_ops in pages_content:
            stream_content = "\n".join(p_ops)
            stream_len = len(stream_content.encode("latin-1", errors="replace"))
            content_id = add_object(
                f"<< /Length {stream_len} >>\nstream\n{stream_content}\nendstream"
            )
            page_obj = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                f"/Resources << /Font << /F1 {f1_id} 0 R /F2 {f2_id} 0 R /F3 {f3_id} 0 R >> >> "
                f"/Contents {content_id} 0 R >>"
            )
            page_id = add_object(page_obj)
            page_ids.append(f"{page_id} 0 R")

        # Update Pages object (id 2)
        kids_str = " ".join(page_ids)
        objects[1] = f"<< /Type /Pages /Kids [{kids_str}] /Count {len(page_ids)} >>"

        # Assemble PDF file with xref table
        output_bytes = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for i, obj in enumerate(objects):
            offsets.append(len(output_bytes))
            obj_str = f"{i+1} 0 obj\n{obj}\nendobj\n"
            output_bytes.extend(obj_str.encode("latin-1", errors="replace"))

        xref_start = len(output_bytes)
        output_bytes.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1"))
        for off in offsets:
            output_bytes.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
            
        trailer = (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        )
        output_bytes.extend(trailer.encode("latin-1"))

        with open(output_path, "wb") as f:
            f.write(output_bytes)
