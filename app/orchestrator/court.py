# app/orchestrator/court.py — финальный отчёт .md
import os
import re
from pathlib import Path

from app.config import get_policy
from app.orchestrator.triage_snapshot import canonical_triage_for_court
from app.dashboard.documents import COURT_VERDICT_STEP
from app.shared.redaction import redact

from app.dashboard.business_view import business_value_text, mission_headline, owner_workstream_label

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "app/artifacts"))
_OWNER_TEXT_VERDICT_PREVIEW_CHARS = 2800


def _execution_gap_analysis(owner_text: str | None) -> dict:
    """
    Эвристика: запрос требует данных вне доступного runtime (локальный диск, личные кабинеты OpenAI/Google и т.д.).
    """
    raw = (owner_text or "").strip()
    t = raw.lower()
    needs = False
    hints: list[str] = []
    if any(x in t for x in ("openai", "опенаи", "google", "гугл")):
        hints.append("внешние сервисы/аккаунты")
        if any(x in t for x in ("проект", "список", "все ", "всех", "локал", "local", "компьютер")):
            needs = True
    if any(x in t for x in ("local", "локал", "компьютер", "на пк", "диске", "диск ", "папк", "каталог")):
        hints.append("локальный компьютер/диск")
        if any(x in t for x in ("проект", "список", "все ", "всех")):
            needs = True
    if any(x in t for x in ("список", "перечисл", "инвентар")) and "проект" in t:
        needs = True
        hints.append("перечень/инвентарь проектов")
    preview = redact(raw)[:_OWNER_TEXT_VERDICT_PREVIEW_CHARS] if raw else ""
    return {
        "needs_external_access": needs,
        "hints": list(dict.fromkeys(hints)),
        "owner_preview": preview,
    }


def _gap_verdict_explanation() -> str:
    return (
        "Текущий контур AI-Team **не имеет доступа** к файловой системе вашего ПК и к личным кабинетам "
        "OpenAI/Google для автоматической выгрузки списков проектов. Сгенерированные handoffs и этот вердикт "
        "отражают **процессную** разборку запроса (триаж, роли, риски), а не фактический перечень проектов. "
        "Чтобы получить требуемый список, приложите к задаче экспорт или выписки вручную, либо используйте "
        "отдельный runtime/интеграцию с явным доступом."
    )


DOMAIN_LABELS = {
    "BUSINESS": "Коммерция и выручка",
    "CLIENTOPS": "Клиентские операции",
    "PRODUCT_DEV": "Продуктовая разработка",
    "EVENTS": "Ивенты и запуски",
    "MEDIA_OPS": "Медиа и контент",
    "GAME": "Игра и продукт SnowPolia",
    "SPONSOR_PLATFORM": "Платформа спонсоров и партнёров",
    "RND_EXTREME": "R&D / Extreme Media",
    "RUZA": "Направление Ruza",
    "INFRA": "Инфраструктура и инвестиции",
    "AUTHORITY_CONTENT": "Экспертный контент",
}

TASK_TYPE_LABELS = {
    "revenue_execution": "Выполнение revenue: клиенты, лиды, оплата",
    "studio_bot_admin": "Доработка и администрирование студийного бота",
    "feature_delivery": "Поставка фичи",
    "deploy_prod": "Внедрение в рабочую среду",
    "general": "Общая задача",
}

CRITICALITY_LABELS = {
    "LOW": "Низкая",
    "MEDIUM": "Средняя",
    "HIGH": "Высокая",
    "CRITICAL": "Критическая",
}

PLAN_EXECUTE_LABELS = {
    "PLAN": "Планирование",
    "EXECUTE": "Исполнение",
}

EXECUTE_GATE_LABELS = {
    "OWNER_APPROVAL_ALWAYS": "Требуется согласование владельца перед любым исполнением",
    "OWNER_APPROVAL_IF_PROD": "Требуется согласование владельца для боевого контура",
    "OWNER_APPROVAL_IF_PII_OR_PROD": "Требуется согласование владельца при работе с персональными данными или боевым контуром",
}

