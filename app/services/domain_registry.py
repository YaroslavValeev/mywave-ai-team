# app/services/domain_registry.py — Phase 9.9: domain expertise registry (reads registry, not raw know_proff)
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _get_registry_dir() -> Path | None:
    """Каталог с domain_registry.yaml и domain_aliases.yaml."""
    env_path = os.environ.get("KNOW_PROFF_REGISTRY_DIR", "").strip()
    if env_path:
        p = Path(env_path)
        if (p / "domain_registry.yaml").exists():
            return p
    # От app/services/domain_registry.py: parents[1]=app → app/data/domain_registry; workspace docs = parents[4]/[5]
    resolved = Path(__file__).resolve()
    candidates = [resolved.parents[1] / "data" / "domain_registry"]
    if len(resolved.parents) > 4:
        candidates.insert(0, resolved.parents[4] / "docs" / "know_proff" / "registry")
    if len(resolved.parents) > 5:
        candidates.insert(0, resolved.parents[5] / "docs" / "know_proff" / "registry")
    candidates.extend([
        Path.cwd() / "docs" / "know_proff" / "registry",
        Path.cwd() / ".." / "docs" / "know_proff" / "registry",
    ])
    for base in candidates:
        if (base / "domain_registry.yaml").exists():
            return base
    return None


def _load_registry() -> dict[str, Any]:
    """Загрузить domain_registry.yaml. Кэш не делаем — файл маленький."""
    reg_dir = _get_registry_dir()
    if not reg_dir:
        return {"domains": {}}
    path = reg_dir / "domain_registry.yaml"
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {"domains": {}}
    except Exception:
        return {"domains": {}}


def _load_aliases() -> dict[str, str]:
    """Канонический domain_key по алиасу (нормализованный нижний регистр)."""
    reg_dir = _get_registry_dir()
    if not reg_dir:
        return {}
    path = reg_dir / "domain_aliases.yaml"
    out: dict[str, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        mapping = data.get("mapping") or data.get("domains") or {}
        for dk, info in (mapping if isinstance(mapping, dict) else {}).items():
            if isinstance(info, dict):
                canonical = info.get("canonical") or dk
                aliases = info.get("aliases") or []
                out[str(dk).lower()] = str(canonical)
                for a in aliases:
                    out[str(a).lower().strip()] = str(canonical)
            else:
                out[str(dk).lower()] = str(dk)
    except Exception:
        pass
    # Из domain_registry.yaml тоже собрать domain_key и aliases
    reg = _load_registry()
    for dk, ent in (reg.get("domains") or {}).items():
        if isinstance(ent, dict):
            out[str(dk).lower()] = str(dk)
            for a in ent.get("aliases") or []:
                out[str(a).lower().strip()] = str(dk)
    return out


def list_domains() -> list[dict[str, Any]]:
    """Список всех доменов из реестра."""
    reg = _load_registry()
    domains = reg.get("domains") or {}
    return [dict(entry, domain_key=dk) for dk, entry in domains.items() if isinstance(entry, dict)]


def get_domain(domain_key: str) -> dict[str, Any] | None:
    """Домен по domain_key."""
    reg = _load_registry()
    domains = reg.get("domains") or {}
    ent = domains.get(domain_key)
    if isinstance(ent, dict):
        return dict(ent, domain_key=domain_key)
    # попробовать по алиасу
    key = get_domain_by_alias(domain_key)
    if key:
        return get_domain(key)
    return None


def get_domain_by_alias(name: str) -> str | None:
    """Канонический domain_key по алиасу или имени файла."""
    name = (name or "").strip().lower()
    if not name:
        return None
    aliases = _load_aliases()
    return aliases.get(name)


def get_domain_registry_summary() -> dict[str, Any]:
    """Краткая сводка реестра: количество доменов, список ключей."""
    doms = list_domains()
    return {
        "total": len(doms),
        "domain_keys": [d.get("domain_key") for d in doms if d.get("domain_key")],
    }


def get_expert_profile(domain_key: str) -> dict[str, Any] | None:
    """Экспертный профиль по домену (baseline: один профиль на домен из полей реестра)."""
    dom = get_domain(domain_key)
    if not dom:
        return None
    return {
        "expert_profile_key": dom.get("domain_key"),
        "domain_key": dom.get("domain_key"),
        "profile_name": dom.get("canonical_name"),
        "scope": dom.get("summary"),
        "strengths": dom.get("routing_keywords", [])[:10],
        "methods": [],
        "typical_outputs": dom.get("typical_requests", []),
        "good_for": dom.get("typical_requests", []),
        "not_for": [],
        "context_pack_sections": ["summary", "strengths", "typical_requests", "routing_keywords"],
    }


def get_domain_context_pack(domain_key: str) -> dict[str, Any] | None:
    """Контекст-пак по домену для промптов/рекомендаций (без сырого текста файла)."""
    dom = get_domain(domain_key)
    if not dom:
        return None
    return {
        "domain_key": dom.get("domain_key"),
        "canonical_name": dom.get("canonical_name"),
        "summary": dom.get("summary"),
        "routing_keywords": dom.get("routing_keywords", []),
        "typical_requests": dom.get("typical_requests", []),
        "source_file": dom.get("source_file"),
        "structure_type": dom.get("structure_type"),
    }


def search_domains(query: str) -> list[dict[str, Any]]:
    """Поиск доменов по query (по summary, keywords, typical_requests)."""
    query = (query or "").strip().lower()
    if not query:
        return list_domains()
    doms = list_domains()
    out = []
    for d in doms:
        score = 0
        if query in (d.get("summary") or "").lower():
            score += 2
        if query in (d.get("canonical_name") or "").lower():
            score += 2
        for kw in d.get("routing_keywords") or []:
            if query in str(kw).lower():
                score += 1
        for tr in d.get("typical_requests") or []:
            if query in str(tr).lower():
                score += 1
        if query in str(d.get("domain_key", "")).lower():
            score += 1
        if score > 0:
            out.append(dict(d, _score=score))
    out.sort(key=lambda x: (-x.get("_score", 0), x.get("domain_key", "")))
    for d in out:
        d.pop("_score", None)
    return out
