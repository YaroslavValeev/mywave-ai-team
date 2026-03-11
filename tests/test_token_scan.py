# tests/test_token_scan.py — логика token leakage scan (v0.2.1)
import tempfile
from pathlib import Path


def _scan_content(content: str, patterns: list[str]) -> bool:
    """Возвращает True если найдено совпадение (leak)."""
    import re
    for p in patterns:
        if re.search(p, content):
            return True
    return False


def test_token_scan_detects_ghp():
    """ghp_ паттерн обнаруживается (CI token-scan исключает этот файл)."""
    patterns = [r"ghp_", r"github_pat_", r"sk-[a-zA-Z0-9]{20,}", r"xoxb-[a-zA-Z0-9]{10,}", r"-----BEGIN (RSA )?PRIVATE KEY"]
    assert _scan_content("token=ghp_FAKE123", patterns) is True
    assert _scan_content("xoxb-abc123xyz12", patterns) is True


def test_token_scan_clean_content():
    """Чистый контент не срабатывает."""
    patterns = [r"ghp_", r"github_pat_"]
    assert _scan_content("token=placeholder", patterns) is False
    assert _scan_content("# GH_TOKEN from env", patterns) is False