STEP_LABELS = {
    "PS": "Продуктовый стратег",
    "PM": "Менеджер поставки",
    "UX": "UX-дизайнер",
    "FE": "Frontend-инженер",
    "BE": "Backend-инженер",
    "FE_BE": "Команда frontend и backend",
    "ARCH": "Архитектор",
    "QA": "QA-ревьюер",
    "DEVOPS": "DevOps-инженер",
    "SEC": "Ревью безопасности",
    "RC": "Проверка реалистичности",
    "LEGAL": "Юрист",
    "FIN": "Финансовый аналитик",
    "JUDGE": "Судья",
    "OWNER": "Владелец",
    "COURT_VERDICT": "Финальный вердикт суда",
}


def run_court(
    task_id: int,
    triage_result: dict,
    pipeline_result: dict,
    roundtable_result: dict,
    repo,
    control=None,
) -> dict:
    """
    Генерирует финальный отчёт .md и short summary.
    """
    task = repo.get_task(task_id)
    if not task:
        return {"report_path": None, "summary": "Task not found"}

    triage_result = canonical_triage_for_court(task, triage_result)

    if control:
        control.set_phase("court", message="Суд формирует финальный verdict и отчёт.", current_step="JUDGE")
        control.check_cancelled()

    max_chars = get_policy().get("limits", {}).get("telegram_summary_max_chars", 1200)
    handoffs = pipeline_result.get("handoffs", [])
    risk_table = roundtable_result.get("risk_table", [])
    reviewers = roundtable_result.get("reviewers", [])

    gap_analysis = _execution_gap_analysis(task.owner_text)

    owner_approval_needed = any(risk.get("owner_approval_needed") for risk in risk_table)
    step_names = [handoff.get("step", "-") for handoff in handoffs]
    key_decisions = _collect_unique_items(handoffs, "decisions", limit=6)
    assumptions = _collect_unique_items(handoffs, "assumptions", limit=6)
    open_questions = _collect_unique_items(handoffs, "open_questions", limit=6)

    report_lines = [
        "# Финальный отчёт AI-Team",
        "",
        f"**Задача #{task_id}**",
        "",
    ]
    if gap_analysis.get("owner_preview"):
        report_lines.extend(
            [
                "## Запрос владельца (исходная формулировка)",
                "К этому отчёту относится следующая постановка задачи (может быть сокращена и маскирована):",
                "",
            ]
        )
        for line in (gap_analysis["owner_preview"] or "").splitlines()[:120]:
            report_lines.append(f"> {line}")
        report_lines.append("")
    if gap_analysis.get("needs_external_access"):
        report_lines.extend(
            [
                "## Ограничения текущего контура",
                _gap_verdict_explanation(),
                "",
            ]
        )

    report_lines.extend(
        [
        "## Краткое резюме",
        f"Домен: {_describe_domain(triage_result.get('domain'), include_code=False)}",
        f"Тип задачи: {_describe_task_type(triage_result.get('task_type'), include_code=False)}",
        f"Критичность: {_describe_criticality(triage_result.get('criticality'), include_code=False)}",
        f"Режим работы: {_describe_plan_execute(triage_result.get('plan_or_execute'), include_code=False)}",
        f"Контур исполнения: {_describe_execute_gate(triage_result.get('execute_gate'), include_code=False)}",
        f"Этапы pipeline завершены: {_describe_step_list(step_names, include_code=False)}",
        f"Участники совещания: {_describe_step_list(reviewers, include_code=False)}",
        "",
        "## Что решила команда простыми словами",
        ]
    )

    plain_language_points = _build_plain_language_points(
        triage_result=triage_result,
        handoffs=handoffs,
        risk_table=risk_table,
        reviewers=reviewers,
        owner_approval_needed=owner_approval_needed,
        gap_analysis=gap_analysis,
        task=task,
        project=getattr(task, "project", None),
    )

    for point in plain_language_points:
        report_lines.append(f"- {point}")

    report_lines.extend([
        "",
        "## Что делать владельцу прямо сейчас",
    ])

    for step in _build_owner_now_steps(owner_approval_needed):
        report_lines.append(f"- {step}")

    report_lines.extend([
        "",
        "## Что произойдёт после решения владельца",
    ])

    for step in _build_after_owner_decision_steps(owner_approval_needed):
        report_lines.append(f"- {step}")

    report_lines.extend([
        "",
        "## Что подготовила команда",
        f"- Создано передаточных документов: {len(handoffs)}",
        f"- Зафиксировано рисков: {len(risk_table)}",
        f"- Требуется решение владельца: {_format_yes_no(owner_approval_needed)}",
        "",
        "## Чек-лист приёмки",
        f"- [ ] Решение владельца по пути исполнения: {_format_owner_gate(owner_approval_needed)}",
        f"- [ ] Проверено передаточных документов: {len(handoffs)}",
        f"- [ ] Проверено рисков: {len(risk_table)}",
        "",
        "## Ключевые решения",
    ])

    if key_decisions:
        for decision in key_decisions:
            report_lines.append(f"- {_localize_text(decision)}")
    else:
        report_lines.append("- Использовать стандартный рабочий маршрут без дополнительных отклонений.")

    report_lines.extend(["", "## Допущения"])
    if assumptions:
        for assumption in assumptions:
            report_lines.append(f"- {_localize_text(assumption)}")
    else:
        report_lines.append("- Явные допущения не зафиксированы.")

    report_lines.extend(["", "## Риски и меры"])
    for risk in risk_table:
        report_lines.append(
            f"- **{_localize_text(risk.get('issue', ''))}** [{_describe_criticality(risk.get('severity'), include_code=False)}]: "
            f"{_localize_text(risk.get('recommendation', ''))} | Основание: {_localize_evidence(risk.get('evidence', ''), include_code=False)}"
        )

    report_lines.extend(["", "## Открытые вопросы"])
    if open_questions:
        for question in open_questions:
            report_lines.append(f"- {_localize_text(question)}")
    else:
        report_lines.append("- Открытых вопросов не осталось.")

    report_lines.extend(["", "## Следующие действия"])
    if owner_approval_needed:
        report_lines.append("- Владельцу: утвердить, вернуть на доработку или запросить уточнение перед любым действием исполнения.")
    else:
        report_lines.append("- Владельцу: проверить итог и либо закрыть задачу, либо продолжить реализацию.")

    report_lines.extend(["", "## Технические идентификаторы"])
    report_lines.extend(_build_technical_identifiers_lines(triage_result, step_names, reviewers))
    report_lines.extend([""])

    report_content = redact("\n".join(report_lines))
    court_path = ARTIFACTS_DIR / "tasks" / f"task_{task_id}" / "court"
    court_path.mkdir(parents=True, exist_ok=True)
    report_path = court_path / "final_report.md"
    report_path.write_text(report_content, encoding="utf-8")

    verdict_content = redact(
        _build_verdict_md(
            task_id=task_id,
            triage_result=triage_result,
            handoffs=handoffs,
            risk_table=risk_table,
            reviewers=reviewers,
            owner_approval_needed=owner_approval_needed,
            key_decisions=key_decisions,
            assumptions=assumptions,
            open_questions=open_questions,
            report_path=str(report_path),
            gap_analysis=gap_analysis,
            task=task,
            project=getattr(task, "project", None),
        )
    )
    verdict_path = court_path / "final_verdict.md"
    verdict_path.write_text(verdict_content, encoding="utf-8")

    next_step_index = max((handoff.step_index for handoff in task.handoffs), default=-1) + 1
    repo.add_handoff(
        task_id=task_id,
        step_index=next_step_index,
        step_name=COURT_VERDICT_STEP,
        payload={
                "document_role": "final_verdict",
                "document_title": "Финальный вердикт суда",
                "summary": [
                "Каноничное решение команды после суда сохранено в проекте. Используйте этот документ как опорный вердикт при следующих действиях по задаче.",
                ("Перед следующим шагом требуется решение владельца." if owner_approval_needed else "Следующий шаг можно выполнять, опираясь на текущий вердикт, без повторного прохода через суд."),
            ],
            "owner_gate_required": owner_approval_needed,
            "report_path": str(report_path),
            "related_handoffs": [handoff.get("md_path") for handoff in handoffs if handoff.get("md_path")],
            "next_action": "Требуется решение владельца" if owner_approval_needed else "Можно продолжать по текущему вердикту",
        },
        md_path=str(verdict_path),
    )

    summary_core = (
        f"Задача #{task_id} готова. "
        f"{_describe_domain(triage_result.get('domain'), include_code=False)}, {_describe_task_type(triage_result.get('task_type'), include_code=False)}. "
        f"Передаточных документов: {len(handoffs)}, рисков: {len(risk_table)}. "
        + ("Требуется решение владельца." if owner_approval_needed else "Можно завершать проверку и закрытие без дополнительного решения владельца.")
    )
    if gap_analysis.get("needs_external_access"):
        summary_core = (
            f"Задача #{task_id}: запрос требует данных вне доступа сервера (ПК/аккаунты OpenAI/Google) — итог процессный, не инвентарь. "
            + summary_core
        )
    summary = redact(summary_core)[:max_chars]

    repo.update_task(task_id, report_path=str(report_path), summary=summary)
    if control:
        control.check_cancelled()

    return {"report_path": str(report_path), "summary": summary}


