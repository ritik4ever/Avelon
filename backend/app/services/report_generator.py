"""Report generator for Avelon reliability evaluations."""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Tuple

import structlog
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = structlog.get_logger()


def _serialize_vuln(v: dict) -> dict:
    return {
        "vuln_type": v.get("vuln_type", "unknown"),
        "function_name": v.get("function_name"),
        "line_number": v.get("line_number"),
        "severity": v.get("severity", "medium"),
        "description": v.get("description", ""),
        "confidence": v.get("confidence"),
    }


def _build_failure_analysis(comparison: dict) -> dict:
    false_positives = comparison.get("false_positives", [])
    false_negatives = comparison.get("false_negatives", [])
    true_positives = comparison.get("true_positives", [])

    missed_critical = [
        v for v in false_negatives if (v.get("severity") or "").lower() == "critical"
    ]
    high_confidence_hallucinations = [
        v for v in false_positives if (v.get("confidence") or 0.0) >= 0.8
    ]
    low_confidence_true_positives = [
        tp["ai_finding"] for tp in true_positives if (tp["ai_finding"].get("confidence") or 0.0) <= 0.3
    ]

    return {
        "missed_critical_vulnerabilities": [_serialize_vuln(v) for v in missed_critical],
        "hallucinated_findings": [_serialize_vuln(v) for v in false_positives],
        "high_confidence_hallucinations": [_serialize_vuln(v) for v in high_confidence_hallucinations],
        "confidence_correctness_mismatch_count": (
            len(high_confidence_hallucinations) + len(low_confidence_true_positives)
        ),
        "total_false_positives": len(false_positives),
        "total_false_negatives": len(false_negatives),
    }


def _trust_assessment(scores: dict, failure: dict) -> dict:
    reliability = scores.get("weighted_reliability", 0.0)
    critical_misses = len(failure.get("missed_critical_vulnerabilities", []))
    mismatch = failure.get("confidence_correctness_mismatch_count", 0)

    if reliability >= 0.8 and critical_misses == 0 and mismatch <= 1:
        verdict = "trusted_with_controls"
        statement = "Model is reliable enough for analyst-assisted triage."
    elif reliability >= 0.6 and critical_misses <= 1:
        verdict = "needs_human_review"
        statement = "Model can assist review, but critical misses still require manual validation."
    else:
        verdict = "not_trustworthy_for_primary_audit"
        statement = "Model should not be trusted as a primary smart contract auditor."

    return {
        "question": "Can this AI model be trusted for smart contract auditing?",
        "verdict": verdict,
        "statement": statement,
        "weighted_reliability": reliability,
        "critical_misses": critical_misses,
        "confidence_mismatch_count": mismatch,
    }


