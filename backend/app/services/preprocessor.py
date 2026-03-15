"""Solidity contract preprocessing engine.

Responsibilities:
- Detect Solidity version from pragma
- Install the correct compiler via py-solc-x
- Flatten imports (basic)
- Remove comments while preserving line mapping
"""

import re
from typing import Optional, Tuple

import structlog

logger = structlog.get_logger()


def detect_solidity_version(source: str) -> Optional[str]:
    """Extract the Solidity version from pragma statements.

    Supports patterns like:
        pragma solidity ^0.8.0;
        pragma solidity >=0.8.0 <0.9.0;
        pragma solidity 0.8.19;
    """
    patterns = [
        r"pragma\s+solidity\s+\^?(\d+\.\d+\.\d+)",
        r"pragma\s+solidity\s+>=?\s*(\d+\.\d+\.\d+)",
        r"pragma\s+solidity\s+(\d+\.\d+\.\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, source)
        if match:
            return match.group(1)
    return None


def install_compiler(version: str) -> bool:
    """Install the Solidity compiler for the detected version."""
    try:
        import solcx

        installed = [str(v) for v in solcx.get_installed_solc_versions()]
        if version not in installed:
            logger.info("installing_solc", version=version)
            solcx.install_solc(version)
        return True
    except Exception as e:
        logger.error("solc_install_failed", version=version, error=str(e))
        return False


def remove_comments(source: str) -> Tuple[str, dict]:
    """Remove single-line and multi-line comments from Solidity source.

    Returns the cleaned source and a line mapping dictionary.
    The mapping records original line numbers to cleaned line numbers.
    """
    lines = source.split("\n")
    cleaned_lines = []
    line_map = {}
    in_block_comment = False

    for i, line in enumerate(lines, start=1):
        if in_block_comment:
            end_idx = line.find("*/")
            if end_idx != -1:
                in_block_comment = False
                remainder = line[end_idx + 2:]
                cleaned_lines.append(remainder)
                line_map[len(cleaned_lines)] = i
            else:
                cleaned_lines.append("")
                line_map[len(cleaned_lines)] = i
        else:
            # Remove single-line comments
            processed = re.sub(r"//.*$", "", line)
            # Check for block comment start
            while "/*" in processed:
                start_idx = processed.find("/*")
                end_idx = processed.find("*/", start_idx + 2)
                if end_idx != -1:
                    processed = processed[:start_idx] + processed[end_idx + 2:]
                else:
                    processed = processed[:start_idx]
                    in_block_comment = True
                    break
            cleaned_lines.append(processed)
            line_map[len(cleaned_lines)] = i

    return "\n".join(cleaned_lines), line_map


def flatten_imports(source: str) -> str:
    """Basic import flattening — removes import statements and replaces
    with a comment noting the import was removed.

    For production use, a full import resolver (e.g., via solc --flatten)
    would be more appropriate.
    """
    lines = source.split("\n")
    flattened = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("import "):
            flattened.append(f"// [FLATTENED] {stripped}")
        else:
            flattened.append(line)
    return "\n".join(flattened)


def extract_function_signatures(source: str) -> list[dict]:
    """Extract function signatures from Solidity source.

    Returns a list of dicts: {name, line, visibility, modifiers}
    """
    patterns = [
        r"function\s+(\w+)\s*\([^)]*\)\s*(public|external|internal|private)?",
        r"constructor\s*\([^)]*\)",
        r"receive\s*\(\s*\)\s*external",
        r"fallback\s*\([^)]*\)\s*external",
    ]

    functions = []
    for i, line in enumerate(source.split("\n"), start=1):
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                name = match.group(1) if match.lastindex and match.lastindex >= 1 else match.group(0).split("(")[0].strip()
                functions.append({
                    "name": name,
                    "line": i,
                    "visibility": match.group(2) if match.lastindex and match.lastindex >= 2 else "unknown",
                    "raw": match.group(0),
                })
                break

    return functions


def preprocess_contract(source: str) -> dict:
    """Run the full preprocessing pipeline on a Solidity contract.

    Returns a dict with all preprocessing results.
    """
    version = detect_solidity_version(source)
    if version:
        install_compiler(version)

    flattened = flatten_imports(source)
    cleaned, line_map = remove_comments(flattened)
    functions = extract_function_signatures(cleaned)

    return {
        "solidity_version": version,
        "flattened_source": flattened,
        "cleaned_source": cleaned,
        "line_map": line_map,
        "functions": functions,
    }
