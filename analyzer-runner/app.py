"""Analyzer Runner — isolated FastAPI microservice for running
Slither and Mythril in a sandboxed container.

This service MUST run inside a security-constrained Docker container:
- CPU / memory / process limits
- Read-only filesystem (except /tmp)
- No outbound network access
- Execution timeouts
"""

import os
import tempfile
import subprocess
import json
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Avelon Analyzer Runner", version="1.0.0")


class AnalyzeRequest(BaseModel):
    contract_source: str
    solidity_version: Optional[str] = None


class VulnFinding(BaseModel):
    vuln_type: str
    function_name: Optional[str] = None
    line_number: Optional[int] = None
    severity: str = "medium"
    confidence: Optional[float] = None
    description: str = ""


EXECUTION_TIMEOUT = 180  # 3 minutes per analyzer

# Venv-specific binary paths (Slither and Mythril have incompatible deps)
SLITHER_BIN = "/opt/slither-env/bin/slither"
MYTHRIL_BIN = "/opt/mythril-env/bin/myth"


def _get_tool_version(tool: str) -> str:
    """Get the version of an installed tool."""
    try:
        result = subprocess.run(
            [tool, "--version"], capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip().split("\n")[0]
    except Exception:
        return "unknown"


def _run_slither(contract_path: str, solidity_version: Optional[str]) -> list[dict]:
    """Run Slither on a contract file and parse findings."""
    cmd = [SLITHER_BIN, contract_path, "--json", "-"]
    if solidity_version:
        cmd.extend(["--solc-solcs-select", solidity_version])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=EXECUTION_TIMEOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

        findings = []
        try:
            output = json.loads(result.stdout) if result.stdout else {}
        except json.JSONDecodeError:
            # Try to extract JSON from mixed output
            for line in result.stdout.split("\n"):
                line = line.strip()
                if line.startswith("{"):
                    try:
                        output = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
            else:
                output = {}

        detectors = output.get("results", {}).get("detectors", [])
        for d in detectors:
            function_name = None
            line_number = None

            elements = d.get("elements", [])
            for elem in elements:
                if elem.get("type") == "function":
                    function_name = elem.get("name")
                if "source_mapping" in elem:
                    lines = elem["source_mapping"].get("lines", [])
                    if lines:
                        line_number = lines[0]
                    break

            severity_map = {
                "High": "high",
                "Medium": "medium",
                "Low": "low",
                "Informational": "info",
                "Optimization": "info",
            }

            findings.append({
                "vuln_type": d.get("check", "unknown"),
                "function_name": function_name,
                "line_number": line_number,
                "severity": severity_map.get(d.get("impact", "Medium"), "medium"),
                "confidence": {"High": 0.9, "Medium": 0.6, "Low": 0.3}.get(d.get("confidence", "Medium"), 0.5),
                "description": d.get("description", ""),
            })

        return findings

    except subprocess.TimeoutExpired:
        return [{"vuln_type": "timeout", "severity": "info", "description": "Slither timed out"}]
    except FileNotFoundError:
        return [{"vuln_type": "tool-not-found", "severity": "info", "description": "Slither not installed"}]
    except Exception as e:
        return [{"vuln_type": "error", "severity": "info", "description": f"Slither error: {str(e)}"}]


def _run_mythril(contract_path: str, solidity_version: Optional[str]) -> list[dict]:
    """Run Mythril on a contract file and parse findings."""
    cmd = [MYTHRIL_BIN, "analyze", contract_path, "-o", "json", "--execution-timeout", "120"]
    if solidity_version:
        cmd.extend(["--solv", solidity_version])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=EXECUTION_TIMEOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

        findings = []
        try:
            output = json.loads(result.stdout) if result.stdout else {}
        except json.JSONDecodeError:
            output = {}

        issues = output.get("issues", [])
        for issue in issues:
            severity_map = {
                "High": "high",
                "Medium": "medium",
                "Low": "low",
            }

            findings.append({
                "vuln_type": issue.get("swc-id", issue.get("title", "unknown")),
                "function_name": issue.get("function", None),
                "line_number": issue.get("lineno"),
                "severity": severity_map.get(issue.get("severity", "Medium"), "medium"),
                "confidence": 0.7,
                "description": issue.get("description", ""),
            })

        return findings

    except subprocess.TimeoutExpired:
        return [{"vuln_type": "timeout", "severity": "info", "description": "Mythril timed out"}]
    except FileNotFoundError:
        return [{"vuln_type": "tool-not-found", "severity": "info", "description": "Mythril not installed"}]
    except Exception as e:
        return [{"vuln_type": "error", "severity": "info", "description": f"Mythril error: {str(e)}"}]


@app.post("/analyze")
async def analyze_contract(req: AnalyzeRequest):
    """Analyze a contract with Slither and Mythril.

    Returns parsed findings from both tools in a standardized format.
    """
    errors = []

    # Write contract to temp file
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sol", delete=False, dir="/tmp"
        ) as f:
            f.write(req.contract_source)
            contract_path = f.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write temp file: {e}")

    try:
        # Run both analyzers
        slither_findings = _run_slither(contract_path, req.solidity_version)
        mythril_findings = _run_mythril(contract_path, req.solidity_version)

        return {
            "slither": slither_findings,
            "mythril": mythril_findings,
            "versions": {
                "slither": _get_tool_version(SLITHER_BIN),
                "mythril": _get_tool_version(MYTHRIL_BIN),
            },
            "errors": errors,
        }
    finally:
        # Always clean up temp files
        try:
            os.unlink(contract_path)
        except OSError:
            pass


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "slither": _get_tool_version(SLITHER_BIN),
        "mythril": _get_tool_version(MYTHRIL_BIN),
    }
