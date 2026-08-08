from __future__ import annotations

from io import BytesIO
from typing import Mapping
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


NAVY = colors.HexColor("#17365D")
TEAL = colors.HexColor("#0F766E")
LIGHT_BLUE = colors.HexColor("#EAF2F8")
LIGHT_TEAL = colors.HexColor("#E8F5F2")
LIGHT_GRAY = colors.HexColor("#F3F4F6")
TEXT = colors.HexColor("#1F2937")


def _number(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _money(value: object) -> str:
    return f"INR {_number(value):,.0f}"


def _percent(value: object) -> str:
    return f"{_number(value):,.1f}%"


def _text(value: object, fallback: str = "Not available") -> str:
    rendered = str(value).strip() if value is not None else ""
    return escape(rendered or fallback)


def build_procurement_report(
    explanation: Mapping[str, object],
    part: Mapping[str, object],
) -> bytes:
    """Build a detailed, part-specific procurement decision report as PDF bytes."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title=f"Procurement Decision Report - {part.get('part_id', '')}",
        author="Sheet Metal Cost Digital Twin",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=NAVY,
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyReport",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=TEXT,
            spaceAfter=7,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Callout",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=TEAL,
            backColor=LIGHT_TEAL,
            borderPadding=8,
            spaceBefore=4,
            spaceAfter=10,
        )
    )

    body = styles["BodyReport"]
    section = styles["Section"]
    story = [
        Paragraph("Detailed Procurement Decision Report", styles["ReportTitle"]),
        Paragraph(
            f"Explainable AI cost intelligence for part <b>{_text(part.get('part_id'))}</b>",
            styles["BodyReport"],
        ),
        Spacer(1, 4),
    ]

    summary_data = [
        ["Part", _text(part.get("part_name")), "Vendor", _text(explanation.get("vendor"))],
        ["Category", _text(part.get("category")), "Region", _text(part.get("supplier_region"))],
        ["ERP price", _money(explanation.get("erp_price")), "ML fair price", _money(explanation.get("fair_price"))],
        ["Should-cost", _money(explanation.get("should_cost")), "Price gap", _percent(explanation.get("price_gap_pct"))],
        ["Annual volume", f"{_number(part.get('annual_volume')):,.0f}", "Qualified savings", _money(explanation.get("savings_opportunity"))],
        ["Prediction confidence", _text(part.get("prediction_confidence")), "Label quality", _text(part.get("label_quality_status"))],
    ]
    summary_table = Table(summary_data, colWidths=[31 * mm, 56 * mm, 35 * mm, 54 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), LIGHT_BLUE),
                ("BACKGROUND", (2, 0), (2, -1), LIGHT_BLUE),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 9)])

    story.extend(
        [
            Paragraph("Executive decision summary", section),
            Paragraph(_text(explanation.get("xai_summary")), styles["Callout"]),
            Paragraph(
                "This opportunity is commercially actionable because the current ERP unit price is above the "
                "modelled fair-price reference. Qualified savings are calculated only on the positive unit-price "
                "gap multiplied by annual volume; negative gaps are never counted as savings.",
                body,
            ),
            Paragraph("1. ERP price explanation", section),
            Paragraph(_text(explanation.get("erp_price_explanation")), body),
            Paragraph(
                f"The current ERP price is <b>{_money(explanation.get('erp_price'))}</b> per part versus an ML fair "
                f"price of <b>{_money(explanation.get('fair_price'))}</b>. The resulting gap is "
                f"<b>{_percent(explanation.get('price_gap_pct'))}</b>. The engineering should-cost of "
                f"<b>{_money(explanation.get('should_cost'))}</b> provides an independent cost anchor rather than "
                "treating historical ERP price as unquestioned market truth.",
                body,
            ),
        ]
    )

    cost_rows = [["Cost element", "Estimated amount"]]
    for label, column in [
        ("Material", "material_cost"),
        ("Energy", "energy_cost"),
        ("Labour", "labour_cost"),
        ("Bends and holes", "process_complexity_cost"),
        ("Surface finish", "surface_finish_cost"),
        ("Overhead", "overhead"),
        ("Template adjustments", "manual_template_adjustment_cost"),
        ("Supplier margin", "supplier_margin"),
    ]:
        cost_rows.append([label, _money(part.get(column))])
    cost_table = Table(cost_rows, colWidths=[95 * mm, 55 * mm], repeatRows=1)
    cost_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), LIGHT_GRAY),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([cost_table, PageBreak()])

    story.extend(
        [
            Paragraph("2. Negotiation recommendation", section),
            Paragraph(_text(explanation.get("negotiation_recommendation")), styles["Callout"]),
            Paragraph("Recommended negotiation sequence", section),
            Paragraph("<b>1. Validate scope.</b> Confirm drawing revision, material grade, thickness, finish, annual volume, tooling treatment, freight, rejection allowance, and payment terms before comparing quotations.", body),
            Paragraph("<b>2. Lead with evidence.</b> Present the ERP-to-fair-price gap, engineering should-cost breakdown, volume commitment, and the dominant cost driver. Ask the supplier to reconcile each material difference rather than offering an unsupported blanket discount.", body),
            Paragraph("<b>3. Set the commercial target.</b> Use ML fair price as the negotiation reference and should-cost as the engineering anchor. Separate recurring piece price from one-time tooling, expedited freight, and non-recurring charges.", body),
            Paragraph("<b>4. Trade, do not concede.</b> Exchange any volume commitment, forecast visibility, payment-term improvement, or contract duration only for a measurable unit-price reduction and documented cost transparency.", body),
            Paragraph("<b>5. Close with governance.</b> Record the agreed price basis, commodity/FX adjustment rule, validity period, quality assumptions, and a reopener threshold to avoid silent price escalation.", body),
            Paragraph("Evidence to take into the supplier meeting", section),
            Paragraph(
                f"Part drawing and revision; annual demand of {_number(part.get('annual_volume')):,.0f} units; ERP price history; "
                f"ML fair price of {_money(explanation.get('fair_price'))}; should-cost of {_money(explanation.get('should_cost'))}; "
                f"top increase feature: <b>{_text(explanation.get('top_price_increase_feature'))}</b>; supplier quality and delivery evidence; and comparable regional quotations.",
                body,
            ),
            Paragraph("3. BATNA and escalation path", section),
            Paragraph(_text(explanation.get("batna")), styles["Callout"]),
            Paragraph(
                "If the incumbent cannot substantiate or close the gap, issue a controlled re-quote to qualified alternatives "
                "using the same drawing revision and commercial assumptions. Validate capacity, tooling ownership, quality "
                "approval, logistics, lead time, and transition cost before treating an alternate quote as executable.",
                body,
            ),
            Paragraph(
                "Escalate when the supplier response remains materially above the fair-price reference, when cost breakdown "
                "evidence is withheld, or when commodity/FX movements do not explain the requested price. Do not switch on "
                "unit price alone if qualification or supply-continuity costs erase the apparent benefit.",
                body,
            ),
            Paragraph("4. Explainable-AI interpretation", section),
            Paragraph(_text(explanation.get("xai_summary")), body),
            Paragraph(
                f"The strongest part-level ML signal is <b>{_text(part.get('shap_top_feature'))}</b>. "
                f"Model explanation: {_text(part.get('shap_procurement_explanation'))}. The prediction-confidence rating is "
                f"<b>{_text(part.get('prediction_confidence'))}</b>; use it together with drawing completeness, similar ERP "
                "history, market-data freshness, and commercial validation.",
                body,
            ),
            Paragraph(
                "The ML fair price is decision support, not an automatic award recommendation. It should be challenged against "
                "drawing revision, supplier-specific process route, actual tooling status, minimum-order quantity, logistics, "
                "quality performance, and current commodity and FX conditions.",
                body,
            ),
            Paragraph("Decision checklist", section),
            Paragraph("&#8226; Confirm the drawing and commercial scope match the ERP line item.<br/>&#8226; Validate one-time charges and remove them from recurring piece price.<br/>&#8226; Ask the supplier to explain the dominant cost driver with evidence.<br/>&#8226; Negotiate toward the ML fair-price reference with a documented give/get plan.<br/>&#8226; Validate BATNA capacity, quality, lead time, and transition cost.<br/>&#8226; Record the final decision, assumptions, owner, and review date.", body),
        ]
    )

    def add_page_number(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(17 * mm, 10 * mm, "Explainable AI Procurement Intelligence")
        canvas.drawRightString(193 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return output.getvalue()
