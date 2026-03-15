"""HTTP client for communicating with the isolated analyzer-runner service.

The backend NEVER runs Slither/Mythril directly — it sends jobs to
the analyzer-runner container and receives parsed JSON results.
"""

from typing import Optional

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

ANALYZER_TIMEOUT = 300  # 5 minutes max per analyzer run


async def run_static_analysis(
    contract_source: str,
    solidity_version: Optional[str] = None,
) -> dict:
    """Send contract source to the analyzer-runner and receive parsed results.

    Returns:
        {
            "slither": [{"vuln_type": ..., "function_name": ..., ...}],
            "mythril": [{"vuln_type": ..., "function_name": ..., ...}],
            "versions": {"slither": "0.10.x", "mythril": "0.24.x"},
            "errors": []
        }
    """
    url = f"{settings.analyzer_runner_url}/analyze"
    payload = {
        "contract_source": contract_source,
        "solidity_version": solidity_version,
    }

    logger.info("sending_to_analyzer_runner", url=url)

    try:
        async with httpx.AsyncClient(timeout=ANALYZER_TIMEOUT) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            logger.info(
                "analyzer_runner_response",
                slither_count=len(result.get("slither", [])),
                mythril_count=len(result.get("mythril", [])),
            )
            return result

    except httpx.TimeoutException:
        logger.error("analyzer_runner_timeout")
        return {
            "slither": [],
            "mythril": [],
            "versions": {},
            "errors": ["Analyzer runner timed out"],
        }
    except httpx.HTTPStatusError as e:
        logger.error("analyzer_runner_http_error", status=e.response.status_code, detail=e.response.text)
        return {
            "slither": [],
            "mythril": [],
            "versions": {},
            "errors": [f"Analyzer runner HTTP error: {e.response.status_code}"],
        }
    except Exception as e:
        logger.error("analyzer_runner_connection_error", error=str(e))
        return {
            "slither": [],
            "mythril": [],
            "versions": {},
            "errors": [f"Analyzer runner connection error: {str(e)}"],
        }