def _collect_unique_items(handoffs: list[dict], key: str, limit: int = 5) -> list[str]:
    seen = set()
    items = []
    for handoff in handoffs:
        payload = handoff.get("payload", {})
        for value in payload.get(key, []):
            if value and value not in seen:
                seen.add(value)
                items.append(value)
            if len(items) >= limit:
                return items
    return items


def _build_verdict_md(
    *,
    task_id: int,
    triage_result: dict,
    handoffs: list[dict],
    risk_table: list[dict],
    reviewers: list[str],
    owner_approval_needed: bool,
    key_decisions: list[str],
    assumptions: list[str],
    open_questions: list[str],
    report_path: str,
    gap_analysis: dict | None = None,
    task=None,
    project=None,
) -> str:
    gap_analysis = gap_analysis or {}
    next_action = (
        "Владелец должен принять решение: утвердить, вернуть на доработку или запросить уточнение, прежде чем задача выйдет из судебного контура."
        if owner_approval_needed
        else "Команда может ссылаться на этот вердикт как на итоговую позицию и переходить к следующему рабочему шагу."
    )
    verdict_line = (
        "Суд зафиксировал, что без решения владельца дальнейшее движение задачи блокируется."
        if owner_approval_needed
        else "Суд зафиксировал, что по текущим данным задача может двигаться дальше без повторного прохода через суд."
    )

    lines = [
        "# Финальный вердикт суда",
        "",
        f"**Задача #{task_id}**",
        "",
    ]
    if gap_analysis.get("owner_preview"):
        lines.extend(
            [
                "## Запрос владельца (исходная формулировка)",
                "Этот вердикт относится к следующей постановке задачи (текст может быть сокращён и маскирован):",
                "",
            ]
        )
        for line in (gap_analysis.get("owner_preview") or "").splitlines()[:120]:
            lines.append(f"> {line}")
        lines.append("")
    if gap_analysis.get("needs_external_access"):
        lines.extend(
            [
                "## Ограничения текущего контура",
                _gap_verdict_explanation(),
                "",
            ]
        )

    lines.extend(
        [
            "## Назначение документа",
            "Этот файл — каноничное финальное решение команды после суда.",
            "Команда и агенты должны ссылаться на него при следующих действиях по задаче, а не пересобирать позицию с нуля.",
            "",
            "## Позиция суда",
            f"- Домен: {_describe_domain(triage_result.get('domain'), include_code=False)}",
            f"- Тип задачи: {_describe_task_type(triage_result.get('task_type'), include_code=False)}",
            f"- Критичность: {_describe_criticality(triage_result.get('criticality'), include_code=False)}",
            f"- Режим работы: {_describe_plan_execute(triage_result.get('plan_or_execute'), include_code=False)}",
            f"- Контур исполнения: {_describe_execute_gate(triage_result.get('execute_gate'), include_code=False)}",
            f"- Участники совещания: {_describe_step_list(reviewers, include_code=False)}",
            f"- Требуется решение владельца: {_format_yes_no(owner_approval_needed)}",
            f"- Вердикт: {verdict_line}",
            "",
            "## Обязательное следующее действие",
            f"- {next_action}",
            "",
            "## Что решила команда простыми словами",
        ]
    )

    for point in _build_plain_language_points(
        triage_result=triage_result,
        handoffs=handoffs,
        risk_table=risk_table,
        reviewers=reviewers,
        owner_approval_needed=owner_approval_needed,
        gap_analysis=gap_analysis,
        task=task,
        project=getattr(task, "project", None),
    ):
        lines.append(f"- {point}")

    lines.extend([
        "",
        "## Что делать владельцу прямо сейчас",
    ])

    for step in _build_owner_now_steps(owner_approval_needed):
        lines.append(f"- {step}")

    lines.extend([
        "",
        "## Что произойдёт после решения владельца",
    ])

    for step in _build_after_owner_decision_steps(owner_approval_needed):
        lines.append(f"- {step}")

    lines.extend([
        "",
        "## Ключевые решения",
    ])

    if key_decisions:
        for decision in key_decisions:
            lines.append(f"- {_localize_text(decision)}")
    else:
        lines.append("- Использовать стандартный маршрут выполнения без дополнительных отклонений.")

    lines.extend(["", "## Сохраняющиеся риски"])
    if risk_table:
        for risk in risk_table:
            lines.append(
                f"- {_localize_text(risk.get('issue', ''))} [{_describe_criticality(risk.get('severity'), include_code=False)}]: {_localize_text(risk.get('recommendation', ''))}"
            )
    else:
        lines.append("- Существенных блокирующих рисков не зафиксировано.")

    lines.extend(["", "## Допущения"])
    if assumptions:
        for assumption in assumptions:
            lines.append(f"- {_localize_text(assumption)}")
    else:
        lines.append("- Явных допущений не зафиксировано.")

    lines.extend(["", "## Открытые вопросы"])
    if open_questions:
        for question in open_questions:
            lines.append(f"- {_localize_text(question)}")
    else:
        lines.append("- Открытых вопросов не осталось.")

    lines.extend(["", "## Связанные файлы", f"- Финальный отчёт: {report_path}"])
    for handoff in handoffs:
        if handoff.get("md_path"):
            lines.append(f"- Документ роли {_describe_step(handoff.get('step', '-'), include_code=False)}: {handoff['md_path']}")

    lines.extend(["", "## Технические идентификаторы"])
    lines.extend(_build_technical_identifiers_lines(triage_result, [handoff.get("step", "-") for handoff in handoffs], reviewers))
    lines.extend(["", "## Как использовать", "Если задача вернётся на доработку, этот вердикт остаётся опорной фиксацией текущей позиции суда до появления нового финального решения."])
    return "\n".join(lines)


