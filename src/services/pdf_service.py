from __future__ import annotations

import io
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)


def sanitize_pdf_text(text: str) -> str:
    """
    Sanitizes non-ASCII/unicode characters that cause missing glyph black boxes (■)
    in ReportLab standard fonts (Helvetica, Times).
    """
    if not text:
        return ""
    
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2014": " - ",
        "\u2013": "-",
        "\u2010": "-",
        "\u2011": "-",  # non-breaking hyphen (caused "above■mentioned", "cyber■malware")
        "\u25a0": "-",
        "\u2022": "&bull;",
        "\u2026": "...",
        "\u00a0": " ",  # non-breaking space
        "\u00ad": "",   # soft hyphen
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    
    return text


def format_inline_markdown(text: str) -> str:
    """
    Converts inline markdown syntax into ReportLab-compatible HTML tags (<b>, <i>).
    Safely escapes &, <, > and protects underscore fill-in-the-blank placeholders.
    """
    if not text:
        return ""
    
    # 1. Protect blank underline placeholders (e.g. _______________________)
    blank_lines = []
    def save_blank(m):
        idx = len(blank_lines)
        blank_lines.append(m.group(0))
        return f"___BLANK_PLACEHOLDER_{idx}___"
    
    text = re.sub(r'_{2,}', save_blank, text)

    # 2. Escape XML special characters
    text = text.replace("&bull;", "___ENTITY_BULL___")
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace("___ENTITY_BULL___", "&bull;")

    # 3. Bold: **text** (non-greedy)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # 4. Italic: *text* (when not surrounded by other stars)
    text = re.sub(r'(?<![a-zA-Z0-9*])\*(?!\s)(.+?)(?<!\s)\*(?![a-zA-Z0-9*])', r'<i>\1</i>', text)

    # 5. Inline code: `text` -> bold
    text = re.sub(r'`(.+?)`', r'<b>\1</b>', text)

    # 6. Restore blank underline placeholders
    for idx, blank in enumerate(blank_lines):
        text = text.replace(f"___BLANK_PLACEHOLDER_{idx}___", blank)

    return text


