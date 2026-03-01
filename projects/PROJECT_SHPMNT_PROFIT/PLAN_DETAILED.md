# PLAN: profitability-service — Go+React реализация FM-LS-PROFIT

## Context

FM-LS-PROFIT (контроль рентабельности отгрузок по ЛС) прошла полный цикл review (v1.0.5, 5 аудитов, бизнес-ревью, 143 объекта архитектуры). Текущая архитектура рассчитана на 1С:УТ 10.2 (расширение .cfe), но платформа устарела (EOL 01.04.2024), нет AI-аналитики, ограниченный UI.

**Решение:** Реализовать ФМ как отдельный Go+React сервис с AI-аналитикой на Claude API. 1С:УТ остаётся source of truth для документов/регистров. Go-сервис добавляет: интеллектуальную аналитику, современный dashboard, автономные расследования аномалий.

**Ожидаемый результат:** Работающий сервис profitability-service (6 Go микросервисов + React frontend) с полным покрытием тестами (88%), AI-аналитикой (Level 3 — agentic), CI/CD, мониторингом, и документацией.

**Принципиальные решения (утверждены пользователем 2026-03-01):**
- Отдельный репозиторий: `/home/dev/projects/claude-agents/profitability-service/`
- AI: Sonnet 4.6 (analyst, 90%) + Opus 4.6 (investigator, 10%). NO Haiku
- Auth: AD (LDAP/Kerberos), NOT HR system
- Release Manager: Agent 16 (NEW) — не человек
- Coverage: 88% total, domain 95%, mutation testing
- Mini MDM: temporal PostgreSQL tables в integration-service
- 17 интеграций (8 из ФМ + 9 новых)

**Полный контекст решений:** `memory/profitability-service-decisions.md`

---

## Phase 0: Подготовка протоколов и инфраструктуры

### 0.1 Создать Agent 16 — Release Engineer (NEW)
**Файлы:**
- `.claude/agents/agent-16-release-engineer.md` (subagent definition)
- `agents/dev/AGENT_16_RELEASE_ENGINEER.md` (protocol)

**Содержание протокола:**
- model: opus (критичные решения о продакшене)
- Фаза: deploy
- Команды: `/release`, `/deploy-staging`, `/deploy-prod`, `/rollback`, `/status`
- Quality Gate: 12 обязательных проверок перед deploy
- Auto-rollback при error rate >1% в течение 15 мин
- Changelog generation из conventional commits
- Semantic versioning (auto-determine patch/minor/major)
- Telegram + Confluence notifications

**Acceptance Criteria:**
- [ ] Subagent definition создан, keywords: "релиз", "деплой", "deploy", "release"
- [ ] Protocol ≥200 строк с полным decision tree
- [ ] Quality Gate checklist документирован (12 пунктов)

**Verification:** Agent вызывается через Claude Code subagent system

### 0.2 Обновить Agent 5: поддержка AI-аналитики
**Файл:** `agents/AGENT_5_TECH_ARCHITECT.md`
- Заголовок: "ТЕХНИЧЕСКИЙ АРХИТЕКТОР 1С" → "ТЕХНИЧЕСКИЙ АРХИТЕКТОР"
- Добавить в /platform-go: секция "AI Service Architecture" (Claude API, model selection, prompt caching, guardrails)
- Добавить в /domain: "AI Analytics Aggregate" (deterministic + LLM + agentic layers)
- Добавить mapping: AI Model Config → Go env vars

**Acceptance Criteria:**
- [ ] Title обновлён
- [ ] AI секции добавлены в /platform-go и /domain
- [ ] Existing 1С functionality не сломана

### 0.3 Обновить Agent 14: coverage targets + k6 + security testing
**Файл:** `agents/dev/AGENT_14_QA_GO.md`
- **CRITICAL FIX:** Обновить coverage targets: 70% → 88% total, domain 95%, adapter/claude 90%
- Добавить таблицу per-layer targets (из memory/profitability-service-decisions.md)
- Добавить раздел: "Security testing" — gosec, govulncheck, npm audit, OWASP ZAP (CI)

**Acceptance Criteria:**
- [ ] Coverage targets в протоколе Agent 14 = 88% total (совпадают с планом)
- [ ] Security testing раздел добавлен (gosec, govulncheck)
- [ ] Команда /generate-security-test описана

### 0.3b Обновить Agent 14: k6 load testing
**Файл:** `agents/dev/AGENT_14_QA_GO.md`
- Добавить раздел 7: "Нагрузочное тестирование (k6)"
- Добавить команду `/generate-load-test`
- k6 сценарии: API load (70 users), Kafka throughput (1000 msg/s), AI service (100 concurrent)
- Thresholds: p95 <200ms, p99 <500ms, error rate <1%

**Acceptance Criteria:**
- [ ] k6 section добавлен с примерами сценариев
- [ ] Thresholds документированы
- [ ] Команда /generate-load-test описана

### 0.4 Обновить Agent 14: visual regression
**Файл:** `agents/dev/AGENT_14_QA_GO.md`
- Добавить раздел 8: "Visual Regression (Playwright screenshots)"
- Baseline snapshots: Dashboard, DataTable, KPIWidget, ApprovalForm
- Diff threshold: 0.1% pixel difference

**Acceptance Criteria:**
- [ ] Visual regression section добавлен
- [ ] Baseline workflow описан

### 0.5 Обновить schemas/agent-contracts.json
**Файл:** `schemas/agent-contracts.json`
- Добавить `agentOutput_Agent16_ReleaseEngineer`
- Поля: deployedVersion, environment, qualityGateResults, changelog, rollbackAvailable

**Acceptance Criteria:**
- [ ] Schema валидна (JSON parse ok)
- [ ] Agent 16 output schema добавлена

### 0.6 Обновить pipeline config + исправить баг
**Файл:** `config/pipeline.json`
- **BUG FIX:** Agent 12 depends_on: Agent 10 (SE 1С) → исправить на Agent 9 (SE Go)
- Добавить Agent 16 в AGENT_REGISTRY
- Добавить Go pipeline: `5 → 9 → 12 → 14 → 16 → 7`
- Добавить Phase 1.5 → Agent 10 SE review для 1С extension: `11 → 10`
- Budget: Agent 16 = $5/run

**Acceptance Criteria:**
- [ ] Agent 12 depends on Agent 9 (NOT Agent 10) — BUG FIXED
- [ ] Agent 11 → Agent 10 review chain added
- [ ] Pipeline dry-run проходит без ошибок
- [ ] Agent 16 в registry

