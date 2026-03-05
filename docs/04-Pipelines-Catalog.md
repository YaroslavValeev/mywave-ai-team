# Каталог конвейеров (presets) — v1.1

Этот документ описывает готовые “конвейеры” под типовые задачи MyWave.
Конвейер = **последовательность ролей** + обязательные артефакты + обязательные ревьюеры (Roundtable).

## Обозначения ролей
- PM = Sprint Prioritizer
- PS = Product Strategist
- ARCH = Solution Architect
- BE = Backend Engineer
- FE = Frontend Engineer
- DEVOPS = DevOps Automator
- QA = QA Evidence Collector
- SEC = Security Reviewer
- LEGAL = Legal Compliance
- FIN = Finance Planner
- BRAND = Brand Guardian
- CONTENT = Content Producer
- UX = UX/UI Designer
- RC = Reality Checker
- DATA = Data/Analytics Engineer
- PROMPT = Prompt Engineer

---

## 1) PRODUCT_DEV — Site_MyWave / боты / платформа
### 1.1 Bugfix / восстановление функционала (HIGH)
**Pipeline:** PM → FE/BE → ARCH → QA → (опц. DEVOPS)  
**Roundtable:** RC + QA + SEC (если затрагивает auth/PII/CSP)  
**DoD:** чек-лист тестов, список файлов/правок, план деплоя, rollback.

### 1.2 Новая фича (MED/HIGH)
**Pipeline:** PS → PM → UX → FE/BE → ARCH → QA  
**Roundtable:** RC + QA + (опц. SEC)  
**DoD:** PRD-lite, UX flow, API contract, acceptance tests.

### 1.3 Деплой/прод-изменение (EXECUTE / CRITICAL)
**Pipeline (Plan):** DEVOPS → QA → ARCH  
**Gate:** Owner approval BEFORE execute  
**Roundtable:** SEC + RC  
**DoD:** backup, миграции, healthchecks, rollback, post-deploy verification.

---

## 2) MEDIA_OPS — парсер/публикации/блог
### 2.1 Контент-цепочка “сбор → обработка → публикация” (MED/HIGH)
**Pipeline:** CONTENT → PROMPT → DATA → ARCH  
**Roundtable:** BRAND + RC + (опц. LEGAL)  
**DoD:** шаблоны постов, правила источников, анти-галлюцинации, статусы публикаций.

### 2.2 Публикация в крупный канал (EXECUTE / CRITICAL)
**Pipeline (Plan):** CONTENT → BRAND → RC  
**Gate:** Owner approval before publish  
**Roundtable:** (опц. LEGAL для спорных кейсов)

---

## 3) EVENTS — соревнования/ивенты
### 3.1 Операционный план мероприятия (HIGH)
**Pipeline:** Event Producer → PM → FIN → LEGAL → ARCH  
**Roundtable:** RC + SEC (если данные участников/медицина/страховки) + BRAND  
**DoD:** runbook, чек-листы, бюджет, риски, коммуникации.

### 3.2 Судейство/рейтинг/правила (HIGH/CRITICAL)
**Pipeline:** PS → Event Producer → DATA → LEGAL → ARCH  
**Roundtable:** RC + LEGAL + SEC  
**DoD:** прозрачность правил, формулы, апелляции, протоколы.

---

## 4) GAME — SnowPolia (board/mobile)
### 4.1 Баланс/экономика (HIGH)
**Pipeline:** Game Designer (PS) → DATA → RC → ARCH  
**Roundtable:** RC(вторая независимая) + BRAND  
**DoD:** таблицы экономики, ограничения эксплойтов, плейтест план.

### 4.2 Арт/ассеты/стор-листинг (MED/HIGH)
**Pipeline:** BRAND → CONTENT → UX → PROMPT  
**Roundtable:** RC + (опц. LEGAL)  
**DoD:** style guide, prompts, список ассетов, checklist качества.

---

## 5) SPONSOR_PLATFORM — AI sponsorship
### 5.1 MVP прототип (HIGH)
**Pipeline:** PS → ARCH → DATA → BE → QA  
**Roundtable:** FIN + LEGAL + RC  
**DoD:** intake, rule-based scoring, отчётность, договорные поля.

---

## 6) RND_EXTREME — ExtremeMedia
### 6.1 MVP Judge Console + Evidence Pack (HIGH/CRITICAL)
**Pipeline:** ARCH → ML/Prompt → BE → DEVOPS → QA  
**Roundtable:** RC + SEC + FIN  
**Gate:** любой сбор/хранение видео с людьми = CRITICAL (Owner approval)
**DoD:** dataset v0, метрики v0, evidence pack, воспроизводимость.

---

## 7) INFRA — Турьев хутор / комплекс
### 7.1 Инвест/финмодель/риски (HIGH/CRITICAL)
**Pipeline:** FIN → LEGAL → PS → ARCH  
**Roundtable:** RC + LEGAL + BRAND  
**Gate:** публичные цифры/обещания = CRITICAL → Owner approval
**DoD:** финмодель, риски, roadmap, инвест-коммуникации.

---

## 8) AUTHORITY_CONTENT — книга/методички
### 8.1 Структура книги (MED)
**Pipeline:** CONTENT → PS → BRAND  
**Roundtable:** RC  
**DoD:** оглавление, главы, tone-of-voice, план производства.

---

## 9) CLIENTOPS — сторонние проекты (pilatesreformer18)
### 9.1 Бот-админ студии (HIGH)
**Pipeline:** PS → PM → BE → QA → SEC  
**Roundtable:** LEGAL + RC  
**DoD:** сценарии, правила отмен, PII/сроки хранения, тесты.
