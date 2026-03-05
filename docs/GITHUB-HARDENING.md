# GitHub Hardening — настройки вручную

Эти настройки выполняются в GitHub UI (Settings).

## 1. Branch Protection для `main`

**Settings → Branches → Add rule** (или Edit rule для `main`):

| Параметр | Значение |
|----------|----------|
| Branch name pattern | `main` |
| Require a pull request before merging | ✅ |
| Required approvals | 1 |
| Require status checks to pass | ✅ |
| Require branches to be up to date | ✅ |
| Status checks: | `test` (имя job из `.github/workflows/ci.yml`) |
| Require conversation resolution | ✅ |
| Do not allow bypassing the above settings | ✅ |
| Restrict pushes that create matching branches | ✅ |
| Allow force pushes | ❌ (Disabled) |
| Allow deletions | ❌ (Disabled) |
| Require linear history | (опционально) ✅ |

## 2. Security

**Settings → Code security and analysis:**

| Фича | Действие |
|------|----------|
| Dependency graph | Enable |
| Dependabot alerts | Enable |
| Dependabot security updates | Enable |
| Secret scanning | Enable (включая push protection) |
| Code scanning (CodeQL) | Enable для Python (опционально) |

## 3. CodeQL (опционально)

Создать `.github/workflows/codeql.yml`:

```yaml
name: CodeQL
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'  # еженедельно понедельник
jobs:
  analyze:
    runs-on: ubuntu-latest
    permissions:
      security-events: write
      actions: read
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: github/codeql-action/init@v3
        with:
          languages: python
      - uses: github/codeql-action/analyze@v3
```

---

**Правило:** всё в `main` только через PR, даже при одном участнике.