### 0.7 Обновить маршрутизацию
**Файлы:** `.claude/rules/subagents-registry.md`, `CLAUDE.md`
- Добавить Agent 16 в таблицу
- Маршруты: "релиз", "деплой" → Agent 16
- Обновить pipeline diagram

**Acceptance Criteria:**
- [ ] Agent 16 в маршрутизации
- [ ] Pipeline diagram актуален

### 0.8 Secrets management для profitability-service
**Файлы:** Infisical project setup, `scripts/load-secrets.sh` update
- Создать проект `profitability-service` в Infisical (или папку в существующем)
- Добавить secrets: DB URLs (×5), Redis URL, Kafka brokers, AD credentials, ELMA API key, Claude API key, Telegram Bot token, SMTP credentials, JWT signing key (RS256 keypair)
- Обновить `scripts/load-secrets.sh`: поддержка multi-project или subfolder
- `.env.example` в profitability-service repo — все ключи без значений

**Acceptance Criteria:**
- [ ] Все 15+ secrets зарегистрированы в Infisical
- [ ] `check-secrets.sh --verbose` проходит для нового проекта
- [ ] Нет secrets в коде или git history

**Phase 0 Verification:**
```bash
pytest tests/ -x -q  # 0 failures
python3 -c "import json; json.load(open('schemas/agent-contracts.json'))"  # valid
python3 scripts/run_agent.py --pipeline --project PROJECT_SHPMNT_PROFIT --dry-run  # ok
```

---

## Phase 1: Архитектура и ТЗ (Agent 5)

**Agent:** Agent 5 (Tech Architect), model: opus
**Input:** FM-LS-PROFIT v1.0.5 (Confluence PAGE_ID 83951683)
**Commands:** `/domain` → `/platform-go` → `/full`

### 1A. Domain Model (DDD) — 6 задач

#### 1.1 Выделить Aggregates
**Deliverable:** Список агрегатов с invariants и lifecycle
- `Shipment` (отгрузка по ЛС — центральная сущность)
- `LocalEstimate` (ЛС — план vs факт)
- `ApprovalProcess` (state machine согласования)
- `ProfitabilityCalculation` (расчёт маржи)
- `Client` (контрагент с историей)
- `Sanction` (санкции за невыкуп)
- `PriceSheet` (НПСС — себестоимость)
**Verification:** Каждый aggregate имеет ≥1 invariant, ≥1 domain event

#### 1.2 Определить Value Objects
**Deliverable:** Immutable VOs с validation rules
- `Money` (amount + currency, precision 2)
- `Percentage` (0-100, precision 2)
- `SLADeadline` (priority-based: P1=2h, P2=4h, P3=12h)
- `ProfitabilityThreshold` (target margin per client category)
- `ApprovalDecision` (approve/reject/escalate + reason)
- `PriceCorrection` (per line item, max 5 iterations)
- `DateRange` (from-to, immutable)
**Verification:** Каждый VO имеет конструктор с validation, Equals method

#### 1.3 Определить Domain Events
**Deliverable:** Event catalog с payload schemas
- `ShipmentCreated`, `ShipmentUpdated`, `ShipmentPosted`
- `ProfitabilityCalculated` (margin, threshold, deviation)
- `ApprovalRequested`, `ApprovalCompleted`, `ApprovalExpired`, `ApprovalEscalated`
- `ThresholdViolated` (deviation > auto-approve limit)
- `SanctionTriggered`, `SanctionApplied`
- `PriceSheetUpdated`, `PriceSheetTriggered` (ЦБ >5%, purchase >15%)
- `AnomalyDetected` (AI Level 1/2/3)
- `InvestigationStarted`, `InvestigationCompleted` (AI agentic)
**Verification:** Каждый event имеет timestamp, aggregate_id, payload schema

#### 1.4 Определить Domain Services
**Deliverable:** Service interfaces с методами
- `ProfitabilityCalculator` — формулы из ФМ (нетто-выручка, себестоимость, маржа)
- `ApprovalRouter` — 4-level matrix (auto → РБЮ → ДП → ГД), threshold-based
- `SLATracker` — countdown per priority, escalation at 80%
- `SanctionManager` — warning → sanction → block, timer-based
- `ThresholdEvaluator` — aggregate limits (20K/day mgr, 100K/day BU)
- `CrossValidator` — перекрёстный контроль при изменении плана ЛС
**Verification:** Каждый service — interface в port/, implementation в usecase/

#### 1.5 Описать бизнес-правила
**Deliverable:** Все LS-BR-* из ФМ → domain rules с формулами
- LS-BR-035: таймаут блокировки 5 мин
- LS-BR-075: автотриггеры НПСС (курс ЦБ >5%, закупка >15%)
- Порог автосогласования: ≤1.00 п.п.
- Агрегированные лимиты: 20K/day менеджер, 100K/day БЮ
- Лимит итераций корректировки: 5
- Пороги нагрузки: 30 (автоперелив), 50 (доп. согласующий)
- ELMA fallback: ≤5 п.п. авто, >5 п.п. FIFO очередь
**Verification:** Каждое правило трассируется к LS-BR-* в ФМ

#### 1.6 Описать Sagas
**Deliverable:** Distributed transaction workflows
- `ApprovalSaga`: create → route → wait → approve/reject → notify → update 1С
  - Compensation: timeout → escalate → auto-reject after SLA×2
- `SanctionSaga`: detect → warn → grace period → apply → block
  - Compensation: manual override by ГД
- `PriceUpdateSaga`: trigger → fetch rates → recalculate → notify → update affected LS
**Verification:** Каждая saga имеет compensation steps

### 1B. Go Microservices Architecture — 9 задач

#### 1.7 Спроектировать profitability-service
**Deliverable:** Service spec (endpoints, DB schema, business logic)
- REST endpoints: POST /calculate, GET /shipments/:id/profitability, GET /ls/:id/summary
- DB: shipments, line_items, calculations, thresholds
- Формулы: нетто-выручка = сумма - возвраты - скидки; маржа = (выручка - себестоимость) / выручка × 100
- Кэш НПСС в Redis (TTL 1h, invalidate on PriceSheetUpdated event)
**Verification:** OpenAPI spec для всех endpoints, DB migration SQL

#### 1.8 Спроектировать workflow-service
**Deliverable:** Service spec с state machine
- State machine: PENDING → AUTO_APPROVED | ROUTING → LEVEL_1..4 → APPROVED | REJECTED | EXPIRED
- ELMA integration: REST client with circuit breaker (5 failures → open → 30s → half-open)
- Fallback mode: ≤5 п.п. auto, >5 п.п. FIFO queue (ОчередьРезервногоРежима)
- Aggregate limits: per-manager (20K/day), per-BU (100K/day)
- SLA tracking: countdown timer, escalation at 80%, notification at 50%
**Verification:** State machine diagram, all transitions documented

