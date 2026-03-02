# Phase 1B: Go Microservices Architecture

**Проект:** FM-LS-PROFIT (Контроль рентабельности отгрузок по ЛС)
**Версия ФМ:** 1.0.7
**Дата:** 01.03.2026
**Автор:** Шаховский А.С.
**Платформа:** Go 1.22+ (Clean Architecture)
**Domain Model:** см. `phase1a_domain_model.md`

---

## Содержание

1. [Service Decomposition](#1-service-decomposition)
2. [profitability-service](#2-profitability-service)
3. [workflow-service](#3-workflow-service)
4. [analytics-service](#4-analytics-service)
5. [integration-service](#5-integration-service)
6. [notification-service](#6-notification-service)
7. [api-gateway](#7-api-gateway)
8. [Database Migrations](#8-database-migrations)
9. [Kafka Topic Catalog](#9-kafka-topic-catalog)
10. [Outbox Pattern](#10-outbox-pattern)
11. [Inter-Service Communication](#11-inter-service-communication)
12. [Graceful Shutdown](#12-graceful-shutdown)
13. [OpenAPI 3.0 Specification](#13-openapi-30-specification)

---

## 1. Service Decomposition

```
                        +-------------------+
                        |   api-gateway     |
                        | (auth, RBAC,      |
                        |  rate limiting)   |
                        +---------+---------+
                                  |
                    +-------------+-------------+
                    |             |             |
           +-------v-------+ +--v----------+ +v--------------+
           | profitability  | | workflow    | | analytics     |
           | service        | | service     | | service       |
           | (calc, LS,     | | (approval,  | | (anomaly,     |
           |  shipments)    | |  SLA, ELMA) | |  AI, reports) |
           +-------+-------+ +------+------+ +-------+-------+
                   |                |                 |
                   +--------+-------+---------+-------+
                            |                 |
                   +--------v-------+ +-------v--------+
                   | integration    | | notification   |
                   | service        | | service        |
                   | (Kafka, MDM,   | | (Telegram,     |
                   |  outbox, 1C)   | |  Email, 1C)    |
                   +----------------+ +----------------+
```

**Протоколы связи:**
- Frontend -> api-gateway: REST (HTTPS)
- api-gateway -> services: gRPC (connect-go, protobuf)
- services -> services (async): Kafka events (franz-go)
- services -> integration-service (sync read): gRPC
- services -> DB: PostgreSQL (sqlc)
- services -> cache: Redis

**Стек каждого сервиса:**

| Компонент | Технология |
|-----------|-----------|
| HTTP router | chi v5 |
| gRPC | connect-go (buf) |
| DB queries | sqlc |
| Kafka | franz-go |
| DI | Wire |
| Config | envconfig |
| Logging | slog (structured) |
| Metrics | prometheus/client_golang |
| Tracing | OpenTelemetry |

---

## 2. profitability-service

**Bounded Context:** Profitability
**Aggregates:** LocalEstimate, Shipment, ProfitabilityCalculation, PriceSheet (см. phase1a_domain_model.md, секции 2.1, 2.2, 2.4, 2.7)
**Domain Services:** ProfitabilityCalculator, ThresholdEvaluator, CrossValidator (секции 5.1, 5.5, 5.6)
**Business Rules:** BR-001..006, BR-050..056, BR-060..063, BR-070..071, LS-BR-035, LS-BR-075/075b (секция 6)

### 2.1. REST Endpoints

| Method | Path | Description | Auth Role | Request | Response |
|--------|------|-------------|-----------|---------|----------|
| POST | /api/v1/shipments/{id}/calculate | Рассчитать рентабельность заказа | manager, rbu | - | `CalculationResult` |
| GET | /api/v1/shipments/{id}/profitability | Получить расчет рентабельности | manager, rbu, dp, gd, fd | - | `ProfitabilityView` |
| GET | /api/v1/local-estimates/{id}/summary | Сводка рентабельности по ЛС | manager, rbu, dp, gd, fd | query: `include_items=bool` | `LSSummary` |
| GET | /api/v1/local-estimates/{id}/shipments | Список заказов по ЛС | manager, rbu | query: `status`, `page`, `per_page` | `[]ShipmentView` |
| GET | /api/v1/local-estimates/{id}/remainder | Рентабельность остатка ЛС | manager, rbu | - | `RemainderView` |
| GET | /api/v1/shipments/{id} | Детали заказа | manager, rbu, dp, gd, fd | - | `ShipmentDetail` |
| GET | /api/v1/dashboard/manager | Панель менеджера: ЛС и заказы | manager | query: `date_from`, `date_to` | `ManagerDashboard` |
| GET | /api/v1/price-sheets/{product_id} | Текущая НПСС по товару | manager, rbu, fd | query: `date` | `PriceSheetView` |
| GET | /api/v1/price-sheets/stale | Список устаревших НПСС | fd | query: `older_than_days` | `[]PriceSheetView` |

### 2.2. gRPC Services (internal)

```protobuf
// api/proto/profitability/v1/profitability.proto

syntax = "proto3";
package profitability.v1;

service ProfitabilityService {
  // Вызывается workflow-service при создании заявки на согласование
  rpc GetCalculation(GetCalculationRequest) returns (CalculationResponse);
  // Вызывается workflow-service при cross-validation
  rpc RecalculateForPlanChange(RecalculateRequest) returns (RecalculateResponse);
  // Вызывается analytics-service для получения данных
  rpc GetShipmentHistory(ShipmentHistoryRequest) returns (ShipmentHistoryResponse);
  // Вызывается analytics-service для what-if сценариев
  rpc CalculateWhatIf(WhatIfRequest) returns (WhatIfResponse);
}

message GetCalculationRequest {
  string shipment_id = 1; // UUID
}

message CalculationResponse {
  string calculation_id = 1;
  string shipment_id = 2;
  string local_estimate_id = 3;
  double planned_profitability = 4;
  double order_profitability = 5;
  double cumulative_plus_order = 6;
  double remainder_profitability = 7;
  double deviation = 8;
  string required_level = 9; // auto/rbu/dp/gd
}

message RecalculateRequest {
  string local_estimate_id = 1;
  double old_plan = 2;
  double new_plan = 3;
}

message RecalculateResponse {
  repeated CrossValidationResult results = 1;
}

message CrossValidationResult {
  string shipment_id = 1;
  string old_level = 2;
  string new_level = 3;
  double new_deviation = 4;
  bool requires_reapproval = 5;
}

message ShipmentHistoryRequest {
  string local_estimate_id = 1;
  int32 limit = 2;
  string status_filter = 3; // optional
}

message ShipmentHistoryResponse {
  repeated ShipmentSummary shipments = 1;
}

message ShipmentSummary {
  string id = 1;
  string external_id = 2;
  double order_profitability = 3;
  double deviation = 4;
  string status = 5;
  string created_at = 6; // RFC 3339
}

message WhatIfRequest {
  string local_estimate_id = 1;
  repeated WhatIfLineItem items = 2;
}

message WhatIfLineItem {
  string product_id = 1;
  double quantity = 2;
  double price = 3;
}

message WhatIfResponse {
  double order_profitability = 1;
  double cumulative_plus_order = 2;
  double remainder_profitability = 3;
  double deviation = 4;
  string required_level = 5;
}
```

### 2.3. DB Schema

```sql
-- migrations/profitability/001_initial.up.sql

-- Локальные сметы
CREATE TABLE local_estimates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(11) NOT NULL UNIQUE,
    client_id UUID NOT NULL,
    manager_id UUID NOT NULL,
    business_unit_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','expired','closed','cancelled')),
    planned_profitability BIGINT NOT NULL, -- basis points (сотые доли %)
    total_amount BIGINT NOT NULL, -- копейки
    renewal_count INT NOT NULL DEFAULT 0 CHECK (renewal_count <= 2),
    npss_fixed_at TIMESTAMPTZ NOT NULL,
    advisory_control BOOLEAN NOT NULL DEFAULT false,
    version INT NOT NULL DEFAULT 1,
    created_at_db TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_local_estimates_client ON local_estimates(client_id);
CREATE INDEX idx_local_estimates_manager ON local_estimates(manager_id);
CREATE INDEX idx_local_estimates_status ON local_estimates(status);
CREATE INDEX idx_local_estimates_expires ON local_estimates(expires_at) WHERE status = 'active';
CREATE INDEX idx_local_estimates_external ON local_estimates(external_id);

-- Позиции ЛС
CREATE TABLE local_estimate_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    local_estimate_id UUID NOT NULL REFERENCES local_estimates(id),
    product_id UUID NOT NULL,
    quantity NUMERIC(18,6) NOT NULL CHECK (quantity > 0), -- shopspring/decimal, 6 знаков дробной части
    price BIGINT NOT NULL, -- копейки
    amount BIGINT NOT NULL, -- копейки
    npss BIGINT NOT NULL, -- копейки (зафиксированная НПСС)
    profitability BIGINT NOT NULL, -- basis points
    min_allowed_price BIGINT NOT NULL, -- копейки
    business_unit_id UUID NOT NULL
);

CREATE INDEX idx_le_line_items_le ON local_estimate_line_items(local_estimate_id);
CREATE INDEX idx_le_line_items_product ON local_estimate_line_items(product_id);

-- Заказы клиентов (отгрузки)
CREATE TABLE shipments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(30) NOT NULL UNIQUE,
    local_estimate_id UUID NOT NULL REFERENCES local_estimates(id),
    client_id UUID NOT NULL,
    manager_id UUID NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'draft'
        CHECK (status IN (
            'draft','awaiting_stock','pending_approval','rejected',
            'approval_expired','partially_approved','approved',
            'in_progress','fulfilled','partially_closed','overdue','cancelled'
        )),
    priority VARCHAR(5) NOT NULL DEFAULT 'P2' CHECK (priority IN ('P1','P2')),
    source VARCHAR(10) NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','edi')),

    -- Расчетные показатели
    order_profitability BIGINT, -- basis points
    cumulative_plus_order BIGINT, -- basis points
    remainder_profitability BIGINT, -- basis points
    deviation BIGINT, -- basis points
    required_approval_level VARCHAR(10),

    -- Согласование
    approval_type VARCHAR(15),
    approver_name VARCHAR(255),
    approved_at TIMESTAMPTZ,
    approval_expires_at TIMESTAMPTZ,
    approval_decision VARCHAR(30),
    approver_comment TEXT,
    justification TEXT,

    -- Контроль
    handed_to_warehouse BOOLEAN NOT NULL DEFAULT false,
    handed_to_warehouse_at TIMESTAMPTZ,
    cancellation_count INT NOT NULL DEFAULT 0,
    correction_iteration INT NOT NULL DEFAULT 0 CHECK (correction_iteration <= 5),
    draft_created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_shipments_le ON shipments(local_estimate_id);
CREATE INDEX idx_shipments_client ON shipments(client_id);
CREATE INDEX idx_shipments_manager ON shipments(manager_id);
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_draft_expiry ON shipments(draft_created_at)
    WHERE status = 'draft';
CREATE INDEX idx_shipments_approval_expiry ON shipments(approval_expires_at)
    WHERE status = 'approved' AND handed_to_warehouse = false;

-- Позиции заказа
CREATE TABLE shipment_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID NOT NULL REFERENCES shipments(id),
    product_id UUID NOT NULL,
    quantity NUMERIC(18,6) NOT NULL CHECK (quantity > 0), -- shopspring/decimal, 6 знаков дробной части
    price BIGINT NOT NULL, -- копейки
    amount BIGINT NOT NULL, -- копейки
    npss BIGINT NOT NULL, -- копейки (из ЛС)
    profitability BIGINT NOT NULL, -- basis points
    min_allowed_price BIGINT NOT NULL, -- копейки
    business_unit_id UUID NOT NULL,
    is_non_liquid BOOLEAN NOT NULL DEFAULT false,
    price_deviation_pct BIGINT NOT NULL DEFAULT 0 -- basis points
);

CREATE INDEX idx_sh_line_items_shipment ON shipment_line_items(shipment_id);
CREATE INDEX idx_sh_line_items_product ON shipment_line_items(product_id);

-- Расчеты рентабельности (снимки)
CREATE TABLE profitability_calculations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    local_estimate_id UUID NOT NULL REFERENCES local_estimates(id),
    shipment_id UUID NOT NULL REFERENCES shipments(id),
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    planned_profitability BIGINT NOT NULL, -- basis points
    order_profitability BIGINT NOT NULL,
    cumulative_profitability BIGINT NOT NULL,
    cumulative_plus_order BIGINT NOT NULL,
    remainder_profitability BIGINT NOT NULL,
    deviation BIGINT NOT NULL,

    -- Компоненты
    shipped_revenue BIGINT NOT NULL, -- копейки
    shipped_cost_npss BIGINT NOT NULL,
    order_revenue BIGINT NOT NULL,
    order_cost_npss BIGINT NOT NULL,
    remainder_revenue BIGINT NOT NULL,
    remainder_cost_npss BIGINT NOT NULL,

    version INT NOT NULL DEFAULT 1
);

CREATE INDEX idx_calculations_shipment ON profitability_calculations(shipment_id);
CREATE INDEX idx_calculations_le ON profitability_calculations(local_estimate_id);
CREATE INDEX idx_calculations_time ON profitability_calculations(calculated_at);

-- Детализация расчета по позициям
CREATE TABLE calculation_line_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calculation_id UUID NOT NULL REFERENCES profitability_calculations(id),
    product_id UUID NOT NULL,
    quantity NUMERIC(18,6) NOT NULL, -- shopspring/decimal, 6 знаков дробной части
    price BIGINT NOT NULL,
    npss BIGINT NOT NULL,
    profitability BIGINT NOT NULL,
    is_blocked BOOLEAN NOT NULL DEFAULT false,
    block_reason VARCHAR(100)
);

CREATE INDEX idx_calc_items_calc ON calculation_line_items(calculation_id);

-- Шкалы НПСС (локальная копия, source of truth в integration-service MDM)
CREATE TABLE price_sheet_cache (
    product_id UUID NOT NULL,
    npss BIGINT NOT NULL, -- копейки
    calculated_at TIMESTAMPTZ NOT NULL,
    method VARCHAR(20) NOT NULL CHECK (method IN ('planned','temporary')),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (product_id, valid_from)
);

CREATE INDEX idx_price_cache_product ON price_sheet_cache(product_id, valid_from DESC);

-- Агрегированные лимиты автосогласования (дневные счетчики)
CREATE TABLE auto_approval_counters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(10) NOT NULL CHECK (entity_type IN ('manager','bu')),
    entity_id UUID NOT NULL,
    counter_date DATE NOT NULL,
    total_amount BIGINT NOT NULL DEFAULT 0, -- копейки
    approval_count INT NOT NULL DEFAULT 0,
    UNIQUE(entity_type, entity_id, counter_date)
);

CREATE INDEX idx_auto_counters_lookup
    ON auto_approval_counters(entity_type, entity_id, counter_date);

-- Outbox для domain events
CREATE TABLE profitability_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    kafka_topic VARCHAR(200) NOT NULL,
    kafka_key VARCHAR(100) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE INDEX idx_profitability_outbox_unpublished
    ON profitability_outbox(created_at)
    WHERE published_at IS NULL;
```

### 2.4. Business Logic (ссылки на Domain Model)

**Расчет рентабельности (BR-001..006):**
- Формулы реализованы в `ProfitabilityCalculator` (phase1a, секция 5.1)
- Рентабельность позиции: `(price - npss) / price * 100%` -- INV-PC-01
- (Накопленная + Заказ): `(shipped_rev + order_rev - shipped_cost - order_cost) / (shipped_rev + order_rev) * 100%` -- INV-PC-02
- Остаток: исключает заказы в статусах `pending_approval` и `approved` -- INV-PC-03
- Отклонение: `plan - MAX(cumulative_plus_order, remainder)`, округление до 2 знаков ДО сравнения -- INV-PC-04
- НПСС=0 или Цена=0 блокирует позицию -- INV-PC-05, INV-PC-06

**Кэш НПСС в Redis:**
- Key: `npss:{product_id}`
- TTL: 1 час
- Invalidation: при получении события `PriceSheetUpdated` из Kafka
- Fallback: запрос в integration-service через gRPC при cache miss

**Агрегированные лимиты (BR-011, BR-012):**
- Менеджер: 20 000 руб/день -- таблица `auto_approval_counters` (entity_type='manager')
- БЮ: 100 000 руб/день -- таблица `auto_approval_counters` (entity_type='bu')
- Проверка: `ThresholdEvaluator.CheckManagerLimit/CheckBULimit` (phase1a, секция 5.5)

### 2.5. Dependencies

| Зависимость | Протокол | Назначение |
|-------------|----------|------------|
| integration-service | gRPC | Чтение НПСС, клиентов, курсов |
| Redis | TCP | Кэш НПСС |
| Kafka (producer) | TCP | Публикация domain events через outbox |
| PostgreSQL | TCP | Хранение данных (profitability) |

---

## 3. workflow-service

**Bounded Context:** Workflow
**Aggregates:** ApprovalProcess, EmergencyApproval (phase1a, секции 2.3, 2.8)
**Domain Services:** ApprovalRouter, SLATracker (секции 5.2, 5.3)
**Business Rules:** BR-010..021, BR-030..035, BR-040..043 (секция 6)

### 3.1. REST Endpoints

| Method | Path | Description | Auth Role | Request | Response |
|--------|------|-------------|-----------|---------|----------|
| POST | /api/v1/approvals | Создать заявку на согласование | manager | `CreateApprovalRequest` | `ApprovalProcess` |
| GET | /api/v1/approvals/{id} | Детали согласования | manager, rbu, dp, gd, fd | - | `ApprovalProcessView` |
| POST | /api/v1/approvals/{id}/decide | Принять решение | rbu, dp, gd | `DecisionRequest` | `ApprovalProcess` |
| POST | /api/v1/approvals/{id}/correct | Предложить корректировку цены | manager | `CorrectionRequest` | `ApprovalProcess` |
| GET | /api/v1/approvals/queue | Очередь согласующего | rbu, dp, gd | query: `priority`, `level` | `[]ApprovalQueueItem` |
| GET | /api/v1/approvals/queue/count | Количество задач в очереди | rbu, dp, gd | - | `QueueCount` |
| POST | /api/v1/emergency-approvals | Зафиксировать экстренное | manager | `EmergencyRequest` | `EmergencyApproval` |
| POST | /api/v1/emergency-approvals/{id}/confirm | Подтвердить постфактум | rbu, dp, gd | `ConfirmRequest` | `EmergencyApproval` |
| GET | /api/v1/approvals/sla/{id} | Оставшееся время SLA | manager, rbu, dp, gd | - | `SLAStatus` |
| GET | /api/v1/approvals/aggregate-limits | Текущие лимиты менеджера | manager | query: `date` | `AggregateLimits` |
| GET | /api/v1/approvals/workload/{approver_id} | Нагрузка согласующего | rbu, dp, gd, fd | - | `WorkloadMetrics` |
| GET | /api/v1/fallback/status | Статус резервного режима ELMA | fd | - | `FallbackStatus` |
| GET | /api/v1/fallback/queue | Очередь резервного режима | fd | - | `[]FallbackQueueItem` |

### 3.2. gRPC Services (internal)

```protobuf
// api/proto/workflow/v1/workflow.proto

syntax = "proto3";
package workflow.v1;

service WorkflowService {
  // Вызывается profitability-service при ThresholdViolated
  rpc CreateApprovalProcess(CreateApprovalRequest) returns (ApprovalProcessResponse);
  // Вызывается integration-service при ELMA callback
  rpc HandleELMACallback(ELMACallbackRequest) returns (ELMACallbackResponse);
  // Вызывается analytics-service для данных согласований
  rpc GetApprovalHistory(ApprovalHistoryRequest) returns (ApprovalHistoryResponse);
}

message CreateApprovalRequest {
  string shipment_id = 1;
  string local_estimate_id = 2;
  string initiator_id = 3;
  double deviation = 4;
  string priority = 5; // P1/P2
  bool is_small_order = 6; // < 100 т.р.
}

message ApprovalProcessResponse {
  string process_id = 1;
  string required_level = 2;
  string mode = 3; // standard/fallback
  int32 sla_hours = 4;
  string sla_deadline = 5; // RFC 3339
}

message ELMACallbackRequest {
  string elma_task_id = 1;
  string decision = 2;
  string approver_id = 3;
  string comment = 4;
}

message ELMACallbackResponse {
  bool success = 1;
}

message ApprovalHistoryRequest {
  string shipment_id = 1;
}

message ApprovalHistoryResponse {
  repeated ApprovalHistoryItem items = 1;
}

message ApprovalHistoryItem {
  string process_id = 1;
  string level = 2;
  string decision = 3;
  string approver_name = 4;
  int32 sla_hours = 5;
  int32 actual_hours = 6;
  bool sla_breached = 7;
  string decided_at = 8;
}
```

### 3.3. State Machine

```
                        +------------------+
                        |     PENDING      |
                        +--------+---------+
                                 |
                  +--------------+--------------+
                  |                             |
         deviation < 1pp                deviation >= 1pp
         AND limits OK                         |
                  |                    +-------v--------+
                  v                    |    ROUTING     |
         +--------+--------+          | (find approver)|
         |  AUTO_APPROVED   |          +-------+--------+
         +-----------------+                   |
                                      +--------v--------+
                                      | LEVEL_1 (RBU)   |
                                      +--+-----+-----+--+
                                         |     |     |
                                   approve reject correct
                                         |     |     |
                                         |     |     v
                                         |     | correction_iteration < 5?
                                         |     |   yes: -> ROUTING (back)
                                         |     |   no:  -> REJECTED
                                         |     |
                                         |     v
                                         | +---+--------+
                                         | | REJECTED   |
                                         | +------------+
                                         v
                                  +------+-------+
                                  | LEVEL_2 (DP) | (via escalation or direct)
                                  +--+-----+-----+
                                     |     |
                               approve  reject
                                     |     |
                                     v     v
                              +------+  REJECTED
                              |
                       +------v-------+
                       | LEVEL_3 (GD) | (via escalation or direct)
                       +--+-----+-----+
                          |     |
                    approve  SLA timeout (48h)
                          |     |
                          v     v
                    APPROVED  +--+----------+
                              | EXPIRED     |
                              | (auto-reject|
                              |  +CFO notify|
                              +-------------+

  Fallback (ELMA down):
    deviation <= 5pp -> FALLBACK_AUTO_APPROVED
    deviation > 5pp  -> FALLBACK_QUEUED -> (ELMA up) -> ROUTING
```

**Переходы состояний:**

| Из | В | Условие | Действие |
|----|---|---------|----------|
| PENDING | AUTO_APPROVED | deviation < 1.00 п.п. AND manager limit <= 20K AND BU limit <= 100K | Обновить shipment, emit ApprovalAutoApproved |
| PENDING | ROUTING | deviation >= 1.00 п.п. OR limits exceeded | Определить уровень по матрице |
| ROUTING | LEVEL_1 | deviation 1.00-15.00 п.п. | Найти РБЮ, создать задачу ELMA |
| ROUTING | LEVEL_2 | deviation 15.01-25.00 п.п. | Найти ДП, создать задачу ELMA |
| ROUTING | LEVEL_3 | deviation > 25.00 п.п. | Найти ГД, создать задачу ELMA |
| LEVEL_1 | APPROVED | РБЮ одобрил | Emit ApprovalDecisionMade |
| LEVEL_1 | REJECTED | РБЮ отклонил | Emit ApprovalDecisionMade |
| LEVEL_1 | ROUTING | Корректировка цены (iteration < 5) | Increment iteration, вернуть менеджеру |
| LEVEL_1 | REJECTED | Корректировка (iteration >= 5) | Emit ApprovalCorrectionLimitReached |
| LEVEL_1 | LEVEL_2 | SLA breach -> escalation to Дир. ДРП -> ДП | Emit ApprovalEscalated |
| LEVEL_2 | APPROVED | ДП одобрил | Emit ApprovalDecisionMade |
| LEVEL_2 | LEVEL_3 | SLA breach -> escalation | Emit ApprovalEscalated |
| LEVEL_3 | APPROVED | ГД одобрил | Emit ApprovalDecisionMade |
| LEVEL_3 | EXPIRED | SLA timeout 48h | Emit ApprovalAutoRejected, notify CFO |
| PENDING | FALLBACK_AUTO_APPROVED | ELMA down AND deviation <= 5.00 п.п. | Emit ApprovalFallbackActivated |
| PENDING | FALLBACK_QUEUED | ELMA down AND deviation > 5.00 п.п. | Enqueue FIFO (P1 first) |
| FALLBACK_QUEUED | ROUTING | ELMA restored | Drain queue, emit ApprovalFallbackQueueDrained |

### 3.4. ELMA Integration

**Circuit Breaker:**
- Threshold: 5 consecutive failures
- Open state: 30 seconds
- Half-open: 1 test request
- Recovery: automatic on success

**Endpoints consumed:**
- `POST /api/bpm/tasks` -- создать задачу согласования
- `GET /api/bpm/tasks/{id}` -- статус задачи
- `POST /api/bpm/tasks/{id}/complete` -- завершить задачу

**Fallback mode (BR-040..043):**
- Activation: circuit breaker OPEN
- deviation <= 5.00 п.п.: автосогласование с пометкой `mode=fallback`
- deviation > 5.00 п.п.: очередь `ОчередьРезервногоРежима` (FIFO, P1 first)
- Recovery: drain queue into ELMA, notify approvers about fallback-approved items
- Health check: every 5 minutes via `GET /api/health`

### 3.5. DB Schema

```sql
-- migrations/workflow/001_initial.up.sql

-- Процессы согласования
CREATE TABLE approval_processes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID NOT NULL,
    local_estimate_id UUID NOT NULL,
    initiator_id UUID NOT NULL,
    deviation BIGINT NOT NULL, -- basis points
    required_level VARCHAR(10) NOT NULL
        CHECK (required_level IN ('auto','rbu','drp','dp','gd')),
    priority VARCHAR(5) NOT NULL CHECK (priority IN ('P1','P2')),
    current_approver_id UUID,
    decision VARCHAR(30),
    approver_comment TEXT,
    is_resubmission BOOLEAN NOT NULL DEFAULT false,
    attempt_number INT NOT NULL DEFAULT 1,
    mode VARCHAR(15) NOT NULL DEFAULT 'standard'
        CHECK (mode IN ('standard','fallback')),
    cross_validation_reason TEXT,
    correction_iteration INT NOT NULL DEFAULT 0 CHECK (correction_iteration <= 5),

    -- State machine
    state VARCHAR(30) NOT NULL DEFAULT 'pending'
        CHECK (state IN (
            'pending','auto_approved','routing',
            'level_1','level_2','level_3',
            'approved','rejected','expired',
            'fallback_auto_approved','fallback_queued'
        )),

    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    version INT NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_approvals_shipment ON approval_processes(shipment_id);
CREATE INDEX idx_approvals_approver ON approval_processes(current_approver_id)
    WHERE state IN ('level_1','level_2','level_3');
CREATE INDEX idx_approvals_state ON approval_processes(state);
CREATE INDEX idx_approvals_initiator ON approval_processes(initiator_id);

-- Согласования мульти-БЮ
CREATE TABLE bu_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id UUID NOT NULL REFERENCES approval_processes(id),
    business_unit_id UUID NOT NULL,
    approver_id UUID NOT NULL,
    decision VARCHAR(30),
    decided_at TIMESTAMPTZ,
    comment TEXT,
    UNIQUE(process_id, business_unit_id)
);

CREATE INDEX idx_bu_approvals_process ON bu_approvals(process_id);

-- История маршрутизации
CREATE TABLE routing_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id UUID NOT NULL REFERENCES approval_processes(id),
    step_number INT NOT NULL,
    approver_id UUID NOT NULL,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at TIMESTAMPTZ,
    decision VARCHAR(30),
    sla_breached BOOLEAN NOT NULL DEFAULT false,
    comment TEXT
);

CREATE INDEX idx_routing_history_process ON routing_history(process_id);

-- SLA tracking
CREATE TABLE sla_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id UUID NOT NULL REFERENCES approval_processes(id),
    level VARCHAR(10) NOT NULL,
    priority VARCHAR(5) NOT NULL,
    sla_hours INT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    deadline TIMESTAMPTZ NOT NULL,
    escalation_threshold TIMESTAMPTZ NOT NULL, -- 80% of SLA
    notification_threshold TIMESTAMPTZ NOT NULL, -- 50% of SLA
    resolved_at TIMESTAMPTZ,
    breached BOOLEAN NOT NULL DEFAULT false,
    breached_at TIMESTAMPTZ,
    UNIQUE(process_id, level)
);

CREATE INDEX idx_sla_deadline ON sla_tracking(deadline)
    WHERE resolved_at IS NULL;
CREATE INDEX idx_sla_escalation ON sla_tracking(escalation_threshold)
    WHERE resolved_at IS NULL;

-- Очередь резервного режима ELMA
CREATE TABLE fallback_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id UUID NOT NULL REFERENCES approval_processes(id),
    priority VARCHAR(5) NOT NULL,
    deviation BIGINT NOT NULL,
    enqueued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_to_elma_at TIMESTAMPTZ,
    position INT NOT NULL -- FIFO order within priority
);

CREATE INDEX idx_fallback_queue_pending ON fallback_queue(priority, position)
    WHERE sent_to_elma_at IS NULL;

-- Экстренные согласования
CREATE TABLE emergency_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID NOT NULL,
    manager_id UUID NOT NULL,
    authorized_person_id UUID NOT NULL,
    reason TEXT NOT NULL,
    documentary_proof TEXT,
    communication_channel VARCHAR(20) NOT NULL
        CHECK (communication_channel IN ('phone','messenger','in_person')),
    obtained_at TIMESTAMPTZ NOT NULL,
    post_factum_confirmed BOOLEAN NOT NULL DEFAULT false,
    post_factum_confirmed_at TIMESTAMPTZ,
    confirmation_status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (confirmation_status IN ('pending','approved','rejected')),
    check_24h BOOLEAN NOT NULL DEFAULT false,
    check_48h BOOLEAN NOT NULL DEFAULT false,
    incident_registered BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_emergency_manager ON emergency_approvals(manager_id, created_at);
CREATE INDEX idx_emergency_pending ON emergency_approvals(confirmation_status)
    WHERE confirmation_status = 'pending';

-- Outbox
CREATE TABLE workflow_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    kafka_topic VARCHAR(200) NOT NULL,
    kafka_key VARCHAR(100) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE INDEX idx_workflow_outbox_unpublished
    ON workflow_outbox(created_at)
    WHERE published_at IS NULL;
```

### 3.6. SLA Matrix (from FM)

| Level | SLA P1 | SLA P2 | SLA <100K |
|-------|--------|--------|-----------|
| RBU | 4h | 24h | 2h |
| DP | 8h | 48h | 4h |
| GD | 24h | 72h | 12h |

**SLA Timer logic:**
- Check every 15 minutes (09:00-18:00 MSK, business hours only)
- At 50% SLA: notification to approver
- At 80% SLA: escalation warning
- At 100% SLA: auto-escalation to next level
- GD timeout (48h): auto-reject + CFO notification

### 3.7. Dependencies

| Зависимость | Протокол | Назначение |
|-------------|----------|------------|
| profitability-service | gRPC | Получение расчета, cross-validation |
| integration-service | gRPC | Данные о клиентах, сотрудниках |
| ELMA BPM | REST (circuit breaker) | Создание/завершение задач согласования |
| Kafka (producer) | TCP | Domain events, commands к 1С |
| PostgreSQL | TCP | Хранение данных (workflow) |

---

## 4. analytics-service

**Bounded Context:** Analytics
**Aggregates:** Anomaly, Investigation (phase1a, секция 8)
**Domain Services:** AnomalyDetector, AIAnalyst, AIInvestigator (секции 8.3, 8.4, 8.5)
**Guardrails:** секция 8.6

### 4.1. REST Endpoints

| Method | Path | Description | Auth Role | Request | Response |
|--------|------|-------------|-----------|---------|----------|
| GET | /api/v1/anomalies | Список аномалий | rbu, dp, gd, fd | query: `level`, `status`, `date_from`, `date_to`, `page`, `per_page` | `[]AnomalyView` |
| GET | /api/v1/anomalies/{id} | Детали аномалии | rbu, dp, gd, fd | - | `AnomalyDetail` |
| GET | /api/v1/anomalies/{id}/investigation | Результат расследования | dp, gd, fd | - | `InvestigationView` |
| POST | /api/v1/anomalies/{id}/resolve | Отметить как решенную / false positive | dp, gd, fd | `ResolveRequest` | `AnomalyView` |
| GET | /api/v1/forecasts/profitability | Прогноз рентабельности (ARIMA) | fd | query: `entity_type`, `entity_id`, `horizon_days` | `ForecastView` |
| GET | /api/v1/reports/daily-efficiency | Дашборд эффективности (LS-RPT-070) | fd | query: `date` | `DailyEfficiencyReport` |
| GET | /api/v1/reports/npss-age | Возраст НПСС (LS-RPT-071) | fd | query: `threshold_days` | `NPSSAgeReport` |
| GET | /api/v1/reports/baseline-kpi | Базовый замер KPI (LS-RPT-073) | fd | - | `BaselineKPIReport` |
| GET | /api/v1/reports/pilot-progress | Промежуточный отчет пилота (LS-RPT-074) | fd | - | `PilotProgressReport` |
| GET | /api/v1/reports/low-fulfillment | Клиенты с низким выкупом (LS-RPT-068) | dp, gd, fd | query: `threshold_pct` | `[]LowFulfillmentClient` |
| POST | /api/v1/ai/ask | Вопрос аналитика к AI | dp, gd, fd | `AskRequest` | `AskResponse` |
| GET | /api/v1/ai/costs | Стоимость AI-аналитики | fd | query: `date_from`, `date_to` | `AICostReport` |
| GET | /api/v1/kpi/manager/{id} | KPI менеджера | rbu, dp, gd, fd | query: `period` | `ManagerKPIView` |
| GET | /api/v1/kpi/approver/{id}/workload | Нагрузка согласующего (пороги 30/50) | rbu, dp, gd, fd | - | `ApproverWorkloadView` |

### 4.2. gRPC Services (internal)

```protobuf
// api/proto/analytics/v1/analytics.proto

syntax = "proto3";
package analytics.v1;

service AnalyticsService {
  // Вызывается profitability-service при расчете (Level 1 check)
  rpc CheckAnomaly(CheckAnomalyRequest) returns (CheckAnomalyResponse);
  // Вызывается notification-service для описания аномалии
  rpc GetAnomalySummary(AnomalySummaryRequest) returns (AnomalySummaryResponse);
}

message CheckAnomalyRequest {
  string shipment_id = 1;
  string local_estimate_id = 2;
  double deviation = 3;
  double order_profitability = 4;
  string client_id = 5;
  string manager_id = 6;
}

message CheckAnomalyResponse {
  bool is_anomaly = 1;
  double z_score = 2;
  string level = 3; // "1", "2", "3"
  string anomaly_id = 4; // UUID, empty if not anomaly
}

message AnomalySummaryRequest {
  string anomaly_id = 1;
}

message AnomalySummaryResponse {
  string description = 1;
  double confidence = 2;
  repeated string recommendations = 3;
  string investigation_status = 4;
}
```

### 4.3. Three-Level AI Architecture

**Level 1 -- Deterministic (gonum/stat):**
- Z-score anomaly detection: window 90 days, threshold +/- 2 sigma
- ARIMA forecast: 30-day horizon (gonum)
- Threshold rules engine: margin drop > 5 п.п. in 7 days, volume anomaly > 3x avg, client deviation from historical pattern
- Cost: $0/request
- Latency: < 100ms

**Level 2 -- LLM Interpretation (Sonnet 4.6):**
- Triggered when Level 1 detects anomaly
- System prompt: FM context (~20K tokens), cached (90% discount on input tokens)
- User prompt: anomaly data, recent shipments, client history, price changes
- Output: structured JSON (explanation, confidence 0.0-1.0, recommendations, requires_level_3)
- If confidence < 0.7: escalate to Level 3
- Cost: ~$0.003/request
- Timeout: 15s
- Rate limit: 200 req/hour

**Level 3 -- Agentic Investigation (Opus 4.6):**
- Triggered when Level 2 confidence < 0.7
- Orchestration loop: max 10 iterations, 60s timeout
- Tools available:

| Tool | Description | Input | Output |
|------|-------------|-------|--------|
| `query_shipments` | Получить заказы по ЛС/клиенту/менеджеру | `{local_estimate_id, client_id, date_from, date_to}` | `[]ShipmentSummary` |
| `query_client_history` | История клиента (объемы, частота, маржа) | `{client_id, months}` | `ClientHistorySummary` |
| `query_price_changes` | Изменения цен/НПСС | `{product_id, date_from}` | `[]PriceChange` |
| `calculate_what_if` | Сценарий "что если" | `{ls_id, items}` | `WhatIfResult` |
| `get_approval_history` | История согласований | `{shipment_id}` | `[]ApprovalRecord` |

- Cost: ~$0.05/request
- Timeout: 60s
- Rate limit: 50 req/hour

**Model configuration (environment variables):**
```
AI_MODEL_ANALYST=claude-sonnet-4-6-20250514
AI_MODEL_INVESTIGATOR=claude-opus-4-6-20250514
AI_PROMPT_CACHE_ENABLED=true
AI_DAILY_COST_CEILING=50.00
AI_COST_ALERT_THRESHOLD=0.6
```

**Cost monitoring:**
- Per-request logging to `ai_audit_log` table
- Daily aggregation: Langfuse integration
- Alert at 60% of daily ceiling ($30)
- Hard stop at $50/day (reject new Level 2/3 requests)

### 4.4. Prompt Templates

**Level 2 System Prompt (cached):**
```
You are an analyst for EKF Group's shipment profitability control system.

Context:
- System controls profitability of shipments against Local Estimates (LS)
- Key metric: deviation = planned_profitability - MAX(cumulative_plus_order, remainder_profitability)
- Thresholds: <1pp auto, 1-15pp RBU, 15-25pp DP, >25pp GD
- NPSS = normative planned cost price (from SBS project)
- Cherry-picking = selective fulfillment of low-margin items

Your task: explain detected anomalies, assess severity, recommend actions.
Output MUST be valid JSON matching the AnomalyExplanation schema.
```

**Level 3 System Prompt:**
```
You are an autonomous investigator for EKF Group's profitability control system.
You have access to tools to query shipments, client history, price changes, and run what-if scenarios.

Investigation protocol:
1. Examine the anomaly data
2. Query relevant shipments and client history
3. Check for price/NPSS changes that could explain the anomaly
4. Run what-if scenarios if needed
5. Form a root cause hypothesis with evidence chain
6. Provide confidence score and actionable recommendation

Constraints:
- Max 10 tool calls
- Focus on factual evidence, not speculation
- If evidence is insufficient, state confidence < 0.5 and recommend manual review
```

### 4.5. DB Schema

```sql
-- migrations/analytics/001_initial.up.sql

-- Аномалии
CREATE TABLE anomalies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    level INT NOT NULL CHECK (level IN (1, 2, 3)),
    score DOUBLE PRECISION NOT NULL,
    description TEXT NOT NULL,
    affected_entity VARCHAR(20) NOT NULL
        CHECK (affected_entity IN ('ls','shipment','client','manager')),
    affected_id UUID NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open','investigating','resolved','false_positive')),

    -- Level 2-3 fields
    llm_explanation TEXT,
    confidence DOUBLE PRECISION,
    recommendations JSONB, -- []string

    resolved_at TIMESTAMPTZ,
    resolved_by UUID,
    resolution_comment TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_anomalies_status ON anomalies(status);
CREATE INDEX idx_anomalies_level ON anomalies(level);
CREATE INDEX idx_anomalies_affected ON anomalies(affected_entity, affected_id);
CREATE INDEX idx_anomalies_detected ON anomalies(detected_at);

-- Расследования (Level 3)
CREATE TABLE investigations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    anomaly_id UUID NOT NULL REFERENCES anomalies(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    root_cause TEXT,
    recommendation TEXT,
    confidence_score DOUBLE PRECISION,
    iterations INT NOT NULL DEFAULT 0 CHECK (iterations <= 10),
    model VARCHAR(50) NOT NULL, -- claude-opus-4-6
    total_tokens INT NOT NULL DEFAULT 0,
    cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress','completed','failed','timeout'))
);

CREATE INDEX idx_investigations_anomaly ON investigations(anomaly_id);
CREATE INDEX idx_investigations_status ON investigations(status);

-- Цепочка улик (Level 3 tool calls)
CREATE TABLE investigation_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id UUID NOT NULL REFERENCES investigations(id),
    step_number INT NOT NULL,
    tool_used VARCHAR(50) NOT NULL,
    input JSONB NOT NULL,
    output JSONB NOT NULL,
    obtained_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evidence_investigation ON investigation_evidence(investigation_id);

-- AI audit log (все запросы к Claude API)
CREATE TABLE ai_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_type VARCHAR(20) NOT NULL
        CHECK (request_type IN ('level_2','level_3','ask','summarize')),
    model VARCHAR(50) NOT NULL,
    input_tokens INT NOT NULL,
    output_tokens INT NOT NULL,
    cached_tokens INT NOT NULL DEFAULT 0,
    cost_usd DOUBLE PRECISION NOT NULL,
    latency_ms INT NOT NULL,
    anomaly_id UUID,
    user_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_audit_date ON ai_audit_log(created_at);
CREATE INDEX idx_ai_audit_type ON ai_audit_log(request_type);

-- Прогнозы (ARIMA)
CREATE TABLE forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(20) NOT NULL
        CHECK (entity_type IN ('ls','client','business_unit','overall')),
    entity_id UUID,
    horizon_days INT NOT NULL,
    predicted_values JSONB NOT NULL, -- [{timestamp, value}]
    upper_bound JSONB NOT NULL,
    lower_bound JSONB NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_forecasts_entity ON forecasts(entity_type, entity_id);

-- Outbox
CREATE TABLE analytics_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    kafka_topic VARCHAR(200) NOT NULL,
    kafka_key VARCHAR(100) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE INDEX idx_analytics_outbox_unpublished
    ON analytics_outbox(created_at)
    WHERE published_at IS NULL;
```

### 4.6. Dependencies

| Зависимость | Протокол | Назначение |
|-------------|----------|------------|
| profitability-service | gRPC | Данные заказов, what-if сценарии |
| workflow-service | gRPC | История согласований |
| integration-service | gRPC | Данные клиентов, цен |
| Claude API (Sonnet) | REST | Level 2 интерпретация |
| Claude API (Opus) | REST | Level 3 расследование |
| Kafka (consumer) | TCP | Подписка на domain events |
| PostgreSQL | TCP | Хранение данных (analytics) |

---

## 5. integration-service

**Bounded Context:** Integration
**Aggregates:** Client, Sanction, PriceSheet (phase1a, секции 2.5, 2.6, 2.7)
**Domain Services:** SanctionManager (секция 5.4)
**Business Rules:** BR-080..084, BR-050..056

### 5.1. REST Endpoints (MDM API)

| Method | Path | Description | Auth Role | Request | Response |
|--------|------|-------------|-----------|---------|----------|
| GET | /api/v1/mdm/npss | Текущая НПСС по товару на дату | all services | query: `product_id`, `date` | `NPSSView` |
| GET | /api/v1/mdm/npss/batch | Пакетный запрос НПСС | all services | query: `product_ids[]`, `date` | `[]NPSSView` |
| GET | /api/v1/mdm/clients/{id} | Карточка контрагента | all services | query: `at_date` | `ClientView` |
| GET | /api/v1/mdm/clients/{id}/history | Темпоральная история | dp, fd | query: `from`, `to` | `[]ClientVersion` |
| GET | /api/v1/mdm/diff | Изменения MDM-сущности за период | fd | query: `entity`, `from`, `to` | `[]DiffRecord` |
| GET | /api/v1/mdm/exchange-rates | Курсы валют ЦБ РФ | all services | query: `currency`, `date` | `ExchangeRateView` |
| GET | /api/v1/mdm/employees/{id} | Данные сотрудника | all services | - | `EmployeeView` |
| GET | /api/v1/mdm/business-units/{id} | Бизнес-юнит | all services | - | `BusinessUnitView` |
| GET | /api/v1/sanctions/{client_id} | Активные санкции | rbu, dp, gd, fd | - | `[]SanctionView` |
| POST | /api/v1/sanctions/{id}/cancel | Отмена санкции (решение ДП) | dp | `CancelRequest` | `SanctionView` |

### 5.2. gRPC Services (internal)

```protobuf
// api/proto/integration/v1/integration.proto

syntax = "proto3";
package integration.v1;

service IntegrationService {
  // MDM read operations
  rpc GetNPSS(GetNPSSRequest) returns (NPSSResponse);
  rpc GetNPSSBatch(GetNPSSBatchRequest) returns (NPSSBatchResponse);
  rpc GetClient(GetClientRequest) returns (ClientResponse);
  rpc GetEmployee(GetEmployeeRequest) returns (EmployeeResponse);
  rpc GetBusinessUnit(GetBURequest) returns (BUResponse);
  rpc GetExchangeRate(GetExchangeRateRequest) returns (ExchangeRateResponse);

  // Sanction operations
  rpc GetActiveSanctions(GetSanctionsRequest) returns (SanctionsResponse);
}

message GetNPSSRequest {
  string product_id = 1;
  string at_date = 2; // RFC 3339, optional (default=now)
}

message NPSSResponse {
  string product_id = 1;
  int64 npss_cents = 2;
  string method = 3; // planned/temporary
  string calculated_at = 4;
  string valid_from = 5;
  string valid_to = 6; // empty = current
}

message GetNPSSBatchRequest {
  repeated string product_ids = 1;
  string at_date = 2;
}

message NPSSBatchResponse {
  repeated NPSSResponse items = 1;
}

message GetClientRequest {
  string client_id = 1;
  string at_date = 2; // temporal query
}

message ClientResponse {
  string id = 1;
  string external_id = 2;
  string name = 3;
  bool is_strategic = 4;
  string strategic_criteria = 5;
  double allowed_deviation = 6;
  string manager_id = 7;
  string business_unit_id = 8;
  int32 sanction_cancel_count = 9;
}

message GetEmployeeRequest {
  string employee_id = 1;
}

message EmployeeResponse {
  string id = 1;
  string external_id = 2;
  string name = 3;
  string position = 4;
  string department = 5;
  string business_unit_id = 6;
  bool is_active = 7;
}

message GetBURequest {
  string business_unit_id = 1;
}

message BUResponse {
  string id = 1;
  string name = 2;
  string head_id = 3;
  string deputy_id = 4;
}

message GetExchangeRateRequest {
  string currency = 1; // USD, EUR, CNY
  string date = 2;
}

message ExchangeRateResponse {
  string currency = 1;
  double rate = 2;
  string date = 3;
  double change_7d_pct = 4; // % change over 7 days
}

message GetSanctionsRequest {
  string client_id = 1;
}

message SanctionsResponse {
  repeated SanctionItem sanctions = 1;
}

message SanctionItem {
  string id = 1;
  string type = 2;
  double discount_reduction = 3;
  double cumulative_reduction = 4;
  string applied_at = 5;
  string rehabilitation_at = 6;
  string status = 7;
}
```

### 5.3. Kafka Consumers (9 inbound topics from 1C)

| Topic | Partition Key | Handler | Target Table |
|-------|--------------|---------|-------------|
| `1c.order.created.v1` | order_id | `OrderCreatedHandler` | -> profitability-service via evt topic |
| `1c.order.updated.v1` | order_id | `OrderUpdatedHandler` | -> profitability-service via evt topic |
| `1c.shipment.posted.v1` | order_id | `ShipmentPostedHandler` | -> profitability-service via evt topic |
| `1c.shipment.returned.v1` | order_id | `ShipmentReturnedHandler` | -> profitability-service via evt topic |
| `1c.price.npss-updated.v1` | product_id | `NPSSUpdatedHandler` | mdm_price_sheets |
| `1c.price.purchase-changed.v1` | product_id | `PurchasePriceHandler` | mdm_price_sheets + trigger check |
| `1c.client.updated.v1` | client_id | `ClientUpdatedHandler` | mdm_clients |
| `1c.ls.created.v1` | ls_id | `LSCreatedHandler` | -> profitability-service via evt topic |
| `1c.ls.plan-changed.v1` | ls_id | `LSPlanChangedHandler` | -> profitability-service via evt topic |

**Processing flow:**
1. Consumer receives message from Kafka
2. Check `kafka_dedup` table for message_id (idempotency)
3. If new: process, update MDM tables, emit domain events via outbox
4. If duplicate: skip, ack

### 5.4. Outbox Pattern Implementation

```
+------------+     +-------------+     +---------+     +-------+
| Service    | --> | DB (same tx)| --> | Poller   | --> | Kafka |
| (business  |     | outbox      |     | (100ms)  |     |       |
|  logic)    |     | table       |     |          |     |       |
+------------+     +-------------+     +---------+     +-------+
```

**Design:**
1. Domain event created within business transaction
2. Event written to `outbox` table in same DB transaction (atomicity)
3. Background poller reads unpublished events every 100ms
4. Poller produces to Kafka, on ack marks `published_at`
5. Cleanup: events with `published_at` older than 7 days are deleted

**Poller configuration:**
```go
type OutboxPollerConfig struct {
    PollInterval   time.Duration // 100ms
    BatchSize      int           // 100
    MaxRetries     int           // 10
    RetryBackoff   time.Duration // 1s * 2^attempt
    CleanupAfter   time.Duration // 7 * 24h
    CleanupBatch   int           // 1000
}
```

**Failure handling:**
- Kafka produce failure: increment retry_count, set last_error, exponential backoff
- After MaxRetries (10): move to DLQ, alert

### 5.5. Mini MDM (Temporal Tables)

**Design principle:** Temporal PostgreSQL tables with `valid_from`/`valid_to` columns. All queries use point-in-time semantics: find record where `valid_from <= date AND (valid_to IS NULL OR valid_to > date)`.

**Cold start procedure:**
1. Script `scripts/seed-mdm.sh` calls 1C HTTP service for bulk export (CSV/JSON)
2. Loads into MDM tables with `valid_from = export_timestamp`, `valid_to = NULL`
3. Subsequent updates via Kafka events use temporal insert (close old record, open new)

### 5.6. DB Schema

```sql
-- migrations/integration/001_initial.up.sql

-- MDM: Контрагенты (temporal)
CREATE TABLE mdm_clients (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    external_id VARCHAR(30) NOT NULL,
    name VARCHAR(500) NOT NULL,
    is_strategic BOOLEAN NOT NULL DEFAULT false,
    strategic_criteria VARCHAR(30),
    strategic_since TIMESTAMPTZ,
    allowed_deviation BIGINT NOT NULL DEFAULT 0, -- basis points
    sanction_cancel_count INT NOT NULL DEFAULT 0 CHECK (sanction_cancel_count <= 3),
    manager_id UUID,
    business_unit_id UUID,

    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    PRIMARY KEY (id, valid_from)
);

CREATE INDEX idx_mdm_clients_external ON mdm_clients(external_id);
CREATE INDEX idx_mdm_clients_temporal ON mdm_clients(external_id, valid_from DESC)
    WHERE valid_to IS NULL;
CREATE INDEX idx_mdm_clients_strategic ON mdm_clients(is_strategic)
    WHERE is_strategic = true AND valid_to IS NULL;

-- MDM: Товары (temporal)
CREATE TABLE mdm_products (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    external_id VARCHAR(30) NOT NULL,
    name VARCHAR(500) NOT NULL,
    sku VARCHAR(50),
    category VARCHAR(200),
    is_non_liquid BOOLEAN NOT NULL DEFAULT false,
    origin VARCHAR(20) CHECK (origin IN ('import','domestic','production')),

    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    PRIMARY KEY (id, valid_from)
);

CREATE INDEX idx_mdm_products_external ON mdm_products(external_id);
CREATE INDEX idx_mdm_products_temporal ON mdm_products(external_id, valid_from DESC)
    WHERE valid_to IS NULL;

-- MDM: НПСС (temporal)
CREATE TABLE mdm_price_sheets (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    product_id UUID NOT NULL,
    npss BIGINT NOT NULL, -- копейки
    purchase_price BIGINT, -- копейки
    logistics_cost BIGINT,
    overhead_cost BIGINT,
    calculated_at TIMESTAMPTZ NOT NULL,
    calculated_by UUID,
    method VARCHAR(20) NOT NULL CHECK (method IN ('planned','temporary')),
    trigger VARCHAR(20) NOT NULL DEFAULT 'planned'
        CHECK (trigger IN ('planned','exchange_rate','purchase_price','manual')),

    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    PRIMARY KEY (id, valid_from)
);

CREATE INDEX idx_mdm_prices_product ON mdm_price_sheets(product_id, valid_from DESC)
    WHERE valid_to IS NULL;
CREATE INDEX idx_mdm_prices_stale ON mdm_price_sheets(calculated_at)
    WHERE valid_to IS NULL;

-- MDM: Курсы валют
CREATE TABLE mdm_exchange_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    currency VARCHAR(3) NOT NULL CHECK (currency IN ('USD','EUR','CNY')),
    rate DOUBLE PRECISION NOT NULL,
    rate_date DATE NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(currency, rate_date)
);

CREATE INDEX idx_exchange_rates_lookup ON mdm_exchange_rates(currency, rate_date DESC);

-- MDM: Сотрудники (temporal)
CREATE TABLE mdm_employees (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    external_id VARCHAR(30) NOT NULL,
    name VARCHAR(300) NOT NULL,
    position VARCHAR(200),
    department VARCHAR(200),
    business_unit_id UUID,
    is_active BOOLEAN NOT NULL DEFAULT true,
    ad_login VARCHAR(100),

    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    PRIMARY KEY (id, valid_from)
);

CREATE INDEX idx_mdm_employees_external ON mdm_employees(external_id);
CREATE INDEX idx_mdm_employees_temporal ON mdm_employees(external_id, valid_from DESC)
    WHERE valid_to IS NULL;
CREATE INDEX idx_mdm_employees_ad ON mdm_employees(ad_login)
    WHERE valid_to IS NULL AND is_active = true;

-- MDM: Бизнес-юниты
CREATE TABLE mdm_business_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(300) NOT NULL,
    head_id UUID,
    deputy_id UUID
);

-- Kafka dedup (idempotency)
CREATE TABLE kafka_dedup (
    message_id VARCHAR(100) PRIMARY KEY,
    topic VARCHAR(200) NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_kafka_dedup_cleanup ON kafka_dedup(processed_at);

-- Outbox
CREATE TABLE integration_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    kafka_topic VARCHAR(200) NOT NULL,
    kafka_key VARCHAR(100) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE INDEX idx_integration_outbox_unpublished
    ON integration_outbox(created_at)
    WHERE published_at IS NULL;

-- Санкции
CREATE TABLE sanctions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL,
    type VARCHAR(30) NOT NULL
        CHECK (type IN ('none','discount_reduction_3pp','discount_reduction_10pp','standard_prices_only')),
    discount_reduction BIGINT NOT NULL, -- basis points
    cumulative_reduction BIGINT NOT NULL, -- basis points
    trigger_ls_id UUID NOT NULL,
    fulfillment_rate BIGINT NOT NULL, -- basis points
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    rehabilitation_at TIMESTAMPTZ NOT NULL,
    cancelled_by_dp BOOLEAN NOT NULL DEFAULT false,
    cancellation_reason TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','rehabilitated','cancelled')),
    version INT NOT NULL DEFAULT 1
);

CREATE INDEX idx_sanctions_client ON sanctions(client_id);
CREATE INDEX idx_sanctions_active ON sanctions(client_id)
    WHERE status = 'active';
CREATE INDEX idx_sanctions_rehab ON sanctions(rehabilitation_at)
    WHERE status = 'active';

-- MDM audit log (append-only, no UPDATE/DELETE)
CREATE TABLE mdm_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type VARCHAR(30) NOT NULL,
    entity_id UUID NOT NULL,
    operation VARCHAR(10) NOT NULL CHECK (operation IN ('INSERT','UPDATE','CLOSE')),
    old_values JSONB,
    new_values JSONB NOT NULL,
    changed_by VARCHAR(100) NOT NULL, -- 'kafka:{topic}' or 'seed' or 'manual'
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    hash VARCHAR(64) NOT NULL -- SHA-256 chain: hash(prev_hash + payload)
);

-- Запрет UPDATE/DELETE на audit log
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'mdm_audit_log is append-only: UPDATE and DELETE are prohibited';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_audit_update
    BEFORE UPDATE OR DELETE ON mdm_audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

CREATE INDEX idx_audit_log_entity ON mdm_audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_log_time ON mdm_audit_log(changed_at);
```

### 5.7. Temporal Query Examples

```sql
-- Получить НПСС товара на конкретную дату (point-in-time query)
SELECT id, product_id, npss, method, calculated_at
FROM mdm_price_sheets
WHERE product_id = $1
  AND valid_from <= $2
  AND (valid_to IS NULL OR valid_to > $2)
ORDER BY valid_from DESC
LIMIT 1;

-- Получить историю изменений клиента за период
SELECT id, external_id, name, is_strategic, strategic_criteria,
       valid_from, valid_to
FROM mdm_clients
WHERE external_id = $1
  AND valid_from <= $3
  AND (valid_to IS NULL OR valid_to > $2)
ORDER BY valid_from;

-- Получить diff (что изменилось за период)
SELECT entity_type, entity_id, operation, old_values, new_values, changed_at
FROM mdm_audit_log
WHERE entity_type = $1
  AND changed_at BETWEEN $2 AND $3
ORDER BY changed_at;
```

### 5.8. Dependencies

| Зависимость | Протокол | Назначение |
|-------------|----------|------------|
| Kafka (consumer) | TCP | 9 inbound topics from 1C |
| Kafka (producer) | TCP | Domain events, commands to 1C |
| CBR API | REST | Курсы валют (ежедневно 08:00) |
| PostgreSQL | TCP | Хранение MDM, dedup, outbox |

---

## 6. notification-service

### 6.1. REST Endpoints

| Method | Path | Description | Auth Role | Request | Response |
|--------|------|-------------|-----------|---------|----------|
| GET | /api/v1/notifications | Список уведомлений пользователя | all | query: `status`, `page`, `per_page` | `[]NotificationView` |
| PUT | /api/v1/notifications/{id}/read | Отметить прочитанным | all | - | `NotificationView` |
| GET | /api/v1/notifications/preferences | Настройки уведомлений | all | - | `UserPreferences` |
| PUT | /api/v1/notifications/preferences | Обновить настройки | all | `UpdatePreferencesRequest` | `UserPreferences` |

### 6.2. Kafka Consumers

Подписка на domain events из всех сервисов для формирования уведомлений.

| Event Topic | Template | Channels | Priority |
|------------|----------|----------|----------|
| `evt.workflow.approval.created.v1` | `approval_request` | Telegram + Email | HIGH |
| `evt.workflow.approval.decided.v1` | `approval_result` | Telegram | HIGH |
| `evt.workflow.approval.routed.v1` | `approval_request` | Telegram + Email | HIGH |
| `evt.workflow.sla.breached.v1` | `sla_warning` | Telegram + Email + 1C | CRITICAL |
| `evt.workflow.approval.escalated.v1` | `sla_warning` | Telegram + Email | HIGH |
| `evt.workflow.emergency.escalated-48h.v1` | `sla_warning` | Telegram + Email + 1C | CRITICAL |
| `evt.workflow.fallback.activated.v1` | `sla_warning` | Telegram + Email | CRITICAL |
| `evt.profitability.threshold.violated.v1` | `approval_request` | Telegram | MEDIUM |
| `evt.integration.price.exchange-trigger.v1` | `anomaly_alert` | Telegram + Email | HIGH |
| `evt.integration.sanction.applied.v1` | `anomaly_alert` | Telegram + Email | HIGH |
| analytics anomaly events | `anomaly_alert` | Telegram | MEDIUM |
| daily scheduled | `daily_digest` | Email | LOW |

### 6.3. Templates

| Template ID | Description | Variables | FM Reference |
|-------------|-------------|-----------|-------------|
| `approval_request` | Запрос на согласование | shipment_id, deviation, level, sla_hours, manager_name | п. 3.5-3.7 |
| `approval_result` | Результат согласования | shipment_id, decision, approver_name, comment | п. 3.5 |
| `sla_warning` | Предупреждение SLA / эскалация | process_id, remaining_time, level, priority | п. 3.11 |
| `anomaly_alert` | Обнаружена аномалия | anomaly_type, description, affected_entity, score | п. 3.20 (AI) |
| `daily_digest` | Ежедневная сводка | approvals_count, anomalies_count, sla_breaches, kpi_summary | LS-RPT-070 |

### 6.4. Throttling and Priority Routing

**Throttling rules:**
- Max 10 notifications/hour per user
- Quiet hours: 22:00-07:00 MSK (except CRITICAL)
- Dedup: same template + same entity within 5 minutes = merge

**Priority routing:**

| Priority | Channels | Quiet hours |
|----------|----------|-------------|
| CRITICAL | Telegram + Email + 1C push | Ignore (send always) |
| HIGH | Telegram + Email | Defer to 07:00 |
| MEDIUM | Telegram | Defer to 07:00 |
| LOW | Daily digest (email) | N/A (scheduled) |

**Fallback chain:**
1. Telegram Bot API -> if down -> Email (SMTP)
2. Email (SMTP) -> if down -> 1C push (REST callback)
3. All down -> log to DB, retry on next cycle

### 6.5. DB Schema

```sql
-- migrations/notification/001_initial.up.sql

-- Уведомления
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    template_id VARCHAR(50) NOT NULL,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('telegram','email','push_1c')),
    priority VARCHAR(10) NOT NULL CHECK (priority IN ('critical','high','medium','low')),
    subject VARCHAR(500),
    body TEXT NOT NULL,
    variables JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','sent','delivered','failed','read')),
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    error TEXT,
    retry_count INT NOT NULL DEFAULT 0,
    source_event_id UUID, -- domain event that triggered this
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_user ON notifications(user_id, created_at DESC);
CREATE INDEX idx_notifications_status ON notifications(status)
    WHERE status IN ('pending','failed');
CREATE INDEX idx_notifications_template ON notifications(template_id);

-- Шаблоны
CREATE TABLE notification_templates (
    id VARCHAR(50) PRIMARY KEY,
    channel VARCHAR(20) NOT NULL,
    subject_template TEXT,
    body_template TEXT NOT NULL,
    variables_schema JSONB NOT NULL, -- JSON Schema for variables
    is_active BOOLEAN NOT NULL DEFAULT true,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Настройки пользователей
CREATE TABLE user_notification_preferences (
    user_id UUID NOT NULL,
    channel VARCHAR(20) NOT NULL CHECK (channel IN ('telegram','email','push_1c')),
    enabled BOOLEAN NOT NULL DEFAULT true,
    quiet_hours_start TIME DEFAULT '22:00',
    quiet_hours_end TIME DEFAULT '07:00',
    telegram_chat_id BIGINT,
    email VARCHAR(255),
    PRIMARY KEY (user_id, channel)
);

-- Throttle counters
CREATE TABLE notification_throttle (
    user_id UUID NOT NULL,
    hour_bucket TIMESTAMPTZ NOT NULL, -- truncated to hour
    count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, hour_bucket)
);
```

### 6.6. Dependencies

| Зависимость | Протокол | Назначение |
|-------------|----------|------------|
| Telegram Bot API | REST | Отправка уведомлений |
| Email (SMTP) | SMTP | Отправка email |
| 1C REST callback | REST | Push-уведомления в 1С |
| Kafka (consumer) | TCP | Domain events |
| PostgreSQL | TCP | Хранение уведомлений |

---

## 7. api-gateway

### 7.1. Auth Flow

```
Client (browser) --> api-gateway --> AD (LDAP/Kerberos)
                         |
                    JWT issued (RS256)
                    access_token (15min)
                    refresh_token (7d)
                         |
                    Subsequent requests:
                    Authorization: Bearer {access_token}
                         |
                    api-gateway validates JWT
                    extracts role from AD groups
                    forwards to service via gRPC
```

**AD Group -> Role mapping:**

| AD Group | App Role | Description |
|----------|----------|-------------|
| `APP-PROFIT-MANAGER` | manager | Менеджер по продажам |
| `APP-PROFIT-RBU` | rbu | Руководитель бизнес-юнита |
| `APP-PROFIT-DP` | dp | Директор по продажам |
| `APP-PROFIT-GD` | gd | Генеральный директор |
| `APP-PROFIT-FD` | fd | Финансовый директор |

**2FA/MFA:** Optional middleware (`AUTH_MFA_ENABLED=false` in Phase 1). Prepared for Phase 2 if required by security policy.

### 7.2. Route Table

| Path Prefix | Target Service | Rate Limit | Auth Required |
|------------|---------------|------------|---------------|
| `/api/v1/shipments/**` | profitability-service | 100/min | Yes |
| `/api/v1/local-estimates/**` | profitability-service | 100/min | Yes |
| `/api/v1/dashboard/**` | profitability-service | 100/min | Yes |
| `/api/v1/price-sheets/**` | profitability-service | 100/min | Yes |
| `/api/v1/approvals/**` | workflow-service | 100/min | Yes |
| `/api/v1/emergency-approvals/**` | workflow-service | 100/min | Yes |
| `/api/v1/fallback/**` | workflow-service | 100/min | Yes |
| `/api/v1/anomalies/**` | analytics-service | 100/min | Yes |
| `/api/v1/forecasts/**` | analytics-service | 100/min | Yes |
| `/api/v1/reports/**` | analytics-service | 100/min | Yes |
| `/api/v1/ai/**` | analytics-service | 50/min | Yes |
| `/api/v1/kpi/**` | analytics-service | 100/min | Yes |
| `/api/v1/mdm/**` | integration-service | 100/min | Yes |
| `/api/v1/sanctions/**` | integration-service | 100/min | Yes |
| `/api/v1/notifications/**` | notification-service | 100/min | Yes |
| `/auth/login` | api-gateway (internal) | 20/min | No |
| `/auth/refresh` | api-gateway (internal) | 20/min | Yes (refresh) |
| `/auth/logout` | api-gateway (internal) | 20/min | Yes |
| `/health` | api-gateway (internal) | - | No |
| `/ready` | api-gateway (internal) | - | No |
| `/metrics` | api-gateway (internal) | - | No |

**Rate limiting:** Per-user token bucket. Standard users: 100 req/min. GD/FD: 200 req/min.
AI endpoints (`/api/v1/ai/**`): 50 req/min to protect Claude API budget.

### 7.3. CORS and Security Headers

```
Access-Control-Allow-Origin: https://profit.ekf.su
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

### 7.4. Health and Metrics

| Endpoint | Description | Response |
|----------|-------------|----------|
| `GET /health` | Liveness probe | `{"status":"ok"}` |
| `GET /ready` | Readiness probe (checks all downstream services) | `{"status":"ready","services":{"profitability":"ok",...}}` |
| `GET /metrics` | Prometheus metrics | Prometheus text format |

**Prometheus metrics exposed:**
- `http_requests_total{method, path, status}`
- `http_request_duration_seconds{method, path}`
- `grpc_requests_total{service, method, status}`
- `auth_login_total{result}`
- `rate_limit_exceeded_total{user_role}`

### 7.5. Dependencies

| Зависимость | Протокол | Назначение |
|-------------|----------|------------|
| AD (LDAP) | LDAP/Kerberos | Аутентификация |
| profitability-service | gRPC | Proxy |
| workflow-service | gRPC | Proxy |
| analytics-service | gRPC | Proxy |
| integration-service | gRPC | Proxy |
| notification-service | gRPC | Proxy |
| Redis | TCP | Rate limiting, JWT blacklist |

---

## 8. Database Migrations

**Tooling:** golang-migrate/migrate v4

**Convention:**
```
migrations/
  profitability/
    001_initial.up.sql
    001_initial.down.sql
  workflow/
    001_initial.up.sql
    001_initial.down.sql
  analytics/
    001_initial.up.sql
    001_initial.down.sql
  integration/
    001_initial.up.sql
    001_initial.down.sql
  notification/
    001_initial.up.sql
    001_initial.down.sql
```

**Per-service isolation:** Each service has its own PostgreSQL database. No cross-service joins. Data sharing only through gRPC (sync) or Kafka events (async).

**Database naming:**
- `profitability_db`
- `workflow_db`
- `analytics_db`
- `integration_db`
- `notification_db`

All migrations are defined in sections 2.3, 3.5, 4.5, 5.6, 6.5 above.

**Total tables by service:**

| Service | Tables | Key tables |
|---------|--------|-----------|
| profitability | 7 | local_estimates, shipments, profitability_calculations, price_sheet_cache, auto_approval_counters |
| workflow | 7 | approval_processes, bu_approvals, routing_history, sla_tracking, fallback_queue, emergency_approvals |
| analytics | 6 | anomalies, investigations, investigation_evidence, ai_audit_log, forecasts |
| integration | 10 | mdm_clients, mdm_products, mdm_price_sheets, mdm_exchange_rates, mdm_employees, mdm_business_units, kafka_dedup, sanctions, mdm_audit_log |
| notification | 4 | notifications, notification_templates, user_notification_preferences, notification_throttle |
| **Total** | **34** + 5 outbox tables = **39** | |

---

## 9. Kafka Topic Catalog

### 9.1. Naming Convention

Format: `{source}.{domain}.{event}.v{N}`

- `1c.*` -- events from 1C (inbound)
- `evt.*` -- internal domain events
- `cmd.*` -- commands to external systems (outbound)
- `*.dlq` -- dead letter queue
- `*.retry.*` -- retry topics

### 9.2. Inbound Topics (1C -> Go)

| # | Topic | Source | Partition Key | Retention | Schema |
|---|-------|--------|--------------|-----------|--------|
| 1 | `1c.order.created.v1` | 1C:UT | order_id | 7d | OrderCreatedPayload |
| 2 | `1c.order.updated.v1` | 1C:UT | order_id | 7d | OrderUpdatedPayload |
| 3 | `1c.shipment.posted.v1` | 1C:UT | order_id | 7d | ShipmentPostedPayload |
| 4 | `1c.shipment.returned.v1` | 1C:UT | order_id | 7d | ShipmentReturnedPayload |
| 5 | `1c.price.npss-updated.v1` | 1C:UT | product_id | 7d | NPSSUpdatedPayload |
| 6 | `1c.price.purchase-changed.v1` | 1C:UT | product_id | 7d | PurchasePricePayload |
| 7 | `1c.client.updated.v1` | 1C:UT | client_id | 7d | ClientUpdatedPayload |
| 8 | `1c.ls.created.v1` | 1C:UT | ls_id | 7d | LSCreatedPayload |
| 9 | `1c.ls.plan-changed.v1` | 1C:UT | ls_id | 7d | LSPlanChangedPayload |

### 9.3. Internal Domain Event Topics

| # | Topic | Producer | Partition Key | Retention | Consumers |
|---|-------|----------|--------------|-----------|-----------|
| 10 | `evt.profitability.ls.created.v1` | profitability | ls_id | 7d | analytics, workflow |
| 11 | `evt.profitability.ls.plan-changed.v1` | profitability | ls_id | 7d | workflow, analytics |
| 12 | `evt.profitability.ls.closed.v1` | profitability | ls_id | 7d | analytics, integration |
| 13 | `evt.profitability.shipment.created.v1` | profitability | shipment_id | 7d | analytics |
| 14 | `evt.profitability.calculation.completed.v1` | profitability | shipment_id | 7d | workflow, analytics |
| 15 | `evt.profitability.threshold.violated.v1` | profitability | shipment_id | 7d | workflow, analytics, notification |
| 16 | `evt.workflow.approval.created.v1` | workflow | process_id | 7d | notification, analytics |
| 17 | `evt.workflow.approval.auto-approved.v1` | workflow | process_id | 7d | profitability, notification, analytics |
| 18 | `evt.workflow.approval.routed.v1` | workflow | process_id | 7d | notification |
| 19 | `evt.workflow.approval.decided.v1` | workflow | process_id | 7d | profitability, notification, analytics |
| 20 | `evt.workflow.approval.escalated.v1` | workflow | process_id | 7d | notification, analytics |
| 21 | `evt.workflow.sla.breached.v1` | workflow | process_id | 7d | notification, analytics |
| 22 | `evt.workflow.correction.limit-reached.v1` | workflow | process_id | 7d | notification, analytics |
| 23 | `evt.workflow.fallback.activated.v1` | workflow | - | 7d | notification, analytics |
| 24 | `evt.workflow.fallback.queue-drained.v1` | workflow | - | 7d | notification, analytics |
| 25 | `evt.workflow.emergency.created.v1` | workflow | ea_id | 7d | notification, analytics |
| 26 | `evt.workflow.emergency.escalated-48h.v1` | workflow | ea_id | 7d | notification, integration |
| 27 | `evt.integration.price.npss-updated.v1` | integration | product_id | 7d | profitability, analytics |
| 28 | `evt.integration.price.exchange-trigger.v1` | integration | currency | 7d | notification, analytics |
| 29 | `evt.integration.sanction.applied.v1` | integration | client_id | 7d | notification, analytics |
| 30 | `evt.integration.sanction.rehabilitated.v1` | integration | client_id | 7d | notification |
| 31 | `evt.integration.client.updated.v1` | integration | client_id | 7d | profitability, analytics |
| 32 | `evt.analytics.anomaly.detected.v1` | analytics | anomaly_id | 7d | notification |
| 33 | `evt.analytics.investigation.completed.v1` | analytics | anomaly_id | 7d | notification |

### 9.4. Outbound Command Topics (Go -> 1C)

| # | Topic | Producer | Partition Key | Retention | Consumer |
|---|-------|----------|--------------|-----------|----------|
| 34 | `cmd.approval.result.v1` | workflow | order_id | 30d | 1C:UT |
| 35 | `cmd.sanction.applied.v1` | integration | client_id | 30d | 1C:UT |
| 36 | `cmd.block.shipment.v1` | workflow | order_id | 30d | 1C:UT, WMS |

### 9.5. DLQ and Retry Topics

| # | Topic | Source Topic | Retention |
|---|-------|-------------|-----------|
| 37 | `1c.order.dlq` | `1c.order.*.v1` | 30d |
| 38 | `1c.shipment.dlq` | `1c.shipment.*.v1` | 30d |
| 39 | `1c.price.dlq` | `1c.price.*.v1` | 30d |
| 40 | `1c.client.dlq` | `1c.client.*.v1` | 30d |
| 41 | `1c.ls.dlq` | `1c.ls.*.v1` | 30d |
| 42 | `cmd.approval.dlq` | `cmd.approval.*.v1` | 30d |
| 43 | `cmd.sanction.dlq` | `cmd.sanction.*.v1` | 30d |
| 44 | `cmd.block.dlq` | `cmd.block.*.v1` | 30d |

**Retry policy (3 levels):**
- Level 1: retry after 1s
- Level 2: retry after 30s
- Level 3: retry after 5min
- After Level 3 failure: move to DLQ with error headers (`X-Error-Message`, `X-Original-Topic`, `X-Retry-Count`)

### 9.6. Topic Summary

| Category | Count |
|----------|-------|
| Inbound (1C) | 9 |
| Internal events | 24 |
| Outbound commands | 3 |
| DLQ | 8 |
| **Total** | **44** |

**Coverage check:** All 17 integrations from FM integration matrix (phase1a, section 10) are covered:
- 6 inbound from 1C (orders, shipments, prices, clients, LS) = 9 topics
- 3 outbound to 1C (approval result, sanction, block) = 3 topics
- 5 external systems (ELMA, WMS, CBR, Claude Sonnet, Claude Opus) = via REST/gRPC, not Kafka
- 3 notification channels (Telegram, Email, 1C push) = via REST/SMTP, not Kafka

---

## 10. Outbox Pattern

All 5 services use the same outbox pattern for reliable event publishing. Each service has its own outbox table (see DB schemas above).

### 10.1. Outbox Table Structure (common)

```sql
CREATE TABLE {service}_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type VARCHAR(50) NOT NULL,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    kafka_topic VARCHAR(200) NOT NULL,
    kafka_key VARCHAR(100) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    last_error TEXT
);

CREATE INDEX idx_{service}_outbox_unpublished
    ON {service}_outbox(created_at)
    WHERE published_at IS NULL;
```

### 10.2. Poller Implementation

```go
// internal/infrastructure/outbox/poller.go

type Poller struct {
    db       *sql.DB
    producer *franz.Client
    cfg      PollerConfig
    logger   *slog.Logger
    metrics  *prometheus.CounterVec
}

type PollerConfig struct {
    PollInterval time.Duration // 100ms
    BatchSize    int           // 100
    MaxRetries   int           // 10
    CleanupTTL   time.Duration // 7 days
}

// Run polls for unpublished events and produces to Kafka.
// Runs in a dedicated goroutine per service.
func (p *Poller) Run(ctx context.Context) error {
    ticker := time.NewTicker(p.cfg.PollInterval)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-ticker.C:
            if err := p.pollBatch(ctx); err != nil {
                p.logger.Error("outbox poll failed", "error", err)
            }
        }
    }
}
```

### 10.3. Guarantees

- **At-least-once delivery:** Event may be delivered multiple times if Kafka ack fails after produce. Consumers must be idempotent (via `kafka_dedup` table).
- **Ordering:** Events for same aggregate_id are ordered by `created_at` within outbox. Kafka partition key = aggregate_id ensures ordering within partition.
- **Atomicity:** Business state change + outbox insert in same DB transaction. No window for inconsistency.

---

## 11. Inter-Service Communication

### 11.1. Sync (gRPC / connect-go)

```
api-gateway --> profitability-service (REST -> gRPC)
api-gateway --> workflow-service      (REST -> gRPC)
api-gateway --> analytics-service     (REST -> gRPC)
api-gateway --> integration-service   (REST -> gRPC)
api-gateway --> notification-service  (REST -> gRPC)

profitability-service --> integration-service (gRPC: GetNPSS, GetClient)
workflow-service      --> profitability-service (gRPC: GetCalculation, RecalculateForPlanChange)
workflow-service      --> integration-service (gRPC: GetEmployee, GetBusinessUnit)
analytics-service     --> profitability-service (gRPC: GetShipmentHistory, CalculateWhatIf)
analytics-service     --> workflow-service (gRPC: GetApprovalHistory)
analytics-service     --> integration-service (gRPC: GetClient, GetNPSS)
```

**Rules:**
- NO direct HTTP between services (only through api-gateway for external, gRPC for internal)
- Protobuf contracts in `api/proto/`, managed by `buf`
- Connect-go for gRPC (HTTP/2, works with standard Go HTTP servers)

### 11.2. Async (Kafka Events)

```
profitability-service --[evt.profitability.*]--> workflow-service
                                             --> analytics-service
                                             --> notification-service

workflow-service --[evt.workflow.*]--> profitability-service
                                  --> analytics-service
                                  --> notification-service

integration-service --[evt.integration.*]--> profitability-service
                                         --> analytics-service
                                         --> notification-service

analytics-service --[evt.analytics.*]--> notification-service
```

**Rules:**
- Events are fire-and-forget from producer perspective (outbox guarantees delivery)
- Consumers are idempotent (dedup via message_id)
- No request-response over Kafka (use gRPC for that)

---

## 12. Graceful Shutdown

### 12.1. Shutdown Sequence

```
SIGTERM received
    |
    v
[1] Stop accepting new HTTP/gRPC connections (close listeners)
    |
    v
[2] Mark /ready as NOT READY (Kubernetes stops sending traffic)
    |
    v
[3] Wait for in-flight requests to complete (max 30s)
    |
    v
[4] Stop Kafka consumers (commit offsets, leave consumer group)
    |
    v
[5] Flush outbox poller (process remaining batch)
    |
    v
[6] Close database connections (connection pool drain)
    |
    v
[7] Close Redis connections
    |
    v
[8] Flush metrics/traces (OpenTelemetry shutdown)
    |
    v
[9] Exit 0
```

### 12.2. Implementation

```go
// cmd/service/main.go (common pattern for all services)

func main() {
    ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
    defer cancel()

    // ... initialize service ...

    // Start servers
    g, gCtx := errgroup.WithContext(ctx)

    g.Go(func() error { return httpServer.ListenAndServe() })
    g.Go(func() error { return grpcServer.Serve(lis) })
    g.Go(func() error { return kafkaConsumer.Run(gCtx) })
    g.Go(func() error { return outboxPoller.Run(gCtx) })

    // Graceful shutdown
    g.Go(func() error {
        <-gCtx.Done()

        shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 30*time.Second)
        defer shutdownCancel()

        // Step 1-3: drain HTTP/gRPC
        httpServer.Shutdown(shutdownCtx)
        grpcServer.GracefulStop()

        // Step 4: stop Kafka
        kafkaConsumer.Close()

        // Step 5: flush outbox
        outboxPoller.Flush(shutdownCtx)

        // Step 6-7: close connections
        db.Close()
        redis.Close()

        // Step 8: flush telemetry
        tracerProvider.Shutdown(shutdownCtx)

        return nil
    })

    if err := g.Wait(); err != nil && !errors.Is(err, context.Canceled) {
        slog.Error("service stopped with error", "error", err)
        os.Exit(1)
    }
}
```

### 12.3. Timeouts

| Phase | Timeout | Action on expiry |
|-------|---------|-----------------|
| In-flight drain | 30s | Force close connections |
| Kafka consumer close | 10s | Force leave group |
| Outbox flush | 5s | Leave unprocessed (will retry on restart) |
| DB pool drain | 5s | Force close |
| Total shutdown | 45s | SIGKILL by orchestrator |

---

## 13. OpenAPI 3.0 Specification

```yaml
openapi: 3.0.3
info:
  title: Profitability Control System API
  description: |
    API for EKF Group's shipment profitability control system (FM-LS-PROFIT).
    Controls profitability of shipments against Local Estimates (LS), manages
    approval workflows, AI-powered analytics, and integration with 1C:UT.
  version: 1.0.0
  contact:
    name: EKF DIT Architecture
    email: dit@ekfgroup.com

servers:
  - url: https://profit-api.ekf.su/api/v1
    description: Production
  - url: https://profit-api-staging.ekf.su/api/v1
    description: Staging

security:
  - bearerAuth: []

tags:
  - name: Profitability
    description: Shipment profitability calculations and LS management
  - name: Workflow
    description: Approval process management
  - name: Analytics
    description: AI-powered analytics and reporting
  - name: Integration
    description: MDM and external system integration
  - name: Notifications
    description: User notification management
  - name: Auth
    description: Authentication

paths:
  /auth/login:
    post:
      tags: [Auth]
      summary: Authenticate via AD credentials
      security: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [username, password]
              properties:
                username:
                  type: string
                  example: ivanov_aa
                password:
                  type: string
                  format: password
      responses:
        '200':
          description: Login successful
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AuthTokens'
        '401':
          $ref: '#/components/responses/Unauthorized'

  /shipments/{id}/calculate:
    post:
      tags: [Profitability]
      summary: Calculate shipment profitability
      parameters:
        - $ref: '#/components/parameters/ShipmentID'
      responses:
        '200':
          description: Calculation result
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CalculationResult'
        '404':
          $ref: '#/components/responses/NotFound'

  /shipments/{id}/profitability:
    get:
      tags: [Profitability]
      summary: Get profitability data for shipment
      parameters:
        - $ref: '#/components/parameters/ShipmentID'
      responses:
        '200':
          description: Profitability data
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ProfitabilityView'

  /local-estimates/{id}/summary:
    get:
      tags: [Profitability]
      summary: LS profitability summary (plan vs actual)
      parameters:
        - $ref: '#/components/parameters/LSID'
        - name: include_items
          in: query
          schema:
            type: boolean
            default: false
      responses:
        '200':
          description: LS summary
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/LSSummary'

  /approvals:
    post:
      tags: [Workflow]
      summary: Create approval request
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateApprovalRequest'
      responses:
        '201':
          description: Approval created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ApprovalProcess'

  /approvals/{id}/decide:
    post:
      tags: [Workflow]
      summary: Make approval decision
      parameters:
        - $ref: '#/components/parameters/ApprovalID'
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/DecisionRequest'
      responses:
        '200':
          description: Decision recorded
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ApprovalProcess'

  /approvals/queue:
    get:
      tags: [Workflow]
      summary: Get approver's task queue
      parameters:
        - name: priority
          in: query
          schema:
            type: string
            enum: [P1, P2]
        - $ref: '#/components/parameters/CursorParam'
        - $ref: '#/components/parameters/LimitParam'
      responses:
        '200':
          description: Queue items
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PaginatedApprovalQueue'

  /anomalies:
    get:
      tags: [Analytics]
      summary: List detected anomalies
      parameters:
        - name: level
          in: query
          schema:
            type: integer
            enum: [1, 2, 3]
        - name: status
          in: query
          schema:
            type: string
            enum: [open, investigating, resolved, false_positive]
        - $ref: '#/components/parameters/DateFrom'
        - $ref: '#/components/parameters/DateTo'
        - $ref: '#/components/parameters/CursorParam'
        - $ref: '#/components/parameters/LimitParam'
      responses:
        '200':
          description: Anomaly list
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PaginatedAnomalies'

  /ai/ask:
    post:
      tags: [Analytics]
      summary: Ask AI analyst a question
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [question]
              properties:
                question:
                  type: string
                  minLength: 10
                  maxLength: 2000
                  example: "Why did client X have a margin drop of 15pp last week?"
                context_ids:
                  type: array
                  items:
                    type: string
                    format: uuid
                  description: Optional entity IDs for context
      responses:
        '200':
          description: AI response
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/AskResponse'
        '429':
          description: AI daily cost ceiling reached

  /mdm/npss:
    get:
      tags: [Integration]
      summary: Get NPSS for product at date
      parameters:
        - name: product_id
          in: query
          required: true
          schema:
            type: string
            format: uuid
        - name: date
          in: query
          schema:
            type: string
            format: date-time
      responses:
        '200':
          description: NPSS data
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/NPSSView'

components:
  securitySchemes:
    bearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  parameters:
    ShipmentID:
      name: id
      in: path
      required: true
      schema:
        type: string
        format: uuid
    LSID:
      name: id
      in: path
      required: true
      schema:
        type: string
        format: uuid
    ApprovalID:
      name: id
      in: path
      required: true
      schema:
        type: string
        format: uuid
    CursorParam:
      name: cursor
      in: query
      description: Cursor for pagination (opaque string from previous response)
      schema:
        type: string
    LimitParam:
      name: limit
      in: query
      schema:
        type: integer
        minimum: 1
        maximum: 100
        default: 20
    DateFrom:
      name: date_from
      in: query
      schema:
        type: string
        format: date-time
    DateTo:
      name: date_to
      in: query
      schema:
        type: string
        format: date-time

  schemas:
    AuthTokens:
      type: object
      properties:
        access_token:
          type: string
        refresh_token:
          type: string
        expires_in:
          type: integer
          description: Access token TTL in seconds (900 = 15min)
        role:
          type: string
          enum: [manager, rbu, dp, gd, fd]

    CalculationResult:
      type: object
      properties:
        calculation_id:
          type: string
          format: uuid
        shipment_id:
          type: string
          format: uuid
        local_estimate_id:
          type: string
          format: uuid
        planned_profitability:
          type: number
          format: double
          description: Planned LS profitability (%)
        order_profitability:
          type: number
          format: double
        cumulative_plus_order:
          type: number
          format: double
        remainder_profitability:
          type: number
          format: double
        deviation:
          type: number
          format: double
          description: Deviation from plan (percentage points)
        required_level:
          type: string
          enum: [auto, rbu, dp, gd]
        line_items:
          type: array
          items:
            $ref: '#/components/schemas/LineItemCalculation'

    LineItemCalculation:
      type: object
      properties:
        product_id:
          type: string
          format: uuid
        quantity:
          type: number
        price:
          type: number
          description: Price in rubles
        npss:
          type: number
          description: NPSS in rubles
        profitability:
          type: number
        is_blocked:
          type: boolean
        block_reason:
          type: string

    ProfitabilityView:
      type: object
      properties:
        shipment_id:
          type: string
          format: uuid
        local_estimate_id:
          type: string
          format: uuid
        status:
          type: string
        planned_profitability:
          type: number
        order_profitability:
          type: number
        cumulative_plus_order:
          type: number
        remainder_profitability:
          type: number
        deviation:
          type: number
        required_level:
          type: string

    LSSummary:
      type: object
      properties:
        id:
          type: string
          format: uuid
        external_id:
          type: string
        client_name:
          type: string
        planned_profitability:
          type: number
        actual_profitability:
          type: number
        total_amount:
          type: number
        shipped_amount:
          type: number
        fulfillment_rate:
          type: number
        status:
          type: string
        expires_at:
          type: string
          format: date-time
        shipments_count:
          type: integer
        pending_approvals:
          type: integer

    CreateApprovalRequest:
      type: object
      required: [shipment_id, justification]
      properties:
        shipment_id:
          type: string
          format: uuid
        justification:
          type: string
          minLength: 50
          description: Manager's justification (min 50 chars for deviation >= 1pp)

    DecisionRequest:
      type: object
      required: [decision]
      properties:
        decision:
          type: string
          enum: [approved, rejected, approved_with_correction]
        comment:
          type: string
        correction_price:
          type: number
          description: New suggested price (for approved_with_correction)

    ApprovalProcess:
      type: object
      properties:
        id:
          type: string
          format: uuid
        shipment_id:
          type: string
          format: uuid
        state:
          type: string
        required_level:
          type: string
        deviation:
          type: number
        sla_deadline:
          type: string
          format: date-time
        sla_remaining_minutes:
          type: integer
        decision:
          type: string
        approver_name:
          type: string
        mode:
          type: string
          enum: [standard, fallback]
        correction_iteration:
          type: integer

    PaginatedApprovalQueue:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/ApprovalProcess'
        next_cursor:
          type: string
        total:
          type: integer

    PaginatedAnomalies:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/AnomalyView'
        next_cursor:
          type: string
        total:
          type: integer

    AnomalyView:
      type: object
      properties:
        id:
          type: string
          format: uuid
        level:
          type: integer
        score:
          type: number
        description:
          type: string
        affected_entity:
          type: string
        status:
          type: string
        confidence:
          type: number
        detected_at:
          type: string
          format: date-time

    AskResponse:
      type: object
      properties:
        answer:
          type: string
        confidence:
          type: number
        sources:
          type: array
          items:
            type: string
        cost_usd:
          type: number

    NPSSView:
      type: object
      properties:
        product_id:
          type: string
          format: uuid
        npss:
          type: number
          description: NPSS in rubles
        method:
          type: string
          enum: [planned, temporary]
        calculated_at:
          type: string
          format: date-time
        age_days:
          type: integer
        is_stale:
          type: boolean
          description: true if age > 90 days

  responses:
    NotFound:
      description: Resource not found
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ProblemDetail'
    Unauthorized:
      description: Authentication required
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ProblemDetail'
    Forbidden:
      description: Insufficient permissions
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ProblemDetail'
    ProblemDetail:
      description: Error response (RFC 7807)
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ProblemDetail'

    ProblemDetail:
      type: object
      properties:
        type:
          type: string
          format: uri
          example: "https://profit-api.ekf.su/errors/not-found"
        title:
          type: string
          example: "Resource Not Found"
        status:
          type: integer
          example: 404
        detail:
          type: string
          example: "Shipment with ID abc-123 not found"
        instance:
          type: string
          format: uri
```

**Pagination:** Cursor-based (not offset). The `next_cursor` in response is an opaque string encoding the last item's sort key. Client passes it as `?cursor=...` for next page.

**Error format:** RFC 7807 Problem Details. All errors return JSON with `type`, `title`, `status`, `detail`, `instance` fields.

---

## Appendix A. Environment Variables (per service)

| Variable | Service | Default | Description |
|----------|---------|---------|-------------|
| `DATABASE_URL` | all | - | PostgreSQL connection string |
| `REDIS_URL` | profitability, api-gateway | - | Redis connection string |
| `KAFKA_BROKERS` | all except api-gateway | - | Kafka broker addresses |
| `GRPC_PORT` | all | 50051 | gRPC listen port |
| `HTTP_PORT` | all | 8080 | HTTP listen port |
| `JWT_PRIVATE_KEY_PATH` | api-gateway | - | Path to RS256 private key |
| `JWT_PUBLIC_KEY_PATH` | api-gateway | - | Path to RS256 public key |
| `LDAP_URL` | api-gateway | - | AD LDAP server URL |
| `LDAP_BASE_DN` | api-gateway | - | LDAP base DN |
| `AUTH_MFA_ENABLED` | api-gateway | false | Enable 2FA middleware |
| `ELMA_BASE_URL` | workflow | - | ELMA BPM API URL |
| `ELMA_API_KEY` | workflow | - | ELMA API key |
| `AI_MODEL_ANALYST` | analytics | claude-sonnet-4-6-20250514 | Sonnet model ID |
| `AI_MODEL_INVESTIGATOR` | analytics | claude-opus-4-6-20250514 | Opus model ID |
| `ANTHROPIC_API_KEY` | analytics | - | Claude API key |
| `AI_DAILY_COST_CEILING` | analytics | 50.00 | Max daily AI spend ($) |
| `AI_PROMPT_CACHE_ENABLED` | analytics | true | Enable prompt caching |
| `TELEGRAM_BOT_TOKEN` | notification | - | Telegram Bot API token |
| `SMTP_HOST` | notification | - | SMTP server |
| `SMTP_PORT` | notification | 587 | SMTP port |
| `CALLBACK_1C_URL` | notification | - | 1C push callback URL |
| `OTEL_EXPORTER_ENDPOINT` | all | - | OpenTelemetry collector |
| `LOG_LEVEL` | all | info | Log level |
| `SHUTDOWN_TIMEOUT` | all | 30s | Graceful shutdown timeout |
