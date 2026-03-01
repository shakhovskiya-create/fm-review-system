# ROADMAP: profitability-service — Go+React FM-LS-PROFIT

> **Version:** 1.0.0 | **Date:** 2026-03-01 | **Status:** APPROVED
> **Plan source:** `.claude/plans/jaunty-wibbling-ember.md`

## Executive Summary

FM-LS-PROFIT (контроль рентабельности отгрузок по ЛС) реализуется как отдельный Go+React сервис. 1С:УТ 10.2 остаётся source of truth. Go-сервис добавляет AI-аналитику, dashboard, автономные расследования.

**Key numbers:**
- **~195 задач** across 7 phases
- **11 weeks** timeline
- **6 Go microservices** + React frontend
- **17 integrations** (8 from FM + 9 new)
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

**Full context:** `../../memory/profitability-service-decisions.md`

---

## Gantt Chart

```
Phase 0: Protocols & Infrastructure
Week 1  |████████████████████████████████████████|
         0.1 Agent16  0.2 Agent5  0.3-0.4 Agent14  0.5-0.7 Config  0.8 Secrets

Phase 1A-1B: Domain Model + Go Services Architecture (Agent 5)
Week 2  |████████████████████████████████████████|
         1.1-1.6 Aggregates, VOs, Events, Services, Rules, Sagas
Week 3  |████████████████████████████████████████|
         1.7-1.15 profitability, workflow, analytics, integration, notification, API GW, OpenAPI, DB, Kafka

Phase 1C-1E: Frontend + AI + Integrations (Agent 5)
Week 3  |████████████████████░░░░░░░░░░░░░░░░░░░░| (parallel with 1B tail)
Week 4  |████████████████████████████████████████|
         1.16-1.22 Dashboard, Shipment, Approval, AI, Reports, Settings, Components
         1.23-1.27 AI Levels, Prompt Caching, Guardrails
         1.28-1.31 1С→Kafka, Go→1С, ELMA, External

Phase 1.5: 1С Extension (Agent 11 + Agent 10 review)
Week 3  |░░░░░░░░████████████████████████░░░░░░░░| (parallel with 1C-1E)
         1.5.1-1.5.3 HTTP-сервис, Подписки, Фоновое задание
         1.5.4 Agent 10 SE Review

Phase 2: SE Review (Agent 9)
Week 5  |████████████████████████████████████████|
         2.1-2.9 Architecture, API, Data, Security, Performance, AI, Integration, Coverage, AI Eval

Phase 3A-3C: Scaffold + Domain + UseCases (Agent 12)
Week 6  |████████████████████████████████████████|
         3.1-3.4 Repo, Go tooling, React, Docker
         3.5-3.10 Entities, VOs, Events, Errors, Ports, Services
         3.11-3.16 Calculate, Approve, Detect, Sanction, Price, Report

Phase 3D-3E: Adapters + AI Service (Agent 12)
Week 7  |████████████████████████████████████████|
         3.17-3.26 HTTP, PG, Kafka, Redis, Claude, ELMA, WMS, CBR, Notifications
         3.27-3.30 Deterministic, Claude integration, Agentic pipeline, AI audit

Phase 3F-3H: Frontend + Infra + Cross-Cutting (Agent 12)
Week 8  |████████████████████████████████████████|
         3.31-3.38 Components, Dashboard, Shipment, Approval, AI, Reports, Settings, Auth
         3.39-3.42 Migrations, Kafka topics, Seed data, Wire DI
         3.43-3.50 Logging, Tracing, Shutdown, Mocks, Grafana, Errors, Outbox, DevExp

Phase 4A-4D: Unit + Integration + Contract Tests (Agent 14)
Week 9  |████████████████████████████████████████|
         4.1-4.4 Domain, UseCase, HTTP, AI tests
         4.5-4.7 React components, pages, forms
         4.8-4.13 PG, Kafka, DLQ, Redis, LDAP, API contract, Kafka schema

Phase 4E-4K: E2E + Load + Security + Mutation (Agent 14)
Week 10 |████████████████████████████████████████|
         4.14-4.18 Playwright E2E (12 flows)
         4.19-4.21 k6 load tests
         4.22-4.23 Visual regression
         4.24-4.26 AI eval suite
         4.27-4.29 Security testing
         4.30-4.32 Data consistency + mutation

Phase 5: Documentation (Agent 15) — parallel with Phase 4E-4K
Week 10 |████████████████████░░░░░░░░░░░░░░░░░░░░|
         5.1-5.8 User Guide, Admin, Quick Start, FAQ, API, Release Notes, Runbook, AI Guide

Phase 6A-6C: Repo + Data Migration + Backup (Agent 16)
Week 11 |████████████████████████████████████████|
         6.1-6.3 GitHub repo, Push code, CI/CD
         6.4-6.6 Data seed plan, Dev migration, Staging migration
         6.7-6.9 Backup strategy, DR plan, Retention policy

Phase 6D-6F: Deploy + Release + Publish (Agent 16 + Agent 7)
Week 12 |████████████████████████████████████████|
         6.10-6.13 Deploy Dev, Smoke test, Deploy Staging, E2E on Staging
         6.14-6.17 Quality Gate, Deploy Prod, Monitor, Capacity planning
         6.18-6.19 Confluence publish
```

**Critical path:** Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 6D
**Parallel tracks:** Phase 1.5 || Phase 1C-1E, Phase 5 || Phase 4E-4K

