import io
import os
from pathlib import Path
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from backend.models.inspection import InspectionResult, ComplianceStatus


def generate_compliance_pdf(inspection: InspectionResult) -> bytes:
    """
    Generates a formal Legal Metrology Compliance Inspection Report in PDF format.
    Returns: PDF content as raw bytes.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1e3a8a"),
        alignment=1, # Center
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        alignment=1,
        spaceAfter=15
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6
    )
    
    normal_style = ParagraphStyle(
        'NormalText',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155")
    )
    
    bold_style = ParagraphStyle(
        'BoldText',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor("#0f172a")
    )

    story = []

    # Title & Header
    story.append(Paragraph("MINISTRY OF CONSUMER AFFAIRS, FOOD & PUBLIC DISTRIBUTION", subtitle_style))
    story.append(Paragraph("LEGAL METROLOGY COMPLIANCE REPORT", title_style))
    story.append(Paragraph("Automated Assessment under Legal Metrology (Packaged Commodities) Rules, 2011", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1e3a8a"), spaceAfter=15))

    # Meta Info Table
    status = inspection.compliance.status
    if status == ComplianceStatus.PASS:
        status_color = colors.HexColor("#16a34a") # Green
        status_text = "COMPLIANT (PASS)"
    elif status == ComplianceStatus.FAIL:
        status_color = colors.HexColor("#dc2626") # Red
        status_text = "NON-COMPLIANT (FAIL)"
    else:
        status_color = colors.HexColor("#ea580c") # Orange
        status_text = "UNDER REVIEW"

    meta_data = [
        [Paragraph("<b>Inspection ID:</b>", normal_style), Paragraph(inspection.inspection_id, normal_style),
         Paragraph("<b>Date & Time:</b>", normal_style), Paragraph(inspection.created_at or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"), normal_style)],
        [Paragraph("<b>Product Name:</b>", normal_style), Paragraph(inspection.product.name or "N/A", normal_style),
         Paragraph("<b>Category:</b>", normal_style), Paragraph(inspection.product.category or "FMCG / Packaged", normal_style)],
        [Paragraph("<b>Image Reference:</b>", normal_style), Paragraph(inspection.image_id or "N/A", normal_style),
         Paragraph("<b>Compliance Status:</b>", normal_style), Paragraph(f"<font color='{status_color.hexval()}'><b>{status_text}</b></font>", bold_style)]
    ]
    
    meta_table = Table(meta_data, colWidths=[110, 155, 110, 155])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # Declarations Table (Rule 6)
    story.append(Paragraph("1. Mandatory Declarations Audit (Rule 6)", section_heading))
    
    decl_data = [
        [Paragraph("<b>Mandatory Declaration</b>", bold_style),
         Paragraph("<b>Extracted Value</b>", bold_style),
         Paragraph("<b>Audit Status</b>", bold_style)]
    ]

    field_map = [
        ("Manufacturer / Packer Address", inspection.fields.manufacturer),
        ("Country of Origin", inspection.fields.country_of_origin),
        ("Net Quantity", inspection.fields.net_quantity),
        ("Date of Manufacture / Packing", inspection.fields.manufacture_date),
        ("Maximum Retail Price (MRP)", inspection.fields.mrp),
        ("Consumer Care Details", inspection.fields.consumer_care),
    ]

    for label, val in field_map:
        val_str = str(val) if val else "MISSING"
        is_missing = (not val or val_str.lower() in ["missing", "none", "null"])
        status_label = "<font color='#dc2626'><b>NON-COMPLIANT</b></font>" if is_missing else "<font color='#16a34a'><b>VERIFIED</b></font>"
        decl_data.append([
            Paragraph(label, normal_style),
            Paragraph(val_str, normal_style),
            Paragraph(status_label, normal_style)
        ])

    decl_table = Table(decl_data, colWidths=[180, 230, 120])
    decl_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(decl_table)
    story.append(Spacer(1, 15))

    # Visual & Readability Checks (Rule 7)
    story.append(Paragraph("2. Legibility & Physical Dimension Checks (Rule 7)", section_heading))
    vis = inspection.visual_checks or None
    readability = vis.readability if vis else "N/A"
    font_ht = f"{vis.font_height:.2f} mm" if (vis and vis.font_height) else "Pending Calibration"
    placement = vis.placement if vis else "Standard Display Panel"

    vis_data = [
        [Paragraph("<b>Parameter</b>", bold_style), Paragraph("<b>Observed Result</b>", bold_style), Paragraph("<b>Requirement (Rule 7)</b>", bold_style)],
        [Paragraph("Text Readability", normal_style), Paragraph(readability, normal_style), Paragraph("Prominent & clearly legible", normal_style)],
        [Paragraph("Calibrated Font Height", normal_style), Paragraph(font_ht, normal_style), Paragraph("≥ 1.0mm (scale adjusted)", normal_style)],
        [Paragraph("Principal Display Panel", normal_style), Paragraph(placement, normal_style), Paragraph("Clear group placement", normal_style)],
    ]
    vis_table = Table(vis_data, colWidths=[180, 180, 170])
    vis_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(vis_table)
    story.append(Spacer(1, 15))

    # Violations Summary
    story.append(Paragraph("3. Infringements & Violations Detected", section_heading))
    if inspection.compliance.violations:
        for idx, v in enumerate(inspection.compliance.violations, 1):
            v_para = Paragraph(f"<b>[{idx}]</b> <font color='#dc2626'>{v}</font>", normal_style)
            story.append(v_para)
            story.append(Spacer(1, 3))
    else:
        story.append(Paragraph("<b>No statutory violations detected.</b> The package meets all mandatory Rule 6 declarations.", normal_style))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceAfter=10))

    # Official Footer & Signature Block
    sig_data = [
        [Paragraph("Generated by Synaptix AI Metrology Inspector<br/>Govt. SIH 2026 Innovation Track", normal_style),
         Paragraph("<b>Authorized Inspector Signature:</b> ____________________<br/>Date: ________________________", normal_style)]
    ]
    sig_table = Table(sig_data, colWidths=[300, 230])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(sig_table)

    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
