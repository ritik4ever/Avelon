"""Adversarial smart-contract task generation service."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any


TASK_CATEGORIES = [
    "reentrancy_edge_case",
    "misleading_naming",
    "fake_vulnerability_bait",
    "unusual_control_flow",
    "proxy_upgradeable_trap",
    "storage_layout_trap",
    "flash_loan_pattern",
    "hidden_access_control",
    "arithmetic_edge_case",
    "nested_contract_interaction",
]


DIFFICULTY_LEVELS = ["easy", "medium", "hard", "adversarial"]


@dataclass
class GeneratedTask:
    task_id: str
    language: str
    contract_code: str
    expected_vulnerabilities: list[dict[str, Any]]
    difficulty: str
    category: str
    generation_method: str
    metadata_json: dict[str, Any]


def _normalize_difficulty_mix(difficulty_mix: dict[str, float]) -> dict[str, float]:
    if not difficulty_mix:
        return {"easy": 0.2, "medium": 0.35, "hard": 0.3, "adversarial": 0.15}
    clean = {k: max(v, 0.0) for k, v in difficulty_mix.items() if k in DIFFICULTY_LEVELS}
    if not clean:
        return {"easy": 0.2, "medium": 0.35, "hard": 0.3, "adversarial": 0.15}
    total = sum(clean.values())
    return {k: v / total for k, v in clean.items()}


def _pick_difficulty(rng: random.Random, mix: dict[str, float]) -> str:
    pointer = rng.random()
    cumulative = 0.0
    for level, weight in mix.items():
        cumulative += weight
        if pointer <= cumulative:
            return level
    return "medium"


def _pick_generation_method(rng: random.Random, allowed: list[str]) -> str:
    if not allowed:
        return "mixed"
    return rng.choice(allowed)


def _template_contract(category: str, difficulty: str, index: int) -> tuple[str, list[dict[str, Any]]]:
    if category == "reentrancy_edge_case":
        return (
            f"""
pragma solidity ^0.8.19;
contract VaultTask{index} {{
    mapping(address => uint256) public balance;
    bool private locked;
    function deposit() external payable {{
        balance[msg.sender] += msg.value;
    }}
    function withdraw(uint256 amount) external {{
        require(balance[msg.sender] >= amount, "insufficient");
        if ({'false' if difficulty == 'easy' else 'locked'}) {{
            revert("guard");
        }}
        (bool ok,) = msg.sender.call{{value: amount}}("");
        require(ok, "transfer failed");
        balance[msg.sender] -= amount;
    }}
}}
""".strip(),
            [{"type": "reentrancy", "severity": "high", "function": "withdraw"}],
        )
    if category == "hidden_access_control":
        return (
            f"""
pragma solidity ^0.8.19;
contract AccessTask{index} {{
    address public owner;
    constructor() {{ owner = msg.sender; }}
    function upgradeExecutor(address next) external {{
        if ({'msg.sender == owner' if difficulty == 'easy' else 'tx.origin == owner'}) {{
            owner = next;
        }}
    }}
}}
""".strip(),
            [{"type": "access-control", "severity": "critical", "function": "upgradeExecutor"}],
        )
    if category == "misleading_naming":
        return (
            f"""
pragma solidity ^0.8.19;
contract NamingTask{index} {{
    address public safetyOfficer;
    constructor() {{ safetyOfficer = msg.sender; }}
    function safeRotateGuardian(address next) external {{
        require(next != address(0), "zero");
        if ({'msg.sender == safetyOfficer' if difficulty == 'easy' else 'tx.origin == safetyOfficer'}) {{
            safetyOfficer = next;
        }}
    }}
}}
""".strip(),
            [{"type": "access-control", "severity": "high", "function": "safeRotateGuardian"}],
        )
    if category == "fake_vulnerability_bait":
        return (
            f"""
pragma solidity ^0.8.19;
contract BaitTask{index} {{
    mapping(address => uint256) public balance;
    bool private entered;
    function deposit() external payable {{
        balance[msg.sender] += msg.value;
    }}
    function withdraw(uint256 amount) external {{
        require(!entered, "reentrant");
        entered = true;
        require(balance[msg.sender] >= amount, "insufficient");
        balance[msg.sender] -= amount;
        (bool ok,) = msg.sender.call{{value: amount}}("");
        require(ok, "transfer");
        entered = false;
    }}
}}
""".strip(),
            [],
        )
    if category == "unusual_control_flow":
        return (
            f"""
pragma solidity ^0.8.19;
contract ControlFlowTask{index} {{
    address public owner = msg.sender;
    uint256 public total;
    function settle(address to, uint256 amount) external {{
        if ({'msg.sender != owner' if difficulty == 'easy' else 'to == address(0)'}) {{
            return;
        }}
        (bool ok,) = to.call{{value: amount}}("");
        require(ok, "pay failed");
        total += amount;
    }}
}}
""".strip(),
            [{"type": "access-control", "severity": "high", "function": "settle"}],
        )
    if category == "arithmetic_edge_case":
        return (
            f"""
pragma solidity ^0.8.19;
contract ArithmeticTask{index} {{
    uint256 public fee;
    function setFee(uint256 x) external {{
        unchecked {{
            fee = x * {2 if difficulty in ('easy', 'medium') else 1000000000000000000};
        }}
    }}
}}
""".strip(),
            [{"type": "integer-overflow", "severity": "medium", "function": "setFee"}],
        )
    if category == "proxy_upgradeable_trap":
        return (
            f"""