#### 1.9 Спроектировать analytics-service
**Deliverable:** 3-level AI architecture spec
- **Level 1 (Deterministic):** Z-score anomaly (gonum/stat), ARIMA forecast (gonum), threshold rules engine
- **Level 2 (LLM — Sonnet):** System prompt (FM context ~20K tokens, cached), explanation generation, report summarization
- **Level 3 (Agentic — Opus):** Tool definitions (query_shipments, query_client_history, query_price_changes, calculate_what_if), orchestration loop (max 10 iterations, 60s timeout)
- Model config: env vars AI_MODEL_ANALYST, AI_MODEL_INVESTIGATOR
- Prompt caching: system prompt cached (90% discount), user prompt dynamic
- Cost monitoring: per-request logging → Langfuse, daily ceiling alert
- Guardrails: rate limit, timeout, confidence threshold, content filter, audit log
**Verification:** Prompt templates documented, cost estimation per scenario

#### 1.10 Спроектировать integration-service + Mini MDM
**Deliverable:** Kafka consumer architecture + temporal data store
- Kafka topics (9 inbound from 1С): `1c.order.created/updated`, `1c.shipment.posted/returned`, `1c.price.npss-updated`, `1c.price.purchase-changed`, `1c.client.updated`, `1c.ls.created/plan-changed`
- Kafka topics (3 outbound to 1С): `cmd.approval.result`, `cmd.sanction.applied`, `cmd.block.shipment`
- **Outbox pattern:** Domain events → `outbox` table (same DB transaction) → background poller → Kafka producer. Guarantees at-least-once delivery without 2PC. Polling interval: 100ms. Cleanup: after Kafka ack, mark as published (TTL 7 days).
- Mini MDM: temporal PostgreSQL tables (valid_from, valid_to) for clients, products, price_sheets, exchange_rates, employees, business_units
- **MDM cold start:** Initial data seed from 1С via bulk export (CSV/JSON). Script `scripts/seed-mdm.sh` — loads baseline data before first Kafka event. Validates referential integrity after seed.
- MDM API: GET /mdm/npss?product_id=X&date=Y, GET /mdm/diff?entity=clients&from=..&to=..
- MDM alerts: stale data (>30 days without update) → notify FD
- Idempotency: Kafka message_id → dedup table (TTL 7 days)
- DLQ: 3-level retry (1s, 30s, 5min) → DLQ with error headers
- **Audit trail immutability:** All MDM changes in append-only `mdm_audit_log` table (no UPDATE/DELETE). Tamper detection: daily hash chain verification.
**Verification:** Topic list matches FM integrations, temporal query examples, outbox pattern documented, cold start procedure tested

#### 1.11 Спроектировать notification-service
**Deliverable:** Multi-channel notification spec
- Channels: Telegram Bot API, Email (SMTP), 1С push (REST callback)
- Templates: approval_request, approval_result, sla_warning, anomaly_alert, daily_digest
- Throttling: max 10 notifications/hour per user, quiet hours 22:00-07:00
- Priority routing: CRITICAL → all channels, HIGH → Telegram + email, MEDIUM → Telegram, LOW → digest
- Fallback: Telegram down → email, email down → 1С push
**Verification:** Template list covers all FM notification scenarios

#### 1.12 Спроектировать API Gateway
**Deliverable:** Auth + routing spec
- Auth: AD LDAP/Kerberos → JWT (RS256, 15min access + 7d refresh)
- **2FA/MFA:** If corporate policy requires — TOTP (RFC 6238) or AD-native MFA. Design as optional middleware (enable via env var `AUTH_MFA_ENABLED`). Phase 1: LDAP only, Phase 2: add MFA if required.
- RBAC: 5 roles from FM (manager, rbu, dp, gd, fd) → AD groups
- Rate limiting: per-user token bucket (100 req/min standard, 200 for gd/fd)
- CORS: whitelist frontend domain + CSP headers (Content-Security-Policy)
- Health: /health, /ready, /metrics (Prometheus)
- Routing: /api/v1/profitability → profitability-service, /api/v1/approvals → workflow-service, etc.
- **Graceful shutdown:** SIGTERM → stop accepting new requests → drain in-flight (30s timeout) → close DB/Kafka/Redis connections → exit 0
- **Inter-service communication:** synchronous = gRPC (internal, service mesh), async = Kafka events. NO direct HTTP between services (only via API GW for external). gRPC: protobuf contracts in `api/proto/`, buf lint, connect-go library.
**Verification:** Route table documented, auth flow diagram, graceful shutdown sequence documented

#### 1.13 OpenAPI 3.0 спецификация
**Deliverable:** `api/openapi.yaml` — complete spec
- All endpoints from 6 services
- Request/response schemas (JSON Schema)
- Authentication (Bearer JWT)
- Error format (RFC 7807 Problem Details)
- Pagination (cursor-based)
- Examples for each endpoint
**Verification:** OpenAPI validator passes, swagger-ui renders correctly

#### 1.14 Database schema design
**Deliverable:** Per-service PostgreSQL schemas + migrations
- profitability-service: shipments, line_items, calculations, thresholds
- workflow-service: approvals, approval_history, sla_tracking, aggregate_limits, elma_queue
- analytics-service: anomalies, investigations, ai_audit_log, forecasts
- integration-service: mdm_clients, mdm_products, mdm_price_sheets, mdm_exchange_rates, mdm_employees, kafka_dedup
- notification-service: notifications, templates, user_preferences
- Indices: all foreign keys, frequently queried columns
- Temporal tables: valid_from/valid_to with CHECK constraints
**Verification:** Each service has ≥1 migration file, no cross-service joins

#### 1.15 Kafka topic design
**Deliverable:** Topic catalog with schemas
- Naming: `{source}.{domain}.{event}.v{N}` (e.g., `1c.shipment.posted.v1`)
- Partitioning: by aggregate_id (shipment_id for shipments, client_id for clients)
- Retention: 7 days (events), 30 days (commands)
- Schema Registry: JSON Schema per topic
- DLQ naming: `{topic}.dlq`, retry: `{topic}.retry.{level}`
**Verification:** Topic list matches integration matrix (17 integrations)

### 1C. React Frontend Architecture — 7 задач

#### 1.16 Dashboard layout
**Deliverable:** Wireframe + component tree
- KPI row: total profitability %, trend arrow, anomaly count, SLA compliance %
- Chart: profitability trend (30 days, Recharts AreaChart)
- Alert feed: latest 10 anomalies/violations
- Quick filters: period, BU, manager
**Verification:** All KPIs traceable to FM requirements

