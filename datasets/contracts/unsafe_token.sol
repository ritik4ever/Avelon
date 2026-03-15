// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title UnsafeToken
 * @notice Deliberately vulnerable ERC20-like token for Avelon benchmarking.
 * Contains: integer overflow, front-running, timestamp dependence.
 */
contract UnsafeToken {
    string public name = "UnsafeToken";
    string public symbol = "UNSAFE";
    uint8 public decimals = 18;
    uint256 public totalSupply;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    address public owner;
    uint256 public rewardRate;
    uint256 public lastRewardTime;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);

    constructor(uint256 initialSupply) {
        owner = msg.sender;
        totalSupply = initialSupply;
        balanceOf[msg.sender] = initialSupply;
        lastRewardTime = block.timestamp;
    }

    function transfer(address to, uint256 value) external returns (bool) {
        require(balanceOf[msg.sender] >= value, "Insufficient balance");
        balanceOf[msg.sender] -= value;
        balanceOf[to] += value;
        emit Transfer(msg.sender, to, value);
        return true;
    }

    function approve(address spender, uint256 value) external returns (bool) {
        // VULNERABILITY: Front-running — no check-then-set pattern
        allowance[msg.sender][spender] = value;
        emit Approval(msg.sender, spender, value);
        return true;
    }

    function transferFrom(address from, address to, uint256 value) external returns (bool) {
        require(balanceOf[from] >= value, "Insufficient balance");
        require(allowance[from][msg.sender] >= value, "Allowance exceeded");

        balanceOf[from] -= value;
        balanceOf[to] += value;
        allowance[from][msg.sender] -= value;

        emit Transfer(from, to, value);
        return true;
    }

    // VULNERABILITY: Timestamp dependence for reward distribution
    function claimReward() external {
        uint256 timePassed = block.timestamp - lastRewardTime;
        uint256 reward = timePassed * rewardRate;
        balanceOf[msg.sender] += reward;
        totalSupply += reward;
        lastRewardTime = block.timestamp;
    }

    // VULNERABILITY: Arbitrary storage write via delegatecall
    function execute(address target, bytes calldata data) external {
        require(msg.sender == owner, "Not owner");
        (bool success, ) = target.delegatecall(data);
        require(success, "Delegatecall failed");
    }

    function setRewardRate(uint256 rate) external {
        require(msg.sender == owner, "Not owner");
        rewardRate = rate;
    }
}