def _format_yes_no(value: bool) -> str:
    return "Да" if value else "Нет"


def _format_owner_gate(owner_approval_needed: bool) -> str:
    return "требуется" if owner_approval_needed else "не требуется"


def _localize_text(value: str) -> str:
    if not value:
        return value

    text = str(value)
    exact = {
        "Owner approval gate blocks direct execute": "Проверка владельцем блокирует прямое исполнение",
        "High-impact task needs stronger validation": "Для задачи с высоким влиянием нужна усиленная проверка",
        "Production path needs rollback and verification": "Для боевого контура нужен план отката и проверка результата",
        "Sensitive data handling needs explicit review": "Работа с чувствительными данными требует явной проверки",
        "Keep task in WAIT_OWNER until owner approves the execute path.": "Держать задачу в статусе ожидания решения владельца, пока он не одобрит путь исполнения.",
        "Review handoffs and confirm acceptance criteria before closing the task.": "Проверить материалы команды и подтвердить критерии приёмки перед закрытием задачи.",
        "Review handoffs before closing.": "Проверить материалы команды перед закрытием задачи.",
        "Prepare rollback, backup, and post-deploy health checks.": "Подготовить план отката, резервную копию и проверки после внедрения.",
        "Confirm redaction, retention, and access boundaries before execution.": "Подтвердить маскирование данных, правила хранения и границы доступа перед выполнением.",
        "Confirm release acceptance criteria.": "Подтвердить критерии приёмки релиза.",
    }
    if text in exact:
        return exact[text]

    handoff_match = re.fullmatch(r"Hand off to ([A-Z_]+)\.", text)
    if handoff_match:
        return f"Передать задачу специалисту: {_describe_step(handoff_match.group(1), include_code=False)}."

    context_match = re.fullmatch(r"Use context carried from ([A-Z_]+)\.", text)
    if context_match:
        return f"Использовать контекст, переданный от роли {_describe_step(context_match.group(1), include_code=False)}."

    criticality_match = re.fullmatch(r"Keep task criticality at ([A-Z_]+)\.", text)
    if criticality_match:
        return f"Сохранить критичность задачи на уровне {_describe_criticality(criticality_match.group(1), include_code=False)}."

    plan_match = re.fullmatch(r"Task is currently treated as ([A-Z_]+)\.", text)
    if plan_match:
        return f"На текущем этапе задача рассматривается как {_describe_plan_execute(plan_match.group(1), include_code=False)}."

    gate_match = re.fullmatch(r"Execute gate is ([A-Z0-9_]+)\.", text)
    if gate_match:
        return f"Контур исполнения: {_describe_execute_gate(gate_match.group(1), include_code=False)}."

    return text