#### 1.17 Shipment Analysis page
**Deliverable:** Page spec with data flow
- DataTable: sortable, filterable, paginated (cursor-based)
- Columns: ЛС, клиент, сумма, маржа %, статус, SLA, actions
- Drill-down drawer: line items, calculation breakdown, history
- Filters: client, manager, period, status, profitability range
**Verification:** Supports 50-70 concurrent users (per FM)

#### 1.18 Approval Queue page
**Deliverable:** Task list spec
- Task card: ЛС, deviation %, SLA countdown, recommended action
- Batch operations: approve all < threshold, reject selected
- Sorting: by SLA urgency (most urgent first)
- Role-based: РБЮ sees level 1-2, ДП sees level 2-3, ГД sees level 3-4
**Verification:** Matches approval matrix from FM

#### 1.19 AI Insights page
**Deliverable:** AI UX spec
- Anomaly cards: severity, description, affected entities, recommended action
- Investigation timeline: steps taken by agentic AI, data accessed, conclusion
- Chat interface: streaming response, follow-up questions
- Confidence indicator: per recommendation
**Verification:** Covers all 3 AI levels

#### 1.20 Reports page
**Deliverable:** Report catalog
- LS-RPT-* from FM mapped to report components
- Date range picker, BU filter, export (Excel via xlsx, PDF)
- Scheduled reports: daily digest (email), weekly summary
**Verification:** All P1 reports from FM covered

#### 1.21 Settings page
**Deliverable:** Admin interface spec
- Threshold sliders: auto-approve limit, aggregate limits, SLA values
- Role management: view AD groups → app roles mapping
- Notification preferences: per-user channel selection
- Feature flags: 6 functional options from FM
- Audit log viewer: who changed what setting when
**Verification:** All 10 constants from FM configurable

#### 1.22 Component library (Atomic Design)
**Deliverable:** Component inventory
- Atoms: Button, Badge, Card, Input, Select, Spinner, Toast
- Molecules: DataTable, KPIWidget, SLATimer, ProfitabilityBadge, AnomalyCard, FilterBar
- Organisms: ShipmentDetail, ApprovalForm, InvestigationTimeline, ReportViewer
**Verification:** Storybook-compatible structure

### 1D. AI Analytics Architecture — 5 задач

#### 1.23 Level 1: Deterministic analytics
**Deliverable:** Algorithm specifications
- Z-score anomaly: window 90 days, threshold ±2σ
- ARIMA forecast: 30-day prediction, confidence interval
- Threshold rules: all LS-BR-* business rules as evaluated conditions
- Aggregate monitoring: per-manager, per-BU, per-client cumulative tracking
**Verification:** Mathematical formulas documented, test cases defined

#### 1.24 Level 2: LLM Interpretation (Sonnet)
**Deliverable:** Prompt engineering spec
- System prompt template: FM context (~20K tokens), domain rules, output format
- Use cases: anomaly explanation, report summarization, Q&A about data
- Output format: structured JSON (explanation, confidence, recommendations)
- Caching strategy: system prompt cached, user prompt = specific data context
**Verification:** 10 sample prompts with expected outputs

#### 1.25 Level 3: Agentic Analytics (Opus)
**Deliverable:** Agent tool definitions + orchestration spec
- Tools: `query_shipments(filters)`, `query_client_history(client_id, period)`, `query_price_changes(product_ids, period)`, `calculate_what_if(scenario)`, `get_approval_history(ls_id)`
- Orchestration: max 10 iterations, 60s timeout, must output conclusion
- Trigger: Level 1 detects anomaly → Level 2 cannot explain with confidence >0.7 → Level 3
- Output: root cause, evidence chain, recommendation, confidence score
**Verification:** 5 sample investigation scenarios with expected tool call sequences

#### 1.26 Prompt caching strategy
**Deliverable:** Cost optimization design
- System prompt: FM rules + domain context (~20K tokens) → cached (90% discount)
- User prompt: specific data (shipment details, anomaly context) → not cached
- Estimated costs: Sonnet ~$0.003/req (with cache), Opus ~$0.05/req (with cache)
- Daily budget: $50 (prod), auto-degradation to Level 1 at 80%
**Verification:** Cost model validated against expected request volumes

#### 1.27 AI safety & guardrails
**Deliverable:** Safety spec
- Rate limiting: Sonnet 200/hour, Opus 50/hour
- Timeout: Sonnet 15s, Opus 60s → fallback to deterministic
- Content filter: no PII in responses, no "I don't know" without fallback
- Confidence threshold: <0.7 → escalate to higher model
- Audit log: every AI request (input hash, output, model, latency, cost, tokens)
- Cost ceiling: hard limit $50/day, alert at $30
**Verification:** Each guardrail has test case

### 1E. Integration Architecture — 4 задачи

#### 1.28 1С → Kafka pipeline design
**Deliverable:** Integration spec for 1С extension
- HTTP-сервис в расширении 1С:УТ → Kafka producer (via HTTP→Kafka bridge or direct)
- Events: ДокументПроведён, ЦенаИзменена, НПССОбновлена
- Payload: JSON, schema versioned (v1)
- Retry: queue в регистре сведений если Kafka недоступен
**Verification:** Covers all 9 inbound Kafka topics

#### 1.29 Go → 1С обратная связь
**Deliverable:** Callback API spec
- REST API в 1С (HTTP-сервис): PUT /api/v1/approval/{id}/result, PUT /api/v1/sanction/{id}
- Idempotent: request_id header for dedup
- Auth: API key (rotated monthly via Infisical)
**Verification:** Covers all 3 outbound topics

#### 1.30 ELMA integration
**Deliverable:** ELMA client spec
- REST API: create process, get status, cancel
- Circuit breaker: 5 failures → open → 30s → half-open
- Fallback: auto-approve ≤5 п.п., FIFO queue >5 п.п.
**Verification:** Matches FM ELMA integration spec (LS-INT-003)

#### 1.31 External integrations
**Deliverable:** Client specs for remaining integrations
- ЦБ РФ: daily cron, XML parser, retry 3x
- WMS outbound: REST/MQ (approval status)
- WMS inbound: webhook/MQ (shipment facts)
- AD: LDAP bind, group query, user search
**Verification:** All 17 integrations covered

**Phase 1 Deliverables:**
- Architecture document (Confluence page)
- ТЗ document (Confluence page)
- OpenAPI 3.0 spec (`api/openapi.yaml`)
- DB migration schemas
- Kafka topic catalog
- AI prompt templates
- Cost estimation

**Phase 1 Verification:**
- Agent 5 produces `full_summary.json` per schema v2.2
- All FM business rules traced to domain model
- All 17 integrations documented
- No orphan requirements (FM requirement without Go counterpart)

