from pathlib import Path


def test_pipeline_includes_uploaded_file_excerpts_in_handoff(db_session, tmp_path, monkeypatch):
    """Вложения с диска попадают в rule-based handoff (выдержки) и в контекст CrewAI."""
    from app.storage.repositories import TaskRepository
    from app.orchestrator import pipeline as pipeline_module
    from app.orchestrator.triage import run_triage

    monkeypatch.setattr(pipeline_module, "ARTIFACTS_DIR", tmp_path)

    upload = tmp_path / "up.txt"
    upload.write_text("ViabilitY_TEST_MARKER_XYZ viability notes line one.", encoding="utf-8")

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK deep analysis of uploads")
    repo.add_handoff(
        task_id=task.id,
        step_index=0,
        step_name="ATTACHMENT",
        payload={
            "document_role": "source_attachment",
            "original_name": "notes.txt",
            "preview_excerpt": "short",
        },
        md_path=str(upload),
    )
    task = repo.get_task(task.id)
    triage_result = run_triage(task.owner_text)
    result = pipeline_module.run_pipeline(task.id, triage_result, repo)

    first_summary = "\n".join(result["handoffs"][0]["payload"]["summary"])
    assert "ViabilitY_TEST_MARKER_XYZ" in first_summary


def test_pipeline_handoffs_are_contextual(db_session, tmp_path, monkeypatch):
    """Pipeline handoff содержит контекст задачи, политику и следующий шаг."""
    from app.storage.repositories import TaskRepository
    from app.orchestrator import pipeline as pipeline_module
    from app.orchestrator.triage import run_triage

    monkeypatch.setattr(pipeline_module, "ARTIFACTS_DIR", tmp_path)

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK выкатить сайт после проверки healthcheck и rollback")
    triage_result = run_triage(task.owner_text)

    result = pipeline_module.run_pipeline(task.id, triage_result, repo)

    assert result["handoffs"]
    first_payload = result["handoffs"][0]["payload"]
    assert any("Owner brief:" in line for line in first_payload["summary"])
    assert any(item.startswith("policy::") for item in first_payload["artifacts"])
    assert first_payload["next_action"]


def test_roundtable_builds_execute_and_prod_risks(db_session):
    """Roundtable поднимает owner approval и production risks из triage."""
    from app.storage.repositories import TaskRepository
    from app.orchestrator.roundtable import run_roundtable

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK deploy prod")
    triage_result = {
        "domain": "PRODUCT_DEV",
        "task_type": "deploy_prod",
        "criticality": "CRITICAL",
        "plan_or_execute": "EXECUTE",
        "execute_gate": "OWNER_APPROVAL_ALWAYS",
    }
    pipeline_result = {"handoffs": [{"step": "DEVOPS", "payload": {}, "md_path": "handoff.md"}]}

    result = run_roundtable(task.id, triage_result, pipeline_result, repo)
    issues = [risk["issue"] for risk in result["risk_table"]]

    assert any("Owner approval gate" in issue for issue in issues)
    assert any("Production path" in issue for issue in issues)


