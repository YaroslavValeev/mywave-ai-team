from __future__ import annotations

from app.business_execution.schemas import ExecutionPack


def _clean(lines: list[str]) -> list[str]:
    out = []
    for line in lines:
        v = (line or "").strip()
        if v and v not in out:
            out.append(v)
    return out


def offer_pack(action_title: str, why: str, expected_result: str) -> ExecutionPack:
    return ExecutionPack(
        action_title=action_title,
        why=why,
        ready_steps=_clean([
            "Структура оффера: проблема → решение → ценность → формат → цена/условия.",
            "Готовый текст оффера под ваш проект.",
            "Блоки: ценность, доказательства, ограничения, CTA.",
            "CTA: что сделать клиенту сейчас (ответить, оставить заявку, созвон).",
        ]),
        artifacts=["Черновик оффера", "Текст CTA", "Короткая версия для мессенджера"],
        how_to_execute="Вставьте оффер на сайт/лендинг и отправьте целевым партнёрам только после approve Owner.",
        time_estimate="30-60 минут",
        expected_result=expected_result,
        pack_type="offer_pack",
    )


def partner_outreach_pack(action_title: str, why: str, expected_result: str) -> ExecutionPack:
    return ExecutionPack(
        action_title=action_title,
        why=why,
        ready_steps=_clean([
            "Список 5-10 потенциальных партнёров (категория + причина релевантности).",
            "Сообщение для первого контакта (краткое и расширенное).",
            "Сценарий диалога: открытие → ценность → предложение → следующий шаг.",
            "Шаблон follow-up через 48 часов.",
        ]),
        artifacts=["Шаблон outreach-сообщения", "Сценарий созвона", "Чеклист follow-up"],
        how_to_execute="Отправляйте по очереди, фиксируйте ответы и обновляйте приоритет списка.",
        time_estimate="45-90 минут",
        expected_result=expected_result,
        pack_type="partner_outreach_pack",
    )


def content_pack(action_title: str, why: str, expected_result: str) -> ExecutionPack:
    return ExecutionPack(
        action_title=action_title,
        why=why,
        ready_steps=_clean([
            "Готовый пост с ключевым оффером.",
            "3 варианта заголовка под разные площадки.",
            "Описание и CTA для канала/соцсети.",
            "Короткая версия анонса (до 280 символов).",
        ]),
        artifacts=["Текст поста", "Заголовки", "CTA"],
        how_to_execute="Публикуйте только после approve Owner, затем отслеживайте охват/клики.",
        time_estimate="20-45 минут",
        expected_result=expected_result,
        pack_type="content_pack",
    )


def landing_pack(action_title: str, why: str, expected_result: str) -> ExecutionPack:
    return ExecutionPack(
        action_title=action_title,
        why=why,
        ready_steps=_clean([
            "Структура страницы: hero, ценность, доказательства, оффер, FAQ, CTA.",
            "Тексты для каждого блока.",
            "Рекомендация по форме захвата лидов.",
            "Проверочный список перед запуском страницы.",
        ]),
        artifacts=["Структура лендинга", "Тексты блоков", "CTA и форма заявки"],
        how_to_execute="Соберите страницу в CMS/конструкторе, проверьте мобильную версию и подключите аналитику.",
        time_estimate="60-120 минут",
        expected_result=expected_result,
        pack_type="landing_pack",
    )


def launch_plan_pack(action_title: str, why: str, expected_result: str) -> ExecutionPack:
    return ExecutionPack(
        action_title=action_title,
        why=why,
        ready_steps=_clean([
            "Последовательность шагов запуска (T-7, T-3, T-1, T+1).",
            "Приоритеты: must / should / could.",
            "Ответственные роли и сроки.",
            "Риски запуска и fallback-план.",
        ]),
        artifacts=["План запуска", "Приоритеты", "Риск-таблица"],
        how_to_execute="Пройдите шаги по порядку, отмечайте завершение и блокеры перед следующим шагом.",
        time_estimate="45-90 минут",
        expected_result=expected_result,
        pack_type="launch_plan_pack",
    )


def generic_pack(action_title: str, why: str, expected_result: str) -> ExecutionPack:
    return ExecutionPack(
        action_title=action_title,
        why=why,
        ready_steps=_clean([
            "Сформулируйте конкретный результат шага (что должно быть готово).",
            "Подготовьте минимальный артефакт для выполнения.",
            "Согласуйте критичные действия с Owner.",
        ]),
        artifacts=["Черновой план", "Краткий артефакт для выполнения"],
        how_to_execute="Выполните шаг и зафиксируйте фактический результат в миссии.",
        time_estimate="30-60 минут",
        expected_result=expected_result,
        pack_type="generic_pack",
    )
