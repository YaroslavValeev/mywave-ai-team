# Boundary: Site Chat KB ↔ Agents knowledge_intake

Status: accepted (KB-B, 2026-11-23)

## Roles

| Contour | Owner path | Purpose | Write path |
|---------|------------|---------|------------|
| **Site Chat KB** | `/var/www/mywave/knowledge_base/` | FAQ / project snippets for public chat | MD/TXT edit + Site deploy |
| **Agents intake** | `app/knowledge_intake/` in mywave-ai-team | Owner draft → approve → internal memory | Telegram/API draft flow |
| **shared-core MemoryEntry** | umbrella packages | Target cross-layer SoT | Not yet replacing Site KB |

## Rules

1. Do **not** copy Site `knowledge_base/chat/**` into Agents memory automatically.
2. Do **not** publish Agents `knowledge_intake` drafts into Site Chat KB without an explicit bridge + Owner approve.
3. Project one-pagers for the public chat live only in Site `knowledge_base/projects/{wakesurf_safari,wake_challenge,mywave_ruza_camp}.txt`.
4. Prices and booking facts stay in Site `configs/services.yaml`, not in memory snippets.
5. Wave 2 `knowledge_base/chat/projects/` remains optional; until filled, chat uses `projects/*.txt` allowlist.

## Bridge (future, not this PR)

A bridge may sync **approved** intake → Site only if:
- policy marks the artifact `publish_to_site_kb=true`;
- target path is explicit;
- Owner approve gate fires (critical write).

Until then: two stores, one map, no silent sync.
