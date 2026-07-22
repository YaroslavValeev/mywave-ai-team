# Smart Intake v1 — контекст, проект, matcher, память
import pytest

from app.intake import NormalizeIntakeRequest, normalize_intake, task_brief_to_owner_text
from app.intake.memory_writer import write_task_memory_after_orchestration
from app.storage.models import Project, Task
from app.storage.repositories import TaskRepository


@pytest.fixture(autouse=True)
def _intake_flags(monkeypatch):
    monkeypatch.setenv("INTAKE_USE_LLM", "false")
    monkeypatch.setenv("INTAKE_V1", "true")
    monkeypatch.setenv("INTAKE_ATTACH_SIMILARITY_THRESHOLD", "0.18")


def test_v1_continuation_phrase_attach(db_session, monkeypatch):
    """DoD: «добавь к задаче про …» + похожий открытый таск → attach."""
    monkeypatch.setenv("INTAKE_ATTACH_SIMILARITY_THRESHOLD", "0.12")
    repo = TaskRepository(db_session)
    p = Project(slug="parser-proj", name="MyWave Parser", status="ACTIVE")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    t = Task(
        project_id=p.id,
        owner_text="парсер JSON поля dashboard intake модуль тесты",
        status="NEW",
    )
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)

    text = "добавь к задаче про парсер JSON ещё валидацию полей и логирование"
    resp = normalize_intake(
        NormalizeIntakeRequest(text=text, source="pytest"),
        repo=repo,
    )
    assert resp.decision == "attach"
    assert resp.matched_task_id == t.id
    assert resp.task_brief.related_task_id == t.id
    assert isinstance(resp.memory_used, bool)


def test_v1_project_id_hint(db_session):
    repo = TaskRepository(db_session)
    p = Project(slug="ai-office", name="AI Office", status="ACTIVE")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    resp = normalize_intake(
        NormalizeIntakeRequest(
            text="надо сделать новый модуль intake",
            source="pytest",
            project_id_hint=p.id,
        ),
        repo=repo,
    )
    assert resp.decision == "create"
    assert resp.matched_project_id == p.id
    assert resp.task_brief.project_id == p.id
    assert "AI Office" in resp.task_brief.project_name


def test_v1_ambiguous_projects_clarify(db_session):
    repo = TaskRepository(db_session)
    for slug, name in [("p-alpha", "Alpha Dashboard"), ("p-beta", "Beta Dashboard")]:
        db_session.add(Project(slug=slug, name=name, status="ACTIVE"))
    db_session.commit()

    text = "нужно правка для Alpha Dashboard и Beta Dashboard сразу"
    resp = normalize_intake(NormalizeIntakeRequest(text=text, source="pytest"), repo=repo)
    assert resp.decision == "clarify"
    assert resp.needs_clarification is True
    assert resp.matched_project_id is None


def test_v1_memory_write(db_session):
    repo = TaskRepository(db_session)
    p = repo.get_default_project()
    t = repo.create_task(owner_text="#TASK memory test", project_id=p.id)
    repo.update_task(t.id, summary="Итог: готово", status="WAIT_OWNER")
    write_task_memory_after_orchestration(repo, t.id)
    rows = repo.list_memory_entries(p.id, limit=5)
    assert len(rows) >= 1
    assert rows[0].scope == "task_outcome"
    assert str(t.id) in rows[0].content


def test_task_brief_owner_text_v1_fields(db_session):
    repo = TaskRepository(db_session)
    p = repo.get_default_project()
    from app.intake.schemas import TaskBrief

    b = TaskBrief(
        title="T",
        goal="G",
        input_summary="S",
        desired_outcome="O",
        project_id=p.id,
        project_name=p.name,
        related_task_id=7,
        memory_refs=["memory:1"],
        context_summary="ctx",
    )
    s = task_brief_to_owner_text(b, original_input="x")
    assert "SmartIntake v1" in s
    assert "Проект:" in s
    assert "Связанная миссия" in s
