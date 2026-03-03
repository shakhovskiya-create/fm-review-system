# ROADMAP: profitability-service — Go+React FM-LS-PROFIT

> **Version:** 1.1.0 | **Date:** 2026-03-03 | **Status:** IN PROGRESS
> **Jira Plan:** [Portfolio Plan](https://jira.ekf.su/secure/PortfolioReportView.jspa?r=i5SUF) | **Board:** [Profitability Service](https://jira.ekf.su/secure/RapidBoard.jspa?rapidView=39)

## Executive Summary

FM-LS-PROFIT (контроль рентабельности отгрузок по ЛС) реализуется как отдельный Go+React сервис. 1С:УТ 10.2 остаётся source of truth. Go-сервис добавляет AI-аналитику, dashboard, автономные расследования.

**Ключевые цифры:**
- **245 задач** в Jira (33 эпика, 8 спринтов)
- **121 завершены** (49%), **124 осталось**
- **6 Go-микросервисов** + React frontend
- **17 интеграций** (8 из ФМ + 9 новых)
- **88% test coverage** target (domain 95%)
- **3-level AI** (deterministic → LLM → agentic)

## Architecture Decisions (FINAL, user-approved 2026-03-01)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Repository | Separate: `profitability-service/` | fm-review-system = control plane, profitability-service = product |
| AI Models | Sonnet 4.6 (90%) + Opus 4.6 (10%) | NO Haiku. Sonnet=analyst, Opus=investigator |
| Auth | AD (LDAP/Kerberos) → JWT | AD groups = app roles. NOT HR system |
| Release Manager | Agent 16 (AI) | NOT human. 12-point Quality Gate |
| Coverage | 88% total, domain 95% | Mutation testing for domain/ |
| Mini MDM | Temporal PG tables in integration-service | NOT separate product |
| Inter-service | gRPC (sync) + Kafka (async) | NO direct HTTP between services |
| Queue | Kafka (KRaft, franz-go) | Exactly-once, DLQ, outbox pattern |
| Environments | Dev → Staging → Prod | Dev: mocks, Staging: tunnel, Prod: corporate |

**Full context:** [profitability-service-decisions.md](../../memory/profitability-service-decisions.md)

---

## Gantt Chart

```
Sprint 24: Phase 0 — Инфраструктура                              ✅ DONE
  |████████████████████████████████████████|
  Agent 16, протоколы, pipeline, secrets

Sprint 25: Phase 1 — Архитектура и ТЗ                            ✅ DONE
  |████████████████████████████████████████|
  Доменная модель, 6 сервисов, OpenAPI, AI, Frontend, Integrations

Sprint 26: Phase 1.5+2 — 1С Extension + SE Review                ✅ DONE
  |████████████████████████████████████████|
  BSL код, SE-ревью Go+React (0 CRIT, 0 HIGH)

Sprint 27: Phase 3A-3C — Scaffold + Domain + UseCases             ✅ DONE
  |████████████████████████████████████████|
  Репозиторий, Go тулинг, React, Docker, Domain, UseCases

Sprint 28: Phase 3D-3H — Адаптеры + AI + Frontend + Infra        🔄 ACTIVE
  |██████████████████████░░░░░░░░░░░░░░░░░░| 53%
  PostgreSQL, Kafka, Redis, Claude AI, ELMA, React pages, Grafana

Sprint 29: Phase 4A-4D — Unit + Integration + Contract тесты     ⏳ FUTURE
  |░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|

Sprint 30: Phase 4E-4K + 5 — E2E + Load + Docs                   ⏳ FUTURE
  |░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|

Sprint 31: Phase 6 — Deploy & Release                             ⏳ FUTURE
  |░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░|
```

**Critical path:** Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 6D
**Parallel tracks:** Phase 1.5 || Phase 1C-1E, Phase 5 || Phase 4E-4K

---

## Phase Summary Table

| Phase | Description | Sprint | Status | Tasks |
|-------|-------------|--------|--------|-------|
| **0** | Подготовка инфраструктуры и протоколов | 24 | ✅ Done | 9 |
| **1** | Архитектура и ТЗ Go+React | 25 | ✅ Done | 32 |
| **1.5** | Расширение 1С для Kafka | 26 | ✅ Done | 5 |
| **2** | SE-ревью архитектуры Go+React | 26 | ✅ Done | 10 |
| **3A-3C** | Scaffold + Domain + UseCases | 27 | ✅ Done | 20 |
| **3D-3H** | Адаптеры + AI + Frontend + Infra | 28 | 🔄 In Progress | 79 |
| **4A-4D** | Unit + Integration + Contract тесты | 29 | ⏳ Planned | 27 |
| **4E-4K** | E2E + Load + Security + Mutation | 30 | ⏳ Planned | 36 |
| **5** | Документация | 30 | ⏳ Planned | — |
| **6** | Deploy & Release | 31 | ⏳ Planned | 26 |
| | **TOTAL** | **24-31** | | **~245** |

---

## Risk Register

| # | Risk | Impact | Probability | Mitigation |
|---|------|--------|-------------|------------|
| R1 | ELMA API incompatible with Go client | HIGH | MEDIUM | Mock first, test with real ELMA in staging |
| R2 | 1С:УТ 10.2 HTTP-сервис limitations | HIGH | MEDIUM | Minimal extension, test on real 1С instance |
| R3 | Claude API costs exceed budget | MEDIUM | LOW | Prompt caching, cost ceiling, degradation to Level 1 |
| R4 | Kafka throughput insufficient | LOW | LOW | KRaft mode, franz-go, load test early |
| R5 | AD auth complexity (Kerberos) | MEDIUM | MEDIUM | Start with LDAP bind, add Kerberos later |
| R6 | Domain model doesn't match FM | HIGH | LOW | Agent 5 traces every rule to LS-BR-*, Agent 9 cross-checks |
| R7 | MDM cold start — no data | HIGH | MEDIUM | Bulk seed from 1С CSV export, validate before go-live |
| R8 | Outbox poller missed events | MEDIUM | LOW | Same DB transaction, idempotent poller, monitoring |
| R9 | Data migration incomplete | HIGH | MEDIUM | Row count + hash verification, dry-run on staging |
| R10 | Corporate tunnel instability | MEDIUM | MEDIUM | Health checks, auto-reconnect, fallback to mock |
| R11 | gRPC contract breaking | MEDIUM | LOW | buf lint + breaking in CI, contract tests |
| R12 | AI prompt injection | HIGH | LOW | Input sanitization, separate system/user prompts |

---

## Milestones

| Milestone | Sprint | Deliverable | Status |
|-----------|--------|------------|--------|
| M0 | 24 | Инфраструктура готова | ✅ Done |
| M1 | 25 | Архитектура спроектирована | ✅ Done |
| M1.5 | 26 | Расширение 1С готово | ✅ Done |
| M2 | 26 | SE-ревью пройдено (0 CRIT, 0 HIGH) | ✅ Done |
| M3 | 28 | Код написан, docker compose up работает | 🔄 In Progress |
| M4 | 30 | Тесты пройдены (88% coverage) | ⏳ Planned |
| M5 | 30 | Документация готова | ⏳ Planned |
| M6 | 31 | Production release v1.0.0 | ⏳ Planned |

---

## Jira Structure

**Трекер:** [Jira EKFLAB](https://jira.ekf.su/secure/RapidBoard.jspa?rapidView=39) | **Plan:** [Portfolio](https://jira.ekf.su/secure/PortfolioReportView.jspa?r=i5SUF)

Все задачи с label `product:profitability`, fixVersion, component, epic link, sprint.

### Sprints

| Sprint | ID | Phase | Status |
|--------|----|-------|--------|
| 24 | 119 | Phase 0: Инфраструктура | ✅ Closed |
| 25 | 120 | Phase 1: Архитектура | ✅ Closed |
| 26 | 121 | Phase 1.5+2: 1С + SE Review | ✅ Closed |
| 27 | 109 | Phase 3A-3C: Scaffold + Domain | ✅ Closed |
| 28 | 110 | Phase 3D-3H: Адаптеры + Frontend | 🔄 Active |
| 29 | 111 | Phase 4A-4D: Тесты (unit, integration) | ⏳ Future |
| 30 | 112 | Phase 4E-4K + 5: Тесты + Документация | ⏳ Future |
| 31 | 113 | Phase 6: Deploy & Release | ⏳ Future |

### Epics

```
EKFLAB-194: Фаза 0: Подготовка инфраструктуры ✅
EKFLAB-204: Фаза 1: Архитектура и ТЗ Go+React ✅
EKFLAB-236: Фаза 1.5: Расширение 1С для Kafka ✅
EKFLAB-241: Фаза 2: SE-ревью Go+React ✅
EKFLAB-3:   Фаза 3A: Scaffold проекта ✅
EKFLAB-136: Фаза 3B: Domain Layer ✅
EKFLAB-4:   Фаза 3C: Use Cases ✅
EKFLAB-5:   Фаза 3D: Адаптеры 🔄
EKFLAB-6:   Фаза 3E: AI-аналитика 🔄
EKFLAB-7:   Фаза 3F: React-фронтенд 🔄
EKFLAB-8:   Фаза 3G: Инфраструктура 🔄
EKFLAB-9:   Фаза 3H: Сквозные компоненты 🔄
EKFLAB-10:  Фаза 4A: Unit-тесты Go ⏳
EKFLAB-11:  Фаза 4B: Тесты React ⏳
EKFLAB-12:  Фаза 4C: Интеграционные тесты ⏳
EKFLAB-13:  Фаза 4D: Контрактные тесты ⏳
EKFLAB-14:  Фаза 4E: E2E-тесты Playwright ⏳
EKFLAB-15:  Фаза 4F: Нагрузочные тесты k6 ⏳
EKFLAB-16:  Фаза 4G: Визуальная регрессия ⏳
EKFLAB-17:  Фаза 4H: AI Eval Suite ⏳
EKFLAB-18:  Фаза 4I: Тесты безопасности ⏳
EKFLAB-19:  Фаза 4J: Тесты целостности данных ⏳
EKFLAB-20:  Фаза 4K: Мутационное тестирование ⏳
EKFLAB-21:  Фаза 5: Документация ⏳
EKFLAB-22:  Фаза 6A: Репозиторий и CI/CD ⏳
EKFLAB-23:  Фаза 6B: Миграция данных ⏳
EKFLAB-24:  Фаза 6C: Бэкап и DR ⏳
EKFLAB-25:  Фаза 6D: Деплой ⏳
EKFLAB-26:  Фаза 6E: Релиз ⏳
EKFLAB-27:  Фаза 6F: Публикация в Confluence ⏳
EKFLAB-193: Верификация спринтов и Quality Gate 🔄
```

---

## Current Status (2026-03-03)

**Active sprint:** Sprint 28 — Phase 3D-3H (Адаптеры + AI + Frontend + Infra)
**Completed:** Phase 0, 1, 1.5, 2, 3A-3C (52 задачи из архитектуры + 20 из scaffold/domain)
**Next:** Завершение Sprint 28, затем Sprint 29 (тестирование)

### Key artifacts

| Артефакт | Расположение |
|----------|-------------|
| ФМ FM-LS-PROFIT | [Confluence](https://confluence.ekf.su/pages/viewpage.action?pageId=83951683) |
| ТЗ Go+React | [Confluence](https://confluence.ekf.su/pages/viewpage.action?pageId=86049879) |
| Архитектура Go+React | [Confluence](https://confluence.ekf.su/pages/viewpage.action?pageId=86049880) |
| Jira Plan | [Portfolio](https://jira.ekf.su/secure/PortfolioReportView.jspa?r=i5SUF) |
| Код | `/home/dev/projects/claude-agents/profitability-service/` |
