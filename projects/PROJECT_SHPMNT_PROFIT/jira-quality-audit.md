# Аудит качества задач Jira EKFLAB (product:profitability)

Дата: 2026-03-03
JQL: `project = EKFLAB AND labels = "product:profitability" AND status = Готово`

---

## Сводка

| Метрика | Значение |
|---------|----------|
| Всего задач "Готово" | 60 |
| Smart Checklist OK (все `+` или `x`) | **5** (8%) |
| Smart Checklist НЕПОЛНЫЙ (есть `-`) | **7** (12%) |
| Smart Checklist ПУСТОЙ (null) | **48** (80%) |
| Description Jira wiki (OK) | **49** (82%) |
| Description Markdown (broken) | **11** (18%) |
| Description пустое | **0** |
| Дубликаты задач | **1 пара** (EKFLAB-168/169) |

### По спринтам
| Спринт | Закрытых задач |
|--------|---------------|
| Sprint 27 | 20 |
| Sprint 28 | 39 |
| Sprint 29 | 1 |

---

## Проблема 1: Smart Checklist ПУСТОЙ (48 задач, 80%)

Самая массовая проблема. У 48 из 60 закрытых задач Smart Checklist (`customfield_10507`) = null.
Подтверждено через Issue Properties API: `com.railsware.SmartChecklist.checklist` = пустая строка.

Это нарушает правило MEMORY.md: "Smart Checklist ставить СРАЗУ при создании задачи (пункты `-` unchecked), НЕ перед закрытием".

### По типам задач (без Smart Checklist)

**Epic (4):**
| Key | Название |
|-----|---------|
| EKFLAB-3 | Фаза 3A: Scaffold проекта (репозиторий, тулинг, Docker) |
| EKFLAB-4 | Фаза 3C: Use Cases (расчёт рентабельности, согласование, аналитика, санкции, НПСС, отчёты) |
| EKFLAB-136 | Фаза 3B: Domain Layer (сущности, VO, события, ошибки, порты, сервисы) |
| EKFLAB-158 | Sprint 28 Этап 1: Инфраструктурные адаптеры |

**Задача (30):**
| Key | Название |
|-----|---------|
| EKFLAB-28 | 3.1 Инициализация репозитория (go mod, структура каталогов, Makefile, docker-compose, CI) |
| EKFLAB-29 | 3.2 Настройка Go-тулинга (golangci-lint, sqlc, oapi-codegen, wire, golang-migrate) |
| EKFLAB-30 | 3.3 Настройка React-проекта (Next.js 15, TanStack Query, Zustand, Zod, Tailwind) |
| EKFLAB-31 | 3.4 Docker-инфраструктура (multi-stage сборка Go/Next.js, compose dev/staging/prod, мониторинг) |
| EKFLAB-32 | 3.13 Use case: Обнаружение аномалий — internal/usecase/analytics/ |
| EKFLAB-33 | 3.14 Use case: Управление санкциями — internal/usecase/sanction/ |
| EKFLAB-34 | 3.15 Use case: Обновление НПСС — internal/usecase/pricing/ |
| EKFLAB-35 | 3.16 Use case: Генерация отчётов — internal/usecase/reporting/ |
| EKFLAB-36 | 3.17 HTTP handlers (chi + oapi-codegen) — internal/adapter/http/ |
| EKFLAB-131 | Sprint 27: Верификация и закрытие |
| EKFLAB-137 | 3.5 Доменные сущности — internal/domain/entity/ |
| EKFLAB-138 | 3.7 Доменные события — internal/domain/event/ |
| EKFLAB-139 | 3.8 Доменные ошибки — internal/domain/errors.go |
| EKFLAB-140 | 3.6 Value Objects — internal/domain/valueobject/ |
| EKFLAB-141 | 3.9 Port interfaces — internal/port/ |
| EKFLAB-142 | 3.10 Доменные сервисы — internal/domain/service/ |
| EKFLAB-143 | 3.11 Use case: Расчет рентабельности — internal/usecase/profitability/ |
| EKFLAB-144 | 3.12 Use case: Согласование отгрузки — internal/usecase/approval/ |
| EKFLAB-151 | Ревью кода: инфраструктурные адаптеры (PostgreSQL, Kafka, Redis) |
| EKFLAB-152 | Тесты: инфраструктурные адаптеры (PostgreSQL, Kafka, Redis) |
| EKFLAB-159 | Исправить 2 CRIT + 5 HIGH из SE-ревью адаптеров Sprint 28 |
| EKFLAB-161 | Повторное ревью Sprint 28 Stage 1: проверка 7 исправлений CRIT/HIGH |
| EKFLAB-162 | Исправить 5 HIGH замечаний из повторного SE-ревью Sprint 28 |
| EKFLAB-165 | Исправить CRIT-003 (миграция is_small_order) и HIGH-001-R (optimistic lock version bump) |
| EKFLAB-168 | Интеграционные тесты PostgreSQL-репозиториев (testcontainers-go) |
| EKFLAB-169 | Интеграционные тесты PostgreSQL-репозиториев (testcontainers-go) — ДУБЛЬ EKFLAB-168 |
| EKFLAB-184 | Создание ТЗ для Go+React сервиса profitability-service |
| EKFLAB-185 | SE-ревью ТЗ и архитектуры Go+React (Agent 9) |
| EKFLAB-188 | Исправить CRIT+HIGH из SE-ревью ТЗ и архитектуры v1.0 |
| EKFLAB-192 | Повторное SE-ревью ТЗ и архитектуры Go+React v1.0 (R2) |

