# Слой представления «бизнес vs система» для Owner Console (без HTML).
from __future__ import annotations

import os
import re
from types import SimpleNamespace
from typing import Any, Literal

ViewMode = Literal["business", "system"]

# Технический id фазы → подпись для владельца (Business View)
PHASE_BUSINESS_LABELS_RU: dict[str, str] = {
    "triage": "Анализ",
    "exploration": "Сценарии",
    "pipeline": "План",
    "roundtable": "Проверка",
    "court": "Решение",
    "execution_pack_generation": "Готовое действие",
    "approval": "Согласование",
    "delivery": "Итог",
}


def default_dashboard_view() -> ViewMode:
    raw = (os.getenv("DASHBOARD_DEFAULT_VIEW", "business") or "business").strip().lower()
    return "system" if raw == "system" else "business"


def parse_view_mode(value: str | None) -> ViewMode:
    if (value or "").strip().lower() == "system":
        return "system"
    return "business"


def business_action_dict(task: Any) -> dict[str, Any]:
    raw = getattr(task, "business_action_json", None)
    return raw if isinstance(raw, dict) else {}


def exploration_selected_option_id(task: Any) -> str:
    """Совпадает с логикой sync_run: нормализация ключей выбора сценария."""
    j = business_action_dict(task)
    ex = j.get("exploration")
    if not isinstance(ex, dict):
        return ""
    for key in ("selected_option_id", "selected_option", "scenario_id", "option_id"):
        val = ex.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def exploration_bundle_dict(task: Any) -> dict[str, Any]:
    j = business_action_dict(task)
    ex = j.get("exploration")
    return ex if isinstance(ex, dict) else {}


def exploration_waiting_for_scenario(task: Any) -> bool:
    """WAIT_OWNER с активным exploration и без выбранного сценария — UI должен показывать сценарии, не court."""
    if getattr(task, "status", None) != "WAIT_OWNER":
        return False
    ex = exploration_bundle_dict(task)
    if not ex.get("exploration_mode"):
        return False
    return not bool(exploration_selected_option_id(task))


def exploration_mode_active(task: Any) -> bool:
    return bool(exploration_bundle_dict(task).get("exploration_mode"))


def gm_decision_dict(task: Any) -> dict[str, Any]:
    j = business_action_dict(task)
    gm = j.get("gm_decision")
    return gm if isinstance(gm, dict) else {}


def execution_pack_dict(task: Any) -> dict[str, Any]:
    j = business_action_dict(task)
    p = j.get("execution_pack")
    if isinstance(p, dict) and p:
        return p
    gm = gm_decision_dict(task)
    p2 = gm.get("execution_pack")
    return p2 if isinstance(p2, dict) else {}


def execution_from_scenario_dict(task: Any) -> dict[str, Any]:
    """Dry-run exploration: структура, agent_tasks, cursor_prompts (до pipeline/court)."""
    j = business_action_dict(task)
    raw = j.get("execution_from_scenario")
    return raw if isinstance(raw, dict) and raw else {}


def has_execution_from_scenario(task: Any) -> bool:
    return bool(execution_from_scenario_dict(task))


def owner_workstream_from_intake_brief(task_brief: Any, business_action: Any | None) -> str:
    """Тот же owner_workstream, что для задачи, но из ответа intake (до записи в БД)."""
    j: dict[str, Any] = {}
    bu = getattr(task_brief, "business_unit", None)
    if bu:
        j["business_unit"] = bu
    if business_action is not None and hasattr(business_action, "model_dump"):
        act = business_action.model_dump()
        if isinstance(act, dict):
            j.update({k: v for k, v in act.items() if v is not None})
    text = f"{getattr(task_brief, 'title', '')}\n{getattr(task_brief, 'input_summary', '')}"
    t = SimpleNamespace(
        owner_text=text,
        business_type=getattr(task_brief, "business_type", None),
        domain=None,
        task_type=None,
        business_action_json=j if j else None,
    )
    return owner_workstream_label(t, None)


