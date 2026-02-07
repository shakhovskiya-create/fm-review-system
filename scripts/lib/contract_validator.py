#!/usr/bin/env python3
"""
Contract Validator for Inter-Agent Communication v1.0 (R-08)

Validates agent outputs against JSON Schema contracts.

Usage:
    from lib.contract_validator import validate_agent_output

    # Validate Agent 1 output
    result = validate_agent_output("Agent1_Architect", {
        "findings": [...],
        "summary": {"critical": 2, "high": 3, "medium": 5, "low": 1}
    })

    if not result.valid:
        print(f"Validation errors: {result.errors}")
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


# Schema file location
SCHEMA_FILE = Path(__file__).parent.parent.parent / "schemas" / "agent-contracts.json"


@dataclass
class ValidationResult:
    """Result of contract validation"""
    valid: bool
    errors: List[str]
    warnings: List[str]


class ContractValidator:
    """Validator for inter-agent communication contracts"""

    def __init__(self):
        self.schema = self._load_schema()

    def _load_schema(self) -> Dict:
        """Load JSON Schema from file"""
        if SCHEMA_FILE.exists():
            with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def validate_finding(self, finding: Dict) -> ValidationResult:
        """Validate a single finding object"""
        errors = []
        warnings = []

        # Required fields
        required = ["id", "severity", "category", "description"]
        for field in required:
            if field not in finding:
                errors.append(f"Missing required field: {field}")

        # ID format
        if "id" in finding:
            pattern = r"^(CRITICAL|HIGH|MEDIUM|LOW)-[0-9]{3}$"
            if not re.match(pattern, finding["id"]):
                errors.append(f"Invalid finding ID format: {finding['id']}. Expected: SEVERITY-NNN")

        # Severity validation
        if "severity" in finding:
            valid_severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
            if finding["severity"] not in valid_severities:
                errors.append(f"Invalid severity: {finding['severity']}")

        # Category validation
        if "category" in finding:
            valid_categories = ["LOGIC", "UX", "PERFORMANCE", "SECURITY", "INTEGRATION", "1C"]
            if finding["category"] not in valid_categories:
                warnings.append(f"Non-standard category: {finding['category']}")

        # Description length
        if "description" in finding:
            if len(finding["description"]) < 10:
                warnings.append("Description too short (< 10 chars)")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_test_case(self, test_case: Dict) -> ValidationResult:
        """Validate a single test case"""
        errors = []
        warnings = []

        required = ["id", "title", "steps", "expected"]
        for field in required:
            if field not in test_case:
                errors.append(f"Missing required field: {field}")

        # ID format
        if "id" in test_case:
            pattern = r"^TC-[0-9]{3}$"
            if not re.match(pattern, test_case["id"]):
                errors.append(f"Invalid test case ID format: {test_case['id']}. Expected: TC-NNN")

        # Steps must be non-empty
        if "steps" in test_case:
            if not isinstance(test_case["steps"], list) or len(test_case["steps"]) == 0:
                errors.append("Test case must have at least one step")

        # Traceability recommended
        if "traceability" not in test_case:
            warnings.append("No traceability reference (finding or requirement)")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_publish_result(self, result: Dict) -> ValidationResult:
        """Validate publish result from Agent 7"""
        errors = []
        warnings = []

        required = ["pageId", "version", "url", "timestamp"]
        for field in required:
            if field not in result:
                errors.append(f"Missing required field: {field}")

        # URL format
        if "url" in result:
            if not result["url"].startswith("http"):
                errors.append(f"Invalid URL format: {result['url']}")

        # Version must be positive
        if "version" in result:
            if not isinstance(result["version"], int) or result["version"] < 1:
                errors.append("Version must be a positive integer")

        # FM version format
        if "fmVersion" in result:
            pattern = r"^[0-9]+\.[0-9]+\.[0-9]+$"
            if not re.match(pattern, result["fmVersion"]):
                warnings.append(f"Non-standard FM version format: {result['fmVersion']}")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def validate_agent_output(self, agent_type: str, output: Dict) -> ValidationResult:
        """
        Validate full agent output.

        Args:
            agent_type: One of Agent0_Creator, Agent1_Architect, etc.
            output: The output dictionary from the agent

        Returns:
            ValidationResult with valid flag and any errors/warnings
        """
        errors = []
        warnings = []

        if agent_type == "Agent1_Architect":
            if "findings" not in output:
                errors.append("Agent1 output must contain 'findings' array")
            else:
                for i, finding in enumerate(output["findings"]):
                    result = self.validate_finding(finding)
                    if not result.valid:
                        errors.extend([f"Finding[{i}]: {e}" for e in result.errors])
                    warnings.extend([f"Finding[{i}]: {w}" for w in result.warnings])

            if "summary" not in output:
                warnings.append("Missing summary object")

        elif agent_type == "Agent2_Simulator":
            if "uxFindings" not in output:
                errors.append("Agent2 output must contain 'uxFindings' array")
            if "roles" not in output:
                warnings.append("Missing roles array")

        elif agent_type == "Agent4_QA":
            if "testCases" not in output:
                errors.append("Agent4 output must contain 'testCases' array")
            else:
                for i, tc in enumerate(output["testCases"]):
                    result = self.validate_test_case(tc)
                    if not result.valid:
                        errors.extend([f"TestCase[{i}]: {e}" for e in result.errors])
                    warnings.extend([f"TestCase[{i}]: {w}" for w in result.warnings])

        elif agent_type == "Agent7_Publisher":
            if "result" not in output:
                errors.append("Agent7 output must contain 'result' object")
            else:
                result = self.validate_publish_result(output["result"])
                errors.extend(result.errors)
                warnings.extend(result.warnings)

        elif agent_type == "Agent8_BPMN":
            if "result" not in output:
                errors.append("Agent8 output must contain 'result' object")
            else:
                required = ["diagramName", "format", "status"]
                for field in required:
                    if field not in output["result"]:
                        errors.append(f"BPMN result missing: {field}")

        else:
            warnings.append(f"Unknown agent type: {agent_type}, skipping validation")

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )


# Convenience function
def validate_agent_output(agent_type: str, output: Dict) -> ValidationResult:
    """Validate agent output against contract schema"""
    validator = ContractValidator()
    return validator.validate_agent_output(agent_type, output)


if __name__ == "__main__":
    # Test the validator
    print("Contract Validator v1.0")
    print("=" * 40)

    # Test finding validation
    test_finding = {
        "id": "CRITICAL-001",
        "severity": "CRITICAL",
        "category": "LOGIC",
        "description": "Race condition in concurrent access"
    }

    validator = ContractValidator()
    result = validator.validate_finding(test_finding)
    print(f"Finding validation: valid={result.valid}")
    if result.errors:
        print(f"  Errors: {result.errors}")
    if result.warnings:
        print(f"  Warnings: {result.warnings}")

    # Test Agent1 output
    agent1_output = {
        "findings": [test_finding],
        "summary": {"critical": 1, "high": 0, "medium": 0, "low": 0}
    }

    result = validate_agent_output("Agent1_Architect", agent1_output)
    print(f"\nAgent1 output validation: valid={result.valid}")