---

## Phase 1.5: 1С Extension — Kafka Producer (Agent 11)

**Agent:** Agent 11 (Dev 1С), model: opus
**Input:** Integration spec from Phase 1 (task 1.28)

### 1.5.1 Расширение: HTTP-сервис для Kafka
**Deliverable:** BSL код HTTP-сервиса
- Endpoint: POST /api/v1/events — принимает event JSON, отправляет в Kafka
- Auth: API key header
- Queue: если Kafka недоступен → РегистрСведений.ОчередьСобытий
- Retry: фоновое задание каждые 60с проверяет очередь

### 1.5.2 Подписки на проведение документов
**Deliverable:** BSL код подписок
- &После ОбработкаПроведения ЗаказКлиента → event 1c.order.created
- &После ОбработкаПроведения Реализация → event 1c.shipment.posted
- &После ОбработкаПроведения Возврат → event 1c.shipment.returned
- Минимальная инвазия: только &После, никакого &Вместо

### 1.5.3 Фоновое задание мониторинга
**Deliverable:** Scheduled job для retry очереди + мониторинг

### 1.5.4 SE Review 1С extension (Agent 10)
**Agent:** Agent 10 (SE 1С), model: opus
**Input:** BSL code from 1.5.1-1.5.3
- Code quality: naming conventions, error handling, logging
- Performance: &После подписки не блокируют UI (async HTTP calls)
- Security: API key validation, input sanitization
- Compatibility: УТ 10.2 + платформа 8.3, обычные формы (НЕ управляемые)
- Extension best practices: minimal invasion, no &Вместо, rollback-safe
**AC:** 0 CRITICAL findings, extension approved for deployment

**Phase 1.5 Verification:**
- BSL код проходит BSL Language Server checks
- Extension compiles in EDT/конфигуратор (manual check)
- Agent 10 SE review passed (0 CRITICAL)

---

## Phase 2: SE Review (Agent 9)

**Agent:** Agent 9 (SE Go+React), model: opus
**Input:** Phase 1 deliverables (architecture, TZ, OpenAPI, schemas)

### 2.1 Architecture review
- Clean Architecture boundaries: domain has ZERO external imports
- Service coupling: no direct service-to-service DB access
- Single responsibility: each service owns its data
**AC:** 0 CRITICAL findings

### 2.2 API contract review
- Naming: RESTful, consistent (snake_case JSON, PascalCase Go)
- Pagination: cursor-based, not offset
- Error format: RFC 7807
- Versioning: /api/v1/ prefix
**AC:** OpenAPI spec passes linter

### 2.3 Data model review
- Normalization: 3NF minimum
- Indices: all FK + query columns
- N+1: no lazy loading patterns
- Temporal tables: valid_from/valid_to constraints
**AC:** No missing indices, no cross-service joins

### 2.4 Security review
- Auth: JWT RS256, refresh token rotation
- RBAC: role checks on every endpoint
- Input validation: all user input validated (Zod frontend, Go struct tags backend)
- SQL injection: sqlc (parameterized), no raw SQL
- XSS: React auto-escaping + CSP headers
- CORS: whitelist only
- Secrets: Infisical, never in code
**AC:** No HIGH/CRITICAL security findings

### 2.5 Performance review
- Kafka: consumer lag monitoring, DLQ alert
- DB: connection pool sizing (min 5, max 20 per service)
- Cache: Redis TTL strategy, invalidation on events
- Latency budget: API GW 10ms + service 50ms + DB 30ms + network 10ms = <100ms p50
**AC:** Latency budget documented per endpoint

### 2.6 AI architecture review
- Prompt injection: no raw user text in system prompts
- Cost: budget ceiling enforced at middleware level
- Fallback: Level 3 → 2 → 1 → deterministic
- Privacy: no PII in AI logs (hash user_id)
**AC:** All guardrails have implementation plan

### 2.7 Integration review
- Kafka: ordering within partition (by aggregate_id)
- Idempotency: dedup table with message_id
- DLQ: monitored, alert if >0 messages
- 1С compatibility: payload format validated against 1С HTTP-сервис spec
**AC:** All 17 integrations pass review

### 2.8 Coverage targets review
- domain/ 95%: achievable with table-driven tests
- total 88%: requires mutation testing for domain/
- Load test thresholds: realistic for 50-70 users
**AC:** Targets approved or adjusted with justification

### 2.9 AI eval suite design
- 30 test cases defined (10 anomaly, 10 explanation, 5 investigation, 5 edge)
- Scoring: automated accuracy check + human eval for explanations
- Baseline: ≥95% accuracy on anomaly detection, ≥4/5 on explanation quality
**AC:** Eval suite documented, test cases written

**Phase 2 Deliverables:**
- SE Review Report (findings classified CRIT/HIGH/MED/LOW)
- Corrections applied to Phase 1 documents
- AI eval test cases

**Phase 2 Verification:**
- 0 CRITICAL, 0 HIGH findings remaining after corrections
- Agent 9 produces `review_summary.json` per schema v2.2

---

## Phase 3: Code Generation (Agent 12)

**Agent:** Agent 12 (Dev Go+React), model: opus
**Input:** Phase 1+2 deliverables (corrected architecture, TZ, OpenAPI, schemas)
**Output:** Working code in `/home/dev/projects/claude-agents/profitability-service/`

### 3A. Project Scaffold (4 tasks)

#### 3.1 Repository init
- `go mod init github.com/user/profitability-service`
- Directory structure per Clean Architecture template
- `Makefile` with targets: build, test, lint, migrate, generate, dev, docker
- `docker-compose.yml` for dev (PG, Redis, Kafka KRaft, Prometheus, Grafana, Loki)
- `.env.example` with all required env vars
- `CLAUDE.md` for Agent 12/14 instructions
- `.github/workflows/ci.yml` (lint → test → build)

#### 3.2 Go tooling setup
- `golangci-lint` config (`.golangci.yml`)
- `sqlc` config (`sqlc.yaml`)
- `oapi-codegen` config
- `wire` config (`cmd/*/wire.go`)
- `golang-migrate` setup

#### 3.3 React project setup
- Next.js 15 with App Router (`web/`)
- TanStack Query provider
- Zustand stores structure
- Zod schemas from OpenAPI (openapi-typescript)
- Tailwind CSS + component library structure

#### 3.4 Docker infrastructure
- `Dockerfile.api` (multi-stage Go build)
- `Dockerfile.web` (Next.js standalone)
- `docker-compose.yml` (dev)
- `docker-compose.staging.yml` (staging overrides)
- `docker-compose.prod.yml` (prod overrides)
- Monitoring stack: Prometheus + Grafana + Loki configs