def parse_markdown_to_flowables(text: str, styles: dict) -> list:
    """
    Converts multi-line markdown string into a list of styled ReportLab Flowables.
    Removes raw hashes (#), stars (*), and converts them into headings, bold tags,
    bullet points, and dividing rules.
    """
    flowables = []
    text = sanitize_pdf_text(text)
    lines = text.split("\n")

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            flowables.append(Spacer(1, 3))
            continue

        # 1. Horizontal dividing rules: ---, ***, ___
        if re.match(r'^(?:-{3,}|\*{3,}|_{3,})$', line):
            flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E0"), spaceAfter=5, spaceBefore=4))
            continue

        # 2. Markdown Headings: #, ##, ###, ####
        heading_match = re.match(r'^(#{1,6})\s*(.*)$', line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_content = heading_match.group(2).strip()
            heading_content = re.sub(r'\s*#+$', '', heading_content)
            formatted_content = format_inline_markdown(heading_content)

            if level == 1:
                flowables.append(Paragraph(formatted_content, styles["h1"]))
            elif level == 2:
                flowables.append(Paragraph(formatted_content, styles["h2"]))
            else:
                flowables.append(Paragraph(formatted_content, styles["h3"]))
            continue

        # 3. Bullet points: - item, * item, + item
        bullet_match = re.match(r'^[-*+]\s+(.*)$', line)
        if bullet_match:
            bullet_content = bullet_match.group(1).strip()
            formatted_content = format_inline_markdown(bullet_content)
            flowables.append(Paragraph(f"&bull;&nbsp;&nbsp;{formatted_content}", styles["bullet"]))
            continue

        # 4. Numbered list: 1. item, 2. item, etc.
        numbered_match = re.match(r'^(\d+)\.\s+(.*)$', line)
        if numbered_match:
            num = numbered_match.group(1)
            num_content = numbered_match.group(2).strip()
            formatted_content = format_inline_markdown(num_content)
            flowables.append(Paragraph(f"<b>{num}.</b>&nbsp;&nbsp;{formatted_content}", styles["numbered"]))
            continue

        # 5. Regular text / key-value lines
        formatted_line = format_inline_markdown(line)
        flowables.append(Paragraph(formatted_line, styles["body"]))

    return flowables


def generate_fir_pdf(
    session_id: str,
    form_data: dict,
    fir_draft: str,
    created_at: datetime | None = None,
) -> bytes:
    """
    Generates a formal, printable PDF document for an FIR / Cyber Complaint draft.
    Parses and formats markdown elements cleanly with zero raw symbols or unicode artifacts.
    Returns bytes buffer of the generated PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        name="DocTitle",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        alignment=1,  # Center
        textColor=colors.HexColor("#1A365D"),
    )

    subtitle_style = ParagraphStyle(
        name="DocSubtitle",
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        alignment=1,
        textColor=colors.HexColor("#4A5568"),
    )

    section_heading_style = ParagraphStyle(
        name="SectionHeading",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1A365D"),
        spaceBefore=10,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        name="Body",
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#2D3748"),
    )

    body_bold = ParagraphStyle(
        name="BodyBold",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1A202C"),
    )

    # Narrative Styles
    h1_style = ParagraphStyle(
        name="NarrativeH1",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1A365D"),
        spaceBefore=8,
        spaceAfter=4,
    )

    h2_style = ParagraphStyle(
        name="NarrativeH2",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1A365D"),
        spaceBefore=7,
        spaceAfter=3,
    )

    h3_style = ParagraphStyle(
        name="NarrativeH3",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=6,
        spaceAfter=2,
    )

    draft_text_style = ParagraphStyle(
        name="DraftText",
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=3,
    )

    bullet_style = ParagraphStyle(
        name="NarrativeBullet",
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#2D3748"),
        leftIndent=16,
        firstLineIndent=-10,
        spaceAfter=2,
    )

    numbered_style = ParagraphStyle(
        name="NarrativeNumbered",
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#2D3748"),
        leftIndent=12,
        firstLineIndent=-8,
        spaceBefore=3,
        spaceAfter=2,
    )

    flowable_styles = {
        "h1": h1_style,
        "h2": h2_style,
        "h3": h3_style,
        "body": draft_text_style,
        "bullet": bullet_style,
        "numbered": numbered_style,
    }

    story = []

    # 1. Header
    story.append(Paragraph("CYBERSAHAY - CYBERCRIME INCIDENT &amp; FIR REPORT", title_style))
    story.append(Paragraph("National Cybercrime Assistance System | Under IT Act 2000 &amp; BNS", subtitle_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1A365D"), spaceAfter=8))

    # 2. Metadata Banner
    report_date = (created_at or datetime.now()).strftime("%d %B %Y, %I:%M %p")
    incident_cat = sanitize_pdf_text(form_data.get('incident_type', 'General')).upper()
    meta_data = [
        [
            Paragraph(f"<b>Report Reference:</b> CS-{session_id[:10].upper()}", body_style),
            Paragraph(f"<b>Generated On:</b> {report_date}", body_style),
        ],
        [
            Paragraph(f"<b>Incident Category:</b> {incident_cat}", body_style),
            Paragraph("<b>Status:</b> READY FOR SUBMISSION", body_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[260, 260])
    meta_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
            ("PADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ])
    )
    story.append(meta_table)
    story.append(Spacer(1, 8))

    # 3. Complainant & Incident Particulars Table
    story.append(Paragraph("1. PARTICULARS OF COMPLAINANT &amp; INCIDENT", section_heading_style))

    particulars = [
        [
            Paragraph("<b>Complainant Name:</b>", body_bold),
            Paragraph(sanitize_pdf_text(form_data.get("complainant_name")) or "Not Specified", body_style),
            Paragraph("<b>Contact Number:</b>", body_bold),
            Paragraph(sanitize_pdf_text(form_data.get("phone_number")) or "Not Specified", body_style),
        ],
        [
            Paragraph("<b>Email Address:</b>", body_bold),
            Paragraph(sanitize_pdf_text(form_data.get("email")) or "Not Specified", body_style),
            Paragraph("<b>Incident Location:</b>", body_bold),
            Paragraph(sanitize_pdf_text(form_data.get("incident_location")) or "Not Specified", body_style),
        ],
        [
            Paragraph("<b>Incident Date:</b>", body_bold),
            Paragraph(sanitize_pdf_text(form_data.get("incident_date")) or "Not Specified", body_style),
            Paragraph("<b>Incident Time:</b>", body_bold),
            Paragraph(sanitize_pdf_text(form_data.get("incident_time")) or "Not Specified", body_style),
        ],
    ]

    # Add conditional rows if relevant
    if form_data.get("upi_id") or form_data.get("bank_account"):
        particulars.append([
            Paragraph("<b>UPI ID Involved:</b>", body_bold),
            Paragraph(sanitize_pdf_text(form_data.get("upi_id")) or "N/A", body_style),
            Paragraph("<b>Bank Account:</b>", body_bold),
            Paragraph(sanitize_pdf_text(form_data.get("bank_account")) or "N/A", body_style),
        ])

    if form_data.get("imei_number") or form_data.get("vehicle_number"):
        particulars.append([
            Paragraph("<b>IMEI Number:</b>", body_bold),
            Paragraph(sanitize_pdf_text(form_data.get("imei_number")) or "N/A", body_style),
            Paragraph("<b>Vehicle Number:</b>", body_bold),
            Paragraph(sanitize_pdf_text(form_data.get("vehicle_number")) or "N/A", body_style),
        ])

    particulars_table = Table(particulars, colWidths=[120, 140, 120, 140])
    particulars_table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 4.5),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F7FAFC")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#F7FAFC")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ])
    )
    story.append(particulars_table)
    story.append(Spacer(1, 8))

    # 4. Formal FIR Draft Narrative (Cleaned & Parsed from Markdown)
    story.append(Paragraph("2. FORMAL COMPLAINT &amp; FIR DRAFT NARRATIVE", section_heading_style))

    raw_narrative = fir_draft or form_data.get("description", "No narrative generated.")
    parsed_flowables = parse_markdown_to_flowables(raw_narrative, flowable_styles)
    story.extend(parsed_flowables)

    story.append(Spacer(1, 10))

    # 5. Legal Verification & Signature Block
    story.append(Paragraph("3. VERIFICATION &amp; DECLARATION", section_heading_style))
    declaration_text = (
        "I hereby solemnly declare and verify that the facts and circumstances stated in this complaint "
        "are true and correct to the best of my knowledge, belief, and records. No material facts have been concealed. "
        "I request the appropriate cybercrime authority / police station to take cognizance and initiate necessary investigation."
    )
    story.append(Paragraph(declaration_text, body_style))
    story.append(Spacer(1, 18))

    # Signature Table
    sig_data = [
        [
            Paragraph("<b>Date:</b> " + (created_at or datetime.now()).strftime("%d/%m/%Y"), body_style),
            Paragraph("<b>Complainant Signature:</b> ___________________", body_style),
        ],
        [
            Paragraph("<b>Place:</b> " + (sanitize_pdf_text(form_data.get("incident_location")) or "_________________"), body_style),
            Paragraph("<b>Name:</b> " + (sanitize_pdf_text(form_data.get("complainant_name")) or "___________________"), body_style),
        ],
    ]
    sig_table = Table(sig_data, colWidths=[260, 260])
    sig_table.setStyle(TableStyle([
        ("PADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(sig_table)

    # 6. Emergency Footnote
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E0"), spaceAfter=5))
    story.append(Paragraph(
        "<b>Important Notice:</b> In case of financial fraud, immediately dial <b>1930</b> (National Cyber Fraud Helpline) "
        "and report at <b>cybercrime.gov.in</b> within the golden hour to facilitate freezing of fraudulent funds.",
        subtitle_style,
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
