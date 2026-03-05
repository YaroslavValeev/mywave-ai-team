# Карта проектов MyWave (из контекста/чатов)

Ниже — список проектов/инициатив, которые устойчиво повторяются в наших обсуждениях и выглядят **рабочими** (то есть: есть цель, артефакты/код/планы, либо активная разработка/внедрение).  
Формат: **Название → кратко → тип/домен → ключевые артефакты/системы**.

## A) Ядро MyWave (бизнес/бренд)
1. **MyWave (бренд и экосистема)** → обучение, комьюнити, продукты, медиа → *Brand / Ops* → ценности: экстрим, ИИ, ЗОЖ, тех, бизнес, справедливость.
2. **Сайт Site_MyWave (mywavetreaning.ru)** → лендинг + запись + чат + блог + (в будущем) магазин/проекты/ивенты → *Product/Dev* → Flask, JS, Google API, блог через Sheets.
3. **Telegram-бот записи/админ-бот** → бронирование, напоминания, абонементы/сессии, медиа в Drive → *Product/Dev* → Python, Google Sheets/Calendar/Drive.

## B) Контент и медиа (операционная машина)
4. **OrchestraMedia / MyWave_Parser_WakeNews / WakeNews** → сбор новостей (TG/YT/RSS), NLP/summary, публикации → *MediaOps* → collectors/processors/publishers, Google Sheets, отчёты.
5. **Блог-пайплайн на сайте (Sheets → render → post)** → статусы публикаций, SEO, cover image → *MediaOps/Product*.

## C) События и комьюнити
6. **WakeSafari (экспедиции/ивенты по Волге)** → маршрут, логистика, продажи, партнёры → *Events/Ops*.
7. **WakeSurf Coach Challenge / WakeSurf Challenge 2025** → соревнование тренеров, рейтинг, методичка → *Events/Product*.
8. **Чек-листы/организация соревнований (web)** → приоритизация, прогресс 0–100%, UX → *Events/Product*.

## D) Игровое направление
9. **SnowPolia (настольная игра)** → экономика SnowCoin, карточки, правила → *Game/Product*.
10. **GameSnowPolia (мобильная версия)** → Art Bible, style guide, store listing, ассеты/персонажи → *Game/Production*.
11. **Инвест/грант пакет SnowPolia** → one-pager/pitch deck → *BizDev*.

## E) Инфраструктура/долгий цикл
12. **Турьев хутор (freeride/family resort + отель)** → девелопмент, финмодель, партнёры → *Infra/Finance/Legal*.
13. **Спортивно-развлекательный комплекс (Москва)** → концепт, аудитория, зоны → *Infra/Product*.

## F) Платформа и спонсорство
14. **AI платформа спонсорства MyWave** → подбор спонсора, анализ интеграций, сопровождение контрактов → *Platform/Product/Legal*.

## G) R&D / ExtremeMedia
15. **ExtremeMedia (AI/CV спорт-трансляции + судейство)** → трекинг, оверлеи, evidence pack, MVP Judge Console → *R&D/DevOps/ML*.

## H) Контент-книги/экспертиза
16. **Книга по истории вейксерфинга в РФ + методичка** → структура, главы, методология → *Content/Authority*.

## I) Сторонние/клиентские (зафиксированные брифы)
17. **Pilatesreformer18 (Ижевск) — админ-бот студии** → запись/напоминания/абонементы → *ClientOps/Product*.

---

## Домены для маршрутизации (как система их понимает)
- **PRODUCT_DEV**: сайт/боты/платформа
- **MEDIA_OPS**: парсер/публикации/блог
- **EVENTS**: соревнования, чек-листы, расписания, партнёры
- **GAME**: SnowPolia board + mobile
- **INFRA**: Турьев хутор, комплекс
- **SPONSOR_PLATFORM**: AI sponsorship
- **RND_EXTREME**: ExtremeMedia
- **AUTHORITY_CONTENT**: книга/экспертный контент
- **CLIENTOPS**: сторонние боты (pilatesreformer18)
