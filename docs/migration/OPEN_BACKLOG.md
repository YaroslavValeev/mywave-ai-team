# OPEN_BACKLOG — незакрытые вопросы и распределение по AI-команде

Дата: 2026-07-27  
Связано: [AGENT_TEAM_ROLLOUT.md](AGENT_TEAM_ROLLOUT.md), ADR-007, canvas `open-backlog-team`

## Порядок (логический)

1. **P1 / P1b** — structured `deliverable` + log/persist `agent_cluster` + TG hint ← *сейчас в коде*  
2. **TG smoke** — Owner после merge  
3. **P3** — isolation packs (убрать повтор Owner brief)  
4. **PN** — ParserNews CSV unique emails (только после Owner GO)  
5. **EX** — post-approve EXECUTE (Molt→Cursor)  
6. Deferred: EU auto-escalate, ALLOW_FALLBACK=false default, LangGraph  

## Матрица задач

| ID | Задача | Agent / subagent | Owner HITL | Статус |
|----|--------|------------------|------------|--------|
| P0 | ADR-007 hierarchy | Lead | merge #47 | **done** |
| P1 | handoff deliverable object | parent | merge+RU | **in progress** |
| P1b | agent_cluster log + triage_meta + TG | parent | smoke | **in progress** |
| P3 | context isolation | explore+parent | compare handoff size | open |
| PN | CSV 116 emails | shell+DATA | **GO export** | open |
| EX | EXECUTE after approve | molt/sdk | policy | open |
| UX | court brief duplication | parent | — | open (with P3) |
| EU | HIGH→cloud auto | policy | GO | deferred |
| FB | fallback=false default | shell | GO | deferred |
| LG | LangGraph | — | — | blocked |

## Критерий готовности текущей волны

- [ ] PR Phase-1 merged  
- [ ] RU: `grep agent_cluster` в логах triage  
- [ ] TG summary содержит «Кластер агентов: MEDIA»  
- [ ] Handoff CONTENT содержит `payload.deliverable.kind=message_draft`  
