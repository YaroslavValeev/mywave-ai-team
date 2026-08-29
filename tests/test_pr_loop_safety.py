import asyncio

from app.runners.cursor_runner import pr_loop


def test_manual_mode_has_no_side_effects(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(pr_loop, "_run", lambda *args, **kwargs: calls.append(args) or (0, "", ""))

    result = asyncio.run(pr_loop.run_pr_loop(1, str(tmp_path), mode="manual"))

    assert result["success"] is False
    assert result["requires_owner_action"] is True
    assert calls == []


def test_dirty_workspace_is_rejected_before_branch(tmp_path, monkeypatch):
    monkeypatch.setattr(pr_loop.api_client, "task_get", lambda task_id: ({"id": task_id}, None))
    monkeypatch.setattr(pr_loop.api_client, "artifacts_list", lambda task_id: ([], None))
    calls = []

    def fake_run(command, cwd, env=None):
        calls.append(command)
        return 0, " M user-change.txt\n", ""

    monkeypatch.setattr(pr_loop, "_run", fake_run)
    result = asyncio.run(
        pr_loop.run_pr_loop(2, str(tmp_path), apply_callback=lambda *_: None, mode="patch")
    )

    assert result["success"] is False
    assert "clean" in result["error"]
    assert not any(command[:3] == ["git", "checkout", "-b"] for command in calls)


def test_failed_tests_block_commit_and_push(tmp_path, monkeypatch):
    monkeypatch.setattr(pr_loop.api_client, "task_get", lambda task_id: ({"id": task_id}, None))
    monkeypatch.setattr(pr_loop, "merge_gateway_secrets_into_env", lambda *args: {"GH_TOKEN": "test"})
    calls = []
    status_calls = 0

    def fake_run(command, cwd, env=None):
        nonlocal status_calls
        calls.append(command)
        if command[:2] == ["git", "status"]:
            status_calls += 1
            return (0, "" if status_calls == 1 else " M app/file.py\n", "")
        if command[:3] == ["python", "-m", "pytest"]:
            return 1, "failed", "assertion"
        return 0, "", ""

    monkeypatch.setattr(pr_loop, "_run", fake_run)
    result = asyncio.run(
        pr_loop.run_pr_loop(3, str(tmp_path), apply_callback=lambda *_: None, mode="patch")
    )

    assert result["success"] is False
    assert "Validation failed" in result["error"]
    assert not any(command[:2] == ["git", "commit"] for command in calls)
    assert not any(command[:2] == ["git", "push"] for command in calls)


def test_branch_creation_failure_is_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(pr_loop.api_client, "task_get", lambda task_id: ({"id": task_id}, None))
    monkeypatch.setattr(pr_loop, "merge_gateway_secrets_into_env", lambda *args: {"GH_TOKEN": "test"})
    calls = []

    def fake_run(command, cwd, env=None):
        calls.append(command)
        if command[:2] == ["git", "status"]:
            return 0, "", ""
        if command[:3] == ["git", "checkout", "-b"]:
            return 128, "", "branch already exists"
        return 0, "", ""

    monkeypatch.setattr(pr_loop, "_run", fake_run)
    applied = []
    result = asyncio.run(
        pr_loop.run_pr_loop(5, str(tmp_path), apply_callback=lambda *_: applied.append(True), mode="patch")
    )

    assert result["success"] is False
    assert "branch creation failed" in result["error"]
    assert applied == []


def test_executable_mode_requires_apply_callback(tmp_path):
    result = asyncio.run(pr_loop.run_pr_loop(4, str(tmp_path), mode="cursor_agent"))

    assert result["success"] is False
    assert "apply_callback" in result["error"]
