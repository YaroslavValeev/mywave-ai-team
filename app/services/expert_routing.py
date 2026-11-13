# app/services/expert_routing.py — Phase 9.9: explainable keyword/signal-based domain routing
from __future__ import annotations

import re
from typing import Any

from app.services.domain_registry import list_domains, get_domain


def _normalize_text(text: str) -> str:
    return (text or "").lower().strip()

def _tokenize(text: str) -> set[str]:
    """Слова и короткие фразы (2–3 слова) из текста."""
    t = _normalize_text(text)
    words = set(re.findall(r"[a-zа-яё0-9]+", t))
    # добавить биграммы для типичных запросов
    parts = re.split(r"\s+", t)
    for i in range(len(parts) - 1):
        words.add(parts[i] + " " + parts[i + 1])
    return words


def suggest_domains_for_task(task_text: str, limit: int = 5) -> list[dict[str, Any]]:
    """Предложить домены для задачи с explainable scores и причинами."""
    text = _normalize_text(task_text)
    if not text:
        return []
    tokens = _tokenize(task_text)
    scored: list[tuple[float, dict[str, Any], list[str], bool]] = []

    for d in list_domains():
        keywords = [str(k).lower() for k in (d.get("routing_keywords") or [])]
        typical = [str(r).lower() for r in (d.get("typical_requests") or [])]
        aliases = [str(a).lower() for a in (d.get("aliases") or [])]
        all_signals = set(keywords) | set(typical) | set(aliases) | {d.get("domain_key", "").lower()}

        matched: list[str] = []
        score = 0.0
        for tok in tokens:
            if len(tok) < 2:
                continue
            for sig in all_signals:
                if tok in sig or sig in tok or (len(tok) > 3 and sig in tok):
                    score += 1.0
                    if sig not in matched:
                        matched.append(sig)
        for phrase in typical:
            if phrase in text or text in phrase:
                score += 2.0
                if phrase not in matched:
                    matched.append(phrase)
        for kw in keywords:
            if kw in text:
                score += 1.0
                if kw not in matched:
                    matched.append(kw)

        fallback_priority = int(d.get("fallback_priority") or 99)
        scored.append((score, d, matched[:15], False))

    scored.sort(key=lambda x: (-x[0], x[1].get("fallback_priority", 99)))
    result = []
    for sc, dom, matched, _ in scored[: limit + 5]:
        if sc > 0 or len(result) < limit:
            entry = {
                "domain_key": dom.get("domain_key"),
                "canonical_name": dom.get("canonical_name"),
                "score": sc,
                "matched_keywords": matched,
                "reason": "Совпадения: " + ", ".join(matched[:5]) if matched else "Нет совпадений",
                "is_primary": False,
                "is_secondary": False,
                "is_fallback": False,
            }
            result.append(entry)
    # primary = первый с score > 0, иначе fallback по приоритету
    if result:
        if result[0].get("score", 0) > 0:
            result[0]["is_primary"] = True
        else:
            result[0]["is_fallback"] = True
        for i in range(1, min(3, len(result))):
            if result[i].get("score", 0) > 0:
                result[i]["is_secondary"] = True
    return result[:limit]


def explain_domain_match(task_text: str, domain_key: str) -> dict[str, Any]:
    """Объяснение, почему домен подходит (или не подходит) к задаче."""
    suggestions = suggest_domains_for_task(task_text, limit=10)
    for s in suggestions:
        if s.get("domain_key") == domain_key:
            return {
                "domain_key": domain_key,
                "matched_keywords": s.get("matched_keywords", []),
                "reason": s.get("reason", ""),
                "score": s.get("score", 0),
                "is_primary": s.get("is_primary", False),
                "is_secondary": s.get("is_secondary", False),
            }
    dom = get_domain(domain_key)
    return {
        "domain_key": domain_key,
        "matched_keywords": [],
        "reason": "Домен не совпал с текстом задачи по ключевым словам.",
        "score": 0,
        "is_primary": False,
        "is_secondary": False,
        "canonical_name": dom.get("canonical_name") if dom else None,
    }


def get_primary_domain_for_task(task_text: str) -> dict[str, Any] | None:
    """Основной домен для задачи (первый с положительным score или fallback)."""
    suggestions = suggest_domains_for_task(task_text, limit=5)
    for s in suggestions:
        if s.get("is_primary") or s.get("is_fallback"):
            return s
    return None


def get_secondary_domains_for_task(task_text: str, limit: int = 2) -> list[dict[str, Any]]:
    """Вторичные домены для задачи."""
    suggestions = suggest_domains_for_task(task_text, limit=limit + 3)
    return [s for s in suggestions if s.get("is_secondary")][:limit]