pragma solidity ^0.8.19;
contract ProxyTask{index} {{
    address public implementation;
    function setImpl(address impl) external {{
        implementation = impl;
    }}
    fallback() external payable {{
        (bool ok,) = implementation.delegatecall(msg.data);
        require(ok, "delegatecall failed");
    }}
}}
""".strip(),
            [{"type": "delegatecall", "severity": "high", "function": "fallback"}],
        )
    if category == "storage_layout_trap":
        return (
            f"""
pragma solidity ^0.8.19;
contract StorageTrap{index} {{
    bytes32 internal constant IMPLEMENTATION_SLOT = keccak256("eip1967.proxy.implementation");
    bytes32 internal constant OWNER_SLOT = keccak256("proxy.owner");
    function setOwner(address next) external {{
        bytes32 slot = OWNER_SLOT;
        assembly {{ sstore(slot, next) }}
    }}
    function implementation() external view returns (address impl) {{
        bytes32 slot = OWNER_SLOT;
        assembly {{ impl := sload(slot) }}
    }}
}}
""".strip(),
            [{"type": "storage-layout", "severity": "high", "function": "implementation"}],
        )
    if category == "flash_loan_pattern":
        return (
            f"""
pragma solidity ^0.8.19;
interface IFlashPool {{
    function flashLoan(uint256 amount, bytes calldata data) external;
}}
contract FlashLoanTask{index} {{
    uint256 public lastPrice = 1e18;
    function executeArb(IFlashPool pool, uint256 amount) external {{
        pool.flashLoan(amount, abi.encode(msg.sender));
        if ({'amount > 0' if difficulty == 'easy' else 'lastPrice > 0'}) {{
            // price can be manipulated in the flash callback path
            lastPrice = amount;
        }}
    }}
}}
""".strip(),
            [{"type": "price-manipulation", "severity": "critical", "function": "executeArb"}],
        )
    if category == "nested_contract_interaction":
        return (
            f"""
pragma solidity ^0.8.19;
interface IExecutor {{
    function exec(address target, bytes calldata data) external returns (bytes memory);
}}
contract NestedTask{index} {{
    address public owner = msg.sender;
    function run(IExecutor exec, address target, bytes calldata data) external {{
        require(msg.sender == owner, "only owner");
        bytes memory out = exec.exec(target, data);
        if ({'out.length > 0' if difficulty == 'easy' else 'target != address(0)'}) {{
            (bool ok,) = target.call(out);
            require(ok, "nested call failed");
        }}
    }}
}}
""".strip(),
            [{"type": "reentrancy", "severity": "high", "function": "run"}],
        )
    return (
        f"""
pragma solidity ^0.8.19;
contract GenericTask{index} {{
    mapping(address => uint256) internal points;
    function execute(address target, uint256 amount) external {{
        points[target] += amount;
        if ({'amount > 0' if difficulty == 'easy' else 'amount > points[target]'}) {{
            points[target] = amount - points[target];
        }}
    }}
}}
""".strip(),
        [{"type": "logic-bug", "severity": "low", "function": "execute"}],
    )


def _mutate_contract(rng: random.Random, code: str) -> str:
    replacements = [
        ("owner", "guardian"),
        ("withdraw", "rebalance"),
        ("implementation", "executor"),
        ("amount", "requested"),
        ("balance", "credits"),
    ]
    mutated = code
    for old, new in replacements:
        if rng.random() < 0.45:
            mutated = mutated.replace(old, new)
    return mutated


def _fuzz_contract(rng: random.Random, code: str) -> str:
    noise_candidates = [
        "uint256 private nonce;",
        "event Executed(address indexed user, uint256 value);",
        "modifier onlyEOA() { require(msg.sender == tx.origin, 'eoa'); _; }",
        "mapping(bytes32 => uint256) internal shadow;",
    ]
    lines = code.splitlines()
    insertion = noise_candidates[rng.randrange(0, len(noise_candidates))]
    insert_at = max(1, min(len(lines) - 1, rng.randrange(1, max(2, len(lines)))))
    lines.insert(insert_at, f"    {insertion}")
    return "\n".join(lines)


def generate_adversarial_tasks(
    dataset_version: str,
    language: str,
    task_count: int,
    generation_method: str,
    categories: list[str] | None = None,
    difficulty_mix: dict[str, float] | None = None,
    seed: int | None = None,
) -> list[GeneratedTask]:
    """Generate adversarial tasks using template/mutation/fuzzing strategies."""
    rng = random.Random(seed if seed is not None else abs(hash(dataset_version)) % 1000000)
    method_pool = (
        ["template", "mutation", "fuzzing"]
        if generation_method == "mixed"
        else [generation_method]
    )
    selected_categories = categories or TASK_CATEGORIES
    mix = _normalize_difficulty_mix(difficulty_mix or {})

    output: list[GeneratedTask] = []
    for index in range(task_count):
        category = selected_categories[index % len(selected_categories)]
        difficulty = _pick_difficulty(rng, mix)
        method = _pick_generation_method(rng, method_pool)
        base_code, expected = _template_contract(category, difficulty, index + 1)
        code = base_code
        if method == "mutation":
            code = _mutate_contract(rng, code)
        elif method == "fuzzing":
            code = _fuzz_contract(rng, code)

        hash_suffix = hashlib.sha1(f"{dataset_version}-{category}-{index}".encode()).hexdigest()[:10]
        task_id = f"{dataset_version}-{category[:8]}-{hash_suffix}"
        output.append(
            GeneratedTask(
                task_id=task_id,
                language=language,
                contract_code=code,
                expected_vulnerabilities=expected,
                difficulty=difficulty,
                category=category,
                generation_method=method,
                metadata_json={"generator_version": "1.0.0", "seed": seed, "index": index},
            )
        )

    return output