def _describe_domain(code: str | None, include_code: bool = True) -> str:
    return _describe_code(code, DOMAIN_LABELS, include_code=include_code)


def _describe_task_type(code: str | None, include_code: bool = True) -> str:
    return _describe_code(code, TASK_TYPE_LABELS, include_code=include_code)


def _describe_criticality(code: str | None, include_code: bool = True) -> str:
    return _describe_code(code, CRITICALITY_LABELS, include_code=include_code)


def _describe_plan_execute(code: str | None, include_code: bool = True) -> str:
    return _describe_code(code, PLAN_EXECUTE_LABELS, include_code=include_code)


def _describe_execute_gate(code: str | None, include_code: bool = True) -> str:
    if not code:
        return "Без дополнительного согласования"
    return _describe_code(code, EXECUTE_GATE_LABELS, include_code=include_code)


def _describe_step(code: str | None, include_code: bool = True) -> str:
    return _describe_code(code, STEP_LABELS, include_code=include_code)


def _describe_step_list(codes: list[str], include_code: bool = True) -> str:
    if not codes:
        return "-"
    return ", ".join(_describe_step(code, include_code=include_code) for code in codes)


def _describe_code(code: str | None, mapping: dict[str, str], include_code: bool = True) -> str:
    if not code:
        return "Не указано"
    label = mapping.get(code)
    if label:
        return f"{label} ({code})" if include_code else label
    fallback = code.replace("_", " ").strip().lower()
    if fallback:
        fallback = fallback[0].upper() + fallback[1:]
        return f"{fallback} ({code})" if include_code else fallback
    return code


