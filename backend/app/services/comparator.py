"""Comparison Engine — matches AI findings against ground truth.

Matching strategy: function_name + vuln_type (primary key).
Line numbers are supporting metadata only.

Ground truth = Slither ∪ Mythril ∪ Curated dataset.
"""

from typing import Optional

import structlog

logger = structlog.get_logger()


def _match_key(vuln: dict) -> str:
    """Generate a comparison key from function_name + vuln_type."""
    func = (vuln.get("function_name") or "global").lower().strip()
    vtype = vuln.get("vuln_type", "unknown").lower().strip()
    return f"{func}::{vtype}"


def compare_findings(
    ai_vulns: list[dict],
    ground_truth_vulns: list[dict],
) -> dict:
    """Compare AI-detected vulnerabilities against ground truth.

    Args:
        ai_vulns: Normalized AI findings
        ground_truth_vulns: Normalized ground truth (Slither ∪ Mythril ∪ Curated)

    Returns:
        {
            "true_positives": [...],
            "false_positives": [...],   # Hallucinations
            "false_negatives": [...],   # Missed
            "tp_count": int,
            "fp_count": int,
            "fn_count": int,
        }
    """
    # Build ground truth lookup: key -> list of vulns
    gt_lookup: dict[str, list[dict]] = {}
    for v in ground_truth_vulns:
        key = _match_key(v)
        gt_lookup.setdefault(key, []).append(v)

    # Track which ground truth entries have been matched
    gt_matched_keys: set[str] = set()

    true_positives = []
    false_positives = []

    for ai_v in ai_vulns:
        key = _match_key(ai_v)

        # Exact key match
        if key in gt_lookup and key not in gt_matched_keys:
            ai_v["match_classification"] = "true_positive"
            gt_matched_keys.add(key)
            true_positives.append({
                "ai_finding": ai_v,
                "matched_ground_truth": gt_lookup[key][0],
            })
        else:
            # Try fuzzy match: same vuln_type, any function
            fuzzy_matched = False
            for gt_key, gt_list in gt_lookup.items():
                if gt_key in gt_matched_keys:
                    continue
                gt_type = gt_key.split("::")[1]
                ai_type = key.split("::")[1]
                if gt_type == ai_type:
                    ai_v["match_classification"] = "true_positive"
                    gt_matched_keys.add(gt_key)
                    true_positives.append({
                        "ai_finding": ai_v,
                        "matched_ground_truth": gt_list[0],
                    })
                    fuzzy_matched = True
                    break

            if not fuzzy_matched:
                ai_v["match_classification"] = "false_positive"
                false_positives.append(ai_v)

    # False negatives: ground truth entries not matched by any AI finding
    false_negatives = []
    for gt_key, gt_list in gt_lookup.items():
        if gt_key not in gt_matched_keys:
            for gt_v in gt_list:
                gt_v["match_classification"] = "false_negative"
                false_negatives.append(gt_v)

    result = {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "tp_count": len(true_positives),
        "fp_count": len(false_positives),
        "fn_count": len(false_negatives),
    }

    logger.info(
        "comparison_complete",
        tp=result["tp_count"],
        fp=result["fp_count"],
        fn=result["fn_count"],
    )

    return result