### 3B. Domain Layer (6 tasks)

#### 3.5 Domain entities — `internal/domain/entity/`
#### 3.6 Value objects — `internal/domain/valueobject/`
#### 3.7 Domain events — `internal/domain/event/`
#### 3.8 Domain errors — `internal/domain/errors.go`
#### 3.9 Port interfaces — `internal/port/`
#### 3.10 Domain services — `internal/domain/service/`

### 3C. Use Cases (6 tasks)

#### 3.11 CalculateProfitability — `internal/usecase/profitability/`
#### 3.12 ProcessApproval — `internal/usecase/approval/`
#### 3.13 DetectAnomaly — `internal/usecase/analytics/`
#### 3.14 ManageSanction — `internal/usecase/sanction/`
#### 3.15 UpdatePriceSheet — `internal/usecase/pricing/`
#### 3.16 GenerateReport — `internal/usecase/reporting/`

### 3D. Adapters (10 tasks)

#### 3.17 HTTP handlers (chi + oapi-codegen) — `internal/adapter/http/`
#### 3.18 PostgreSQL repositories (sqlc) — `internal/adapter/postgres/`
#### 3.19 Kafka consumers (franz-go) — `internal/adapter/kafka/consumer/`
#### 3.20 Kafka producers (franz-go) — `internal/adapter/kafka/producer/`
#### 3.21 Redis cache + locks — `internal/adapter/redis/`
#### 3.22 Claude API client (anthropic-sdk-go) — `internal/adapter/claude/`
#### 3.23 ELMA REST client — `internal/adapter/elma/`
#### 3.24 WMS client — `internal/adapter/wms/`
#### 3.25 ЦБ РФ rates client — `internal/adapter/cbr/`
#### 3.26 Notification adapters (Telegram + Email) — `internal/adapter/notification/`

### 3E. AI Analytics Service (4 tasks)

#### 3.27 Deterministic engine (Z-score, ARIMA, threshold rules)
#### 3.28 Claude integration (prompts, caching, structured output)
#### 3.29 Agentic pipeline (tools, orchestration loop, timeout)
#### 3.30 AI audit log (input/output/cost/latency logging → Langfuse)

### 3F. React Frontend (8 tasks)

#### 3.31 UI component library (atoms + molecules)
#### 3.32 Dashboard page
#### 3.33 Shipment Analysis page
#### 3.34 Approval Queue page
#### 3.35 AI Insights page
#### 3.36 Reports page
#### 3.37 Settings page
#### 3.38 Auth flow (AD login → JWT → protected routes)

### 3G. Infrastructure (4 tasks)

#### 3.39 DB migrations (all services)
#### 3.40 Kafka topic creation script
#### 3.41 Seed data script (synthetic test data)
#### 3.42 Wire dependency injection (all services)

### 3H. Cross-Cutting Concerns (8 tasks)

#### 3.43 Structured logging (slog)
- `log/slog` (stdlib Go 1.22+), JSON format, correlation_id propagated via context
- Log levels: DEBUG (dev only), INFO, WARN, ERROR
- Sensitive data: mask PII fields (user_id → hash, client_name → "***")
- Loki labels: service, level, correlation_id

#### 3.44 OpenTelemetry tracing
- OTLP/gRPC exporter to Jaeger/Tempo
- Spans: HTTP handler → use case → adapter (DB/Kafka/AI)
- Custom attributes: user_id, role, shipment_id, ai_model
- Sampling: 100% dev, 10% staging, 1% prod (adjust via env)

#### 3.45 Graceful shutdown
- SIGTERM handler: stop HTTP listener → drain Kafka consumers → flush outbox → close DB pools → close Redis → exit 0
- Timeout: 30s hard kill
- Health endpoint: /ready → 503 after SIGTERM (load balancer drain)

#### 3.46 Mock implementations for all external systems
- `internal/adapter/mock/` — mock implementations of all port interfaces
- Mocks: 1С API, ELMA, WMS, ЦБ РФ, AD/LDAP, Claude API, Telegram, SMTP
- Controlled by `INTEGRATION_MODE=mock|real` env var
- Mock data: realistic scenarios from FM (10 shipments, 3 clients, 2 managers)

#### 3.47 Grafana dashboards (5)
- Health dashboard: service status, uptime, error rate, latency p50/p95/p99
- Kafka dashboard: consumer lag, DLQ size, throughput, partition balance
- AI dashboard: model usage, cost per day, latency, cache hit rate, token count
- Business KPIs: profitability trend, approval queue size, SLA compliance
- Alerts dashboard: active alerts, alert history, notification delivery rate

#### 3.48 Error boundary pages (React)
- 404 Not Found, 403 Forbidden, 500 Internal Server Error
- Network error (offline/timeout) → retry button
- Auth expired → redirect to login with return URL
- Zustand error boundary wrapper for all pages

#### 3.49 Outbox table + background poller
- PostgreSQL outbox table per service: id, aggregate_type, aggregate_id, event_type, payload, created_at, published_at
- Poller: goroutine, 100ms interval, batch 100 events, Kafka produce, mark published
- Monitoring: outbox_pending metric (Prometheus), alert if >1000

#### 3.50 Developer experience
- `air` hot reload config (`.air.toml`) for Go services
- `Makefile dev` target: starts all services with air + docker compose (PG, Redis, Kafka)
- Kafka UI: Redpanda Console or kafka-ui (docker-compose dev profile)
- `scripts/dev-setup.sh`: one-command setup (install tools, create DBs, run migrations, seed data)

**Phase 3 Verification:**
```bash
make build        # Go compiles, no errors
make lint         # golangci-lint, 0 errors
cd web && npm run build  # Next.js builds, 0 errors
docker compose up -d     # All services healthy
make test         # Baseline unit tests pass (Agent 12 writes basic tests)
make dev          # Hot reload works, all services start
curl localhost:8080/health  # API GW responds 200
curl localhost:8080/metrics # Prometheus metrics available
```

---

## Phase 4: Testing (Agent 14)

**Agent:** Agent 14 (QA Go+React), model: sonnet
**Input:** Phase 3 code + Phase 1 TZ (requirements for test cases)

### 4A. Go Unit Tests (4 tasks)
#### 4.1 Domain entity + VO tests (target: 95% coverage)
#### 4.2 Use case tests with mocks (target: 92%)
#### 4.3 HTTP handler tests (httptest, target: 85%)
#### 4.4 AI service tests (mock Claude API, target: 90%)

