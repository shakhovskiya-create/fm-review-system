# Universal Project Audit Prompt

> Шаблон промпта для глубокого аудита любого Claude Code проекта.
> Результат: структурированный отчёт с findings, оценками и roadmap.

---

## Промпт (копировать целиком)

```
РОЛЬ: Архитектурный аудитор проекта.

Проведи глубокий аудит текущего проекта по 8 направлениям.

МЕТОДОЛОГИЯ:
1. Перед КАЖДОЙ частью — сначала WebSearch актуальные best practices и стандарты по теме
2. Затем прочитай ВСЕ релевантные файлы проекта (не додумывай — открой и проверь)
3. Сравни найденное в проекте с актуальными стандартами из веба
4. Используй Explore-агентов для параллельного сканирования больших директорий
5. Каждый finding = конкретный файл:строка + риск + рекомендация + ссылка на источник стандарта

СОХРАНИ результат в `audits/audit-{project-name}.md`.

---

## Часть 1: Безопасность

**Веб-исследование (ОБЯЗАТЕЛЬНО перед проверкой):**
- WebSearch: "OWASP Top 10 2025 checklist"
- WebSearch: "{язык/фреймворк проекта} security best practices 2025-2026"
- WebSearch: "CI/CD security hardening GitHub Actions"
- WebSearch: "secrets management best practices production"

**Сверь проект с найденными стандартами:**
- [ ] Секреты в plaintext (.env, hardcoded tokens, API keys в коде)
- [ ] eval/exec на внешних данных (shell injection, code injection)
- [ ] SSL/TLS — отключена ли верификация глобально
- [ ] Permissions на файлы с секретами (chmod 600?)
- [ ] CI/CD — избыточные permissions (contents:write, id-token:write)
- [ ] Hooks — set -euo pipefail? Обработка ошибок?
- [ ] Input validation — sanitization пользовательского ввода
- [ ] Bare except/catch — ловит ли SystemExit/KeyboardInterrupt
- [ ] Dependencies — известные CVE? Устаревшие версии?
- [ ] CORS/CSP/Headers — если есть веб-компонент

Классификация: CRITICAL (эксплуатируемо сейчас), HIGH (требует специфических условий), MEDIUM (defense-in-depth), LOW (hardening).

## Часть 2: Архитектура и код

**Веб-исследование (ОБЯЗАТЕЛЬНО перед проверкой):**
- WebSearch: "{основной фреймворк} project structure best practices 2026"
- WebSearch: "{язык} error handling patterns"
- WebSearch: "{язык} code quality static analysis tools"

**Сверь проект с найденными паттернами:**
- [ ] Структура проекта — логична? Есть ли мёртвый код?
- [ ] Модули — связность (coupling) и зацепление (cohesion)
- [ ] DRY — дублирование логики между файлами
- [ ] Error handling — graceful degradation, retry, fallback
- [ ] Конфигурация — hardcoded values vs environment
- [ ] Data flow — как данные проходят между компонентами
- [ ] API контракты — версионированы? Валидируются?
- [ ] State management — race conditions, idempotency
- [ ] Logging — structured? Уровни? Rotation?

## Часть 3: Best Practices (Claude Code / AI Tooling)

**Веб-исследование (ОБЯЗАТЕЛЬНО перед проверкой):**
- WebSearch: "Claude Code best practices 2026 CLAUDE.md rules skills"
- WebSearch: "Claude Code hooks subagents memory configuration"
- WebSearch: "site:docs.anthropic.com claude code best practices"
- WebSearch: "MCP servers catalog 2026" (проверить есть ли MCP для используемых сервисов)
- WebSearch: "Claude Code SDK agent orchestration patterns"

**Сверь проект с актуальной документацией Anthropic:**
- [ ] CLAUDE.md — размер? Структура? Не дублирует rules?
- [ ] .claude/rules/ — path-scoping? Модульность?
- [ ] .claude/skills/ — повторяемые операции оформлены как skills?
- [ ] Subagents — есть ли? С memory: project? Модели подобраны?
- [ ] Hooks — lifecycle покрыт? SessionStart/Stop, Pre/PostToolUse?
- [ ] Memory — Knowledge Graph / Graphiti / Agent Memory?
- [ ] MCP серверы — используются ли все доступные для стека проекта?
- [ ] Тесты — покрытие? CI? Запускаются одной командой?
- [ ] Observability — трейсинг? Логирование? Метрики?
- [ ] Secrets — менеджер секретов или plaintext .env?

## Часть 4: Домен-специфичные возможности

**Веб-исследование (ОБЯЗАТЕЛЬНО перед проверкой):**
- WebSearch: "{домен проекта} industry standards"
- WebSearch: "{домен проекта} common architecture patterns"
- WebSearch: "{ключевые интеграции проекта} API documentation latest"

**Оцени, насколько проект решает свою бизнес-задачу:**
- [ ] Покрытие бизнес-требований — что из стандартов домена реализовано?
- [ ] Пробелы в домене — что из стандартов не реализовано но нужно?
- [ ] Качество выхода (генерируемых артефактов)
- [ ] Интеграции (внешние системы, API) — соответствуют ли актуальным версиям API?

## Часть 5: Масштабируемость и расширяемость

**Веб-исследование (ОБЯЗАТЕЛЬНО перед проверкой):**
- WebSearch: "{стек проекта} scalability patterns"
- WebSearch: "{стек проекта} performance bottlenecks common"

**Сверь с паттернами масштабирования:**
- [ ] Можно ли добавить новый компонент без изменения существующих?
- [ ] Есть ли абстракции для замены реализаций?
- [ ] Bottlenecks — что сломается при 10x нагрузке?
- [ ] Миграция — можно ли перенести на другой стек?
- [ ] Caching — используется? Инвалидация?

## Часть 6: Документация

**Веб-исследование (ОБЯЗАТЕЛЬНО перед проверкой):**
- WebSearch: "technical documentation best practices developer experience"
- WebSearch: "README template best practices open source"

**Проверь:**
- [ ] README — актуален? Содержит quick start?
- [ ] Inline comments — есть где нужно? Нет где не нужно?
- [ ] CHANGELOG — ведётся?
- [ ] Architecture Decision Records — документированы решения?
- [ ] API docs — автогенерация? OpenAPI/Swagger?

## Часть 7: Позитивные практики

Перечисли 5-10 вещей, которые сделаны ХОРОШО. Аудит — не только критика.
Для каждой позитивной практики — ссылка на стандарт/best practice которому она соответствует.

## Часть 8: Roadmap

Сгруппируй ВСЕ findings в спринты по 1-5 дней:
- Sprint 1: CRITICAL + quick wins
- Sprint 2-N: HIGH/MEDIUM сгруппированные по теме
- Каждый пункт: описание + усилие (часы) + файлы

---

## Формат findings

Каждый finding:
```
#### {SEVERITY}-{AREA}{N}. Краткое описание
**Файл:** `path/to/file.py:123`
**Стандарт:** [Название](URL) — какой best practice нарушен
**Риск:** Что случится если не исправить
**Рекомендация:** Конкретное действие (с примером кода если нужно)
```

Severity: CRITICAL > HIGH > MEDIUM > LOW
Area: S (Security), A (Architecture), D (Domain), P (Practice), X (DX/Extensibility)

---

## Сводная таблица (обязательно в конце)

| # | Severity | ID | Область | Описание | Файл | Стандарт |
|---|----------|-----|---------|----------|------|----------|
| 1 | CRITICAL | S-C1 | Security | ... | `file.py:42` | OWASP A03 |

Плюс таблица по областям (pivot).

---

## Источники (обязательно в конце)

Перечисли ВСЕ URL, которые были найдены через WebSearch и использованы для сверки:

| # | Источник | URL | Использован в |
|---|----------|-----|---------------|
| 1 | OWASP Top 10 | https://... | Часть 1 |
| 2 | Claude Code docs | https://... | Часть 3 |

---

## Метрики (обязательно в конце)

| Метрика | Значение |
|---------|----------|
| Файлов проверено | N |
| Веб-источников использовано | N |
| Findings total | N (C + H + M + L) |
| Security score | X/10 |
| Architecture score | X/10 |
| Best practices score | X/10 |
| Domain score | X/10 |
| Overall maturity | PROTOTYPE / ALPHA / BETA / PRODUCTION |
```

---

## Использование

1. Открыть Claude Code в корне проекта
2. Вставить промпт выше целиком
3. Подождать 10-20 минут (веб-поиск + анализ файлов)
4. Результат: `audits/audit-{project-name}.md`

## Кастомизация

- **Часть 4 (домен):** Заменить WebSearch запросы на свою специфику (1С, Go, React, ML и т.д.)
- **Best Practices:** Промпт сам подтянет актуальные через WebSearch
- **Severity:** Можно добавить BLOCKER для regulatory compliance
- **Спринты:** Адаптировать под свой velocity (1-2 дня vs 1-2 недели)
- **Язык:** Промпт работает на русском и английском, аудит будет на языке промпта
