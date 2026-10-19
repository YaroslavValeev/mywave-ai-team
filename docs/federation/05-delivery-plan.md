# Порядок реализации и приёмка

Это последовательность спринтов с gates, не обещание календарных дат.
Зависимости: S0 → S1 → S2 → S3 → S4. Один PR — одна логическая цель;
Compose/infra отделяются от прикладных PR. Новые возможности выключены до gate.

| Спринт | Атомарные PR и слои | Результат и приёмка |
|---|---|---|
| S0: контекст | этот docs-only PR; затем перечень подтверждённых ролей/источников и владельцев данных | пять материалов, никакого включения новых прав; неизвестное явно обозначено |
| S1a: schema | storage migrations: workspace/membership, nullable связи legacy, backfill review | upgrade/restore на копии PG; legacy не получает автоматических прав, current API работает |
| S1b: policy | scoped repository/API/artifact/retrieval guards, membership/grants/mandate | отрицательные тесты F↔M, product↔product, JOINT без grant; запрет через прямой id/export/cache/background path |
| S1c: registry и аудит | registry/triage после policy; versioned decisions/action authorization | unknown handler не запускается; supersedes atomic, повтор не удваивает события; denied access виден в audit |
| S2a: executive | read-only overview API/UI, meeting briefing, CRM promises/risk projections | разделы дня и 72 часа с timezone, source links, unknown/stale; пять вопросов перед встречей без придумывания поручений |
| S2b: human action | storage/API/UI cards и text receipt; затем отдельный voice adapter | один receipt → одно обновление/контроль; неоднозначность не закрывает задачу; отправка follow-up требует approval |
| S3a: PMO/Москва | scoped handlers, месячный обзор и evidence completion | решения/просрочки/блокеры из реальных подтверждённых данных; измерения с unknown |
| S3b: сборная | event checklist/readiness, official source review, ограниченные файлы | источник у каждого критичного требования, видимые unknown и blockers; gate не заменяется процентом |
| S3c: Sport Station/finance | минимальные детские данные, group outcomes, payment preparation | sensitive intake blocked без основания; платежи только человеку; ownership методики MyWave и дополнений отдельно |
| S4a: продукты/пилоты | отдельные Media и Sponsor handlers + внутренний adapter; digital events | каждый продукт работает без другого; нет автоматического объединения CRM/финансов/договоров; J проекции только по grant |
| S4b: knowledge | scoped provenance/review integration и canonical context | hypothesis не выдаётся как verified; superseded не равноправен current; F источники не становятся коммерческой памятью |

## Readiness и KPI

Readiness сборной: показывать numerator/denominator, неизвестные и критичные
блокеры. Вес/состав checklist подтверждается владельцем конкретного старта.
Неизвестные не исключаются молча из знаменателя. При пустом checklist процент
null, а не 100%; при любом невыполненном критичном условии «готово» запрещено.
Формальные требования подтверждаются актуальным источником, не памятью LLM.

Основной KPI: часы владельца, сэкономленные на принятой бизнес-задаче.
Отдельно фиксировать baseline_minutes, owner_minutes, autonomous_actions,
rework, outcome evidence и acceptance. Если baseline или время не измерены,
saved_hours=null; отрицательную экономию не обнулять. Технические тесты,
количество агентов и отчёт не являются выполненным бизнес-результатом.

## Обязательные сценарии

1. «Что сегодня требует меня?» — scoped решения, физические действия, риски,
   ожидания, 72-часовые сроки; пустые данные явно пусты.
2. Briefing до встречи → заметки → draft протокола → owner review → поручения;
   при изменении решения старая revision видна как superseded.
3. Подготовка звонка → короткий receipt → REPORTED → ожидание письма → evidence;
   повтор receipt не создаёт дублей, внешняя отправка не выполняется сама.
4. Следующий старт → неизвестная страховка → blocker с источником/запросом;
   вывод «всё готово» не появляется из среднего процента.
5. Media доступен без Sponsor; Sponsor без Media; grant можно отозвать,
   после этого поиск/файл/старый execution pack не раскрывают чужие данные.

## Validation, выпуск и rollback

Прикладные PR: unit + integration ключевых сценариев на PG, API backward
compatibility, Docker build/test, отрицательные permission тесты и migration
upgrade/restore на копии. Не использовать живые паспорта, детские/медицинские
данные и production Telegram для fixtures. Исходящие интеграции — sandbox с
явно указанным получателем и duplicate-safe handling.

Перед deploy: exact SHA/CI, реальный Compose profile, свежий restore-tested
backup, app artifacts/config backup, проверка polling singleton и портов.
Owner утверждает конкретный rollout; этот PR ничего не развёртывает.

Rollback прикладного feature: выключить feature, остановить только его pending
jobs, оставить audit и новые scoped данные; совместимость старого app проверить
до выпуска. Additive schema не удаляется при обычном rollback. Разрушающий
downgrade возможен только отдельным планом с восстановлением и решением Owner.
Главные риски: утечка через retrieval/artifacts, неверный мандат, повтор receipt,
подмена reported факта verified, расхождение legacy клиентов; gates S1/S2
должны закрыть их до реальных официальных/коммерческих действий.

Следующий атомарный шаг: S1a design/schema PR с migration/backfill tests;
полноценный агент руководителя включается только после S1b/S1c.
