import json

import pytest

from app.knowledge_intake import (
    approve_knowledge_draft,
    create_knowledge_draft,
    reject_knowledge_draft,
)
from app.storage.models import Project
from app.storage.repositories import TaskRepository


def _project(db_session, *, slug: str, name: str):
    project = Project(slug=slug, name=name, status="ACTIVE")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


def test_knowledge_stays_draft_until_owner_approval(db_session):
    repo = TaskRepository(db_session)
    project = _project(db_session, slug="snowpolia", name="SnowPolia")
    task = repo.create_task(owner_text="Сохранить правила экономики", project_id=project.id)

    draft = create_knowledge_draft(
        repo,
        task.id,
        material="В SnowPolia внутренняя валюта называется Snow. Источник предоставлен владельцем.",
        title="Валюта SnowPolia",
        source_locator="owner:mission-chat",
        category="product",
    )

    assert draft["status"] == "pending_owner_approval"
    assert repo.list_memory_entries(project.id) == []

    published = approve_knowledge_draft(repo, task.id, owner_id="owner", note="Подтверждаю")

    entries = repo.list_memory_entries(project.id)
    assert published["status"] == "published"
    assert len(entries) == 1
    payload = json.loads(entries[0].content)
    assert payload["approved_by"] == "owner"
    assert payload["claims"][0]["kind"] == "fact_candidate"
    assert payload["confidence"][0]["score"] == 0.55


def test_rejected_knowledge_never_reaches_canonical_memory(db_session):
    repo = TaskRepository(db_session)
    project = _project(db_session, slug="extreme-media", name="ExtremeMedia")
    task = repo.create_task(owner_text="Проверить знание", project_id=project.id)
    create_knowledge_draft(
        repo,
        task.id,
        material="Это утверждение требует проверки владельцем.",
        title="Непроверенное утверждение",
        source_locator="owner:mission-chat",
    )

    rejected = reject_knowledge_draft(repo, task.id, reason="Источник недостаточно надёжен")

    assert rejected["status"] == "rejected"
    assert repo.list_memory_entries(project.id) == []
    with pytest.raises(ValueError, match="Нет черновика"):
        approve_knowledge_draft(repo, task.id)


def test_knowledge_api_requires_owner_key_and_separate_approval(
    client, auth_headers, db_session
):
    repo = TaskRepository(db_session)
    project = _project(db_session, slug="sponsor", name="Sponsorship Platform")
    task = repo.create_task(owner_text="Добавить знание", project_id=project.id)
    body = {
        "material": "Партнёрские права подтверждаются только явным документом.",
        "title": "Правило подтверждения прав",
        "source_locator": "owner:mission-chat",
        "category": "policy",
    }

    assert client.post(f"/api/tasks/{task.id}/knowledge/draft", json=body).status_code == 401
    created = client.post(
        f"/api/tasks/{task.id}/knowledge/draft", json=body, headers=auth_headers
    )
    assert created.status_code == 200
    assert created.json()["draft"]["status"] == "pending_owner_approval"

    approved = client.post(
        f"/api/tasks/{task.id}/knowledge/approve",
        json={"note": "Подтверждено"},
        headers=auth_headers,
    )
    assert approved.status_code == 200
    assert approved.json()["draft"]["status"] == "published"


def test_mission_chat_can_create_knowledge_draft_before_owner_approval(
    client, auth_headers, db_session
):
    repo = TaskRepository(db_session)
    project = _project(db_session, slug="ai-office", name="AI Office")
    task = repo.create_task(owner_text="Сохранить правило из чата", project_id=project.id)

    response = client.post(
        f"/api/tasks/{task.id}/chat",
        json={"message": "В базу знаний: Owner approval обязателен перед публикацией факта."},
        headers=auth_headers,
    )

    assert response.status_code == 200
    messages = response.json()["messages"]
    assert any(message["speaker_code"] == "COORDINATOR" for message in messages)
    assert repo.list_memory_entries(project.id) == []
    db_session.expire_all()
    task_after_chat = repo.get_task(task.id)
    draft = task_after_chat.business_action_json["knowledge_intake"]
    assert draft["status"] == "pending_owner_approval"
    assert draft["claims"][0]["statement"] == "Owner approval обязателен перед публикацией факта."

    approved = client.post(
        f"/api/tasks/{task.id}/knowledge/approve",
        json={"note": "Подтверждено из теста"},
        headers=auth_headers,
    )

    assert approved.status_code == 200
    assert approved.json()["draft"]["status"] == "published"
    assert len(repo.list_memory_entries(project.id)) == 1
