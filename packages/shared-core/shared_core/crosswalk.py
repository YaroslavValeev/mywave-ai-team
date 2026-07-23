# Crosswalk mapping: legacy_id <-> canonical_id (ADR-008).
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple


@dataclass
class CrosswalkEntry:
    source_system: str   # personal_helper | agents | molt
    legacy_entity_type: str  # task | run | decision | approval | artifact | memory | event | project
    legacy_id: str
    canonical_entity_type: str
    canonical_id: str
    created_at: datetime


class CrosswalkStore:
    """In-memory crosswalk. Для SQLite/Postgres — отдельный adapter с той же интерфейсом."""

    def __init__(self) -> None:
        self._by_legacy: Dict[Tuple[str, str, str], CrosswalkEntry] = {}
        self._by_canonical: Dict[Tuple[str, str], CrosswalkEntry] = {}

    def register(
        self,
        source_system: str,
        legacy_entity_type: str,
        legacy_id: str,
        canonical_entity_type: str,
        canonical_id: str,
        created_at: Optional[datetime] = None,
    ) -> CrosswalkEntry:
        now = created_at or datetime.utcnow()
        entry = CrosswalkEntry(
            source_system=source_system,
            legacy_entity_type=legacy_entity_type,
            legacy_id=str(legacy_id),
            canonical_entity_type=canonical_entity_type,
            canonical_id=canonical_id,
            created_at=now,
        )
        self._by_legacy[(source_system, legacy_entity_type, str(legacy_id))] = entry
        self._by_canonical[(canonical_entity_type, canonical_id)] = entry
        return entry

    def get_canonical(
        self,
        source_system: str,
        legacy_entity_type: str,
        legacy_id: str,
    ) -> Optional[str]:
        key = (source_system, legacy_entity_type, str(legacy_id))
        entry = self._by_legacy.get(key)
        return entry.canonical_id if entry else None

    def get_legacy(
        self,
        canonical_entity_type: str,
        canonical_id: str,
    ) -> Optional[Tuple[str, str, str]]:
        key = (canonical_entity_type, canonical_id)
        entry = self._by_canonical.get(key)
        if not entry:
            return None
        return (entry.source_system, entry.legacy_entity_type, entry.legacy_id)

    def list_by_source(self, source_system: str) -> List[CrosswalkEntry]:
        return [
            e for e in self._by_legacy.values()
            if e.source_system == source_system
        ]