def generate_reproducibility_hash(
    contract_hash: str,
    ai_provider: str,
    ai_model: str,
    ai_temperature: float,
    analyzer_versions: dict,
) -> str:
    payload = json.dumps(
        {
            "contract_hash": contract_hash,
            "ai_provider": ai_provider,
            "ai_model": ai_model,
            "ai_temperature": ai_temperature,
            "analyzer_versions": analyzer_versions,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def generate_json_report(
    evaluation_id: str,
    contract_filename: str,
    contract_hash: str,
    ai_provider: str,
    ai_model: str,
    ai_temperature: float,
    scores: dict,
    comparison: dict,
    analyzer_versions: dict,
) -> Tuple[dict, str]:
    reproducibility_hash = generate_reproducibility_hash(
        contract_hash, ai_provider, ai_model, ai_temperature, analyzer_versions
    )
    failure_analysis = _build_failure_analysis(comparison)
    trust_assessment = _trust_assessment(scores, failure_analysis)

    report = {
        "report_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_id": evaluation_id,
        "reproducibility_hash": reproducibility_hash,
        "contract": {
            "filename": contract_filename,
            "file_hash": contract_hash,
        },
        "model_metadata": {
            "provider": ai_provider,
            "model": ai_model,
            "temperature": ai_temperature,
            "evaluation_mode": "deterministic_reliability",
        },
        "analyzer_versions": analyzer_versions,
        "scoring": {
            "precision": scores["precision"],
            "recall": scores["recall"],
            "hallucination_rate": scores["hallucination_rate"],
            "miss_rate": scores["miss_rate"],
            "reliability_score": scores["reliability_score"],
            "weighted_precision": scores["weighted_precision"],
            "weighted_recall": scores["weighted_recall"],
            "weighted_reliability": scores["weighted_reliability"],
            "weighted_reliability_score": scores["weighted_reliability_score"],
        },
        "summary": {
            "total_ai_findings": scores["details"]["total_ai_findings"],
            "total_ground_truth": scores["details"]["total_ground_truth"],
            "true_positives": scores["details"]["true_positives"],
            "false_positives": scores["details"]["false_positives"],
            "false_negatives": scores["details"]["false_negatives"],
        },
        "failure_analysis": failure_analysis,
        "trust_assessment": trust_assessment,
        "findings": {
            "true_positives": [
                {
                    "ai_finding": _serialize_vuln(tp["ai_finding"]),
                    "matched_ground_truth": _serialize_vuln(tp["matched_ground_truth"]),
                }
                for tp in comparison["true_positives"]
            ],
            "false_positives": [_serialize_vuln(fp) for fp in comparison["false_positives"]],
            "false_negatives": [_serialize_vuln(fn) for fn in comparison["false_negatives"]],
        },
    }

    return report, reproducibility_hash


def generate_pdf_report(report_json: dict, output_dir: str, evaluation_id: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"avelon_report_{evaluation_id}.pdf")

    doc = SimpleDocTemplate(pdf_path, pagesize=A4, topMargin=30 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=22,
        spaceAfter=20,
        textColor=colors.HexColor("#1a1a2e"),
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        spaceAfter=10,
        spaceBefore=16,
        textColor=colors.HexColor("#16213e"),
    )
    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=6,
    )

    elements = []
    elements.append(Paragraph("Avelon - AI Reliability Evaluation Report", title_style))
    elements.append(Spacer(1, 12))

    meta = report_json.get("model_metadata", {})
    contract = report_json.get("contract", {})
    elements.append(Paragraph(f"<b>Contract:</b> {contract.get('filename', 'N/A')}", body_style))
    elements.append(Paragraph(f"<b>File Hash:</b> {contract.get('file_hash', 'N/A')[:16]}...", body_style))
    elements.append(Paragraph(f"<b>Model:</b> {meta.get('provider', '')} / {meta.get('model', '')}", body_style))
    elements.append(Paragraph(f"<b>Temperature:</b> {meta.get('temperature', 0)} (deterministic)", body_style))
    elements.append(Paragraph(f"<b>Generated:</b> {report_json.get('generated_at', '')}", body_style))
    elements.append(Paragraph(f"<b>Reproducibility Hash:</b> {report_json.get('reproducibility_hash', '')[:16]}...", body_style))
    elements.append(Spacer(1, 16))

    scoring = report_json.get("scoring", {})
    elements.append(Paragraph("Reliability Metrics", heading_style))
    score_data = [
        ["Metric", "Score"],
        ["Precision", f"{scoring.get('precision', 0):.2%}"],
        ["Recall", f"{scoring.get('recall', 0):.2%}"],
        ["Hallucination Rate", f"{scoring.get('hallucination_rate', 0):.2%}"],
        ["Miss Rate", f"{scoring.get('miss_rate', 0):.2%}"],
        ["Reliability Score", f"{scoring.get('reliability_score', 0):.2%}"],
        ["Weighted Reliability", f"{scoring.get('weighted_reliability', 0):.2%}"],
    ]
    score_table = Table(score_data, colWidths=[3 * inch, 2 * inch])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f5")]),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(score_table)
    elements.append(Spacer(1, 16))

    summary = report_json.get("summary", {})
    elements.append(Paragraph("Findings Summary", heading_style))
    elements.append(Paragraph(f"Total AI Findings: {summary.get('total_ai_findings', 0)}", body_style))
    elements.append(Paragraph(f"Total Ground Truth: {summary.get('total_ground_truth', 0)}", body_style))
    elements.append(Paragraph(f"True Positives: {summary.get('true_positives', 0)}", body_style))
    elements.append(Paragraph(f"False Positives (Hallucinated): {summary.get('false_positives', 0)}", body_style))
    elements.append(Paragraph(f"False Negatives (Missed): {summary.get('false_negatives', 0)}", body_style))
    elements.append(Spacer(1, 16))

    trust = report_json.get("trust_assessment", {})
    failure = report_json.get("failure_analysis", {})
    elements.append(Paragraph("Trust Assessment", heading_style))
    elements.append(Paragraph(trust.get("question", ""), body_style))
    elements.append(Paragraph(f"<b>Verdict:</b> {trust.get('verdict', 'unknown')}", body_style))
    elements.append(Paragraph(f"<b>Statement:</b> {trust.get('statement', '')}", body_style))
    elements.append(
        Paragraph(
            f"<b>Missed critical vulnerabilities:</b> {len(failure.get('missed_critical_vulnerabilities', []))}",
            body_style,
        )
    )
    elements.append(
        Paragraph(
            f"<b>Confidence/correctness mismatches:</b> {failure.get('confidence_correctness_mismatch_count', 0)}",
            body_style,
        )
    )
    elements.append(Spacer(1, 16))

    findings = report_json.get("findings", {})
    for section_name, section_key, color_hex in [
        ("True Positives", "true_positives", "#2d6a4f"),
        ("False Positives (Hallucinations)", "false_positives", "#d00000"),
        ("False Negatives (Missed)", "false_negatives", "#e85d04"),
    ]:
        items = findings.get(section_key, [])
        if not items:
            continue

        elements.append(Paragraph(section_name, heading_style))
        table_data = [["Type", "Function", "Severity", "Description"]]
        for item in items:
            vuln = item.get("ai_finding", {}) if section_key == "true_positives" else item
            table_data.append([
                vuln.get("vuln_type", ""),
                vuln.get("function_name", "N/A"),
                vuln.get("severity", ""),
                vuln.get("description", "")[:80],
            ])

        detail_table = Table(table_data, colWidths=[1.5 * inch, 1.2 * inch, 0.8 * inch, 3 * inch])
        detail_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(color_hex)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f8f8")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(detail_table)
        elements.append(Spacer(1, 12))

    doc.build(elements)
    logger.info("pdf_report_generated", path=pdf_path)
    return pdf_path