def owner_workstream_label(task: Any, project: Any | None = None) -> str:
    """
    Видимый владельцу тип работы (не равен внутреннему domain/task_type).
    Приоритет: project_type → business_unit в JSON → domain/task_type → business_type → текст.
    """
    j = business_action_dict(task)
    unit = str(j.get("business_unit") or "").strip().lower()
    bt = str(getattr(task, "business_type", None) or "").strip().lower()
    domain = str(getattr(task, "domain", None) or "").strip().upper()
    tt = str(getattr(task, "task_type", None) or "").strip().lower()
    text = (getattr(task, "owner_text", None) or "").lower()

    ptype = ""
    if project is not None:
        ptype = str(getattr(project, "project_type", None) or "").strip().lower()

    gm = gm_decision_dict(task)
    wtpl = str(gm.get("workflow_template") or "").strip().lower()

    if domain == "BUSINESS":
        return "REVENUE"

    if ptype == "event" or unit == "wakesafari" or domain == "EVENTS":
        if bt == "revenue" or "спонсор" in text or "оффер" in text or domain == "SPONSOR_PLATFORM":
            return "EVENT · REVENUE"
        return "EVENT"
    if ptype == "product":
        return "PRODUCT"
    if ptype == "media":
        return "MEDIA"
    if ptype == "platform":
        return "PLATFORM"

    if unit == "snowpolia" or "snowpolia" in text or domain == "GAME":
        return "GAME"
    if unit in {"media", "mywave"} or domain == "MEDIA_OPS":
        return "MARKETING" if bt == "marketing" or domain == "MEDIA_OPS" else "MEDIA"
    if unit == "platform" or domain == "SPONSOR_PLATFORM":
        return "REVENUE"
    if domain == "EVENTS":
        return "EVENT"
    if domain == "SPONSOR_PLATFORM" or tt == "mvp_scoring":
        return "REVENUE"

    if wtpl == "business" or _launch_hint_text(text):
        return "LAUNCH"

    if bt == "revenue":
        return "REVENUE"
    if bt == "marketing":
        return "MARKETING"
    if bt == "product":
        return "PRODUCT"
    if bt == "ops":
        return "OPS"

    if domain == "PRODUCT_DEV" or not domain:
        return "PRODUCT"

    return domain.replace("_", " ")


def _launch_hint_text(text: str) -> bool:
    return bool(
        re.search(
            r"(стратег\w*\s+запуск|gtm|go-?to-?market|запуск\s+продукта|вывод\s+на\s+рынок)",
            text,
            re.IGNORECASE,
        )
    )


def friendly_phase_name(phase_id: str, view_mode: ViewMode) -> str:
    if view_mode == "business":
        return PHASE_BUSINESS_LABELS_RU.get(phase_id, phase_id)
    return phase_id


def project_impact_blurb(task: Any, project: Any | None, gm: dict[str, Any] | None = None) -> str:
    """Короткий текст блока «Влияние на проект»."""
    gm = gm or gm_decision_dict(task)
    parts: list[str] = []

    if project is not None:
        st = getattr(project, "stage", None) or ""
        foc = getattr(project, "owner_focus_level", None) or ""
        if st:
            parts.append(f"Стадия проекта: {st}.")
        if foc:
            parts.append(f"Фокус владельца: {foc}.")

    wtpl = str(gm.get("workflow_template") or "").strip()
    if wtpl == "business":
        parts.append("Контур: стратегия и запуск — готовность к следующему коммерческому шагу после вашего решения.")

    out = getattr(task, "business_outcome", None) or ""
    if isinstance(out, str) and out.strip():
        parts.append(f"Ожидаемый исход по задаче: {out.strip()[:280]}")

    if not parts:
        parts.append(
            "Свяжите итог миссии с метрикой проекта (регистрации, партнёры, выручка) — при необходимости обновите стадию проекта вручную."
        )

    return " ".join(parts)


def next_business_step_text(task: Any) -> str:
    if getattr(task, "status", None) == "EXECUTION_READY":
        exr = execution_from_scenario_dict(task)
        note = str(exr.get("system_note") or "").strip()
        if note:
            return f"Запустите шаги в Cursor. {note[:400]}"
        return (
            "Запустите подготовленные промпты в Cursor на репозитории проекта. "
            "После появления артефактов можно снова прогнать pipeline при необходимости."
        )
    gm = gm_decision_dict(task)
    step = str(gm.get("next_business_step") or "").strip()
    if step:
        return step
    return (
        "Согласуйте с Owner следующий шаг (публикация, партнёры, деньги) — "
        "система не выполняет его без явного approve."
    )


def business_value_text(task: Any) -> str:
    gm = gm_decision_dict(task)
    hint = str(gm.get("business_value_hint") or "").strip()
    if hint:
        return hint
    j = business_action_dict(task)
    exp = str(j.get("expected_outcome") or "").strip()
    if exp:
        return exp
    return "Ценность для бизнеса: зафиксируйте метрику (что должно измениться после этой миссии)."


def business_goal_display(task: Any, project: Any | None) -> str:
    if project is not None:
        bg = getattr(project, "business_goal", None)
        if isinstance(bg, str) and bg.strip():
            return bg.strip()[:500]
    j = business_action_dict(task)
    gh = str(j.get("business_goal_hint") or "").strip()
    if gh:
        return gh[:500]
    return ""


def mission_headline(task: Any) -> str:
    """Заголовок строки в списке миссий."""
    j = business_action_dict(task)
    title = str(j.get("intake_title") or "").strip()
    if title:
        return title[:160]
    raw = (getattr(task, "owner_text", None) or "").strip()
    if not raw:
        return f"Миссия #{getattr(task, 'id', '')}"
    first = raw.splitlines()[0].strip()
    first = re.sub(r"^\s*#TASK\s*", "", first, flags=re.IGNORECASE).strip()
    return (first[:160] or f"Миссия #{getattr(task, 'id', '')}")


