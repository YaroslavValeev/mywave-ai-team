# Role–domain heuristics (Phase 10.3)

Explainable правила: какой роли на какие домены обратить внимание.

## Owner

- **Домены с backlog/rework:** домены, по которым много задач в WAIT_OWNER, APPROVED_WAIT_MERGE или rework → «требуют внимания owner».
- **Override mismatches:** домены, где много override_mismatch_signal → «частая ручная коррекция домена».
- **Рекомендация:** «Наибольшее внимание: домены X, Y — разобрать approvals/rework; по домену Z много ручных правок домена».

## Operator

- **Домены с degraded/stuck:** домены, по которым сконцентрированы блокеры и long-running задачи (по effective domain задач в blockers/long_running).
- **Рекомендация:** «Основной проблемный домен сейчас — X (блокеры/зависшие задачи)».

## Executor

- **Домены с активной работой:** домены с наибольшим числом активных задач (IN_PIPELINE, IN_ROUNDTABLE, IN_COURT, NEW, TRIAGED и т.д.) и недавних артефактов.
- **Рекомендация:** «Больше всего активной работы сейчас в доменах X, Y».

## Reviewer

- **Домены с очередью решений:** домены, по которым сконцентрированы pending approvals и decision queue (effective domain задач в awaiting decisions).
- **Рекомендация:** «Основная очередь решений связана с доменами X, Y».

Все выводы — rule-based, с явным evidence_summary (количество задач, тип: approvals, rework, blockers и т.д.).