---

## Phase Summary Table

| Phase | Description | Agent(s) | Weeks | Tasks | Dependencies |
|-------|-------------|----------|-------|-------|--------------|
| **0** | Protocols & Infrastructure | Orchestrator | 1 | 9 | - |
| **1** | Architecture & TZ | Agent 5 (opus) | 2-4 | 31 | Phase 0 |
| **1.5** | 1С Extension | Agent 11 + Agent 10 | 3 | 4 | Phase 1 (task 1.28) |
| **2** | SE Review | Agent 9 (opus) | 5 | 9 | Phase 1 |
| **3** | Code Generation | Agent 12 (opus) | 6-8 | 50 | Phase 2 |
| **4** | Testing | Agent 14 (sonnet) | 9-10 | 32 | Phase 3 |
| **5** | Documentation | Agent 15 (sonnet) | 10 | 8 | Phase 4 (partial) |
| **6** | Deploy & Release | Agent 16 + Agent 7 | 11-12 | 19 | Phase 4+5 |
| | | **TOTAL** | **~12** | **~162 explicit + subtasks** | |

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

| Milestone | Target | Deliverable | Success Criteria |
|-----------|--------|------------|------------------|
| M0 | Week 1 | Infrastructure ready | Agent 16 created, protocols updated, pipeline fixed |
| M1 | Week 4 | Architecture complete | Domain model, 6 service specs, OpenAPI, DB schemas, AI design |
| M1.5 | Week 3 | 1С extension ready | BSL code, SE review passed, extension compiles |
| M2 | Week 5 | SE review passed | 0 CRITICAL, 0 HIGH findings, all corrections applied |
| M3 | Week 8 | Code complete | All services build, lint passes, basic tests pass, `docker compose up` works |
| M4 | Week 10 | Tests complete | 88% coverage, E2E passes, load tests pass, security scan clean |
| M5 | Week 10 | Docs complete | User guide, admin guide, FAQ, API docs, runbook |
| M6 | Week 12 | Production release | v1.0.0 deployed, monitored 15min, error rate <1% |

---

## GitHub Issues Structure

All tasks tracked as GitHub Issues with labels:
- `sprint:24` — Phase 0
- `sprint:25` — Phase 1
- `sprint:26` — Phase 1.5 + Phase 2
- `sprint:27` — Phase 3A-3C
- `sprint:28` — Phase 3D-3H
- `sprint:29` — Phase 4A-4D
- `sprint:30` — Phase 4E-4K + Phase 5
- `sprint:31` — Phase 6

Epic hierarchy:
```
#126 Phase 0: Protocols & Infrastructure
  ├── #127 Agent 16 creation
  ├── #128 Agent 5 update
  ├── #129 Agent 14 coverage
  ├── #130 Agent 14 k6 + visual
  ├── #131 Schema update
  ├── #132 Pipeline fix
  ├── #133 Routing update
  ├── #134 Secrets management
  └── #135 Verification

Phase 1: Architecture (epic TBD)
  ├── 1.1-1.6 Domain Model (6 tasks)
  ├── 1.7-1.15 Go Services (9 tasks)
  ├── 1.16-1.22 Frontend (7 tasks)
  ├── 1.23-1.27 AI Analytics (5 tasks)
  └── 1.28-1.31 Integrations (4 tasks)

Phase 1.5: 1С Extension (epic TBD)
  ├── 1.5.1-1.5.3 Extension code (3 tasks)
  └── 1.5.4 SE Review (1 task)

Phase 2: SE Review (epic TBD)
  └── 2.1-2.9 Review areas (9 tasks)

Phase 3: Code Generation (epic TBD)
  ├── 3A Scaffold (4 tasks)
  ├── 3B Domain Layer (6 tasks)
  ├── 3C Use Cases (6 tasks)
  ├── 3D Adapters (10 tasks)
  ├── 3E AI Analytics (4 tasks)
  ├── 3F React Frontend (8 tasks)
  ├── 3G Infrastructure (4 tasks)
  └── 3H Cross-Cutting (8 tasks)

Phase 4: Testing (epic TBD)
  ├── 4A Go Unit Tests (4 tasks)
  ├── 4B React Tests (3 tasks)
  ├── 4C Integration Tests (5 tasks)
  ├── 4D Contract Tests (3 tasks)
  ├── 4E E2E Tests (5+ tasks)
  ├── 4F Load Tests (3 tasks)
  ├── 4G Visual Regression (2 tasks)
  ├── 4H AI Eval Suite (3 tasks)
  ├── 4I Security Testing (3 tasks)
  ├── 4J Data Consistency (2 tasks)
  └── 4K Mutation Testing (1 task)

Phase 5: Documentation (epic TBD)
  └── 5.1-5.8 Docs (8 tasks)

Phase 6: Deploy & Release (epic TBD)
  ├── 6A Repo & CI/CD (3 tasks)
  ├── 6B Data Migration (3 tasks)
  ├── 6C Backup & DR (3 tasks)
  ├── 6D Deploy (4 tasks)
  ├── 6E Release (4 tasks)
  └── 6F Publish (2 tasks)
```

---

## Next Steps

1. Phase 0 in progress — update protocols, fix pipeline, configure secrets
2. After Phase 0 verification → start Phase 1 with Agent 5
3. Each phase starts ONLY after previous phase verification passes
