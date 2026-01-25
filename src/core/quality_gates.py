"""Quality Gates Framework - Automated validation and evidence generation.

This module provides a framework for running quality gates and generating
machine-readable evidence artifacts for governance.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable


class GateStatus(Enum):
    """Status of a quality gate check."""

    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"
    ERROR = "ERROR"


@dataclass
class GateResult:
    """Result of a single quality gate check."""

    name: str
    status: GateStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "duration_ms": self.duration_ms,
        }


@dataclass
class QualityGateReport:
    """Complete quality gate run report."""

    timestamp: str
    overall_status: GateStatus
    gates: list[GateResult]
    summary: dict[str, int]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "summary": self.summary,
            "gates": [g.to_dict() for g in self.gates],
            "metadata": self.metadata,
        }

    def save(self, path: str | Path) -> None:
        """Save report to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)


GateFunction = Callable[[], GateResult]


class QualityGateRunner:
    """Runner for executing quality gates and generating reports."""

    def __init__(self, artifacts_dir: str | Path = "artifacts") -> None:
        """Initialize quality gate runner.

        Args:
            artifacts_dir: Directory for output artifacts
        """
        self._artifacts_dir = Path(artifacts_dir)
        self._gates: list[tuple[str, GateFunction]] = []

    def register(self, name: str, gate_fn: GateFunction) -> None:
        """Register a quality gate.

        Args:
            name: Gate name (for display)
            gate_fn: Function that returns GateResult
        """
        self._gates.append((name, gate_fn))

    def run_all(self, metadata: dict[str, Any] | None = None) -> QualityGateReport:
        """Run all registered quality gates.

        Args:
            metadata: Additional metadata to include in report

        Returns:
            Complete quality gate report
        """
        results: list[GateResult] = []
        summary = {
            "PASS": 0,
            "FAIL": 0,
            "WARN": 0,
            "SKIP": 0,
            "ERROR": 0,
        }

        for name, gate_fn in self._gates:
            start_time = datetime.now(timezone.utc)
            try:
                result = gate_fn()
                result.duration_ms = (
                    datetime.now(timezone.utc) - start_time
                ).total_seconds() * 1000
            except Exception as e:
                result = GateResult(
                    name=name,
                    status=GateStatus.ERROR,
                    message=f"Gate execution failed: {e}",
                    details={"exception": str(e)},
                )

            results.append(result)
            summary[result.status.value] += 1

        # Determine overall status
        if summary["FAIL"] > 0 or summary["ERROR"] > 0:
            overall = GateStatus.FAIL
        elif summary["WARN"] > 0:
            overall = GateStatus.WARN
        elif summary["PASS"] > 0:
            overall = GateStatus.PASS
        else:
            overall = GateStatus.SKIP

        return QualityGateReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            overall_status=overall,
            gates=results,
            summary=summary,
            metadata=metadata or {},
        )

    def run_and_save(
        self,
        output_file: str = "quality_gates_run.json",
        metadata: dict[str, Any] | None = None,
    ) -> QualityGateReport:
        """Run all gates and save report to artifacts directory.

        Args:
            output_file: Output filename
            metadata: Additional metadata

        Returns:
            Quality gate report
        """
        report = self.run_all(metadata)
        output_path = self._artifacts_dir / output_file
        report.save(output_path)
        return report


# =============================================================================
# Built-in Quality Gates
# =============================================================================


