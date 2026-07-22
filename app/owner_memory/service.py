# Чтение Owner Memory и сборка bundle для движка
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.owner_memory.schemas import OwnerRuleItemPublic, OwnerRulesBundle
from app.owner_memory.seed import ensure_canonical_owner_memory

if TYPE_CHECKING:
    from app.storage.repositories import TaskRepository


def owner_memory_enabled() -> bool:
    return os.getenv("OWNER_MEMORY_ENABLED", "true").strip().lower() in {"1", "true", "yes"}


class OwnerMemoryService:
    def __init__(self, repo: TaskRepository, owner_key: str = "default"):
        self.repo = repo
        self.owner_key = owner_key

    def get_owner_profile(self):
        if os.getenv("OWNER_MEMORY_AUTO_SEED", "true").strip().lower() in {"1", "true", "yes"}:
            ensure_canonical_owner_memory(self.repo, self.owner_key)
        return self.repo.get_owner_profile(self.owner_key)

    def build_owner_rules_bundle(
        self,
        *,
        context_scopes: list[str] | None = None,
        target_scope: str | None = None,
        target_id: str | None = None,
    ) -> OwnerRulesBundle:
        if not owner_memory_enabled():
            return OwnerRulesBundle(owner_key=self.owner_key)
        if os.getenv("OWNER_MEMORY_AUTO_SEED", "true").strip().lower() in {"1", "true", "yes"}:
            ensure_canonical_owner_memory(self.repo, self.owner_key)

        scopes = context_scopes or ["global"]
        items = self.repo.list_owner_memory_items(
            self.owner_key,
            scopes=scopes,
            active_only=True,
        )

        def to_pub(row) -> OwnerRuleItemPublic:
            return OwnerRuleItemPublic(
                id=row.id,
                kind=row.kind,
                item_key=row.item_key,
                text=row.text,
                tier=row.tier,
                scope=row.scope,
                strength=float(row.strength),
                weight=float(row.weight),
                priority_rank=int(row.priority_rank),
            )

        rules, prefs, prios = [], [], []
        for row in items:
            if row.tier == "inferred" and not row.is_confirmed:
                continue
            if row.kind == "rule":
                rules.append(to_pub(row))
            elif row.kind == "preference":
                prefs.append(to_pub(row))
            elif row.kind == "priority":
                prios.append(to_pub(row))
            elif row.kind == "pattern":
                if row.is_confirmed:
                    prefs.append(to_pub(row))

        ov_list: list[dict] = []
        if target_scope and target_id:
            for o in self.repo.list_valid_owner_overrides(self.owner_key, target_scope, target_id):
                ov_list.append(
                    {
                        "id": o.id,
                        "override_text": o.override_text,
                        "valid_until": o.valid_until.isoformat() if o.valid_until else None,
                    }
                )

        return OwnerRulesBundle(
            owner_key=self.owner_key,
            rules=rules,
            preferences=prefs,
            priorities=prios,
            overrides=ov_list,
        )


def build_owner_rules_bundle(
    repo: TaskRepository,
    *,
    context_scopes: list[str] | None = None,
    target_scope: str | None = None,
    target_id: str | None = None,
    owner_key: str = "default",
) -> OwnerRulesBundle:
    return OwnerMemoryService(repo, owner_key).build_owner_rules_bundle(
        context_scopes=context_scopes,
        target_scope=target_scope,
        target_id=target_id,
    )
