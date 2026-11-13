# ROLE_ROUTE_ACCESS_MATRIX — Доступ к маршрутам по ролям

## Owner-only routes (полный доступ)

- `/`, `/owner`, `/owner/portfolio`, `/owner/project/{key}`, `/owner/interventions`, `/owner/decision-support`
- `/owner/domains`, `/owner/domain/{key}`
- `/views/operator`, `/views/executor`, `/views/reviewer` — owner может просматривать любую роль
- `/actions`, `/actions/run`, `/api/actions`
- `/api/*` (все API под require_owner_key)

## Role-scoped views (под тем же auth)

- `/views/operator` — рекомендуется для operator (и owner)
- `/views/executor` — для executor (и owner)
- `/views/reviewer` — для reviewer (и owner)

Текущая реализация: все маршруты защищены `require_owner_key`. Роль используется для:
- фильтрации actions в action center;
- выбора представления в role views.

## Route names для can_access_route

| Route name | owner | operator | executor | reviewer |
|------------|-------|----------|----------|----------|
| / | ✓ | | | |
| /owner | ✓ | | | |
| /owner/portfolio | ✓ | | | |
| /owner/project/{key} | ✓ | ✓ | ✓ | ✓ |
| /owner/interventions | ✓ | ✓ | | |
| /owner/decision-support | ✓ | ✓ | ✓ | ✓ |
| /views/operator | ✓ | ✓ | | |
| /views/executor | ✓ | | ✓ | |
| /views/reviewer | ✓ | | | ✓ |
| /actions | ✓ | ✓ | ✓ | ✓ |
| /actions/run | ✓ | ✓ | ✓ | ✓ |

*Примечание: при текущем auth (один owner_key) все web-пользователи = owner. Matrix используется для future multi-role и для явной проверки при добавлении новых каналов.*
