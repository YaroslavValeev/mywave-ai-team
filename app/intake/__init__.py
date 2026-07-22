# Smart Intake Layer — нормализация входа до AI Office (v0/v1)
from app.intake.normalize import normalize_intake, task_brief_to_owner_text
from app.intake.schemas import (
    NormalizeIntakeRequest,
    NormalizeIntakeResponse,
    TaskBrief,
)

__all__ = [
    "normalize_intake",
    "task_brief_to_owner_text",
    "NormalizeIntakeRequest",
    "NormalizeIntakeResponse",
    "TaskBrief",
]