### 4B. React Tests (3 tasks)
#### 4.5 Component unit tests (Vitest + RTL, target: 88%)
#### 4.6 Page integration tests (MSW v2 mocking, target: 80%)
#### 4.7 Form validation tests (React Hook Form + Zod)

### 4C. Integration Tests (5 tasks)
#### 4.8 PostgreSQL tests (testcontainers-go)
#### 4.9 Kafka tests (testcontainers-go KRaft)
#### 4.10 DLQ + retry + outbox tests
#### 4.10b Redis integration tests (testcontainers-go: cache, locks, rate limiting)
#### 4.10c AD/LDAP integration tests (test LDAP server in Docker, bind/search/group membership)

### 4D. Contract Tests (3 tasks)
#### 4.11 Go API contract (libopenapi-validator)
#### 4.12 React client contract (openapi-typescript)
#### 4.13 Kafka schema contract (Schema Registry)

### 4E. E2E Tests — Playwright (5 tasks)
#### 4.14 Login → Dashboard → View shipment
#### 4.15 Approval process (create → approve → verify)
#### 4.16 AI insight investigation (anomaly → drill-down → recommendation)
#### 4.17 Report generation (select → filter → export)
#### 4.18 Error flows (500, timeout, auth expired)
Plus 7 more critical flows to reach 12 total

### 4F. Load Tests — k6 (3 tasks)
#### 4.19 API load test (70 concurrent users, p95 <200ms)
#### 4.20 Kafka throughput (1000 events/sec)
#### 4.21 AI service load (100 concurrent, verify caching)

### 4G. Visual Regression — Playwright (2 tasks)
#### 4.22 Dashboard screenshot baselines
#### 4.23 Key component visual tests

### 4H. AI Eval Suite (3 tasks)
#### 4.24 Anomaly detection accuracy (10 cases, ≥95%)
#### 4.25 Explanation quality (10 cases, human eval ≥4/5)
#### 4.26 Investigation correctness (5 cases, correct root cause)
Plus 5 edge cases

### 4I. Security Testing (3 tasks)
#### 4.27 Static analysis — gosec (Go), govulncheck (Go dependencies)
#### 4.28 Dependency audit — npm audit (React), go mod verify
#### 4.29 OWASP ZAP — basic scan against running API (CI integration)

### 4J. Data Consistency Tests (2 tasks)
#### 4.30 Outbox → Kafka delivery guarantee test (kill service mid-publish → verify recovery)
#### 4.31 Temporal MDM data integrity test (valid_from/valid_to gaps, overlaps, stale data detection)

### 4K. Mutation Testing (1 task)
#### 4.32 domain/ mutation testing (gremlins or go-mutesting) — mutation score ≥80%

**Phase 4 Verification:**
```bash
make test                  # All Go tests pass
cd web && npm test         # All React tests pass
make test-integration      # Integration tests pass (PG + Kafka + Redis + LDAP)
make test-e2e              # Playwright passes (12 flows)
make test-load             # k6 thresholds met (p95 <200ms, 70 users)
make test-coverage         # Total ≥88%, domain ≥95%
make test-mutation         # Mutation score ≥80% for domain/
make test-security         # gosec + govulncheck + npm audit = 0 HIGH/CRITICAL
```

Coverage report output: `AGENT_14_QA_GO/_summary.json` with per-layer numbers.

---

## Phase 5: Documentation (Agent 15)

**Agent:** Agent 15 (Trainer), model: sonnet

### 5.1 User Guide — пошаговая инструкция для менеджера
### 5.2 Admin Guide — настройка, роли, интеграции
### 5.3 Quick Start — 5 минут до первого результата
### 5.4 FAQ — из граничных случаев ФМ
### 5.5 API Documentation — OpenAPI → Swagger UI / Redoc
### 5.6 Release Notes v1.0
### 5.7 Ops Runbook — что делать при инцидентах (Kafka lag, ELMA down, AI cost spike)
### 5.8 AI Model Decision Guide — когда Sonnet, когда Opus, как обновлять

**Phase 5 Verification:**
- Each document reviewed for: completeness, no AI traces, business language
- `grep -E 'Agent|ИИ| AI |Claude' *.md` — 0 matches in published docs

---

## Phase 6: Deploy & Release (Agent 16 + Agent 7)

### 6A. Repository & CI/CD (3 tasks)
#### 6.1 Create profitability-service GitHub repo
#### 6.2 Push all code from Phase 3
#### 6.3 CI/CD: GitHub Actions (lint → test-security → test → build → docker push)

### 6B. Data Migration (3 tasks)
#### 6.4 Initial data seed plan
- Export from 1С:УТ: clients, products, НПСС, exchange rates, employees, BUs → CSV/JSON
- Seed script: `scripts/seed-mdm.sh` → PostgreSQL temporal tables
- Validation: row counts match 1С, referential integrity checks
- **CRITICAL:** Must run BEFORE first Kafka event (MDM cold start)
#### 6.5 Run data migration on Dev (verify with test data)
#### 6.6 Run data migration on Staging (verify with anonymized real data)

### 6C. Backup & Disaster Recovery (3 tasks)
#### 6.7 Backup strategy
- PostgreSQL: pg_dump hourly (cron), WAL archiving to S3/MinIO, retention 30 days
- Kafka: topic data retained 7 days, consumer offsets in PG (not just __consumer_offsets)
- Redis: RDB snapshots every 15 min, AOF for critical data (rate limits, locks)
- Backup verification: weekly restore test to dev (automated)
#### 6.8 Disaster recovery plan
- RTO: ≤30 min (dev/staging), ≤15 min (prod)
- RPO: ≤5 min (DB), ≤0 (Kafka — replay from offset)
- Runbook: what to do when each service goes down
#### 6.9 Data retention policy
- Business data: 3 years (legal requirement)
- AI audit logs: 1 year
- Kafka events: 7 days (replay window)
- MDM audit trail: forever (append-only)
- Notification logs: 90 days

### 6D. Deploy (4 tasks)
#### 6.10 Deploy to Dev (docker compose up on homelab)
#### 6.11 Smoke test Dev environment
#### 6.12 Deploy to Staging (docker compose with staging overrides + tunnel)
#### 6.13 E2E + load tests on Staging

### 6E. Release (4 tasks)
#### 6.14 Agent 16: Quality Gate check (12 points)
#### 6.15 Deploy to Prod (inside corporate network, manual approval)
#### 6.16 Post-deploy monitoring (15 min, error rate <1%)
#### 6.17 Capacity planning document: expected load (50-70 users), resource sizing (CPU/RAM per service), scaling triggers

### 6F. Publish (2 tasks)
#### 6.18 Agent 7: Publish architecture + TZ to Confluence
#### 6.19 Agent 7: Publish release notes + docs to Confluence

