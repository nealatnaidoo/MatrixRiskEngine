"""Unit tests for Quality Gates framework."""

import pytest
from pathlib import Path

from src.core.quality_gates import (
    GateStatus,
    GateResult,
    QualityGateReport,
    QualityGateRunner,
)


class TestGateResult:
    """Test GateResult dataclass."""

    def test_gate_result_creation(self) -> None:
        """GateResult should be created with required fields."""
        result = GateResult(
            name="Test Gate",
            status=GateStatus.PASS,
            message="All checks passed",
        )

        assert result.name == "Test Gate"
        assert result.status == GateStatus.PASS

    def test_gate_result_to_dict(self) -> None:
        """to_dict should return serializable dictionary."""
        result = GateResult(
            name="Test Gate",
            status=GateStatus.FAIL,
            message="Check failed",
            details={"error_count": 5},
        )

        d = result.to_dict()

        assert d["name"] == "Test Gate"
        assert d["status"] == "FAIL"
        assert d["details"]["error_count"] == 5


class TestQualityGateReport:
    """Test QualityGateReport dataclass."""

    def test_report_creation(self) -> None:
        """QualityGateReport should be created correctly."""
        gate = GateResult(
            name="Test",
            status=GateStatus.PASS,
            message="OK",
        )

        report = QualityGateReport(
            timestamp="2026-01-25T00:00:00Z",
            overall_status=GateStatus.PASS,
            gates=[gate],
            summary={"PASS": 1, "FAIL": 0, "WARN": 0, "SKIP": 0, "ERROR": 0},
        )

        assert report.overall_status == GateStatus.PASS
        assert len(report.gates) == 1

    def test_report_to_dict(self) -> None:
        """to_dict should return complete serializable dictionary."""
        gate = GateResult(
            name="Test",
            status=GateStatus.PASS,
            message="OK",
        )

        report = QualityGateReport(
            timestamp="2026-01-25T00:00:00Z",
            overall_status=GateStatus.PASS,
            gates=[gate],
            summary={"PASS": 1, "FAIL": 0, "WARN": 0, "SKIP": 0, "ERROR": 0},
        )

        d = report.to_dict()

        assert d["overall_status"] == "PASS"
        assert len(d["gates"]) == 1

    def test_report_save(self, tmp_path: Path) -> None:
        """save should write JSON file."""
        gate = GateResult(
            name="Test",
            status=GateStatus.PASS,
            message="OK",
        )

        report = QualityGateReport(
            timestamp="2026-01-25T00:00:00Z",
            overall_status=GateStatus.PASS,
            gates=[gate],
            summary={"PASS": 1, "FAIL": 0, "WARN": 0, "SKIP": 0, "ERROR": 0},
        )

        output_file = tmp_path / "report.json"
        report.save(output_file)

        assert output_file.exists()
        import json
        with open(output_file) as f:
            data = json.load(f)
        assert data["overall_status"] == "PASS"


class TestQualityGateRunner:
    """Test QualityGateRunner."""

    def test_register_and_run(self, tmp_path: Path) -> None:
        """Runner should execute registered gates."""
        runner = QualityGateRunner(artifacts_dir=tmp_path)

        def passing_gate() -> GateResult:
            return GateResult(
                name="Passing Gate",
                status=GateStatus.PASS,
                message="All good",
            )

        def failing_gate() -> GateResult:
            return GateResult(
                name="Failing Gate",
                status=GateStatus.FAIL,
                message="Something wrong",
            )

        runner.register("pass", passing_gate)
        runner.register("fail", failing_gate)

        report = runner.run_all()

        assert len(report.gates) == 2
        assert report.summary["PASS"] == 1
        assert report.summary["FAIL"] == 1
        assert report.overall_status == GateStatus.FAIL

    def test_error_handling(self, tmp_path: Path) -> None:
        """Runner should handle gate exceptions."""
        runner = QualityGateRunner(artifacts_dir=tmp_path)

        def error_gate() -> GateResult:
            raise RuntimeError("Gate crashed")

        runner.register("error", error_gate)

        report = runner.run_all()

        assert report.summary["ERROR"] == 1
        assert report.overall_status == GateStatus.FAIL

    def test_run_and_save(self, tmp_path: Path) -> None:
        """run_and_save should create output file."""
        runner = QualityGateRunner(artifacts_dir=tmp_path)

        def passing_gate() -> GateResult:
            return GateResult(
                name="Test",
                status=GateStatus.PASS,
                message="OK",
            )

        runner.register("test", passing_gate)

        report = runner.run_and_save("test_output.json")

        assert (tmp_path / "test_output.json").exists()
        assert report.overall_status == GateStatus.PASS

    def test_warn_status(self, tmp_path: Path) -> None:
        """Overall status should be WARN if only warnings."""
        runner = QualityGateRunner(artifacts_dir=tmp_path)

        def warn_gate() -> GateResult:
            return GateResult(
                name="Warning Gate",
                status=GateStatus.WARN,
                message="Minor issue",
            )

        runner.register("warn", warn_gate)

        report = runner.run_all()

        assert report.overall_status == GateStatus.WARN

    def test_metadata_included(self, tmp_path: Path) -> None:
        """Metadata should be included in report."""
        runner = QualityGateRunner(artifacts_dir=tmp_path)

        def passing_gate() -> GateResult:
            return GateResult(
                name="Test",
                status=GateStatus.PASS,
                message="OK",
            )

        runner.register("test", passing_gate)

        report = runner.run_all(metadata={"project": "test"})

        assert report.metadata["project"] == "test"