def test_court_report_uses_real_handoffs_and_risks(db_session, tmp_path, monkeypatch):
    """Court report включает шаги pipeline, open questions и risk items."""
    from app.storage.repositories import TaskRepository
    from app.orchestrator import court as court_module
    from app.dashboard.documents import latest_verdict_handoff

    monkeypatch.setattr(court_module, "ARTIFACTS_DIR", tmp_path)

    repo = TaskRepository(db_session)
    task = repo.create_task(owner_text="# TASK подготовить release")
    triage_result = {
        "domain": "PRODUCT_DEV",
        "task_type": "feature_delivery",
        "criticality": "HIGH",
        "plan_or_execute": "PLAN",
        "execute_gate": "OWNER_APPROVAL_IF_PROD",
    }
    pipeline_result = {
        "handoffs": [
            {
                "step": "PM",
                "payload": {
                    "decisions": ["Use context carried from PS."],
                    "assumptions": ["Task is currently treated as PLAN."],
                    "open_questions": ["Confirm release acceptance criteria."],
                },
                "md_path": "task_1_step_0.md",
            },
            {
                "step": "ARCH",
                "payload": {
                    "decisions": ["Hand off to Roundtable."],
                    "assumptions": ["Execute gate is OWNER_APPROVAL_IF_PROD."],
                    "open_questions": [],
                },
                "md_path": "task_1_step_1.md",
            },
        ]
    }
    roundtable_result = {
        "reviewers": ["RC", "QA"],
        "risk_table": [
            {
                "issue": "High-impact task needs stronger validation",
                "severity": "HIGH",
                "impact": "Regression impact above baseline.",
                "evidence": "criticality=HIGH",
                "recommendation": "Review handoffs before closing.",
                "owner_approval_needed": False,
            }
        ],
    }

    result = court_module.run_court(task.id, triage_result, pipeline_result, roundtable_result, repo)
    report_content = Path(result["report_path"]).read_text(encoding="utf-8")
    verdict = latest_verdict_handoff(repo.get_task(task.id))
    verdict_content = Path(verdict.md_path).read_text(encoding="utf-8")

    assert "# Финальный отчёт AI-Team" in report_content
    assert "## Что решила команда простыми словами" in report_content
    assert "## Что делать владельцу прямо сейчас" in report_content
    assert "## Что произойдёт после решения владельца" in report_content
    assert "Домен: Продуктовая разработка" in report_content
    assert "Тип задачи: Поставка фичи" in report_content
    assert "Этапы pipeline завершены: Менеджер поставки, Архитектор" in report_content
    assert "Подтвердить критерии приёмки релиза." in report_content
    assert "Для задачи с высоким влиянием нужна усиленная проверка" in report_content
    assert "Использовать контекст, переданный от роли Продуктовый стратег." in report_content
    assert "Контур исполнения: Требуется согласование владельца для боевого контура" in report_content
    assert "Прочитать краткое резюме, ключевые решения и риски." in report_content
    assert "Если владелец принимает итог, задачу можно закрывать" in report_content
    assert "handoff-материалы" not in report_content
    assert "post-deploy" not in report_content
    assert "PII" not in report_content
    assert "## Технические идентификаторы" in report_content
    assert "- Домен: PRODUCT_DEV" in report_content
    assert "- Pipeline steps: PM, ARCH" in report_content
    assert result["report_path"].endswith("final_report.md")
    assert verdict is not None
    assert verdict.step_name == "COURT_VERDICT"
    assert verdict.md_path.endswith("final_verdict.md")
    assert "# Финальный вердикт суда" in verdict_content
    assert "## Что решила команда простыми словами" in verdict_content
    assert "## Что делать владельцу прямо сейчас" in verdict_content
    assert "## Что произойдёт после решения владельца" in verdict_content
    assert "каноничное финальное решение команды после суда" in verdict_content.lower()
    assert "Финальный отчёт:" in verdict_content
    assert "Использовать контекст, переданный от роли Продуктовый стратег." in verdict_content
    assert "Прочитать краткое резюме, ключевые решения и риски." in verdict_content
    assert "Если появляются новые замечания, задача должна вернуться на доработку новым циклом." in verdict_content
    assert "PII" not in verdict_content.split("## Технические идентификаторы")[0]
    assert "## Технические идентификаторы" in verdict_content
    assert "- Reviewers: RC, QA" in verdict_content


def test_execution_gap_detects_local_openai_google_inventory():
    from app.orchestrator.court import _execution_gap_analysis

    text = (
        "#TASK сделай список всех проектов которые у меня есть на Local (на компьютере), "
        "в OpenAI, в Google. Сделай их короткое описание."
    )
    g = _execution_gap_analysis(text)
    assert g["needs_external_access"] is True
    assert "openai" in g["owner_preview"].lower() or "OpenAI" in g["owner_preview"]


def test_court_verdict_includes_gap_sections_for_inventory_task(db_session, tmp_path, monkeypatch):
    """Вердикт связывается с текстом задачи и честно помечает отсутствие доступа к ПК/аккаунтам."""
    from app.storage.repositories import TaskRepository
    from app.orchestrator import court as court_module

    monkeypatch.setattr(court_module, "ARTIFACTS_DIR", tmp_path)

    repo = TaskRepository(db_session)
    owner = "#TASK список проектов на компьютере, в OpenAI и Google"
    task = repo.create_task(owner_text=owner)
    triage_result = {
        "domain": "PRODUCT_DEV",
        "task_type": "feature_delivery",
        "criticality": "MEDIUM",
        "plan_or_execute": "PLAN",
        "execute_gate": "OWNER_APPROVAL_IF_PROD",
    }
    pipeline_result = {"handoffs": []}
    roundtable_result = {"reviewers": [], "risk_table": []}

    court_module.run_court(task.id, triage_result, pipeline_result, roundtable_result, repo)
    verdict_path = tmp_path / "tasks" / f"task_{task.id}" / "court" / "final_verdict.md"
    verdict_content = verdict_path.read_text(encoding="utf-8")

    assert "## Запрос владельца (исходная формулировка)" in verdict_content
    assert "OpenAI" in verdict_content
    assert "## Ограничения текущего контура" in verdict_content
    assert "не имеет доступа" in verdict_content
