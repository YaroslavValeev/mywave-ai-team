# Collaboration outcome persistence

## Хранилище
- **Файл:** `app/data/collaboration_outcomes.json`
- **Override:** переменная окружения `COLLABORATION_OUTCOMES_PATH`

## Связь с executions
- Ключ записи: `outcome_id = co_{execution_id}`.
- `execution_id` дублируется в payload для traceability.
- Один основной документ на execution (последний evaluate перезаписывает поля post/status).

## On-demand vs persisted
- **Persisted:** baseline при `mark_collaboration_execution_closed` (через `record_collaboration_outcome_baseline_on_close`).
- **Persisted:** результат каждого `evaluate_collaboration_execution_outcome` (post bundle, status, labels, reasons).
- **On-demand:** сырые сигналы из `owner_insights` / `list_projects` не кешируются отдельно — пересчитываются при baseline/evaluate.

## Audit
- См. `COLLABORATION_OUTCOME_AUDIT_MODEL.md`; события пишутся через существующий `log_audit`.

## Совместимость
- Executions, созданные до Phase 11.5, при первом evaluate дадут `insufficient_data` до тех пор, пока не будет baseline (закрытие заново не требуется для старых — только осознанный пересчёт после нового close или ручная миграция не делается в baseline).
