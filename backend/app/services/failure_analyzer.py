"""Failure classification engine for AI reasoning breakdowns."""

from __future__ import annotations

from typing import Any


def classify_failures(comparison: dict[str, Any]) -> list[dict[str, Any]]:
    """Classify reasoning failures from TP/FP/FN comparison output."""
    failures: list[dict[str, Any]] = []
    true_positives = comparison.get("true_positives", [])
    false_positives = comparison.get("false_positives", [])
    false_negatives = comparison.get("false_negatives", [])

    for fp in false_positives:
        severity = (fp.get("severity") or "medium").lower()
        confidence = fp.get("confidence")
        failures.append(
            {
                "failure_type": "hallucinated_vulnerability",
                "severity": severity,
                "vulnerability_type": fp.get("vuln_type"),
                "confidence": confidence,
                "details_json": {"finding": fp},
            }
        )
        if confidence is not None and confidence >= 0.8:
            failures.append(
                {
                    "failure_type": "overconfidence",
                    "severity": severity if severity in ("high", "critical") else "high",
                    "vulnerability_type": fp.get("vuln_type"),
                    "confidence": confidence,
                    "details_json": {"finding": fp, "reason": "high_confidence_false_positive"},
                }
            )

    for fn in false_negatives:
        severity = (fn.get("severity") or "high").lower()
        failures.append(
            {
                "failure_type": "missed_vulnerability",
                "severity": severity,
                "vulnerability_type": fn.get("vuln_type"),
                "confidence": None,
                "details_json": {"ground_truth": fn},
            }
        )

    for tp in true_positives:
        ai = tp.get("ai_finding", {})
        gt = tp.get("matched_ground_truth", {})
        ai_type = (ai.get("vuln_type") or "").lower()
        gt_type = (gt.get("vuln_type") or "").lower()
        if ai_type and gt_type and ai_type != gt_type:
            failures.append(
                {
                    "failure_type": "misidentified_vulnerability_type",
                    "severity": (gt.get("severity") or "medium").lower(),
                    "vulnerability_type": gt.get("vuln_type"),
                    "confidence": ai.get("confidence"),
                    "details_json": {"ai_finding": ai, "ground_truth": gt},
                }
            )

        explanation = (ai.get("description") or "").strip()
        if explanation and len(explanation.split()) < 8:
            failures.append(
                {
                    "failure_type": "incorrect_reasoning_chain",
                    "severity": (ai.get("severity") or "medium").lower(),
                    "vulnerability_type": ai.get("vuln_type"),
                    "confidence": ai.get("confidence"),
                    "details_json": {"reason": "insufficient_reasoning", "ai_finding": ai},
                }
            )

    gt_by_func = {}
    for fn in false_negatives:
        fn_name = fn.get("function_name")
        if fn_name:
            gt_by_func.setdefault(fn_name, 0)
            gt_by_func[fn_name] += 1

    for tp in true_positives:
        matched_gt = tp.get("matched_ground_truth", {})
        fn_name = matched_gt.get("function_name")
        if fn_name and gt_by_func.get(fn_name):
            failures.append(
                {
                    "failure_type": "partial_detection",
                    "severity": (matched_gt.get("severity") or "medium").lower(),
                    "vulnerability_type": matched_gt.get("vuln_type"),
                    "confidence": tp.get("ai_finding", {}).get("confidence"),
                    "details_json": {
                        "function_name": fn_name,
                        "remaining_missed_findings": gt_by_func[fn_name],
                    },
                }
            )

    return failures