def _localize_evidence(value: str, include_code: bool = True) -> str:
    if not value:
        return value

    parts = []
    for chunk in str(value).split(";"):
        chunk = chunk.strip()
        if "=" not in chunk:
            parts.append(chunk)
            continue
        key, raw = [item.strip() for item in chunk.split("=", 1)]
        if key == "criticality":
            if include_code:
                parts.append(f"критичность={_describe_criticality(raw, include_code=True)}")
            else:
                parts.append(f"Критичность: {_describe_criticality(raw, include_code=False)}")
        elif key == "execute_gate":
            if include_code:
                parts.append(f"контур_исполнения={_describe_execute_gate(raw, include_code=True)}")
            else:
                parts.append(f"Контур исполнения: {_describe_execute_gate(raw, include_code=False)}")
        elif key == "plan_or_execute":
            if include_code:
                parts.append(f"режим={_describe_plan_execute(raw, include_code=True)}")
            else:
                parts.append(f"Режим работы: {_describe_plan_execute(raw, include_code=False)}")
        elif key == "reviewers":
            reviewers = [item.strip() for item in raw.split(",") if item.strip()]
            if include_code:
                parts.append(f"участники_совещания={_describe_step_list(reviewers, include_code=True)}")
            else:
                parts.append(f"Участники совещания: {_describe_step_list(reviewers, include_code=False)}")
        else:
            parts.append(f"{key}={raw}")
    return "; ".join(parts)


