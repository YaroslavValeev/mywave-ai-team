# Molt runtime expectations (Phase 8.6)

Практичный операционный baseline: что система должна обеспечивать без полноценных SRE/SLO. Используется для проверки готовности и при операционных drill’ах.

---

## Ожидания

1. **Molt отвечает на GET /health**  
   В рабочем состоянии процесс возвращает 200 и `{"status":"ok"}` (или эквивалент). Используется для быстрой проверки «процесс жив».

2. **Molt отвечает на GET /ready**  
   Когда конфиг и runtime-зависимости в порядке, возвращается `{"status":"ready"}`. Перед началом трафика проверять /ready, а не только /health.

3. **Smoke-check проходит**  
   После старта Molt скрипт `scripts/molt/smoke_check_molt_http.py` успешно выполняет health, ready и минимум один boundary-вызов (например create_execution). Это базовая проверка работоспособности boundary.

4. **Basic create_execution работает**  
   В нормальном режиме запрос CreateExecution к Molt (напрямую или через Agents) принимается и возвращает корректный ответ (accepted=true и ожидаемые поля). Ошибки бизнес-логики (accepted=false) считаются отдельно и не означают нарушение этого ожидания.

5. **Retry errors видны**  
   При временной недоступности или таймаутах клиент логирует transport_error и при включённом retry — повторные попытки. В логах и при необходимости в метриках можно увидеть факт ошибок и retry (см. MOLT_BOUNDARY_ERROR_MODEL, MOLT_OBSERVABILITY_MODEL).

6. **Rollback выполним вручную за понятные шаги**  
   Откат с http на stub или local описан в ROLLBACK_HTTP_RUNTIME.md и поддерживается скриптами rollback_to_stub.py, rollback_to_local.py. Владелец или инженер может выполнить откат по документации без скрытых шагов.

---

## Не входит в этот baseline

- Формальные SLO (availability %, latency percentiles).
- Cluster failover и distributed recovery.
- Автоматическая смена режимов (только ручной rollback по документации).
- Гарантии по данным при сбоях (persistence и backup — отдельная тема).

---

## Проверка соответствия

- Регулярно: `check_stack_status.py` (health, ready, metrics, summary).
- После изменений или drill: `smoke_check_molt_http.py`.
- При drill’ах: OPERATIONAL_DRILLS_PLAYBOOK.md и тесты Phase 8.6 (restart, outage, reconnect, rollback, status degraded).

См. также: MOLT_RUNTIME_SUPERVISION.md, DEGRADED_MODE_GUIDE.md, OPERATIONAL_DRILLS_PLAYBOOK.md.
