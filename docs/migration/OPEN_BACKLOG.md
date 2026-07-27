# OPEN_BACKLOG — незакрытые вопросы и распределение по AI-команде

Дата: 2026-07-27  
Связано: [AGENT_TEAM_ROLLOUT.md](AGENT_TEAM_ROLLOUT.md), ADR-007, canvas `open-backlog-team`

## Порядок (логический)

1. **P1 / P1b** — structured `deliverable` + log/persist `agent_cluster` + TG hint ← *done*  
2. **TG smoke** — Owner после merge ← *done (#32/#33)*  
3. **P3** — isolation packs ← *done (#49)*  
4. **PN** — ParserNews CSV unique emails ← *script done; export on GO*  
5. **EX** — post-approve EXECUTE (pack/Cursor) ← *in this PR*  
6. Deferred: EU auto-escalate, ALLOW_FALLBACK=false default, LangGraph  

## Матрица задач

| ID | Задача | Agent / subagent | Owner HITL | Статус |
|----|--------|------------------|------------|--------|
| P0 | ADR-007 hierarchy | Lead | merge #47 | **done** |
| P1 | handoff deliverable object | parent | merge+RU | **done** (#48, #32) |
| P1b | agent_cluster log + triage_meta + TG | parent | smoke | **done** |
| P3 | context isolation | explore+parent | compare handoff size | **done** (#49, #33) |
| PN | CSV unique contacts | shell+DATA | **GO export** | **done** (script; 3 email + 113 handles) |
| EX | EXECUTE after approve | parent | approve→pack | **in progress** (minimal pack) |
| UX | court brief duplication | parent | — | open (noise leftover) |
| EU | HIGH→cloud auto | policy | GO | deferred |
| FB | fallback=false default | shell | GO | deferred |
| LG | LangGraph | — | — | blocked |

## Критерий готовности текущей волны

- [ ] PR Phase-1 merged  
- [ ] RU: `grep agent_cluster` в логах triage  
- [ ] TG summary содержит «Кластер агентов: MEDIA»  
- [ ] Handoff CONTENT содержит `payload.deliverable.kind=message_draft`  
