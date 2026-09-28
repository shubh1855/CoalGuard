# modules/report_gen.py
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import cm
from datetime import datetime
import io


def generate_site_report(site, compliance_items, inspections, violations):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=18, spaceAfter=12)
    story.append(Paragraph("SafeSight Governance Report", title_style))
    story.append(Paragraph(
        f"Site: {site.name} | Generated: {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("1. Compliance Summary", styles["Heading2"]))
    comp_data = [["Regulation", "Category", "Status", "Due Date", "Officer"]]
    for c in compliance_items:
        comp_data.append([
            c.regulation[:40],
            c.category,
            c.status,
            c.due_date.strftime("%d %b %Y") if c.due_date else "N/A",
            c.responsible_officer or "N/A",
        ])
    comp_table = Table(comp_data, colWidths=[6*cm, 3*cm, 3*cm, 3*cm, 3*cm])
    comp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(comp_table)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("2. Inspection Findings", styles["Heading2"]))
    insp_data = [["Date", "Type", "Inspector", "Severity", "Status", "Observations"]]
    for i in inspections:
        insp_data.append([
            i.date.strftime("%d %b %Y"),
            i.inspection_type,
            i.inspector_name,
            i.severity,
            i.status,
            (i.observations or "")[:60],
        ])
    insp_table = Table(insp_data, colWidths=[3*cm, 3*cm, 3*cm, 2.5*cm, 2.5*cm, 4*cm])
    insp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
    ]))
    story.append(insp_table)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("3. CV-Detected Violations", styles["Heading2"]))
    story.append(Paragraph(
        f"Total violations detected by AI safety monitoring: {len(violations)}",
        styles["Normal"]
    ))
    if violations:
        viol_data = [["Worker ID", "Violation Type", "Timestamp"]]
        for v in violations[:20]:
            viol_data.append([v.worker_id, v.violation_type, v.timestamp.strftime("%d %b %Y %H:%M")])
        viol_table = Table(viol_data, colWidths=[5*cm, 6*cm, 7*cm])
        viol_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ]))
        story.append(viol_table)

    doc.build(story)
    buffer.seek(0)
    return buffer
