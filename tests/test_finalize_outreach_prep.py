from pathlib import Path
import csv
import importlib.util
import sys


def _load_mod():
    path = Path(__file__).resolve().parents[1] / "scripts" / "finalize_outreach_prep.py"
    spec = importlib.util.spec_from_file_location("finalize_outreach_prep", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_finalize_outreach_prep_writes_segments(tmp_path, monkeypatch):
    """Prep copies CSV, splits segments, updates send_log — never sends."""
    mod = _load_mod()

    artifacts = tmp_path / "app" / "artifacts"
    src_dir = artifacts / "tasks" / "task_32" / "execution"
    src_dir.mkdir(parents=True)
    src = src_dir / "parsernews_outreach_contacts_20260727.csv"
    src.write_text(
        "channel,value,source,consent_required,notes\n"
        "email,a@example.com,S,yes,n\n"
        "telegram_username,user1,1,yes,n\n"
        "telegram_username,user2,2,yes,n\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mod, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["finalize_outreach_prep.py", "--task-id", "33", "--artifacts-dir", str(artifacts)],
    )
    rc = mod.main()
    assert rc == 0
    exe = artifacts / "tasks" / "task_33" / "execution"
    assert (exe / "contacts_unique.csv").is_file()
    assert (exe / "segment_emails_pilot.csv").is_file()
    assert (exe / "segment_telegram_hold.csv").is_file()
    inv = (exe / "segment_inventory.md").read_text(encoding="utf-8")
    assert "emails: **1**" in inv
    assert "telegram_handles: **2**" in inv
    log = (exe / "send_log.md").read_text(encoding="utf-8")
    assert "recipients_sent: **0**" in log
    pilot_rows = list(csv.DictReader((exe / "segment_emails_pilot.csv").open(encoding="utf-8")))
    assert len(pilot_rows) == 1
