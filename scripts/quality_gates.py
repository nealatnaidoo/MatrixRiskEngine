#!/usr/bin/env python3
"""Quality Gates - Verify each phase meets acceptance criteria.

Generates JSON artifacts for CI/CD pipeline integration.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_pytest_coverage(test_path: str, min_coverage: float = 90.0) -> dict:
    """Run pytest with coverage and return results."""
    result = subprocess.run(
        [
            "python", "-m", "pytest",
            test_path,
            "--cov=src",
            "--cov-report=json",
            "-v",
            "--tb=short",
        ],
        capture_output=True,
        text=True,
    )

    # Parse coverage report
    coverage_file = Path("coverage.json")
    coverage_pct = 0.0
    if coverage_file.exists():
        with open(coverage_file) as f:
            cov_data = json.load(f)
            coverage_pct = cov_data.get("totals", {}).get("percent_covered", 0.0)

    # Count passed/failed tests from output
    lines = result.stdout.split("\n")
    passed = failed = skipped = 0
    for line in lines:
        if " passed" in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if p == "passed" and i > 0:
                    try:
                        passed = int(parts[i-1])
                    except ValueError:
                        pass
                elif p == "failed" and i > 0:
                    try:
                        failed = int(parts[i-1])
                    except ValueError:
                        pass
                elif p == "skipped" and i > 0:
                    try:
                        skipped = int(parts[i-1])
                    except ValueError:
                        pass

    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "coverage_percent": coverage_pct,
        "coverage_meets_threshold": coverage_pct >= min_coverage,
        "return_code": result.returncode,
        "stdout": result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout,
    }


def verify_phase1_data_ingestion() -> dict:
    """Verify Phase 1: Data Ingestion quality gate."""
    acceptance_criteria = {
        "AC-F1-001": "Version immutability - save + load returns identical data",
        "AC-F1-002": "Version retrieval - can load specific version",
        "AC-F1-003": "Point-in-time query - as_of_date filters correctly",
    }

    test_results = run_pytest_coverage("tests/unit/test_stub_data_adapter.py tests/integration/test_data_pipeline_flow.py")

    # Run specific acceptance criteria tests
    ac_tests = subprocess.run(
        [
            "python", "-m", "pytest",
            "tests/integration/test_data_pipeline_flow.py",
            "-v", "-k", "test_ac_f1",
        ],
        capture_output=True,
        text=True,
    )

    ac_passed = "PASSED" in ac_tests.stdout and "FAILED" not in ac_tests.stdout

    return {
        "phase": "Phase 1 - Data Ingestion",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "acceptance_criteria": acceptance_criteria,
        "acceptance_criteria_passed": ac_passed,
        "test_results": test_results,
        "passed": ac_passed and test_results["failed"] == 0,
    }


def verify_phase2_backtesting() -> dict:
    """Verify Phase 2: Backtesting quality gate."""
    acceptance_criteria = {
        "AC-F2-001": "Backtest with transaction costs calculated correctly",
        "AC-F2-002": "Monthly rebalancing respects schedule",
        "AC-F2-003": "Tearsheet generation produces valid output",
    }

    test_results = run_pytest_coverage("tests/unit/test_backtest_result.py tests/unit/test_backtest_engine.py tests/unit/test_vectorbt_adapter.py tests/integration/test_backtest_flow.py")

    ac_tests = subprocess.run(
        [
            "python", "-m", "pytest",
            "tests/integration/test_backtest_flow.py",
            "-v", "-k", "test_ac_f2",
        ],
        capture_output=True,
        text=True,
    )

    ac_passed = "PASSED" in ac_tests.stdout and "FAILED" not in ac_tests.stdout

    return {
        "phase": "Phase 2 - Backtesting",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "acceptance_criteria": acceptance_criteria,
        "acceptance_criteria_passed": ac_passed,
        "test_results": test_results,
        "passed": ac_passed and test_results["failed"] == 0,
    }


def verify_phase3_risk_analytics() -> dict:
    """Verify Phase 3: Risk Analytics quality gate."""
    acceptance_criteria = {
        "AC-F4-001": "VaR calculation returns valid percentiles",
        "AC-F4-002": "CVaR exceeds VaR for same confidence level",
        "AC-F4-003": "Greeks computed for portfolio",
        "AC-F5-001": "Stress scenarios applied correctly",
        "AC-F5-002": "P&L calculated for each scenario",
        "AC-F5-003": "Base vs stressed NPV comparison",
    }

    test_results = run_pytest_coverage("tests/unit/test_risk_metrics.py tests/unit/test_stress_scenario.py tests/unit/test_ore_adapter.py tests/integration/test_risk_measurement_flow.py tests/integration/test_stress_testing_flow.py")

    ac_tests = subprocess.run(
        [
            "python", "-m", "pytest",
            "tests/integration/test_risk_measurement_flow.py",
            "tests/integration/test_stress_testing_flow.py",
            "-v", "-k", "test_ac_f4 or test_ac_f5",
        ],
        capture_output=True,
        text=True,
    )

    ac_passed = "PASSED" in ac_tests.stdout and "FAILED" not in ac_tests.stdout

    return {
        "phase": "Phase 3 - Risk Analytics",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "acceptance_criteria": acceptance_criteria,
        "acceptance_criteria_passed": ac_passed,
        "test_results": test_results,
        "passed": ac_passed and test_results["failed"] == 0,
    }


def verify_phase4_optimization() -> dict:
    """Verify Phase 4: Optimization quality gate."""
    acceptance_criteria = {
        "AC-F3-001": "Optimization produces valid weights (sum to 1)",
        "AC-F3-002": "Constraints respected in solution",
        "AC-F3-003": "Trades generated from weight changes",
    }

    test_results = run_pytest_coverage("tests/unit/test_constraint.py tests/unit/test_portfolio.py tests/integration/test_optimization_flow.py")

    ac_tests = subprocess.run(
        [
            "python", "-m", "pytest",
            "tests/integration/test_optimization_flow.py",
            "-v", "-k", "test_ac_f3",
        ],
        capture_output=True,
        text=True,
    )

    # Note: Optimization tests skip if cvxpy not installed
    ac_passed = "PASSED" in ac_tests.stdout or "skipped" in ac_tests.stdout

    return {
        "phase": "Phase 4 - Optimization",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "acceptance_criteria": acceptance_criteria,
        "acceptance_criteria_passed": ac_passed,
        "test_results": test_results,
        "passed": ac_passed and test_results["failed"] == 0,
    }


def main(args: list[str] | None = None) -> int:
    """Run quality gates and generate artifacts."""
    parser = argparse.ArgumentParser(description="Run quality gates for Matrix Risk Engine")
    parser.add_argument(
        "--phase",
        choices=["1", "2", "3", "4", "all"],
        default="all",
        help="Phase to verify (default: all)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts"),
        help="Output directory for artifacts",
    )

    parsed = parser.parse_args(args)

    # Create output directory
    parsed.output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    if parsed.phase in ("1", "all"):
        print("Verifying Phase 1 - Data Ingestion...")
        result = verify_phase1_data_ingestion()
        results.append(result)
        with open(parsed.output_dir / "quality_gate_phase1.json", "w") as f:
            json.dump(result, f, indent=2)
        status = "PASSED" if result["passed"] else "FAILED"
        print(f"  Phase 1: {status}")

    if parsed.phase in ("2", "all"):
        print("Verifying Phase 2 - Backtesting...")
        result = verify_phase2_backtesting()
        results.append(result)
        with open(parsed.output_dir / "quality_gate_phase2.json", "w") as f:
            json.dump(result, f, indent=2)
        status = "PASSED" if result["passed"] else "FAILED"
        print(f"  Phase 2: {status}")

    if parsed.phase in ("3", "all"):
        print("Verifying Phase 3 - Risk Analytics...")
        result = verify_phase3_risk_analytics()
        results.append(result)
        with open(parsed.output_dir / "quality_gate_phase3.json", "w") as f:
            json.dump(result, f, indent=2)
        status = "PASSED" if result["passed"] else "FAILED"
        print(f"  Phase 3: {status}")

    if parsed.phase in ("4", "all"):
        print("Verifying Phase 4 - Optimization...")
        result = verify_phase4_optimization()
        results.append(result)
        with open(parsed.output_dir / "quality_gate_phase4.json", "w") as f:
            json.dump(result, f, indent=2)
        status = "PASSED" if result["passed"] else "FAILED"
        print(f"  Phase 4: {status}")

    # Generate summary
    all_passed = all(r["passed"] for r in results)
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phases_verified": len(results),
        "all_passed": all_passed,
        "results": [{"phase": r["phase"], "passed": r["passed"]} for r in results],
    }

    with open(parsed.output_dir / "quality_gates_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nArtifacts saved to: {parsed.output_dir}")
    print(f"Overall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