**Test (12):**
| Key | Название |
|-----|---------|
| EKFLAB-170 | Тест: Kafka consumer валидация конфигурации |
| EKFLAB-171 | Тест: Kafka consumer маршрутизация сообщений |
| EKFLAB-172 | Тест: Kafka consumer обработка ошибок и DLQ |
| EKFLAB-173 | Тест: Kafka producer публикация событий |
| EKFLAB-174 | Тест: Kafka producer retry и batch |
| EKFLAB-175 | Тест: Outbox poller цикл опроса |
| EKFLAB-176 | Тест: Outbox poller retry и маркировка ошибок |
| EKFLAB-177 | Тест: Redis cache get/set/delete |
| EKFLAB-178 | Тест: Redis distributed lock |
| EKFLAB-179 | Тест: PostgreSQL ShipmentRepo CRUD |
| EKFLAB-180 | Тест: PostgreSQL ClientRepo CRUD и temporal |
| EKFLAB-181 | Тест: PostgreSQL ApprovalProcessRepo CRUD |

**Test Plan (1):** EKFLAB-167
**Test Execution (1):** EKFLAB-182

---

## Проблема 2: Smart Checklist НЕПОЛНЫЙ (7 задач, 12%)

У 7 задач Smart Checklist есть, но содержит unchecked (`-`) пункты. Все 7 — одинаковая проблема: `- Docs updated: N/A` вместо `x Docs updated: N/A` (skipped) или `+ Docs updated: N/A` (checked).

Прогресс у всех: **5/6**. Это означает, что `jira-tasks.sh done` должен был заблокировать закрытие (правило: "блокирует если есть `-`"), но пропустил.

| Key | Название | Незакрытый пункт |
|-----|---------|-----------------|
| EKFLAB-37 | 3.18 PostgreSQL repositories (sqlc) | `- Docs updated: N/A` |
| EKFLAB-38 | 3.19 Kafka consumers (franz-go) | `- Docs updated: N/A` |
| EKFLAB-39 | 3.20 Kafka producers (franz-go) | `- Docs updated: N/A` |
| EKFLAB-40 | 3.21 Redis cache + locks — internal/adapter/redis/ | `- Docs updated: N/A` |
| EKFLAB-58 | 3.39 DB migrations (all 5 services) | `- Docs updated: N/A` |
| EKFLAB-59 | 3.40 Kafka topic creation script | `- Docs updated: N/A` |
| EKFLAB-68 | 3.49 Outbox table + background poller | `- Docs updated: N/A` |

**Корневая причина:** Агент записал `- Docs updated: N/A` (unchecked) вместо `x Docs updated: N/A` (skipped) или `+ Docs updated: N/A` (checked with N/A). По правилам Smart Checklist формата: `+` = checked, `-` = unchecked, `x` = skipped. "N/A" по смыслу = skipped, но формат не тот.

---

## Проблема 3: Description в Markdown вместо Jira wiki (11 задач, 18%)

Jira Server НЕ поддерживает Markdown. Описание должно быть в Jira wiki markup. 11 задач содержат markdown-артефакты (`## `, `- [ ]`, `- [x]`), которые отображаются как plain text.

