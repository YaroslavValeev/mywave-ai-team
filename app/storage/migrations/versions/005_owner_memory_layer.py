"""Owner Memory / Rules Layer: profiles, items, overrides + seed from canon YAML

Revision ID: 005
Revises: 004
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
import yaml
from alembic import op
from sqlalchemy import inspect, text

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def _canon_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "owner_memory_canon.yaml"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not insp.has_table("owner_profiles"):
        op.create_table(
            "owner_profiles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("owner_key", sa.String(64), nullable=False),
            sa.Column("display_name", sa.String(256), nullable=False),
            sa.Column("role", sa.String(128), nullable=True),
            sa.Column("primary_interface", sa.String(64), nullable=True),
            sa.Column("preferred_work_mode", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("owner_key"),
        )
        op.create_index("ix_owner_profiles_owner_key", "owner_profiles", ["owner_key"], unique=False)

    if not insp.has_table("owner_memory_items"):
        op.create_table(
            "owner_memory_items",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("owner_key", sa.String(64), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False),
            sa.Column("item_key", sa.String(128), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("tier", sa.String(32), nullable=False),
            sa.Column("strength", sa.Float(), nullable=False),
            sa.Column("weight", sa.Float(), nullable=False),
            sa.Column("priority_rank", sa.Integer(), nullable=False),
            sa.Column("scope", sa.String(64), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("is_confirmed", sa.Boolean(), nullable=False),
            sa.Column("meta_json", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_owner_memory_items_owner_key", "owner_memory_items", ["owner_key"], unique=False)
        op.create_index("ix_owner_memory_items_kind", "owner_memory_items", ["kind"], unique=False)
        op.create_index("ix_owner_memory_items_item_key", "owner_memory_items", ["item_key"], unique=False)
        op.create_index("ix_owner_memory_items_scope", "owner_memory_items", ["scope"], unique=False)

    if not insp.has_table("owner_overrides"):
        op.create_table(
            "owner_overrides",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("owner_key", sa.String(64), nullable=False),
            sa.Column("target_scope", sa.String(64), nullable=False),
            sa.Column("target_id", sa.String(128), nullable=False),
            sa.Column("override_text", sa.Text(), nullable=False),
            sa.Column("valid_until", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("meta_json", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_owner_overrides_owner_key", "owner_overrides", ["owner_key"], unique=False)
        op.create_index("ix_owner_overrides_target_scope", "owner_overrides", ["target_scope"], unique=False)
        op.create_index("ix_owner_overrides_target_id", "owner_overrides", ["target_id"], unique=False)

    # Seed (идемпотентно по owner_key + item_key)
    path = _canon_path()
    if not path.is_file():
        return
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    profile = data.get("profile") or {}
    owner_key = profile.get("owner_key") or "default"
    now = datetime.utcnow()

    r = bind.execute(text("SELECT id FROM owner_profiles WHERE owner_key = :k"), {"k": owner_key}).fetchone()
    if not r:
        bind.execute(
            sa.text(
                """INSERT INTO owner_profiles
                (owner_key, display_name, role, primary_interface, preferred_work_mode, created_at, updated_at)
                VALUES (:ok, :dn, :role, :pi, :pwm, :ca, :ua)"""
            ),
            {
                "ok": owner_key,
                "dn": profile.get("display_name") or "Owner",
                "role": profile.get("role"),
                "pi": profile.get("primary_interface"),
                "pwm": profile.get("preferred_work_mode"),
                "ca": now,
                "ua": now,
            },
        )

    for item in data.get("items") or []:
        ik = item.get("item_key")
        if not ik:
            continue
        exists = bind.execute(
            text("SELECT id FROM owner_memory_items WHERE owner_key = :ok AND item_key = :ik"),
            {"ok": owner_key, "ik": ik},
        ).fetchone()
        if exists:
            continue
        bind.execute(
            sa.text(
                """INSERT INTO owner_memory_items
                (owner_key, kind, item_key, text, tier, strength, weight, priority_rank, scope,
                 is_active, is_confirmed, meta_json, created_at, updated_at)
                VALUES (:ok, :kind, :ik, :txt, :tier, :str, :w, :pr, :sc, :ia, :ic, :mj, :ca, :ua)"""
            ),
            {
                "ok": owner_key,
                "kind": item.get("kind") or "rule",
                "ik": ik,
                "txt": item.get("text") or "",
                "tier": item.get("tier") or "canonical",
                "str": float(item.get("strength") or 1.0),
                "w": float(item.get("weight") or item.get("strength") or 1.0),
                "pr": int(item.get("priority_rank") or 0),
                "sc": item.get("scope") or "global",
                "ia": bool(item.get("is_active", True)),
                "ic": bool(item.get("is_confirmed", True)),
                "mj": None,
                "ca": now,
                "ua": now,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    for t in ("owner_overrides", "owner_memory_items", "owner_profiles"):
        if insp.has_table(t):
            op.drop_table(t)
