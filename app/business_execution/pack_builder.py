from __future__ import annotations

import re
from typing import Any

from app.business_execution.learning_hooks import apply_learning_to_pack_builder
from app.business_execution.schemas import ExecutionContext, ExecutionPack
from app.business_execution.templates.pack_templates import (
    content_pack,
    generic_pack,
    landing_pack,
    launch_plan_pack,
    offer_pack,
    partner_outreach_pack,
)


def choose_pack_type(ctx: ExecutionContext) -> str:
    text = "\n".join([
        ctx.next_business_step,
        ctx.owner_text,
        ctx.owner_workstream,
        ctx.business_type,
        ctx.workflow_template,
    ]).lower()

    if re.search(r"оффер|offer|коммерческ|proposal", text):
        return "offer_pack"
    if re.search(r"партн|sponsor|outreach|контакт|переговор", text):
        return "partner_outreach_pack"
    if re.search(r"пост|контент|анонс|smm|reels|content", text):
        return "content_pack"
    if re.search(r"лендинг|landing|страниц|website", text):
        return "landing_pack"
    if re.search(r"запуск|launch|gtm|go-to-market|roadmap", text):
        return "launch_plan_pack"
    return "generic_pack"


def build_pack(ctx: ExecutionContext, learning_hints: dict[str, dict[str, Any]] | None = None) -> ExecutionPack:
    action_title = (ctx.next_business_step or "Следующий бизнес-шаг").strip()
    why = (ctx.business_value_hint or "Действие должно ускорить бизнес-результат проекта.").strip()
    expected = (ctx.expected_outcome or "Переход к измеримому результату (лиды, партнёры, заявки)." ).strip()

    base_pack_type = choose_pack_type(ctx)
    learning = apply_learning_to_pack_builder({"base_pack_type": base_pack_type}, learning_hints or {})
    pack_type = str(learning.get("selected_pack_type") or base_pack_type)
    if pack_type == "offer_pack":
        pack = offer_pack(action_title, why, expected)
    elif pack_type == "partner_outreach_pack":
        pack = partner_outreach_pack(action_title, why, expected)
    elif pack_type == "content_pack":
        pack = content_pack(action_title, why, expected)
    elif pack_type == "landing_pack":
        pack = landing_pack(action_title, why, expected)
    elif pack_type == "launch_plan_pack":
        pack = launch_plan_pack(action_title, why, expected)
    else:
        pack = generic_pack(action_title, why, expected)

    if learning.get("recommended_mode") == "clarify_before_generate":
        hint = str(learning.get("learning_hint") or "")
        if hint:
            pack.ready_steps = [
                "Соберите минимум входных данных перед запуском действия.",
                *pack.ready_steps,
            ]
            pack.how_to_execute = f"{pack.how_to_execute}\n\n⚠ {hint}".strip()
    return pack


# legacy branches removed below

