from __future__ import annotations

from typing import Any


def create_project_structure(task: Any, selected_option: dict[str, Any]) -> list[str]:
    """
    MVP: создаёт план структуры проекта (без записи файлов на диск).
    Сохраняем как артефакт выполнения в JSON для последующего ручного/авто-run.
    """
    root = "Tourism"
    return [
        f"{root}/",
        f"{root}/Kazakhstan/",
        f"{root}/Uzbekistan/",
        f"{root}/Georgia/",
    ]


def build_execution_tasks(task: Any, selected_option: dict[str, Any]) -> list[dict[str, str]]:
    country = "Kazakhstan"
    return [
        {
            "agent": "Collector",
            "task": f"Найти 10 релевантных источников по турам ({country}): организаторы, каналы, сообщества.",
        },
        {
            "agent": "Parser",
            "task": "Собрать JSON-структуру офферов: страна, цена, даты, контакты, ссылка, условия.",
        },
        {
            "agent": "Content",
            "task": f"Подготовить RU + локальный черновик страницы по стране {country}.",
        },
        {
            "agent": "Dev",
            "task": "Собрать прототип карточки/списка туров для быстрого MVP-теста.",
        },
        {
            "agent": "Analyst",
            "task": "Сформировать market summary и 3 следующих шага для owner.",
        },
    ]


def build_cursor_prompts(task: Any, selected_option: dict[str, Any], execution_tasks: list[dict[str, str]]) -> list[dict[str, str]]:
    task_id = getattr(task, "id", None)
    option_title = str(selected_option.get("title") or "сценарий")
    prompts: list[dict[str, str]] = []
    for row in execution_tasks:
        agent = str(row.get("agent") or "").strip().lower()
        body = str(row.get("task") or "").strip()
        prompts.append(
            {
                "agent": agent or "worker",
                "prompt": (
                    f"[Task #{task_id}] Выполни шаг сценария '{option_title}'.\n"
                    f"Роль: {row.get('agent')}.\n"
                    f"Задача: {body}\n"
                    "Сформируй конкретный артефакт и краткий отчёт о результате."
                ),
            }
        )
    return prompts

