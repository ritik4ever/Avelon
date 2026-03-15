// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title VulnerableBank
 * @notice Deliberately vulnerable contract for Avelon benchmarking.
 * Contains: reentrancy, unchecked return, access control issues.
 */
contract VulnerableBank {
    mapping(address => uint256) public balances;
    address public owner;
    bool private locked;

    constructor() {
        owner = msg.sender;
    }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    // VULNERABILITY: Reentrancy — state updated after external call
    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "Insufficient balance");

        (bool success, ) = msg.sender.call{value: amount}("");
        require(success, "Transfer failed");

        balances[msg.sender] -= amount; // State change after external call
    }

    // VULNERABILITY: Unchecked return value
    function unsafeTransfer(address payable to, uint256 amount) external {
        require(msg.sender == owner, "Not owner");
        to.send(amount); // Return value not checked
    }

    // VULNERABILITY: Missing access control
    function destroyContract() external {
        selfdestruct(payable(msg.sender)); // Anyone can call
    }

    // VULNERABILITY: tx.origin authentication
    function transferOwnership(address newOwner) external {
        require(tx.origin == owner, "Not owner"); // Uses tx.origin instead of msg.sender
        owner = newOwner;
    }

    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }

    receive() external payable {}
}
