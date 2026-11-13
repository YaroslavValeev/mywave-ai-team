# Domain alias map (Phase 9.9)

Канонические имена доменов, имена файлов и алиасы для устойчивого routing и поиска.

---

## Канонический domain_key ← источник и алиасы

| domain_key | source_file | aliases / варианты написания |
|------------|-------------|-------------------------------|
| legal | layer.txt | legal, юрист, юридический, law, compliance |
| analytics | Analiz.txt | analytics, analiz, аналитика, анализ данных, data analyst |
| development | Creating.txt | development, creating, разработка, креатив, engineering |
| programming_engineer | Programming ingeneer.txt | programming_engineer, programming ingeneer, ingeneer, программирование, код, разработка ПО |
| finance | Financ.txt | finance, financ, финансы, бухгалтерия, CFO |
| social_media | Sociol media.txt | social_media, sociol media, соцмедиа, SMM отдел |
| brand_manager | Brand manager.txt | brand_manager, brand manager, бренд, позиционирование |
| copywriting | Copiwriter.txt | copywriting, copiwriter, копирайтинг, контент |
| marketing | marketing.txt | marketing, маркетинг, 4Cs, AIDA, STP |
| sales | Sales.txt | sales, продажи, менеджер по продажам |
| smm | Smm.txt | smm, SMM, соцсети, платформы |
| social_engineering | Social ingeneer.txt | social_engineering, social ingeneer, социнженерия, безопасность, фишинг |

---

## Правила разрешения

1. Поиск по domain_key — точное совпадение с каноническим ключом.
2. Поиск по алиасу — нормализация к domain_key через данный map (регистр не учитывается для ключей и алиасов).
3. Имя файла (без пути) может использоваться как алиас только если явно внесено в aliases или в отдельный file→domain_key mapping.

---

## Machine-readable

Алиасы и mapping дублируются в docs/know_proff/registry/domain_aliases.yaml (или в domain_registry.yaml) для загрузки в domain_registry.py.