def create_test_gate(
    test_path: str = "tests/",
    min_coverage: float = 80.0,
) -> GateFunction:
    """Create a gate that runs pytest with coverage.

    Args:
        test_path: Path to test directory
        min_coverage: Minimum coverage percentage required

    Returns:
        Gate function
    """

    def run_tests() -> GateResult:
        try:
            # Run pytest with coverage
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    test_path,
                    "-v",
                    "--tb=short",
                    f"--cov=src",
                    "--cov-report=json:artifacts/coverage.json",
                    "--cov-fail-under=0",  # Don't fail, we check manually
                ],
                capture_output=True,
                text=True,
                timeout=300,
            )

            # Parse results
            passed = result.returncode == 0

            # Try to get coverage
            coverage_pct = 0.0
            coverage_file = Path("artifacts/coverage.json")
            if coverage_file.exists():
                with open(coverage_file) as f:
                    cov_data = json.load(f)
                    coverage_pct = cov_data.get("totals", {}).get("percent_covered", 0)

            # Check coverage threshold
            coverage_ok = coverage_pct >= min_coverage

            if passed and coverage_ok:
                return GateResult(
                    name="Unit Tests",
                    status=GateStatus.PASS,
                    message=f"All tests passed, coverage {coverage_pct:.1f}%",
                    details={
                        "coverage_pct": coverage_pct,
                        "min_coverage": min_coverage,
                    },
                )
            elif passed and not coverage_ok:
                return GateResult(
                    name="Unit Tests",
                    status=GateStatus.WARN,
                    message=f"Tests passed but coverage {coverage_pct:.1f}% < {min_coverage}%",
                    details={
                        "coverage_pct": coverage_pct,
                        "min_coverage": min_coverage,
                    },
                )
            else:
                return GateResult(
                    name="Unit Tests",
                    status=GateStatus.FAIL,
                    message="Some tests failed",
                    details={
                        "stdout": result.stdout[-2000:] if result.stdout else "",
                        "stderr": result.stderr[-2000:] if result.stderr else "",
                    },
                )

        except subprocess.TimeoutExpired:
            return GateResult(
                name="Unit Tests",
                status=GateStatus.ERROR,
                message="Test execution timed out",
            )
        except Exception as e:
            return GateResult(
                name="Unit Tests",
                status=GateStatus.ERROR,
                message=f"Failed to run tests: {e}",
            )

    return run_tests


def create_type_check_gate() -> GateFunction:
    """Create a gate that runs mypy type checking.

    Returns:
        Gate function
    """

    def run_mypy() -> GateResult:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "mypy", "src/", "--ignore-missing-imports"],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                return GateResult(
                    name="Type Checking",
                    status=GateStatus.PASS,
                    message="No type errors found",
                )
            else:
                # Count errors
                error_lines = [
                    line for line in result.stdout.split("\n") if ": error:" in line
                ]
                return GateResult(
                    name="Type Checking",
                    status=GateStatus.FAIL,
                    message=f"Found {len(error_lines)} type errors",
                    details={
                        "error_count": len(error_lines),
                        "errors": error_lines[:20],  # First 20 errors
                    },
                )

        except Exception as e:
            return GateResult(
                name="Type Checking",
                status=GateStatus.ERROR,
                message=f"Failed to run mypy: {e}",
            )

    return run_mypy


def create_lint_gate() -> GateFunction:
    """Create a gate that runs ruff linting.

    Returns:
        Gate function
    """

    def run_ruff() -> GateResult:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "ruff", "check", "src/", "--output-format=json"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return GateResult(
                    name="Linting",
                    status=GateStatus.PASS,
                    message="No lint issues found",
                )
            else:
                try:
                    issues = json.loads(result.stdout) if result.stdout else []
                    return GateResult(
                        name="Linting",
                        status=GateStatus.WARN,
                        message=f"Found {len(issues)} lint issues",
                        details={
                            "issue_count": len(issues),
                            "issues": issues[:20],
                        },
                    )
                except json.JSONDecodeError:
                    return GateResult(
                        name="Linting",
                        status=GateStatus.WARN,
                        message="Lint issues found (could not parse output)",
                        details={"stdout": result.stdout[:2000]},
                    )

        except Exception as e:
            return GateResult(
                name="Linting",
                status=GateStatus.ERROR,
                message=f"Failed to run ruff: {e}",
            )

    return run_ruff


def create_default_runner() -> QualityGateRunner:
    """Create a runner with default quality gates.

    Returns:
        Configured QualityGateRunner
    """
    runner = QualityGateRunner()
    runner.register("tests", create_test_gate())
    runner.register("types", create_type_check_gate())
    runner.register("lint", create_lint_gate())
    return runner


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    runner = create_default_runner()
    report = runner.run_and_save(
        metadata={
            "project": "matrix-risk-engine",
            "triggered_by": "manual",
        }
    )

    print(f"\nQuality Gates: {report.overall_status.value}")
    print(f"Summary: {report.summary}")

    for gate in report.gates:
        status_icon = {
            GateStatus.PASS: "[OK]",
            GateStatus.FAIL: "[FAIL]",
            GateStatus.WARN: "[WARN]",
            GateStatus.SKIP: "[SKIP]",
            GateStatus.ERROR: "[ERR]",
        }.get(gate.status, "[?]")
        print(f"  {status_icon} {gate.name}: {gate.message}")

    # Exit with error if failed
    sys.exit(0 if report.overall_status != GateStatus.FAIL else 1)