| Key | Название | Markdown-артефакты |
|-----|---------|-------------------|
| EKFLAB-136 | Фаза 3B: Domain Layer | `## headers`, `- [x]/- [ ] checkboxes` |
| EKFLAB-137 | 3.5 Доменные сущности | `## headers`, `- [x]/- [ ] checkboxes` |
| EKFLAB-138 | 3.7 Доменные события | `## headers`, `- [x]/- [ ] checkboxes` |
| EKFLAB-139 | 3.8 Доменные ошибки | `## headers`, `- [x]/- [ ] checkboxes` |
| EKFLAB-140 | 3.6 Value Objects | `## headers`, `- [x]/- [ ] checkboxes` |
| EKFLAB-141 | 3.9 Port interfaces | `## headers`, `- [x]/- [ ] checkboxes` |
| EKFLAB-142 | 3.10 Доменные сервисы | `## headers`, `- [x]/- [ ] checkboxes` |
| EKFLAB-143 | 3.11 Use case: Расчет рентабельности | `## headers`, `- [x]/- [ ] checkboxes` |
| EKFLAB-144 | 3.12 Use case: Согласование отгрузки | `## headers`, `- [x]/- [ ] checkboxes` |
| EKFLAB-149 | Симулятор 1С | `## headers`, `- [x]/- [ ] checkboxes` |
| EKFLAB-185 | SE-ревью ТЗ и архитектуры Go+React | `## headers`, `- [x]/- [ ] checkboxes` |

**Корневая причина:** Задачи EKFLAB-136..144 (Sprint 27, Phase 3B Domain Layer) создавались ДО того, как `jira-tasks.sh create` начал конвертировать markdown в wiki (функция `_md_to_wiki`). EKFLAB-149 и EKFLAB-185 — также созданы без конвертации.

**Примечание:** 49 из 60 задач (82%) имеют корректный Jira wiki markup. Проблема локализована в определённом временном периоде.

---

## Проблема 4: Дубликат задачи (EKFLAB-168 / EKFLAB-169)

| Key | Название | Создано |
|-----|---------|---------|
| EKFLAB-168 | Интеграционные тесты PostgreSQL-репозиториев (testcontainers-go) | 2026-03-03 00:27:37 |
| EKFLAB-169 | Интеграционные тесты PostgreSQL-репозиториев (testcontainers-go) | 2026-03-03 00:27:44 |

Одинаковое название, одинаковое содержание, создано с разницей в 7 секунд. Обе закрыты со статусом "Готово".

---

## Задачи с полностью корректным Smart Checklist (5 задач-эталонов)

| Key | Название | Прогресс |
|-----|---------|----------|
| EKFLAB-60 | 3.41 Seed data script | 6/6 - Done |
| EKFLAB-149 | Симулятор 1С | 6/6 - Done |
| EKFLAB-160 | Исправить 2 CRIT + 5 HIGH из SE-ревью | 8/8 - Done |
| EKFLAB-163 | SE Re-review #2 | 6/6 - Done |
| EKFLAB-166 | SE Re-Review #4 | 6/6 - Done |

---

## Корневые причины и рекомендации

### 1. 80% задач без Smart Checklist
**Причина:** Правило "Smart Checklist ставить СРАЗУ при создании" было введено ПОСЛЕ закрытия большинства задач Sprint 27. Задачи Sprint 27 (EKFLAB-3..144) и часть Sprint 28 были созданы и закрыты без чеклиста.
**Рекомендация:** Добавить Smart Checklist ретроспективно (bulk PUT через API) со статусом `+ checked` для закрытых задач, или принять как технический долг ранних спринтов.

### 2. 7 задач с `- Docs updated: N/A`
**Причина:** Агент использовал `-` (unchecked) вместо `x` (skipped) для пункта N/A.
**Рекомендация:** Заменить `- Docs updated: N/A` на `x Docs updated: N/A` (skipped) в 7 задачах. Также проверить валидацию в `jira-tasks.sh done` — она должна была заблокировать закрытие с unchecked пунктами.

### 3. 11 задач с markdown в description
**Причина:** Ранние задачи создавались до внедрения `_md_to_wiki()` в `jira-tasks.sh`.
**Рекомендация:** Пропустить через конвертер wiki markup. Задачи закрыты — влияние минимальное (только визуальное).

### 4. Дубликат EKFLAB-168/169
**Причина:** Вероятно, двойной вызов API при создании.
**Рекомендация:** Удалить одну из задач или пометить как дубль.

---

## Хронология проблем

| Спринт | Задач "Готово" | Без чеклиста | С markdown | Примечание |
|--------|---------------|-------------|-----------|-----------|
| Sprint 27 | 20 | 18 (90%) | 9 (45%) | Ранние задачи, правила ещё не действовали |
| Sprint 28 | 39 | 30 (77%) | 2 (5%) | Правила частично внедрены, но не ретроспективно |
| Sprint 29 | 1 | 0 (0%) | 0 (0%) | Правила работают |
