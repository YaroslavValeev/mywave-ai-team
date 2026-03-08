# tests/test_runner_contract.py — dry-run: формирование команд/отчёта (v0.2)
import tempfile
from pathlib import Path

import pytest

from app.runners.cursor_runner.pr_loop import _build_dev_report


def test_build_dev_report():
    """DEV REPORT содержит task_id, mode, файлы, pytest status, Owner steps."""
    report = _build_dev_report(
        task_id=42,
        summary="Added feature X",
        changed_files=["app/foo.py", "tests/test_foo.py"],
        pytest_ok=True,
        mode="manual",
    )
    assert "task_id" in report and "42" in report
    assert "mode" in report and "manual" in report
    assert "Owner next steps" in report
    assert "app/foo.py" in report
    assert "pytest" in report.lower()
    assert "passed" in report.lower() or "✅" in report


def test_build_dev_report_pytest_failed():
    """DEV REPORT при failed pytest."""
    report = _build_dev_report(task_id=1, summary="", changed_files=[], pytest_ok=False, mode="manual")
    assert "failed" in report.lower() or "❌" in report


def test_runner_no_merge_in_code():
    """Runner запрещает merge — константа MERGE_FORBIDDEN."""
    from app.runners.cursor_runner import pr_loop
    assert pr_loop.MERGE_FORBIDDEN is True
