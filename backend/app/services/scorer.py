"""Scoring Engine — computes precision, recall, hallucination rate,
miss rate, and weighted reliability score.

Critical vulnerabilities carry higher penalty weight.
"""

import structlog

logger = structlog.get_logger()

# ── Severity Weights ───────────────────────────────────────────────────
# Higher weight = higher penalty for missing/hallucinating critical vulns

SEVERITY_WEIGHTS = {
    "critical": 5.0,
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
    "info": 0.5,
}


def _get_weight(severity: str) -> float:
    """Get the penalty weight for a severity level."""
    return SEVERITY_WEIGHTS.get(severity.lower(), 1.0)


def compute_scores(comparison: dict) -> dict:
    """Compute all scoring metrics from comparison results.

    Args:
        comparison: Output from comparator.compare_findings()

    Returns:
        {
            "precision": float,
            "recall": float,
            "hallucination_rate": float,
            "miss_rate": float,
            "reliability_score": float,
            "weighted_precision": float,
            "weighted_recall": float,
            "weighted_reliability": float,
            "details": {...}
        }
    """
    tp = comparison["tp_count"]
    fp = comparison["fp_count"]
    fn = comparison["fn_count"]

    # ── Unweighted Metrics ─────────────────────────────────────────────

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    hallucination_rate = fp / (tp + fp) if (tp + fp) > 0 else 0.0
    miss_rate = fn / (tp + fn) if (tp + fn) > 0 else 0.0
    reliability = precision * recall

    # ── Weighted Metrics ───────────────────────────────────────────────

    weighted_tp = sum(
        _get_weight(tp_item["ai_finding"].get("severity", "medium"))
        for tp_item in comparison["true_positives"]
    )
    weighted_fp = sum(
        _get_weight(fp_item.get("severity", "medium"))
        for fp_item in comparison["false_positives"]
    )
    weighted_fn = sum(
        _get_weight(fn_item.get("severity", "medium"))
        for fn_item in comparison["false_negatives"]
    )

    weighted_precision = weighted_tp / (weighted_tp + weighted_fp) if (weighted_tp + weighted_fp) > 0 else 0.0
    weighted_recall = weighted_tp / (weighted_tp + weighted_fn) if (weighted_tp + weighted_fn) > 0 else 0.0
    weighted_reliability = weighted_precision * weighted_recall

    scores = {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "hallucination_rate": round(hallucination_rate, 4),
        "miss_rate": round(miss_rate, 4),
        "reliability_score": round(reliability, 4),
        "weighted_precision": round(weighted_precision, 4),
        "weighted_recall": round(weighted_recall, 4),
        "weighted_reliability": round(weighted_reliability, 4),
        "weighted_reliability_score": round(weighted_reliability, 4),
        "details": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "total_ai_findings": tp + fp,
            "total_ground_truth": tp + fn,
            "severity_weights": SEVERITY_WEIGHTS,
        },
    }

    logger.info(
        "scoring_complete",
        precision=scores["precision"],
        recall=scores["recall"],
        reliability=scores["reliability_score"],
        weighted_reliability=scores["weighted_reliability"],
    )

    return scores