def _build_plain_language_points(
    *,
    triage_result: dict,
    handoffs: list[dict],
    risk_table: list[dict],
    reviewers: list[str],
    owner_approval_needed: bool,
    gap_analysis: dict | None = None,
    task=None,
    project=None,
) -> list[str]:
    gap_analysis = gap_analysis or {}
    points: list[str] = []
    if gap_analysis.get("needs_external_access"):
        points.append(
            "Система не может автоматически собрать списки проектов с вашего компьютера и из аккаунтов OpenAI/Google; "
            "ниже — процессный итог разборки запроса (триаж, handoffs), а не фактический инвентарь."
        )

    if task is not None:
        ow = owner_workstream_label(task, project)
        tl = mission_headline(task)
        points.append(
            f"Команда подготовила материалы по миссии «{tl}» (направление: {ow}): "
            f"сформирована структура работ, определены ключевые шаги и зафиксированы риски."
        )
    else:
        points.append(
            f"Команда разобрала задачу в направлении «{_describe_domain(triage_result.get('domain'), include_code=False)}» "
            f"и оформила маршрут работы для типа «{_describe_task_type(triage_result.get('task_type'), include_code=False)}»."
        )
    points.append(
        f"Подготовлено {len(handoffs)} передаточных документов, чтобы следующему участнику не приходилось собирать контекст заново."
    )

    if task is not None:
        bv = business_value_text(task)
        if bv and "зафиксируйте метрику" not in bv.lower():
            points.append(f"Бизнес-ориентир: {bv[:420]}")

    if risk_table:
        top_risk = _localize_text(risk_table[0].get("issue", ""))
        points.append(f"Главный риск сейчас: {top_risk.lower()}.")
    else:
        points.append("Блокирующих рисков на текущем этапе не зафиксировано.")

    if reviewers:
        points.append(f"Финальную позицию дополнительно проверили: {_describe_step_list(reviewers, include_code=False)}.")

    if owner_approval_needed:
        points.append("Переходить к следующему исполняющему шагу без решения владельца нельзя.")
    else:
        points.append("Дополнительное решение владельца для следующего шага не требуется.")

    return points


def _build_owner_now_steps(owner_approval_needed: bool) -> list[str]:
    if owner_approval_needed:
        return [
            "Прочитать краткое резюме и финальный вердикт команды.",
            "Выбрать одно действие: утвердить задачу, вернуть её на доработку или запросить уточнение.",
            "Если после утверждения нужен merge, подтвердить его только после фактического завершения.",
        ]
    return [
        "Прочитать краткое резюме, ключевые решения и риски.",
        "Если итог устраивает, перевести задачу дальше по рабочему контуру или закрыть её.",
        "Если есть сомнения, вернуть задачу на доработку или запросить уточнение.",
    ]


def _build_after_owner_decision_steps(owner_approval_needed: bool) -> list[str]:
    if owner_approval_needed:
        return [
            "После «Утвердить» задача либо перейдёт в ожидание merge, либо сразу завершится, если отдельный merge не нужен.",
            "После «На доработку» команда запустит новый цикл AI-Team и подготовит обновлённый результат.",
            "После «Нужно уточнение» текущий цикл остановится до появления новых вводных от владельца.",
        ]
    return [
        "Если владелец принимает итог, задачу можно закрывать или переводить дальше без повторного суда.",
        "Если появляются новые замечания, задача должна вернуться на доработку новым циклом.",
        "Финальный отчёт и verdict остаются опорными документами до следующего пересмотра решения.",
    ]


def _build_technical_identifiers_lines(triage_result: dict, step_names: list[str], reviewers: list[str]) -> list[str]:
    return [
        f"- Домен: {triage_result.get('domain', 'N/A')}",
        f"- Тип задачи: {triage_result.get('task_type', 'N/A')}",
        f"- Критичность: {triage_result.get('criticality', 'N/A')}",
        f"- Режим работы: {triage_result.get('plan_or_execute', 'N/A')}",
        f"- Контур исполнения: {triage_result.get('execute_gate') or 'NONE'}",
        f"- Pipeline steps: {', '.join(step_names) or '-'}",
        f"- Reviewers: {', '.join(reviewers) or '-'}",
    ]