**Phase 6 Verification:**
- All services healthy on all 3 environments
- Data migration verified (row counts, integrity)
- Backup/restore tested on dev
- E2E passes on staging
- Load test passes on staging
- Monitoring dashboards show green
- Confluence pages published and verified
- Capacity planning document reviewed

---

## Timeline (Gantt)

```
Week 1:   ████ Phase 0 (protocols, Agent 16, secrets)
Week 2:   ████████████████ Phase 1A-1B (domain model, services arch)
Week 3:   ████████████████ Phase 1C-1E (frontend, AI, integrations)
Week 3:   ████ Phase 1.5 (1С extension + SE review, parallel with 1C-1E)
Week 4:   ████████ Phase 2 (SE review + corrections)
Week 5:   ████████████████ Phase 3A-3C (scaffold, domain, usecases)
Week 6:   ████████████████ Phase 3D-3E (adapters, AI service)
Week 7:   ████████████████ Phase 3F-3H (React frontend, infra, cross-cutting)
Week 8:   ████████████████ Phase 4A-4D (unit, integration, contract tests)
Week 9:   ████████████████ Phase 4E-4K (E2E, load, visual, AI eval, security, mutation)
Week 9:   ████████ Phase 5 (documentation, parallel with 4E-4K)
Week 10:  ████████ Phase 6A-6C (repo, data migration, backup strategy)
Week 11:  ████████ Phase 6D-6F (deploy, release, publish)
```

**Total: ~11 weeks** (with parallel phases where possible)
**~195 tasks** (original 173 + 22 gap-fill tasks)

---

## Risk Assessment

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| R1 | ELMA API incompatible with Go client | HIGH | Mock first, test with real ELMA in staging |
| R2 | 1С:УТ 10.2 HTTP-сервис limitations | HIGH | Minimal extension, test on real 1С instance |
| R3 | Claude API costs exceed budget | MEDIUM | Prompt caching, cost ceiling, degradation to Level 1 |
| R4 | Kafka throughput insufficient | LOW | KRaft mode, franz-go (4x faster), load test early |
| R5 | AD auth complexity (Kerberos) | MEDIUM | Start with simple LDAP bind, add Kerberos later |
| R6 | Domain model doesn't match FM perfectly | HIGH | Agent 5 traces every rule to LS-BR-*, Agent 9 cross-checks |
| R7 | MDM cold start — no data before first Kafka event | HIGH | Bulk seed from 1С CSV export (task 6.4), validate before go-live |
| R8 | Outbox poller missed events after crash | MEDIUM | Outbox table in same DB transaction, poller idempotent, monitoring alert |
| R9 | Data migration from 1С incomplete/corrupted | HIGH | Row count + hash verification, dry-run on staging, rollback plan |
| R10 | Corporate network tunnel instability (staging/prod) | MEDIUM | Health checks, auto-reconnect, fallback to mock mode |
| R11 | gRPC contract breaking between services | MEDIUM | buf lint + buf breaking in CI, contract tests (Phase 4D) |
| R12 | AI prompt injection via user-facing chat | HIGH | Input sanitization, separate system/user prompts, no raw user text in tools |

---

## API Versioning Strategy

- All endpoints under `/api/v1/` prefix
- Breaking changes → new version (`/api/v2/`), old version supported for 6 months
- Non-breaking changes (new fields, new endpoints) → same version
- Kafka schemas: versioned suffix `*.v1`, `*.v2`. Consumer handles both during migration.
- gRPC: buf breaking checks in CI, deprecation annotations, 3-month sunset period
- OpenAPI spec versioned in git tags alongside service releases

---

## Critical Files

**New repository:** `/home/dev/projects/claude-agents/profitability-service/`
**FM review system updates:**
- `agents/AGENT_5_TECH_ARCHITECT.md` — update title + AI sections
- `agents/dev/AGENT_14_QA_GO.md` — add coverage targets 88% + k6 + visual regression + security testing
- `agents/dev/AGENT_16_RELEASE_ENGINEER.md` — NEW protocol
- `.claude/agents/agent-16-release-engineer.md` — NEW subagent
- `schemas/agent-contracts.json` — add Agent 16 schema
- `config/pipeline.json` — FIX Agent 12 dependency bug + add Go pipeline + Agent 16 + Agent 11→10 chain
- `.claude/rules/subagents-registry.md` — add Agent 16
- `CLAUDE.md` — add Agent 16 route
- `projects/PROJECT_SHPMNT_PROFIT/PROJECT_CONTEXT.md` — update status

**Memory:** `memory/profitability-service-decisions.md` — all decisions documented

---

## Gap Analysis (incorporated from SE review)

All gaps found by the review agent have been incorporated into the plan above:

**CRITICAL (6 → all resolved):**
1. ~~2FA/MFA~~ → Added as optional middleware in task 1.12 (env var toggle)
2. ~~Data migration plan~~ → Added Phase 6B (tasks 6.4-6.6)
3. ~~Pipeline config bug~~ → Fixed in task 0.6 (Agent 12 → Agent 9)
4. ~~Agent 14 coverage targets~~ → Updated in task 0.3 (70% → 88%)
5. ~~Secrets management~~ → Added task 0.8 (Infisical multi-project)
6. ~~Graceful shutdown~~ → Added in task 1.12 (spec) + task 3.45 (implementation)

**HIGH (8 → all resolved):**
1. ~~Outbox pattern~~ → Added in task 1.10 (spec) + task 3.49 (implementation)
2. ~~Security testing~~ → Added in task 0.3 (protocol) + Phase 4I (execution)
3. ~~SE review for 1С extension~~ → Added task 1.5.4 (Agent 10 review)
4. ~~Backup strategy~~ → Added task 6.7 (PG/Kafka/Redis backup)
5. ~~Mock implementations~~ → Added task 3.46 (all external systems)
6. ~~MDM cold start~~ → Added in task 1.10 (seed procedure) + task 6.4 (execution)
7. ~~Inter-service communication~~ → Added in task 1.12 (gRPC + Kafka pattern)
8. ~~Audit trail immutability~~ → Added in task 1.10 (append-only + hash chain)

**MEDIUM (incorporated inline):**
- Structured logging → task 3.43
- OpenTelemetry → task 3.44
- Grafana dashboards → task 3.47
- Error boundary pages → task 3.48
- Developer experience → task 3.50
- Redis/LDAP integration tests → tasks 4.10b-4.10c
- Data consistency tests → Phase 4J
- Disaster recovery → task 6.8
- Data retention policy → task 6.9
- Capacity planning → task 6.17
- API versioning → dedicated section above
