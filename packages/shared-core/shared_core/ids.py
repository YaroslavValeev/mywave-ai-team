# Генерация канонических ID. Только shared-core выдаёт task_id, run_id и т.д.
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional


def _uuid7_like() -> str:
    """Уникальный строковый ID (UUID4 для совместимости; при необходимости заменить на UUID7)."""
    return str(uuid.uuid4()).replace("-", "")[:24]


class TaskIdFactory:
    """Единственная точка создания task_id. Вызывается при create_task в shared-core."""

    @staticmethod
    def create(prefix: str = "task") -> str:
        return f"{prefix}_{_uuid7_like()}"


class RunIdFactory:
    """Единственная точка создания run_id. Вызывается при create_run в shared-core (только Molt инициирует)."""

    @staticmethod
    def create(prefix: str = "run") -> str:
        return f"{prefix}_{_uuid7_like()}"


class DecisionIdFactory:
    @staticmethod
    def create(prefix: str = "dec") -> str:
        return f"{prefix}_{_uuid7_like()}"


class ApprovalIdFactory:
    @staticmethod
    def create(prefix: str = "appr") -> str:
        return f"{prefix}_{_uuid7_like()}"


class ArtifactIdFactory:
    @staticmethod
    def create(prefix: str = "art") -> str:
        return f"{prefix}_{_uuid7_like()}"


class MemoryIdFactory:
    @staticmethod
    def create(prefix: str = "mem") -> str:
        return f"{prefix}_{_uuid7_like()}"


class EventIdFactory:
    @staticmethod
    def create(prefix: str = "evt") -> str:
        return f"{prefix}_{_uuid7_like()}"


class ProjectIdFactory:
    @staticmethod
    def create(prefix: str = "proj") -> str:
        return f"{prefix}_{_uuid7_like()}"
