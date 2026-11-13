# app/services/registry_validation.py — Phase 10.7: validation baseline for registry patches
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

_RESULT_OK = "ok"
_RESULT_ERROR = "error"


def _parse_yaml(content: str) -> tuple[str, list[str], Any]:
    """Парсит YAML; возвращает (status, errors, data)."""
    errs: list[str] = []
    try:
        data = yaml.safe_load(content)
        if data is None:
            data = {}
        return _RESULT_OK, [], data
    except yaml.YAMLError as e:
        errs.append(str(e))
        return _RESULT_ERROR, errs, None


def validate_yaml_file(path: Path) -> tuple[str, list[str], Any]:
    """Проверка файла: парсинг YAML. Возвращает (status, errors, parsed_data)."""
    if not path.exists():
        return _RESULT_ERROR, [f"File not found: {path}"], None
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return _RESULT_ERROR, [f"Read error: {e}"], None
    return _parse_yaml(content)


def validate_yaml_content(content: str) -> tuple[str, list[str], Any]:
    """Проверка содержимого (для dry-run после применения патча в памяти)."""
    return _parse_yaml(content)


def validate_specializations_structure(data: dict[str, Any]) -> tuple[str, list[str]]:
    """Проверка структуры specializations: ключ specializations, записи с specialization_key, domain_key, workflow_step."""
    errs: list[str] = []
    if not isinstance(data, dict):
        errs.append("Root must be a dict")
        return _RESULT_ERROR, errs
    spec = data.get("specializations")
    if spec is None:
        errs.append("Missing key: specializations")
        return _RESULT_ERROR, errs
    if not isinstance(spec, dict):
        errs.append("specializations must be a dict")
        return _RESULT_ERROR, errs
    for key, entry in spec.items():
        if not isinstance(entry, dict):
            errs.append(f"specializations.{key}: entry must be a dict")
            continue
        for req in ("specialization_key", "domain_key", "workflow_step"):
            if req not in entry:
                errs.append(f"specializations.{key}: missing {req}")
    return (_RESULT_OK, []) if not errs else (_RESULT_ERROR, errs)


def validate_domain_registry_structure(data: dict[str, Any]) -> tuple[str, list[str]]:
    """Проверка структуры domain_registry: ключ domains, вложенные объекты с routing_keywords (list)."""
    errs: list[str] = []
    if not isinstance(data, dict):
        errs.append("Root must be a dict")
        return _RESULT_ERROR, errs
    domains = data.get("domains")
    if domains is None:
        errs.append("Missing key: domains")
        return _RESULT_ERROR, errs
    if not isinstance(domains, dict):
        errs.append("domains must be a dict")
        return _RESULT_ERROR, errs
    for dk, entry in domains.items():
        if not isinstance(entry, dict):
            errs.append(f"domains.{dk}: entry must be a dict")
            continue
        if "routing_keywords" in entry and not isinstance(entry["routing_keywords"], list):
            errs.append(f"domains.{dk}: routing_keywords must be a list")
    return (_RESULT_OK, []) if not errs else (_RESULT_ERROR, errs)


def check_duplicate_specialization_key(data: dict[str, Any], key: str) -> bool:
    """True если ключ уже есть в specializations."""
    spec = (data or {}).get("specializations") or {}
    return key in spec
