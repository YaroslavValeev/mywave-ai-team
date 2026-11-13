# Domain prompt/context baseline (Phase 10.1)

Как compact_context входит в prompt/context, ограничения, отличия от full profile.

---

## Как compact_context входит в prompt/context

- В **pipeline handoff** и/или **court report** добавляется секция вида «## Domain context (expertise)» с текстом compact_context (или урезанным до лимита символов).
- В будущем при сборке agent prompt envelope тот же compact_context может подставляться в системный или пользовательский блок; на Phase 10.1 достаточно передачи через handoff и report.
- **Формат:** один текстовый блок; без сырых YAML/JSON в пользовательском выводе; маркер «Domain context» чтобы агент/executor понимал природу блока.

---

## Ограничения объёма

- **Compact_context** на один workflow не более 1500 символов (настраиваемо); при формировании в select_context_for_task уже ограничен (~1500 в domain_triage).
- **Secondary domains:** не более 2; в compact включаются summary + ключевые слова по каждому выбранному домену, без полного expert profile.
- **Цель:** избежать context bloat; оставить место для основного текста задачи и инструкций.

---

## Отличие compact_context от full expert profile

- **Full profile** = полный набор полей из know_proff (для страницы /domain &lt;key&gt; или внутреннего референса).
- **Compact_context** = краткая выжимка: summary домена(ов), до 5–7 strengths/keywords, до 3–5 typical_tasks; один слитный текст для подстановки в handoff/report/prompt.
- В workflow и промптах используется только compact; полный профиль не подставляется.
