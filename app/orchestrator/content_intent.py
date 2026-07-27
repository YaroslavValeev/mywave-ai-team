"""Content / outreach drafts for MEDIA_OPS content_pipeline (owner-facing deliverable)."""

from __future__ import annotations

import re


_CONTACT_RE = re.compile(
    r"(?:контакт\w*|рассылк\w*|parsernews|парсер|email|e-mail|телеграм.?канал|участник\w*)",
    re.IGNORECASE | re.UNICODE,
)
_MESSAGE_RE = re.compile(
    r"(?:сообщен\w*|текст|написа\w*|дружелюбн\w*|приветств\w*|пост\w*|анонс\w*)",
    re.IGNORECASE | re.UNICODE,
)

DEFAULT_SITE = "https://mywavewake.ru"
DEFAULT_YCLIENTS = (
    "https://n347190.yclients.com/company/2043174/personal/menu?o="
)


def is_content_outreach_brief(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    return bool(_CONTACT_RE.search(raw) or _MESSAGE_RE.search(raw))


def build_content_outreach_draft(owner_brief: str) -> dict[str, list[str]]:
    """Rule-based deliverable: message draft + contact-collection checklist.

    Does NOT scrape ParserNews/live DBs — that needs EXECUTE + Cursor/runner after owner approve.
    """
    brief = (owner_brief or "").strip()
    usp = _extract_usp_bullets(brief)
    channels = _extract_channels(brief)
    site = _extract_site(brief) or DEFAULT_SITE
    yclients = _extract_yclients(brief) or DEFAULT_YCLIENTS

    message_lines = [
        "Привет! Это команда MyWave 👋",
        "",
        "Мы вместе с Loaded открыли клуб на Озернинском водохранилище.",
        "",
        "Почему к нам:",
    ]
    for u in usp:
        message_lines.append(f"• {u}")
    message_lines.extend(
        [
            "",
            "Подробнее и запись:",
            f"• сайт: {site}",
            f"• онлайн-запись YClients: {yclients}",
            "",
            "Telegram:",
        ]
    )
    if channels:
        for ch in channels:
            message_lines.append(f"• {ch}")
    else:
        message_lines.extend(
            [
                "• @MyWave_Admin — запись",
                "• @MyWave_WakesurfNews — новости вейка",
            ]
        )
    message_lines.extend(["", "Будем рады видеть вас на воде!"])

    return {
        "message_draft": message_lines,
        "contact_plan": [
            "Источник контактов (из брифа): ParserNews — выгрузить все доступные контакты.",
            "Это EXECUTE-шаг: нужен доступ к проекту/БД ParserNews (Cursor runner или ручной экспорт).",
            "До approve: зафиксировать поля выгрузки (имя, канал, username/phone/email, согласие на связь).",
            "После approve: прогнать выгрузку → дедуп → сегмент «можно писать» vs «нужно уточнить».",
            "Не слать массово без owner approve (публикация / PII / репутация).",
        ],
        "channels_cta": [
            f"Площадка: {site}",
            f"YClients: {yclients}",
            *(channels or ["@MyWave_Admin (запись)", "@MyWave_WakesurfNews (новости)"]),
            "CTA: «Напиши в @MyWave_Admin — подберём слот» / «Запись на сайте или в YClients».",
        ],
        "owner_now": [
            "1) Проверь черновик сообщения ниже — тон/факты/USP.",
            "2) Подтверди, что ParserNews доступен для выгрузки (путь/репо/учётка).",
            "3) Нажми «Утвердить» только когда готов к EXECUTE сбора контактов + рассылки.",
            "4) Или «Доработать» / «OpenAI (EU)» если нужен более сильный текст.",
        ],
        "honest_limits": [
            "Сейчас режим PLAN: система подготовила черновик текста и чеклист сбора контактов.",
            "Автоматический парсинг ParserNews и отправка сообщений в этом шаге НЕ выполняются.",
            "После approve — отдельный execute (Cursor/runner или ручной экспорт).",
        ],
    }


def _extract_usp_bullets(brief: str) -> list[str]:
    """Canonical outreach USP (marketing SoT). Brief may add extras later; do not drop defaults."""
    defaults = [
        "самая чистая вода — водохранилище со статусом питьевого запаса Москвы",
        "большая акватория, красивые заливы и укрытия от ветра",
        "без катеров с волной (только рыбацкие резиновые лодки)",
        "тренер с 24-летним стажем; чемпион Москвы 2026 (ФСР) — ученик тренера",
        "Ваш тренер — мой ученик. Тренируйся с эффективным тренером, а не с громким вейксерфером",
    ]
    # Keep signature for callers; brief reserved for future optional extras.
    _ = (brief or "").strip()
    return list(defaults)


def _extract_channels(brief: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"@([A-Za-z0-9_]{3,64})", brief):
        handle = f"@{m.group(1)}"
        if handle not in out:
            out.append(handle)
    # named channels without @
    for name, label in (
        ("MyWave_Admin", "@MyWave_Admin — запись"),
        ("MyWave_WakesurfNews", "@MyWave_WakesurfNews — новости"),
    ):
        if name.lower() in brief.lower() and not any(name in x for x in out):
            out.append(label)
    return out


def _extract_site(brief: str) -> str | None:
    # Prefer site URL; ignore yclients links here.
    for m in re.finditer(r"(https?://[^\s]+|mywavewake\.ru[^\s]*)", brief, re.IGNORECASE):
        url = m.group(1).rstrip(").,;")
        if "yclients.com" in url.lower():
            continue
        if not url.startswith("http"):
            url = "https://" + url
        return url
    return None


def _extract_yclients(brief: str) -> str | None:
    m = re.search(r"(https?://[^\s]*yclients\.com[^\s]*)", brief, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).rstrip(").,;")
