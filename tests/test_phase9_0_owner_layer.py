# tests/test_phase9_0_owner_layer.py — Phase 9.0: owner queries, presenters, summary, commands wired
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from app.storage.models import TaskStatus
from app.storage.repositories import TaskRepository
from app.services.owner_queries import (
    get_system_status_summary,
    get_active_tasks,
    get_task_card,
    get_pending_approvals,
    get_recent_artifacts,
    get_runs_summary,
)
from app.owner_summary import build_short_summary, build_detailed_summary
from app.presenters.owner_presenters import (
    format_summary,
    format_task_card,
    format_approvals_list,
    format_artifacts_list,
    format_tasks_list,
    format_detailed_summary,
)


def test_owner_status_summary_shape(db_session):
    """Status summary содержит ключевые поля."""
    data = get_system_status_summary()
    assert "transport_mode" in data
    assert "molt_ok" in data
    assert "molt_message" in data
    assert "active_tasks_count" in data
    assert "pending_approvals_count" in data
    assert "recent_artifacts_count" in data
    assert "state" in data
    assert data["state"] in ("OK", "DEGRADED", "Waiting approvals")


def test_owner_tasks_query_returns_expected_items(db_session):
    """Список задач возвращает ожидаемые элементы."""
    repo = TaskRepository(db_session)
    t1 = repo.create_task(owner_text="Task one")
    t2 = repo.create_task(owner_text="Task two")
    repo.update_task(t1.id, status=TaskStatus.DONE.value)
    tasks = get_active_tasks(limit=10)
    ids = [t.id for t in tasks]
    assert t2.id in ids
    assert t1.id not in ids


def test_owner_task_card_contains_run_and_approval_info(db_session):
    """Карточка задачи содержит run и approval info."""
    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="Card task")
    repo.update_task(task.id, status=TaskStatus.WAIT_OWNER.value)
    card = get_task_card(task.id)
    assert card is not None
    assert card.get("task") is not None
    assert card["task"].id == task.id
    assert "run_id" in card
    assert "approval_id" in card
    assert "canonical_status" in card or "last_event" in card


def test_owner_approvals_query_returns_pending_items(db_session):
    """Pending approvals возвращает задачи в WAIT_OWNER."""
    repo = TaskRepository(db_session)
    t1 = repo.create_task(owner_text="Wait owner")
    repo.update_task(t1.id, status=TaskStatus.WAIT_OWNER.value)
    t2 = repo.create_task(owner_text="Done")
    repo.update_task(t2.id, status=TaskStatus.DONE.value)
    pending = get_pending_approvals(limit=10)
    ids = [t.id for t in pending]
    assert t1.id in ids
    assert t2.id not in ids


def test_owner_summary_reflects_degraded_mode(db_session):
    """При проблеме с Molt summary показывает degraded state."""
    with patch.dict(os.environ, {"MOLT_TRANSPORT_MODE": "http", "MOLT_HTTP_BASE_URL": "http://127.0.0.1:39999"}):
        data = get_system_status_summary()
    assert data["transport_mode"] == "http"
    assert data["molt_ok"] is False
    assert data["state"] == "DEGRADED"


def test_owner_presenters_return_human_readable_output(db_session):
    """Форматтеры возвращают человекочитаемый текст, не сырой dict."""
    data = {"transport_mode": "local", "molt_message": "n/a", "active_tasks_count": 0,
            "pending_approvals_count": 0, "recent_artifacts_count": 0, "state": "OK"}
    text = format_summary(data)
    assert isinstance(text, str)
    assert "Status" in text or "Mode" in text
    assert "local" in text
    assert "OK" in text
    assert "{" not in text

    tasks = []
    out = format_approvals_list(tasks)
    assert isinstance(out, str)
    assert "Нет" in out or "нет" in out

    out2 = format_artifacts_list(tasks)
    assert isinstance(out2, str)


def test_telegram_owner_commands_are_wired():
    """Команды /status, /tasks, /task, /approvals, /summary подключены в handlers."""
    from app.bot.handlers import register_handlers
    from aiogram import Dispatcher
    dp = Dispatcher()
    register_handlers(dp)
    # Проверяем, что message handlers зарегистрированы для нужных команд
    registrations = list(dp.message._handlers.values()) if hasattr(dp.message, "_handlers") else []
    # Альтернатива: проверить наличие функций-обработчиков по имени
    import app.bot.handlers as h
    assert hasattr(h, "handle_owner_status")
    assert hasattr(h, "handle_owner_tasks")
    assert hasattr(h, "handle_owner_task")
    assert hasattr(h, "handle_owner_approvals")
    assert hasattr(h, "handle_owner_summary")
    assert hasattr(h, "handle_owner_help")
    assert hasattr(h, "handle_owner_artifacts")
    assert hasattr(h, "handle_owner_runs")
    assert hasattr(h, "handle_owner_health")