def impact_display(task: Any) -> str:
    lvl = str(getattr(task, "impact_level", None) or "").strip().lower()
    if lvl == "high":
        return "Высокий"
    if lvl == "medium":
        return "Средний"
    if lvl == "low":
        return "Низкий"
    return lvl or "—"


def friendly_current_phase(task: Any, workflow_summary: dict[str, Any], view_mode: ViewMode) -> str:
    if getattr(task, "status", None) == "EXECUTION_READY":
        return "Запуск в Cursor" if view_mode == "business" else "EXECUTION_READY"
    if exploration_waiting_for_scenario(task):
        return friendly_phase_name("exploration", view_mode)
    raw = workflow_summary.get("current_step") or "idle"
    if view_mode == "system":
        return str(raw)
    if raw == "idle" and getattr(task, "status", None) == "WAIT_OWNER":
        return friendly_phase_name("approval", view_mode)
    return friendly_phase_name(str(raw), view_mode) if raw in PHASE_BUSINESS_LABELS_RU else str(raw)


def artifact_action_hints(step_name: str | None, owner_workstream: str) -> list[str]:
    """Что владелец может сделать с артефактом (эвристика по шагу)."""
    sn = (step_name or "").upper()
    ws = (owner_workstream or "").upper()
    hints: list[str] = []

    if "VERDICT" in sn or "COURT" in sn or "JUDGE" in sn:
        hints.append("Использовать как итоговое решение по миссии и основу для следующего шага.")
        hints.append("Передать заинтересованным сторонам после вашего approve.")
    elif "ROUND" in sn or "RC" in sn or "RISK" in sn:
        hints.append("Сверить выявленные риски с реальным планом запуска.")
        hints.append("Зафиксировать, что принимаете риск или что меняете в scope.")
    elif any(x in sn for x in ("PM", "PS", "ARCH", "FE", "BE", "UX")):
        hints.append("Использовать как основу для реализации или брифа исполнителям.")
        hints.append("Вынести в backlog / спринт, если это продуктовые задачи.")
    else:
        hints.append("Использовать как рабочий материал по миссии.")
        hints.append("При необходимости прикрепить к письму партнёрам или в маркетинг после согласования.")

    if "REVENUE" in ws or "EVENT" in ws:
        hints.append("Для выручки/ивента: согласовать оффер и список контактов до массовой рассылки.")

    if len(hints) > 4:
        return hints[:4]
    return hints


def enrich_workflow_steps_for_template(
    steps: list[dict[str, Any]],
    view_mode: ViewMode,
) -> list[dict[str, Any]]:
    out = []
    for s in steps:
        name = s.get("name", "")
        row = dict(s)
        row["display_name"] = friendly_phase_name(str(name), view_mode)
        out.append(row)
    return out


def enrich_artifacts_for_template(
    artifacts: list[dict[str, Any]],
    owner_workstream: str,
) -> list[dict[str, Any]]:
    out = []
    for a in artifacts:
        row = dict(a)
        row["action_hints"] = artifact_action_hints(row.get("step_name"), owner_workstream)
        out.append(row)
    return out


def access_query_with_view(base_query: str, view_mode: ViewMode) -> str:
    """Добавить view= к query (?link= или ?api_key=)."""
    q = (base_query or "").lstrip("?")
    if not q:
        return f"?view={view_mode}"
    if "view=" in q:
        return f"?{q}"
    return f"?{q}&view={view_mode}"


def mission_list_row(task: Any, project: Any | None, workflow_summary: dict[str, Any]) -> dict[str, Any]:
    ws = owner_workstream_label(task, project)
    gm = gm_decision_dict(task)
    ep = execution_pack_dict(task)
    exr = execution_from_scenario_dict(task)
    ex_wait = exploration_waiting_for_scenario(task)
    wait = getattr(task, "status", None) == "WAIT_OWNER"
    return {
        "id": getattr(task, "id", 0),
        "headline": mission_headline(task),
        "status": getattr(task, "status", ""),
        "owner_workstream": ws,
        "next_business_step": next_business_step_text(task),
        "impact_display": impact_display(task),
        "friendly_phase": friendly_current_phase(task, workflow_summary, "business"),
        "progress": f"{workflow_summary.get('progress_done', 0)}/{workflow_summary.get('progress_total', 0)}",
        "workflow_status": workflow_summary.get("status", ""),
        "needs_approval": wait and not ex_wait,
        "exploration_waiting": ex_wait,
        "business_type": getattr(task, "business_type", None) or "-",
        "project_stage": getattr(project, "stage", None) if project else None,
        "project_focus": getattr(project, "owner_focus_level", None) if project else None,
        "gm_workflow_template": gm.get("workflow_template"),
        "has_execution_pack": bool(ep),
        "has_execution_ready": bool(exr),
        "execution_pack_title": str(ep.get("action_title") or "").strip(),
    }

