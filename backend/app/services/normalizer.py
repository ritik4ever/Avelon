"""Normalization layer — converts all vulnerability findings into a canonical form.

Canonical form: {type, function_name, severity, line_number (metadata only)}
This ensures AI results, Slither results, Mythril results, and curated data
can all be compared using the same schema.
"""

import re
from typing import Optional

import structlog

logger = structlog.get_logger()

# ── Vulnerability Type Normalization ───────────────────────────────────

TYPE_ALIASES = {
    # Reentrancy
    "reentrancy-eth": "reentrancy",
    "reentrancy-no-eth": "reentrancy",
    "reentrancy-benign": "reentrancy",
    "reentrancy-events": "reentrancy",
    "reentrancy-unlimited-gas": "reentrancy",
    "external-call": "reentrancy",
    "state-change-after-external-call": "reentrancy",

    # Integer issues
    "integer-overflow": "integer-overflow",
    "integer-underflow": "integer-underflow",
    "arithmetic": "integer-overflow",

    # Access control
    "access-control": "access-control",
    "unprotected-function": "access-control",
    "missing-access-control": "access-control",
    "suicidal": "access-control",
    "owned": "access-control",

    # Unchecked return
    "unchecked-return": "unchecked-return",
    "unchecked-call": "unchecked-return",
    "unchecked-lowlevel": "unchecked-return",
    "unchecked-send": "unchecked-return",

    # Delegatecall
    "delegatecall": "delegatecall",
    "delegatecall-loop": "delegatecall",
    "controlled-delegatecall": "delegatecall",

    # tx.origin
    "tx-origin": "tx-origin",
    "tx.origin": "tx-origin",

    # Timestamp
    "timestamp-dependence": "timestamp-dependence",
    "timestamp": "timestamp-dependence",
    "block-timestamp": "timestamp-dependence",
    "weak-randomness": "timestamp-dependence",

    # Front-running
    "front-running": "front-running",
    "frontrunning": "front-running",

    # DoS
    "denial-of-service": "denial-of-service",
    "dos": "denial-of-service",
    "dos-with-gas-limit": "denial-of-service",
    "gas-limit": "denial-of-service",

    # Storage
    "uninitialized-storage": "uninitialized-storage",
    "uninitialized-state": "uninitialized-storage",
    "arbitrary-storage-write": "arbitrary-storage-write",

    # Self-destruct
    "self-destruct": "self-destruct",
    "selfdestruct": "self-destruct",

    # Flash loan
    "flash-loan-attack": "flash-loan-attack",
    "flash-loan": "flash-loan-attack",
}

SEVERITY_MAP = {
    "informational": "info",
    "info": "info",
    "optimization": "info",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}


def normalize_type(vuln_type: str) -> str:
    """Normalize vulnerability type to canonical form."""
    key = vuln_type.lower().strip().replace(" ", "-").replace("_", "-")
    return TYPE_ALIASES.get(key, key)


def normalize_severity(severity: str) -> str:
    """Normalize severity level to canonical form."""
    key = severity.lower().strip()
    return SEVERITY_MAP.get(key, "medium")


def normalize_function_name(name: Optional[str]) -> Optional[str]:
    """Normalize function name — strip visibility, parameters, whitespace."""
    if not name:
        return None
    # Remove parameters
    name = re.sub(r"\(.*\)", "", name).strip()
    # Remove visibility keywords
    for kw in ["public", "external", "internal", "private", "view", "pure", "payable"]:
        name = name.replace(kw, "").strip()
    return name if name else None


def normalize_vulnerabilities(vulns: list[dict], source: str) -> list[dict]:
    """Normalize a list of vulnerability dicts to canonical form.

    Args:
        vulns: Raw vulnerability dicts from AI, analyzers, or curated data
        source: Origin label — "ai", "slither", "mythril", "curated"

    Returns:
        List of normalized vulnerability dicts
    """
    normalized = []
    for v in vulns:
        normalized.append({
            "source": source,
            "vuln_type": normalize_type(v.get("vuln_type", v.get("type", "unknown"))),
            "function_name": normalize_function_name(v.get("function_name", v.get("function"))),
            "line_number": v.get("line_number", v.get("line")),
            "severity": normalize_severity(v.get("severity", "medium")),
            "confidence": v.get("confidence"),
            "description": v.get("description", v.get("explanation", "")),
        })

    logger.info("normalized_vulns", source=source, count=len(normalized))
    return normalized
