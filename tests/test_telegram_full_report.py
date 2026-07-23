# tests/test_telegram_full_report.py
from pathlib import Path

from app.bot.handlers import _load_full_report_text


class _T:
    def __init__(self, summary=None, report_path=None):
        self.summary = summary
        self.report_path = report_path


def test_load_full_report_from_file(tmp_path: Path):
    p = tmp_path / "final_report.md"
    p.write_text("# Отчёт\n\nПлан маркетинга 0 ₽\n", encoding="utf-8")
    text = _load_full_report_text(_T(summary="short", report_path=str(p)))
    assert "План маркетинга" in text
    assert "Отчёт" in text


def test_load_full_report_falls_back_to_summary():
    text = _load_full_report_text(_T(summary="только summary", report_path="/no/such/file.md"))
    assert text == "только summary"


def test_load_full_report_empty():
    text = _load_full_report_text(_T())
    assert "не сформирован" in text
