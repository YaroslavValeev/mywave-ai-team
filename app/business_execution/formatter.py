from __future__ import annotations

from app.business_execution.schemas import ExecutionPack


def format_pack_preview(pack: ExecutionPack) -> str:
    lines = [
        f"Действие: {pack.action_title}",
        f"Зачем: {pack.why}",
        "",
        "Готово:",
    ]
    for step in pack.ready_steps[:5]:
        lines.append(f"- {step}")
    lines.extend(
        [
            "",
            f"Как использовать: {pack.how_to_execute}",
            f"Оценка времени: {pack.time_estimate}",
            f"Ожидаемый результат: {pack.expected_result}",
        ]
    )
    return "\n".join(lines).strip()


def format_pack_short(pack: ExecutionPack) -> str:
    return f"{pack.action_title} · {pack.time_estimate} · результат: {pack.expected_result}"
