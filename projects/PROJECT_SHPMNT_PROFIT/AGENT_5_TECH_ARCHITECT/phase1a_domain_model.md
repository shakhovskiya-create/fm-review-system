# Domain Model (DDD) -- profitability-service

**Проект:** FM-LS-PROFIT (Контроль рентабельности отгрузок по ЛС)
**Версия ФМ:** 1.0.7
**Дата:** 01.03.2026
**Автор:** Шаховский А.С.
**Платформа:** Go + React (Clean Architecture)
**Стек:** chi, sqlc, franz-go, Wire, connect-go, anthropic-sdk-go, shopspring/decimal

---

## Содержание

1. [Bounded Contexts](#1-bounded-contexts)
2. [Aggregates](#2-aggregates)
3. [Value Objects](#3-value-objects)
4. [Domain Events](#4-domain-events)
5. [Domain Services](#5-domain-services)
6. [Business Rules](#6-business-rules)
7. [Sagas](#7-sagas)
8. [AI Analytics Aggregate](#8-ai-analytics-aggregate)
9. [Read Models / Projections](#9-read-models--projections)
10. [Integration Contracts](#10-integration-contracts)
11. [Traceability Matrix](#11-traceability-matrix)

---

## 1. Bounded Contexts

```
+---------------------+    +---------------------+    +---------------------+
|  Profitability       |    |  Workflow            |    |  Analytics           |
|  Context             |    |  Context             |    |  Context             |
|                      |    |                      |    |                      |
|  - LocalEstimate     |    |  - ApprovalProcess   |    |  - AnomalyDetection  |
|  - Shipment          |    |  - SLATracking       |    |  - Investigation     |
|  - ProfitCalc        |    |  - ApprovalQueue     |    |  - Forecast          |
|  - PriceSheet        |    |  - EmergencyApproval |    |  - Report            |
+----------+-----------+    +----------+-----------+    +----------+-----------+
           |                           |                           |
           +---------------------------+---------------------------+
                                       |
                          +------------+------------+
                          |  Integration Context    |
                          |                         |
                          |  - Client (MDM)         |
                          |  - Product (MDM)        |
                          |  - ExchangeRate         |
                          |  - Sanction             |
                          +-------------------------+
```

**Взаимодействие между контекстами:**

| Из | В | Способ | Паттерн |
|----|---|--------|---------|
| Profitability | Workflow | Domain Events (Kafka) | Published Language |
| Workflow | Profitability | Domain Events (Kafka) | Published Language |
| Profitability | Analytics | Domain Events (Kafka) | Published Language |
| Integration | Profitability | gRPC (sync read), Kafka (async update) | Anti-Corruption Layer |
| Integration | Workflow | gRPC (sync read) | Anti-Corruption Layer |
| Integration | Analytics | Kafka (async update) | Published Language |

---

## 2. Aggregates

### 2.1. LocalEstimate (Локальная Смета)

**Bounded Context:** Profitability
**Описание:** Центральная сущность. Плановая рентабельность ЛС, позиции с зафиксированной НПСС, жизненный цикл.

**Invariants:**
- INV-LE-01: Плановая рентабельность фиксируется при создании и изменяется только при явном пересчете (с аудит-логом)
- INV-LE-02: НПСС позиций фиксируются на момент создания ЛС (snapshot, не ссылка)
- INV-LE-03: Количество продлений не более 2
- INV-LE-04: При НПСС > 90 дней -- блокировка согласования (не самой ЛС)
- INV-LE-05: Максимум 1000 позиций в одной ЛС
- INV-LE-06: Максимум 50 Заказов на согласовании по одной ЛС

```go
package domain

import (
    "time"

    "github.com/google/uuid"
)

// LocalEstimate -- агрегат Локальная Смета.
// Хранит плановую рентабельность и зафиксированные позиции.
type LocalEstimate struct {
    ID                   uuid.UUID
    ExternalID           string // код ЛС из 1С (Строка(11))
    ClientID             uuid.UUID
    ManagerID            uuid.UUID
    BusinessUnitID       uuid.UUID
    CreatedAt            time.Time
    ExpiresAt            time.Time
    Status               LocalEstimateStatus
    PlannedProfitability Percentage
    TotalAmount          Money
    RenewalCount         int // макс. 2
    NPSSFixedAt          time.Time
    AdvisoryControl      bool // рекомендательный контроль при план. рент. < 5%
    LineItems            []LocalEstimateLineItem
    Version              int // оптимистичная блокировка

    // domain events (uncommitted)
    events []DomainEvent
}

type LocalEstimateLineItem struct {
    ID             uuid.UUID
    ProductID      uuid.UUID
    Quantity       Quantity // shopspring/decimal, NUMERIC(18,6) в БД
    Price          Money
    Amount         Money
    NPSS           Money // зафиксированная НПСС
    Profitability  Percentage
    MinAllowedPrice Money // НПСС / (1 - PlannedProfit/100)
    BusinessUnitID uuid.UUID
}

type LocalEstimateStatus string

const (
    LSStatusActive    LocalEstimateStatus = "active"
    LSStatusExpired   LocalEstimateStatus = "expired"
    LSStatusClosed    LocalEstimateStatus = "closed"
    LSStatusCancelled LocalEstimateStatus = "cancelled"
)
```

**Lifecycle:**
```
Created --> [Active] --> [Expired] --> [Closed]
               |              |
           [Closed]     Renewal --> [Active]  (max 2)
               |
        (full shipment)

Created --> [Active] --> [Cancelled]  (0 shipments)
```

**Domain Events:**
- `LocalEstimateCreated`
- `LocalEstimatePlanChanged` (triggers cross-validation)
- `LocalEstimateExpired`
- `LocalEstimateClosed`
- `LocalEstimateRenewed`

---

### 2.2. Shipment (Отгрузка / Заказ клиента)

**Bounded Context:** Profitability
**Описание:** Заказ клиента по ЛС. Содержит расчет рентабельности, статус контроля, обоснование.

**Invariants:**
- INV-SH-01: Рентабельность пересчитывается при каждом изменении состава/цен
- INV-SH-02: Обоснование обязательно при отклонении >= 1 п.п. (мин. 50 символов)
- INV-SH-03: После установки ПереданНаСклад -- согласование не аннулируется (точка невозврата)
- INV-SH-04: Срок действия согласования -- 5 рабочих дней
- INV-SH-05: При >= 3 аннулированиях -- эскалация на ДП
- INV-SH-06: Черновик удаляется через 7 дней без действий

```go
// Shipment -- агрегат Заказ клиента (отгрузка по ЛС).
type Shipment struct {
    ID                    uuid.UUID
    ExternalID            string // номер Заказа из 1С
    LocalEstimateID       uuid.UUID
    ClientID              uuid.UUID
    ManagerID             uuid.UUID
    Status                ShipmentStatus
    Priority              OrderPriority
    Source                 OrderSource // Manual / EDI

    // Расчетные показатели рентабельности
    OrderProfitability    Percentage   // рентабельность данного Заказа
    CumulativePlusOrder   Percentage   // (Накопленная + Заказ)
    RemainderProfitability Percentage  // рентабельность остатка ЛС
    Deviation             Percentage   // отклонение от плана (п.п.)
    RequiredApprovalLevel *ApprovalLevel // nil = не требуется

    // Согласование
    ApprovalType          ApprovalType // Standard / Emergency / PostFactum
    ApproverName          string
    ApprovedAt            *time.Time
    ApprovalExpiresAt     *time.Time // +5 рабочих дней
    ApprovalDecision      *ApprovalDecisionValue
    ApproverComment       string
    Justification         string // обоснование менеджера (мин. 50 символов)

    // Контроль
    HandedToWarehouse     bool      // точка невозврата
    HandedToWarehouseAt   *time.Time
    CancellationCount     int       // >= 3 -- эскалация на ДП
    CorrectionIteration   int       // текущая итерация корректировки (макс. 5)
    DraftCreatedAt        time.Time // для автоудаления (7 дней)

    LineItems             []ShipmentLineItem
    Version               int
    events                []DomainEvent
}

type ShipmentLineItem struct {
    ID                uuid.UUID
    ProductID         uuid.UUID
    Quantity          Quantity // shopspring/decimal, NUMERIC(18,6) в БД
    Price             Money
    Amount            Money
    NPSS              Money    // из ЛС (зафиксированная)
    Profitability     Percentage
    MinAllowedPrice   Money
    BusinessUnitID    uuid.UUID
    IsNonLiquid       bool     // неликвид (исключается из контроля)
    PriceDeviationPct Percentage // расхождение с ценой ЛС
}

type ShipmentStatus string

const (
    ShipmentDraft             ShipmentStatus = "draft"
    ShipmentAwaitingStock     ShipmentStatus = "awaiting_stock"
    ShipmentPendingApproval   ShipmentStatus = "pending_approval"
    ShipmentRejected          ShipmentStatus = "rejected"
    ShipmentApprovalExpired   ShipmentStatus = "approval_expired"
    ShipmentPartiallyApproved ShipmentStatus = "partially_approved" // мульти-БЮ
    ShipmentApproved          ShipmentStatus = "approved"
    ShipmentInProgress        ShipmentStatus = "in_progress"
    ShipmentFulfilled         ShipmentStatus = "fulfilled"
    ShipmentPartiallyClosed   ShipmentStatus = "partially_closed"
    ShipmentOverdue           ShipmentStatus = "overdue" // 7 дней без действий
    ShipmentCancelled         ShipmentStatus = "cancelled"
)

type OrderPriority string

const (
    PriorityP1 OrderPriority = "P1" // > 500 т.р. или экстренные
    PriorityP2 OrderPriority = "P2" // стандартные
)

type OrderSource string

const (
    OrderSourceManual OrderSource = "manual"
    OrderSourceEDI    OrderSource = "edi"
)

type ApprovalType string

const (
    ApprovalStandard  ApprovalType = "standard"
    ApprovalEmergency ApprovalType = "emergency"
    ApprovalPostFactum ApprovalType = "post_factum"
)
```

**Lifecycle (State Machine):**
```
[Draft] --> [PendingApproval] --> [Approved] --> [InProgress] --> [Fulfilled]
  |              |                    |                             |
  |              v                    v                             v
  |         [Rejected]-->[Draft]  [ApprovalExpired]-->[Draft]   [PartiallyClosed]
  |
  v
[AwaitingStock] --> [PendingApproval]
  |
  v
[Overdue] (7 дней без действий)

[Cancelled] (из Draft, Rejected, ApprovalExpired)

Multi-BU: [PendingApproval] --> [PartiallyApproved] --> [Approved]
                                       |
                                  [Draft] (позиции удалены)

Cross-validation:
[Approved] --> [PendingApproval] (при снижении плана ЛС, если уровень изменился)
```

**Domain Events:**
- `ShipmentCreated`
- `ShipmentUpdated`
- `ShipmentProfitabilityCalculated`
- `ShipmentSubmittedForApproval`
- `ShipmentApproved`
- `ShipmentRejected`
- `ShipmentApprovalExpired`
- `ShipmentApprovalRevoked` (cross-validation)
- `ShipmentHandedToWarehouse` (point of no return)
- `ShipmentFulfilled`
- `ShipmentCancelled`
- `ShipmentDraftExpired` (7 days)

---

### 2.3. ApprovalProcess (Процесс согласования)

**Bounded Context:** Workflow
**Описание:** Маршрутизация согласования через 4-уровневую матрицу. Интеграция с ELMA BPM. Резервный режим.

**Invariants:**
- INV-AP-01: Матрица уровней: < 1 п.п. = авто, 1-15 = РБЮ, 15.01-25 = ДП, > 25 = ГД
- INV-AP-02: SLA определяется уровнем и приоритетом (P1/P2/< 100 т.р.)
- INV-AP-03: При превышении SLA -- автоэскалация на следующий уровень
- INV-AP-04: Автоотказ после SLA ГД (48 часов)
- INV-AP-05: Лимит итераций корректировки цены: 5 (при 6-й -- автоотказ)
- INV-AP-06: Агрегированный лимит автосогласования: 20 000 руб/день на менеджера, 100 000 руб/день на БЮ
- INV-AP-07: При недоступности ELMA -- резервный режим (до 5 п.п. авто, свыше -- очередь FIFO)

```go
// ApprovalProcess -- агрегат процесса согласования.
type ApprovalProcess struct {
    ID                    uuid.UUID
    ShipmentID            uuid.UUID
    LocalEstimateID       uuid.UUID
    InitiatorID           uuid.UUID // менеджер
    Deviation             Percentage
    RequiredLevel         ApprovalLevel
    Priority              OrderPriority
    SLADeadline           SLADeadline
    CurrentApproverID     *uuid.UUID
    Decision              *ApprovalDecisionValue
    ApproverComment       string
    IsResubmission        bool
    AttemptNumber         int
    Mode                  ApprovalMode // Standard / Fallback
    CrossValidationReason string       // при возврате из-за перекрестного контроля
    CorrectionIteration   int          // текущая итерация корректировки (макс. 5)

    // Мульти-БЮ
    BUApprovals           []BUApproval

    // История маршрутизации
    RoutingHistory        []RoutingStep

    CreatedAt             time.Time
    ResolvedAt            *time.Time
    Version               int
    events                []DomainEvent
}

type BUApproval struct {
    BusinessUnitID uuid.UUID
    ApproverID     uuid.UUID
    Decision       *ApprovalDecisionValue
    DecidedAt      *time.Time
    Comment        string
}

type RoutingStep struct {
    StepNumber   int
    ApproverID   uuid.UUID
    AssignedAt   time.Time
    DecidedAt    *time.Time
    Decision     *ApprovalDecisionValue
    SLABreached  bool
    Comment      string
}

type ApprovalLevel string

const (
    LevelAuto ApprovalLevel = "auto"
    LevelRBU  ApprovalLevel = "rbu"   // 1.00 - 15.00 п.п.
    LevelDRP  ApprovalLevel = "drp"   // Директор ДРП (эскалация от РБЮ)
    LevelDP   ApprovalLevel = "dp"    // 15.01 - 25.00 п.п.
    LevelGD   ApprovalLevel = "gd"    // > 25.00 п.п.
)

type ApprovalMode string

const (
    ModeStandard ApprovalMode = "standard"
    ModeFallback ApprovalMode = "fallback" // ELMA недоступна
)
```

**Lifecycle:**
```
[Created] --> [AutoApproved]  (deviation < 1.00 п.п. AND within limits)
    |
    +--> [RoutingToRBU] --> [PendingRBU] --> [ApprovedByRBU]
    |                           |                  |
    |                     [RejectedByRBU]     [CorrectionRequested] (max 5)
    |                           |                  |
    |                      [Returned]        [RoutingBack] --> [PendingRBU]
    |
    +--> [RoutingToDP] --> [PendingDP] --> [ApprovedByDP]
    |                          |
    |                    [RejectedByDP]
    |
    +--> [RoutingToGD] --> [PendingGD] --> [ApprovedByGD]
                               |
                         [AutoRejected] (SLA timeout 48h)

Escalation:
[PendingRBU] --SLA timeout--> [PendingDRP]
[PendingDP]  --SLA timeout--> [PendingGD]
[PendingGD]  --SLA timeout--> [AutoRejected] + CFO notification

Fallback (ELMA unavailable):
[Created] --> [FallbackAutoApproved] (deviation <= 5.00 п.п.)
    |
    +--> [FallbackQueued] --> [SentToELMA] (при восстановлении)
```

**Domain Events:**
- `ApprovalProcessCreated`
- `ApprovalAutoApproved`
- `ApprovalRoutedToApprover`
- `ApprovalDecisionMade`
- `ApprovalEscalated`
- `ApprovalSLABreached`
- `ApprovalAutoRejected`
- `ApprovalCorrectionRequested`
- `ApprovalCorrectionLimitReached` (5 итераций)
- `ApprovalFallbackActivated`
- `ApprovalFallbackQueueDrained`

---

### 2.4. ProfitabilityCalculation (Расчет рентабельности)

**Bounded Context:** Profitability
**Описание:** Расчет рентабельности по формулам ФМ. Хранение снимков расчетов.

**Invariants:**
- INV-PC-01: Рентабельность позиции = (Цена - НПСС) / Цена * 100%
- INV-PC-02: (Накопленная + Заказ) = (Выручка_отгруж + Выручка_заказа - Себест_отгруж - Себест_заказа) / (Выручка_отгруж + Выручка_заказа) * 100%
- INV-PC-03: Рентабельность остатка = SUM((Цена_i - НПСС_i) * Кол_i) / SUM(Цена_i * Кол_i) * 100% (неотгруженные за вычетом заказов "На согласовании" и "Согласован")
- INV-PC-04: Отклонение = Рент_ЛС(план) - MAX(Накопленная+Заказ, Рент_остатка), округление до 2 знаков ДО сравнения с границами
- INV-PC-05: НПСС = 0 или NULL блокирует позицию
- INV-PC-06: Цена = 0 блокирует позицию

```go
// ProfitabilityCalculation -- агрегат расчета рентабельности.
type ProfitabilityCalculation struct {
    ID                       uuid.UUID
    LocalEstimateID          uuid.UUID
    ShipmentID               uuid.UUID
    CalculatedAt             time.Time

    // Результаты расчета
    PlannedProfitability     Percentage   // план ЛС
    OrderProfitability       Percentage   // рент. данного заказа
    CumulativeProfitability  Percentage   // накопленная факт
    CumulativePlusOrder      Percentage   // (накопленная + заказ)
    RemainderProfitability   Percentage   // рент. остатка
    Deviation                Percentage   // отклонение от плана

    // Компоненты расчета
    ShippedRevenue           Money        // выручка отгруженного (нетто)
    ShippedCostNPSS          Money        // себестоимость отгруженного по НПСС
    OrderRevenue             Money        // выручка текущего заказа
    OrderCostNPSS            Money        // себестоимость заказа по НПСС
    RemainderRevenue         Money        // выручка неотгруженного остатка
    RemainderCostNPSS        Money        // себестоимость остатка по НПСС

    // Детализация по позициям
    LineItemResults          []LineItemCalculation

    Version                  int
    events                   []DomainEvent
}

type LineItemCalculation struct {
    ProductID     uuid.UUID
    Quantity      Quantity // shopspring/decimal, NUMERIC(18,6) в БД
    Price         Money
    NPSS          Money
    Profitability Percentage
    IsBlocked     bool    // НПСС=0 или Цена=0
    BlockReason   string
}
```

**Domain Events:**
- `ProfitabilityCalculated`
- `ThresholdViolated` (deviation >= 1.00 п.п.)
- `LineItemBlocked` (НПСС=0 или Цена=0)

---

### 2.5. Client (Контрагент)

**Bounded Context:** Integration (MDM)
**Описание:** Контрагент с историей, статусом стратегичности и санкциями.

**Invariants:**
- INV-CL-01: Стратегический клиент -- критерии: (а) оборот >= 10 млн, (б) реестр ДРП, (в) контракт >= 1 млн
- INV-CL-02: Отмена санкций для стратегических -- макс. 3 раза в год
- INV-CL-03: Актуализация стратегических -- ежеквартально

```go
// Client -- агрегат Контрагент (MDM).
type Client struct {
    ID                    uuid.UUID
    ExternalID            string // код из 1С
    Name                  string
    IsStrategic           bool
    StrategicCriteria     *StrategicCriteria
    StrategicSince        *time.Time
    AllowedDeviation      Percentage // допустимое отклонение от стандартных порогов
    SanctionCancelCount   int        // количество отмен санкций за текущий год (макс. 3)
    ManagerID             uuid.UUID
    BusinessUnitID        uuid.UUID

    // Temporal (MDM)
    ValidFrom             time.Time
    ValidTo               *time.Time // nil = текущая запись

    Version               int
    events                []DomainEvent
}

type StrategicCriteria string

const (
    StrategicByRevenue  StrategicCriteria = "revenue_over_10m"
    StrategicByDRP      StrategicCriteria = "drp_registry"
    StrategicByContract StrategicCriteria = "contract_over_1m"
)
```

**Domain Events:**
- `ClientUpdated`
- `ClientMarkedStrategic`
- `ClientStrategicRevoked`

---

### 2.6. Sanction (Санкции за невыкуп)

**Bounded Context:** Integration
**Описание:** Санкции за невыкуп ЛС. Этап 2 (P2), но домен проектируется сейчас.

**Invariants:**
- INV-SN-01: Типы санкций: снижение скидки 3 п.п. -> 10 п.п. -> только стандартные цены
- INV-SN-02: Санкции кумулятивны (суммируются)
- INV-SN-03: Реабилитация через 6 месяцев без нарушений
- INV-SN-04: ДП может отменить санкцию (с обоснованием)
- INV-SN-05: Для стратегических клиентов -- отмена макс. 3 раза в год

```go
// Sanction -- агрегат Санкция за невыкуп ЛС.
type Sanction struct {
    ID                 uuid.UUID
    ClientID           uuid.UUID
    Type               SanctionType
    DiscountReduction  Percentage // снижение макс. скидки (п.п.)
    CumulativeReduction Percentage // суммарное снижение (кумулятивно)
    TriggerLSID        uuid.UUID  // ЛС, ставшая причиной
    FulfillmentRate    Percentage // % выкупа по причинной ЛС
    AppliedAt          time.Time
    RehabilitationAt   time.Time  // +6 месяцев
    CancelledByDP      bool
    CancellationReason string
    Status             SanctionStatus

    Version            int
    events             []DomainEvent
}

type SanctionType string

const (
    SanctionNone          SanctionType = "none"
    SanctionDiscount3     SanctionType = "discount_reduction_3pp"
    SanctionDiscount10    SanctionType = "discount_reduction_10pp"
    SanctionStandardOnly  SanctionType = "standard_prices_only"
)

type SanctionStatus string

const (
    SanctionActive        SanctionStatus = "active"
    SanctionRehabilitated SanctionStatus = "rehabilitated"
    SanctionCancelled     SanctionStatus = "cancelled"
)
```

**Lifecycle:**
```
[Warning] --> [Active] --> [Rehabilitated] (6 мес. без нарушений)
                 |
            [Cancelled] (решение ДП)
```

**Domain Events:**
- `SanctionWarningIssued`
- `SanctionApplied`
- `SanctionEscalated` (3 п.п. -> 10 п.п. -> стандартные цены)
- `SanctionRehabilitated`
- `SanctionCancelledByDP`

---

### 2.7. PriceSheet (НПСС / Шкала себестоимости)

**Bounded Context:** Profitability
**Описание:** Нормативная плановая себестоимость. Включает автотриггеры пересчета.

**Invariants:**
- INV-PS-01: НПСС = ЦЗсредняя * ТТК_страна (формула из SBS-58)
- INV-PS-02: ЦЗсредняя = средневзвешенная цена закупки за 6 месяцев
- INV-PS-03: Автотриггер: курс ЦБ РФ изменился > 5% за 7 дней -> автопересчет
- INV-PS-04: Автотриггер: закупочная цена отклонилась > 15% от НПСС -> пересмотр 5 р.д.
- INV-PS-05: Возраст НПСС > 90 дней -> блокировка согласования
- INV-PS-06: При фиксации НПСС в ЛС -- snapshot (не ссылка)

```go
// PriceSheet -- агрегат НПСС (нормативная плановая себестоимость).
type PriceSheet struct {
    ID              uuid.UUID
    ProductID       uuid.UUID
    NPSS            Money
    PurchasePrice   Money      // компонент: закупочная цена
    LogisticsCost   Money      // компонент: логистика
    OverheadCost    Money      // компонент: накладные
    CalculatedAt    time.Time
    CalculatedBy    uuid.UUID
    Method          NPSSMethod // Planned / Temporary (last purchase * 1.1)
    Trigger         NPSSTrigger // Planned / ExchangeRate / PurchasePrice / Manual

    // Temporal (MDM)
    ValidFrom       time.Time
    ValidTo         *time.Time

    Version         int
    events          []DomainEvent
}

type NPSSMethod string

const (
    NPSSMethodPlanned   NPSSMethod = "planned"
    NPSSMethodTemporary NPSSMethod = "temporary" // последняя закупка * 1.1
)

type NPSSTrigger string

const (
    NPSSTriggerPlanned       NPSSTrigger = "planned"       // ежеквартально
    NPSSTriggerExchangeRate  NPSSTrigger = "exchange_rate"  // курс ЦБ > 5%
    NPSSTriggerPurchasePrice NPSSTrigger = "purchase_price" // закупочная > 15%
    NPSSTriggerManual        NPSSTrigger = "manual"
)
```

**Domain Events:**
- `PriceSheetUpdated`
- `PriceSheetTriggeredByExchangeRate` (курс ЦБ > 5%)
- `PriceSheetTriggeredByPurchasePrice` (закупочная > 15%)
- `PriceSheetStale` (возраст > 90 дней)

---

### 2.8. EmergencyApproval (Экстренное согласование)

**Bounded Context:** Workflow
**Описание:** Фиксация экстренного (внесистемного) согласования. Постфактум-контроль.

**Invariants:**
- INV-EA-01: Уполномоченное лицо должно быть в справочнике и активно
- INV-EA-02: Лимит экстренных: 3/мес на менеджера, 5/мес на контрагента (пиковые: 5/8)
- INV-EA-03: Подтверждение постфактум в ELMA обязательно в течение 24 часов
- INV-EA-04: При неподтверждении через 48 часов -- эскалация на ДП + запись нарушения
- INV-EA-05: До 10 экстренных/мес в пиковые периоды (декабрь, август)

```go
// EmergencyApproval -- агрегат Экстренное согласование.
type EmergencyApproval struct {
    ID                     uuid.UUID
    ShipmentID             uuid.UUID
    ManagerID              uuid.UUID
    AuthorizedPersonID     uuid.UUID
    Reason                 string
    DocumentaryProof       string
    CommunicationChannel   string // phone / messenger / in_person
    ObtainedAt             time.Time
    PostFactumConfirmed    bool
    PostFactumConfirmedAt  *time.Time
    ConfirmationStatus     ConfirmationStatus
    Check24h               bool // прошла ли автопроверка 24ч
    Check48h               bool // прошла ли расширенная проверка 48ч
    IncidentRegistered     bool
    CreatedAt              time.Time

    Version                int
    events                 []DomainEvent
}

type ConfirmationStatus string

const (
    ConfirmationPending  ConfirmationStatus = "pending"
    ConfirmationApproved ConfirmationStatus = "approved"
    ConfirmationRejected ConfirmationStatus = "rejected"
)
```

**Domain Events:**
- `EmergencyApprovalCreated`
- `EmergencyApprovalConfirmed`
- `EmergencyApprovalRejected`
- `EmergencyApprovalCheck24hFailed`
- `EmergencyApprovalEscalated48h`

---

## 3. Value Objects

### 3.1. Money

```go
// Money -- неизменяемый объект денежной суммы.
// Precision: 2 знака после запятой. Все операции округляют до копеек.
// Overflow protection: все арифметические операции проверяют переполнение int64
// и возвращают ошибку вместо silent wrap-around.
// Максимальное значение: math.MaxInt64 / 100 = 92 233 720 368 547 758.07 руб.
type Money struct {
    amount int64  // в копейках (centesimal)
    // currency всегда RUB для данного домена
}

// MaxMoneyCents -- максимальное значение в копейках (math.MaxInt64).
const MaxMoneyCents int64 = math.MaxInt64 // 9_223_372_036_854_775_807

func NewMoney(rubles float64) (Money, error) {
    if rubles < 0 {
        return Money{}, ErrNegativeMoney
    }
    cents := math.Round(rubles * 100)
    if cents > float64(MaxMoneyCents) {
        return Money{}, ErrMoneyOverflow
    }
    return Money{amount: int64(cents)}, nil
}

func NewMoneyFromCents(cents int64) (Money, error) {
    if cents < 0 {
        return Money{}, ErrNegativeMoney
    }
    return Money{amount: cents}, nil
}

func (m Money) Amount() float64 {
    return float64(m.amount) / 100
}

func (m Money) AmountCents() int64 {
    return m.amount
}

// Add складывает две суммы с проверкой переполнения.
// Возвращает ErrMoneyOverflow если результат > MaxInt64 копеек.
func (m Money) Add(other Money) (Money, error) {
    result := m.amount + other.amount
    // Проверка переполнения: если оба слагаемых положительны,
    // результат не может быть меньше любого из них.
    if m.amount > 0 && other.amount > 0 && result < m.amount {
        return Money{}, ErrMoneyOverflow
    }
    return Money{amount: result}, nil
}

// Subtract вычитает сумму с проверкой на отрицательный результат.
func (m Money) Subtract(other Money) (Money, error) {
    result := m.amount - other.amount
    if result < 0 {
        return Money{}, ErrNegativeMoney
    }
    return Money{amount: result}, nil
}

// Multiply умножает на коэффициент с проверкой переполнения.
// Используется decimal-арифметика промежуточного результата для точности.
// Возвращает ErrMoneyOverflow если результат > MaxInt64 копеек.
func (m Money) Multiply(factor float64) (Money, error) {
    if factor < 0 {
        return Money{}, ErrNegativeMultiplier
    }
    product := float64(m.amount) * factor
    rounded := math.Round(product)
    if rounded > float64(MaxMoneyCents) || math.IsInf(product, 0) || math.IsNaN(product) {
        return Money{}, ErrMoneyOverflow
    }
    return Money{amount: int64(rounded)}, nil
}

func (m Money) IsZero() bool {
    return m.amount == 0
}

func (m Money) Equals(other Money) bool {
    return m.amount == other.amount
}

func (m Money) GreaterThan(other Money) bool {
    return m.amount > other.amount
}

func (m Money) LessOrEqual(other Money) bool {
    return m.amount <= other.amount
}
```

### 3.2. Quantity

```go
// Quantity -- неизменяемый объект количества товара.
// Использует shopspring/decimal для точных финансовых вычислений:
// float64 имеет лишь 15-17 значащих цифр (IEEE 754), что приводит
// к rounding errors при умножении цена * количество.
// Пример: float64(0.1 + 0.2) != 0.3 (= 0.30000000000000004).
//
// Precision: 6 знаков после запятой (позволяет дробные единицы:
// метры, кг, литры и т.п.).
// DB: NUMERIC(18,6) -- точное хранение без потери точности.
//
// Зависимость: github.com/shopspring/decimal
import "github.com/shopspring/decimal"

type Quantity struct {
    value decimal.Decimal
}

// NewQuantity создает количество из строки (предпочтительный способ).
// Принимает: "1.5", "100", "0.000001".
// Не допускает отрицательные и нулевые значения.
func NewQuantity(s string) (Quantity, error) {
    d, err := decimal.NewFromString(s)
    if err != nil {
        return Quantity{}, ErrInvalidQuantity
    }
    if d.LessThanOrEqual(decimal.Zero) {
        return Quantity{}, ErrNonPositiveQuantity
    }
    return Quantity{value: d.Round(6)}, nil
}

// NewQuantityFromFloat создает количество из float64 (для обратной совместимости
// с данными из 1С, где количество передается как число).
// ВНИМАНИЕ: используй NewQuantity(string) когда возможно, чтобы избежать
// потери точности при конвертации float64 -> decimal.
func NewQuantityFromFloat(f float64) (Quantity, error) {
    d := decimal.NewFromFloat(f)
    if d.LessThanOrEqual(decimal.Zero) {
        return Quantity{}, ErrNonPositiveQuantity
    }
    return Quantity{value: d.Round(6)}, nil
}

// Float64 возвращает значение как float64 (для Kafka payload / JSON).
// Используется ТОЛЬКО для сериализации, не для расчетов.
func (q Quantity) Float64() float64 {
    f, _ := q.value.Float64()
    return f
}

// String возвращает строковое представление (для логов, отладки).
func (q Quantity) String() string {
    return q.value.String()
}

// Decimal возвращает внутреннее значение для расчетов.
func (q Quantity) Decimal() decimal.Decimal {
    return q.value
}

// MultiplyByMoney -- Количество * Цена = Сумма (Money).
// Результат округляется до копеек (2 знака).
// Пример: Quantity("1.5") * Money(10000 коп) = Money(15000 коп)
func (q Quantity) MultiplyByMoney(price Money) (Money, error) {
    priceDec := decimal.NewFromInt(price.AmountCents())
    resultDec := q.value.Mul(priceDec).Round(0) // округление до копеек
    if !resultDec.IsPositive() && !resultDec.IsZero() {
        return Money{}, ErrNegativeMoney
    }
    // Проверка переполнения int64
    if resultDec.GreaterThan(decimal.NewFromInt(MaxMoneyCents)) {
        return Money{}, ErrMoneyOverflow
    }
    return NewMoneyFromCents(resultDec.IntPart())
}

// Equals проверяет равенство с точностью до 6 знаков.
func (q Quantity) Equals(other Quantity) bool {
    return q.value.Equal(other.value)
}
```

### 3.3. Percentage

```go
// Percentage -- неизменяемый процент с точностью 2 знака.
// Для маржинальности: допускает отрицательные значения (убыток).
// Для отклонений: знак определяет направление (положительное = снижение маржи).
type Percentage struct {
    basis int64 // в сотых долях процента (basis points * 100)
}

func NewPercentage(value float64) Percentage {
    return Percentage{basis: int64(math.Round(value * 100))}
}

func NewPercentageFromBasisPoints(bp int64) Percentage {
    return Percentage{basis: bp}
}

func (p Percentage) Value() float64 {
    return float64(p.basis) / 100
}

// RoundedValue -- значение, округленное до 2 знаков.
// Используется ДО сравнения с границами (INV-PC-04).
func (p Percentage) RoundedValue() float64 {
    return math.Round(float64(p.basis)/100*100) / 100
}

func (p Percentage) BasisPoints() int64 {
    return p.basis
}

func (p Percentage) IsNegative() bool {
    return p.basis < 0
}

func (p Percentage) GreaterThan(other Percentage) bool {
    return p.basis > other.basis
}

func (p Percentage) LessOrEqual(other Percentage) bool {
    return p.basis <= other.basis
}

func (p Percentage) Subtract(other Percentage) Percentage {
    return Percentage{basis: p.basis - other.basis}
}

func (p Percentage) Equals(other Percentage) bool {
    return p.basis == other.basis
}
```

### 3.3. SLADeadline

```go
// SLADeadline -- неизменяемый срок SLA.
// Определяется по матрице: уровень согласования * приоритет.
type SLADeadline struct {
    hours       int
    priority    OrderPriority
    level       ApprovalLevel
    startedAt   time.Time
    deadline    time.Time
}

// NewSLADeadline создает SLA по матрице из ФМ.
//
// Матрица SLA (рабочие часы):
//   | Уровень | SLA P1 | SLA P2 | SLA <100тр |
//   |---------|--------|--------|------------|
//   | РБЮ     | 4ч     | 24ч    | 2ч         |
//   | ДП      | 8ч     | 48ч    | 4ч         |
//   | ГД      | 24ч    | 72ч    | 12ч        |
func NewSLADeadline(level ApprovalLevel, priority OrderPriority, isSmallOrder bool, startedAt time.Time) SLADeadline {
    hours := slaMatrix(level, priority, isSmallOrder)
    return SLADeadline{
        hours:    hours,
        priority: priority,
        level:    level,
        startedAt: startedAt,
        deadline:  addBusinessHours(startedAt, hours),
    }
}

func (s SLADeadline) Hours() int            { return s.hours }
func (s SLADeadline) Deadline() time.Time   { return s.deadline }
func (s SLADeadline) StartedAt() time.Time  { return s.startedAt }

func (s SLADeadline) IsBreached(now time.Time) bool {
    return now.After(s.deadline)
}

func (s SLADeadline) RemainingMinutes(now time.Time) int {
    if s.IsBreached(now) {
        return 0
    }
    return int(s.deadline.Sub(now).Minutes())
}

func (s SLADeadline) EscalationThreshold() time.Time {
    // Автоэскалация при 80% SLA
    eightyPct := time.Duration(float64(s.deadline.Sub(s.startedAt)) * 0.8)
    return s.startedAt.Add(eightyPct)
}

func (s SLADeadline) Equals(other SLADeadline) bool {
    return s.hours == other.hours && s.priority == other.priority && s.level == other.level
}

func slaMatrix(level ApprovalLevel, priority OrderPriority, isSmallOrder bool) int {
    if isSmallOrder { // < 100 т.р.
        switch level {
        case LevelRBU: return 2
        case LevelDP:  return 4
        case LevelGD:  return 12
        default:       return 0
        }
    }
    switch {
    case level == LevelRBU && priority == PriorityP1: return 4
    case level == LevelRBU && priority == PriorityP2: return 24
    case level == LevelDP && priority == PriorityP1:  return 8
    case level == LevelDP && priority == PriorityP2:  return 48
    case level == LevelGD && priority == PriorityP1:  return 24
    case level == LevelGD && priority == PriorityP2:  return 72
    default: return 0
    }
}
```

### 3.4. ProfitabilityThreshold

```go
// ProfitabilityThreshold -- порог маржинальности для определения уровня согласования.
type ProfitabilityThreshold struct {
    autoApproveLimit     Percentage   // < 1.00 п.п. = автосогласование
    rbuUpperBound        Percentage   // 1.00 - 15.00 п.п. = РБЮ
    dpUpperBound         Percentage   // 15.01 - 25.00 п.п. = ДП
    // > 25.00 п.п. = ГД
}

func DefaultProfitabilityThreshold() ProfitabilityThreshold {
    return ProfitabilityThreshold{
        autoApproveLimit: NewPercentage(1.00),
        rbuUpperBound:    NewPercentage(15.00),
        dpUpperBound:     NewPercentage(25.00),
    }
}

// DetermineLevel определяет требуемый уровень согласования.
// Deviation уже должен быть округлен до 2 знаков (INV-PC-04).
func (t ProfitabilityThreshold) DetermineLevel(deviation Percentage) ApprovalLevel {
    rounded := deviation.RoundedValue()
    switch {
    case rounded < t.autoApproveLimit.Value():
        return LevelAuto
    case rounded <= t.rbuUpperBound.Value():
        return LevelRBU
    case rounded <= t.dpUpperBound.Value():
        return LevelDP
    default:
        return LevelGD
    }
}

func (t ProfitabilityThreshold) Equals(other ProfitabilityThreshold) bool {
    return t.autoApproveLimit.Equals(other.autoApproveLimit) &&
        t.rbuUpperBound.Equals(other.rbuUpperBound) &&
        t.dpUpperBound.Equals(other.dpUpperBound)
}
```

### 3.5. ApprovalDecision

```go
// ApprovalDecisionValue -- неизменяемое решение согласующего.
type ApprovalDecisionValue struct {
    decision  DecisionType
    reason    string
    decidedBy uuid.UUID
    decidedAt time.Time
}

type DecisionType string

const (
    DecisionApproved              DecisionType = "approved"
    DecisionRejected              DecisionType = "rejected"
    DecisionApprovedWithCorrection DecisionType = "approved_with_correction"
    DecisionEscalated             DecisionType = "escalated"
    DecisionAutoRejected          DecisionType = "auto_rejected" // таймаут SLA
)

func NewApprovalDecision(decision DecisionType, reason string, decidedBy uuid.UUID, decidedAt time.Time) (ApprovalDecisionValue, error) {
    if decision == DecisionRejected && len(reason) == 0 {
        return ApprovalDecisionValue{}, ErrReasonRequiredForRejection
    }
    return ApprovalDecisionValue{
        decision:  decision,
        reason:    reason,
        decidedBy: decidedBy,
        decidedAt: decidedAt,
    }, nil
}

func (d ApprovalDecisionValue) Decision() DecisionType { return d.decision }
func (d ApprovalDecisionValue) Reason() string         { return d.reason }
func (d ApprovalDecisionValue) DecidedBy() uuid.UUID   { return d.decidedBy }
func (d ApprovalDecisionValue) DecidedAt() time.Time   { return d.decidedAt }

func (d ApprovalDecisionValue) IsPositive() bool {
    return d.decision == DecisionApproved || d.decision == DecisionApprovedWithCorrection
}

func (d ApprovalDecisionValue) Equals(other ApprovalDecisionValue) bool {
    return d.decision == other.decision && d.decidedBy == other.decidedBy && d.decidedAt.Equal(other.decidedAt)
}
```

### 3.6. PriceCorrection

```go
// PriceCorrection -- неизменяемая запись итерации корректировки цены.
type PriceCorrection struct {
    iteration     int       // 1-5
    proposedPrice Money
    initiatorID   uuid.UUID
    createdAt     time.Time
    result        CorrectionResult
}

type CorrectionResult string

const (
    CorrectionAccepted     CorrectionResult = "accepted"
    CorrectionRejected     CorrectionResult = "rejected"
    CorrectionAutoRejected CorrectionResult = "auto_rejected" // лимит 5 итераций
)

func NewPriceCorrection(iteration int, proposedPrice Money, initiatorID uuid.UUID, createdAt time.Time) (PriceCorrection, error) {
    if iteration < 1 || iteration > 5 {
        return PriceCorrection{}, ErrCorrectionIterationOutOfRange
    }
    if proposedPrice.IsZero() {
        return PriceCorrection{}, ErrZeroCorrectionPrice
    }
    return PriceCorrection{
        iteration:     iteration,
        proposedPrice: proposedPrice,
        initiatorID:   initiatorID,
        createdAt:     createdAt,
        result:        "", // заполняется при решении
    }, nil
}

func (pc PriceCorrection) Iteration() int         { return pc.iteration }
func (pc PriceCorrection) ProposedPrice() Money    { return pc.proposedPrice }
func (pc PriceCorrection) IsLimitReached() bool    { return pc.iteration >= 5 }

func (pc PriceCorrection) Equals(other PriceCorrection) bool {
    return pc.iteration == other.iteration && pc.proposedPrice.Equals(other.proposedPrice)
}
```

### 3.7. DateRange

```go
// DateRange -- неизменяемый диапазон дат.
type DateRange struct {
    from time.Time
    to   time.Time
}

func NewDateRange(from, to time.Time) (DateRange, error) {
    if to.Before(from) {
        return DateRange{}, ErrInvalidDateRange
    }
    return DateRange{from: from, to: to}, nil
}

func (dr DateRange) From() time.Time { return dr.from }
func (dr DateRange) To() time.Time   { return dr.to }

func (dr DateRange) Contains(t time.Time) bool {
    return !t.Before(dr.from) && !t.After(dr.to)
}

func (dr DateRange) DurationDays() int {
    return int(dr.to.Sub(dr.from).Hours() / 24)
}

func (dr DateRange) IsExpired(now time.Time) bool {
    return now.After(dr.to)
}

func (dr DateRange) Equals(other DateRange) bool {
    return dr.from.Equal(other.from) && dr.to.Equal(other.to)
}
```

### 3.8. AggregateLimit

```go
// AggregateLimit -- лимит автосогласования (дневной).
type AggregateLimit struct {
    managerDailyLimit Money // 20 000 руб.
    buDailyLimit      Money // 100 000 руб.
}

func DefaultAggregateLimit() AggregateLimit {
    managerLimit, _ := NewMoney(20_000)
    buLimit, _ := NewMoney(100_000)
    return AggregateLimit{
        managerDailyLimit: managerLimit,
        buDailyLimit:      buLimit,
    }
}

func (al AggregateLimit) CanAutoApprove(managerUsed, buUsed, orderAmount Money) bool {
    return managerUsed.Add(orderAmount).AmountCents() <= al.managerDailyLimit.AmountCents() &&
        buUsed.Add(orderAmount).AmountCents() <= al.buDailyLimit.AmountCents()
}

func (al AggregateLimit) Equals(other AggregateLimit) bool {
    return al.managerDailyLimit.Equals(other.managerDailyLimit) &&
        al.buDailyLimit.Equals(other.buDailyLimit)
}
```

---

## 4. Domain Events

Все события следуют формату CloudEvents JSON и публикуются в Kafka.

### Каталог событий

```go
// DomainEvent -- базовый интерфейс доменного события.
type DomainEvent interface {
    EventID() uuid.UUID
    EventType() string
    AggregateID() uuid.UUID
    AggregateType() string
    OccurredAt() time.Time
    Version() int
}

// BaseEvent -- базовая реализация.
type BaseEvent struct {
    ID            uuid.UUID `json:"id"`
    Type          string    `json:"type"`
    AggregateRef  uuid.UUID `json:"aggregate_id"`
    AggregateKind string    `json:"aggregate_type"`
    Timestamp     time.Time `json:"occurred_at"`
    EventVersion  int       `json:"version"`
}
```

### 4.1. События Profitability Context

| Event | Kafka Topic | Producer | Consumers | Payload |
|-------|-------------|----------|-----------|---------|
| `LocalEstimateCreated` | `evt.profitability.ls.created.v1` | profitability-service | analytics, workflow | ls_id, client_id, planned_profitability, line_items_count |
| `LocalEstimatePlanChanged` | `evt.profitability.ls.plan-changed.v1` | profitability-service | workflow (cross-validation), analytics | ls_id, old_plan, new_plan, reason |
| `LocalEstimateClosed` | `evt.profitability.ls.closed.v1` | profitability-service | analytics, integration (sanctions) | ls_id, fulfillment_rate, actual_profitability |
| `ShipmentCreated` | `evt.profitability.shipment.created.v1` | profitability-service | analytics | shipment_id, ls_id, line_items |
| `ProfitabilityCalculated` | `evt.profitability.calculation.completed.v1` | profitability-service | workflow, analytics | calc_id, shipment_id, ls_id, deviation, required_level |
| `ThresholdViolated` | `evt.profitability.threshold.violated.v1` | profitability-service | workflow (triggers approval), analytics | shipment_id, deviation, required_level |

### 4.2. События Workflow Context

| Event | Kafka Topic | Producer | Consumers | Payload |
|-------|-------------|----------|-----------|---------|
| `ApprovalProcessCreated` | `evt.workflow.approval.created.v1` | workflow-service | notification, analytics | process_id, shipment_id, level, priority, sla_hours |
| `ApprovalAutoApproved` | `evt.workflow.approval.auto-approved.v1` | workflow-service | profitability (update status), notification, analytics | process_id, shipment_id, deviation |
| `ApprovalRoutedToApprover` | `evt.workflow.approval.routed.v1` | workflow-service | notification (push to approver) | process_id, approver_id, level, sla_deadline |
| `ApprovalDecisionMade` | `evt.workflow.approval.decided.v1` | workflow-service | profitability (update status), notification, analytics | process_id, decision, approver_id, comment |
| `ApprovalEscalated` | `evt.workflow.approval.escalated.v1` | workflow-service | notification, analytics | process_id, from_level, to_level, reason |
| `ApprovalSLABreached` | `evt.workflow.sla.breached.v1` | workflow-service | notification (alert), analytics | process_id, sla_hours, actual_hours, level |
| `ApprovalCorrectionLimitReached` | `evt.workflow.correction.limit-reached.v1` | workflow-service | notification, analytics | process_id, iteration_count (=5) |
| `ApprovalFallbackActivated` | `evt.workflow.fallback.activated.v1` | workflow-service | notification (alert IT), analytics | timestamp, reason |
| `ApprovalFallbackQueueDrained` | `evt.workflow.fallback.queue-drained.v1` | workflow-service | notification, analytics | count, timestamp |
| `EmergencyApprovalCreated` | `evt.workflow.emergency.created.v1` | workflow-service | notification, analytics | ea_id, shipment_id, manager_id |
| `EmergencyApprovalEscalated48h` | `evt.workflow.emergency.escalated-48h.v1` | workflow-service | notification (DP alert), integration (violation) | ea_id, manager_id |

### 4.3. События Integration Context

| Event | Kafka Topic | Producer | Consumers | Payload |
|-------|-------------|----------|-----------|---------|
| `PriceSheetUpdated` | `evt.integration.price.npss-updated.v1` | integration-service | profitability (invalidate cache) | product_id, old_npss, new_npss, trigger |
| `PriceSheetTriggeredByExchangeRate` | `evt.integration.price.exchange-trigger.v1` | integration-service | notification (alert FD), analytics | currency, old_rate, new_rate, change_pct |
| `SanctionApplied` | `evt.integration.sanction.applied.v1` | integration-service | notification, analytics | client_id, type, discount_reduction |
| `SanctionRehabilitated` | `evt.integration.sanction.rehabilitated.v1` | integration-service | notification | client_id |
| `ClientUpdated` | `evt.integration.client.updated.v1` | integration-service | profitability, analytics | client_id, changes |

### 4.4. События от 1С (inbound)

| Event | Kafka Topic | Producer | Consumers | Payload |
|-------|-------------|----------|-----------|---------|
| Заказ создан | `1c.order.created.v1` | 1С:УТ (outbox) | integration-service | order_id, ls_id, items, manager_id |
| Заказ изменен | `1c.order.updated.v1` | 1С:УТ (outbox) | integration-service | order_id, changed_fields, items |
| РТУ проведена | `1c.shipment.posted.v1` | 1С:УТ (outbox) | integration-service | rtu_id, order_id, items, amounts |
| Возврат | `1c.shipment.returned.v1` | 1С:УТ (outbox) | integration-service | return_id, rtu_id, items, amounts |
| НПСС обновлена | `1c.price.npss-updated.v1` | 1С:УТ (outbox) | integration-service | product_id, new_npss, method |
| Закупка (цена) | `1c.price.purchase-changed.v1` | 1С:УТ (outbox) | integration-service | product_id, new_price, deviation_pct |
| Контрагент | `1c.client.updated.v1` | 1С:УТ (outbox) | integration-service | client_id, name, is_strategic, sanctions |
| ЛС создана | `1c.ls.created.v1` | 1С:УТ (outbox) | integration-service | ls_id, client_id, items, planned_profit |
| План ЛС изменен | `1c.ls.plan-changed.v1` | 1С:УТ (outbox) | integration-service | ls_id, old_plan, new_plan |

### 4.5. Команды к 1С (outbound)

| Command | Kafka Topic | Producer | Consumer | Payload |
|---------|-------------|----------|----------|---------|
| Результат согласования | `cmd.approval.result.v1` | workflow-service | 1С:УТ | order_id, decision, approver, comment |
| Санкция применена | `cmd.sanction.applied.v1` | integration-service | 1С:УТ | client_id, type, discount_reduction |
| Блокировка отгрузки | `cmd.block.shipment.v1` | workflow-service | 1С:УТ/WMS | order_id, reason |

### 4.6. Payload Schemas

```go
// ProfitabilityCalculatedPayload -- payload события ProfitabilityCalculated.
type ProfitabilityCalculatedPayload struct {
    CalculationID         uuid.UUID   `json:"calculation_id"`
    ShipmentID            uuid.UUID   `json:"shipment_id"`
    LocalEstimateID       uuid.UUID   `json:"local_estimate_id"`
    PlannedProfitability  float64     `json:"planned_profitability"`
    OrderProfitability    float64     `json:"order_profitability"`
    CumulativePlusOrder   float64     `json:"cumulative_plus_order"`
    RemainderProfitability float64    `json:"remainder_profitability"`
    Deviation             float64     `json:"deviation"`
    RequiredLevel         string      `json:"required_level"` // auto/rbu/dp/gd
    LineItemCount         int         `json:"line_item_count"`
    TotalOrderAmount      float64     `json:"total_order_amount"`
}

// ApprovalDecisionMadePayload -- payload события ApprovalDecisionMade.
type ApprovalDecisionMadePayload struct {
    ProcessID     uuid.UUID `json:"process_id"`
    ShipmentID    uuid.UUID `json:"shipment_id"`
    Decision      string    `json:"decision"` // approved/rejected/approved_with_correction/escalated/auto_rejected
    ApproverID    uuid.UUID `json:"approver_id"`
    ApproverName  string    `json:"approver_name"`
    Level         string    `json:"level"`
    Comment       string    `json:"comment,omitempty"`
    SLABreached   bool      `json:"sla_breached"`
    IterationNum  int       `json:"iteration_num,omitempty"` // для корректировки
}

// AnomalyDetectedPayload -- payload события AnomalyDetected.
type AnomalyDetectedPayload struct {
    AnomalyID     uuid.UUID `json:"anomaly_id"`
    Level         int       `json:"level"` // 1=deterministic, 2=llm, 3=agentic
    Score         float64   `json:"score"`
    Description   string    `json:"description"`
    AffectedEntity string   `json:"affected_entity"` // ls/shipment/client
    AffectedID    uuid.UUID `json:"affected_id"`
    Confidence    float64   `json:"confidence,omitempty"` // Level 2-3
}
```

---

## 5. Domain Services

### 5.1. ProfitabilityCalculator

**Назначение:** Реализация формул расчета рентабельности из ФМ.

```go
// port/profitability_calculator.go

// ProfitabilityCalculator -- порт: расчет рентабельности.
type ProfitabilityCalculator interface {
    // CalculateOrderProfitability -- рентабельность отдельного заказа.
    // Формула: SUM((Цена_i - НПСС_i) * Кол_i) / SUM(Цена_i * Кол_i) * 100%
    CalculateOrderProfitability(items []ShipmentLineItem) (Percentage, error)

    // CalculateCumulativePlusOrder -- (Накопленная + Заказ).
    // Формула: (Выручка_отгруж + Выручка_заказа - Себест_отгруж - Себест_заказа) /
    //          (Выручка_отгруж + Выручка_заказа) * 100%
    CalculateCumulativePlusOrder(
        shippedRevenue, shippedCostNPSS Money,
        orderRevenue, orderCostNPSS Money,
    ) (Percentage, error)

    // CalculateRemainderProfitability -- рентабельность остатка ЛС.
    // Формула: SUM((Цена_i - НПСС_i) * Кол_i) / SUM(Цена_i * Кол_i) * 100%
    // где i -- неотгруженные позиции за вычетом позиций Заказов
    // в статусах "На согласовании" и "Согласован".
    CalculateRemainderProfitability(
        remainingItems []LocalEstimateLineItem,
        excludedShipmentIDs []uuid.UUID,
    ) (Percentage, error)

    // CalculateDeviation -- отклонение от плана.
    // Формула: Рент_ЛС(план) - MAX(Накопленная+Заказ, Рент_остатка)
    // Округление до 2 знаков ДО сравнения с границами.
    CalculateDeviation(
        plannedProfitability Percentage,
        cumulativePlusOrder Percentage,
        remainderProfitability Percentage,
    ) Percentage

    // CalculateLineItemProfitability -- рентабельность позиции.
    // Формула: (Цена - НПСС) / Цена * 100%
    CalculateLineItemProfitability(price, npss Money) (Percentage, error)

    // CalculateMinAllowedPrice -- минимальная допустимая цена.
    // Формула: НПСС / (1 - Рент_ЛС_план / 100)
    CalculateMinAllowedPrice(npss Money, plannedProfitability Percentage) Money
}
```

### 5.2. ApprovalRouter

**Назначение:** Маршрутизация согласования. 4-уровневая матрица.

```go
// port/approval_router.go

// ApprovalRouter -- порт: маршрутизация согласований.
type ApprovalRouter interface {
    // DetermineLevel определяет требуемый уровень по отклонению.
    // < 1.00 п.п. = auto, 1.00-15.00 = РБЮ, 15.01-25.00 = ДП, > 25.00 = ГД
    DetermineLevel(deviation Percentage) ApprovalLevel

    // Route направляет заявку нужному согласующему.
    // Учитывает: перелив (порог 30), замещение, доступность.
    Route(ctx context.Context, level ApprovalLevel, businessUnitID uuid.UUID) (*uuid.UUID, error)

    // CheckAutoApproval проверяет возможность автосогласования.
    // Conditions: deviation < 1.00 п.п. AND aggregate limits not exceeded.
    CheckAutoApproval(ctx context.Context, deviation Percentage, managerID, businessUnitID uuid.UUID, orderAmount Money) (bool, error)

    // Escalate эскалирует заявку на следующий уровень.
    // РБЮ -> Директор ДРП -> ДП -> ГД
    Escalate(currentLevel ApprovalLevel) (ApprovalLevel, error)

    // EscalationTarget определяет следующий уровень эскалации.
    // РБЮ -> Директор ДРП, ДП -> ГД, ГД -> автоотказ + уведомление CFO
    EscalationTarget(currentLevel ApprovalLevel) (ApprovalLevel, bool) // level, isTerminal
}
```

### 5.3. SLATracker

**Назначение:** Отслеживание SLA согласований, автоэскалация.

```go
// port/sla_tracker.go

// SLATracker -- порт: отслеживание SLA.
type SLATracker interface {
    // CreateSLA создает запись SLA для новой заявки.
    CreateSLA(processID uuid.UUID, level ApprovalLevel, priority OrderPriority, isSmallOrder bool) (SLADeadline, error)

    // CheckBreaches находит все просроченные SLA.
    // Вызывается каждые 15 минут (09:00-18:00 MSK).
    CheckBreaches(ctx context.Context) ([]SLABreach, error)

    // RecordResolution фиксирует время решения для аналитики.
    RecordResolution(processID uuid.UUID, resolvedAt time.Time) error

    // GetRemainingTime возвращает оставшееся время SLA.
    GetRemainingTime(processID uuid.UUID, now time.Time) (time.Duration, error)
}

type SLABreach struct {
    ProcessID   uuid.UUID
    ShipmentID  uuid.UUID
    Level       ApprovalLevel
    SLAHours    int
    BreachedAt  time.Time
    ApproverID  uuid.UUID
}
```

### 5.4. SanctionManager

**Назначение:** Управление санкциями за невыкуп ЛС (Этап 2).

```go
// port/sanction_manager.go

// SanctionManager -- порт: управление санкциями.
type SanctionManager interface {
    // EvaluateFulfillment оценивает выкуп ЛС и определяет санкцию.
    // Санкции: < 50% = снижение скидки 3 п.п., < 30% = 10 п.п., < 10% = только стандартные
    EvaluateFulfillment(ctx context.Context, localEstimateID uuid.UUID) (*SanctionType, error)

    // ApplySanction применяет санкцию к контрагенту.
    ApplySanction(ctx context.Context, clientID uuid.UUID, sanctionType SanctionType, triggerLSID uuid.UUID) error

    // CheckRehabilitation проверяет, прошло ли 6 месяцев без нарушений.
    // Вызывается ежедневно.
    CheckRehabilitation(ctx context.Context) ([]uuid.UUID, error)

    // CancelSanction отменяет санкцию решением ДП.
    CancelSanction(ctx context.Context, sanctionID uuid.UUID, reason string, dpID uuid.UUID) error

    // GetActiveSanctions возвращает активные санкции контрагента.
    GetActiveSanctions(ctx context.Context, clientID uuid.UUID) ([]Sanction, error)
}
```

### 5.5. ThresholdEvaluator

**Назначение:** Оценка агрегированных лимитов автосогласования.

```go
// port/threshold_evaluator.go

// ThresholdEvaluator -- порт: оценка лимитов.
type ThresholdEvaluator interface {
    // CheckManagerLimit проверяет дневной лимит менеджера (20 000 руб.).
    CheckManagerLimit(ctx context.Context, managerID uuid.UUID, orderAmount Money, date time.Time) (bool, Money, error)
    // Returns: (withinLimit, currentUsed, error)

    // CheckBULimit проверяет дневной лимит БЮ (100 000 руб.).
    CheckBULimit(ctx context.Context, businessUnitID uuid.UUID, orderAmount Money, date time.Time) (bool, Money, error)

    // RecordAutoApproval фиксирует автосогласование в лимите.
    RecordAutoApproval(ctx context.Context, managerID, businessUnitID uuid.UUID, amount Money, date time.Time) error

    // GetWorkloadMetrics возвращает нагрузку согласующего.
    GetWorkloadMetrics(ctx context.Context, approverID uuid.UUID) (*WorkloadMetrics, error)
}

type WorkloadMetrics struct {
    QueueCount     int  // текущее количество задач в очереди
    DailyCount     int  // всего задач за день
    OverflowActive bool // порог 30 превышен
    ExtraAssigned  bool // порог 50 превышен
}
```

### 5.6. CrossValidator

**Назначение:** Перекрестный контроль при изменении плана ЛС.

```go
// port/cross_validator.go

// CrossValidator -- порт: перекрестный контроль шкал.
type CrossValidator interface {
    // ValidateOnPlanChange -- пересчет всех согласованных Заказов при изменении плана ЛС.
    //
    // Алгоритм:
    // 1. Найти все Заказы в статусе "Согласован" (до ПереданНаСклад)
    // 2. Для каждого: пересчитать отклонение по новому плану
    // 3. Если требуемый уровень согласования изменился:
    //    3.1. Аннулировать согласование
    //    3.2. Вернуть Заказ на согласование с новым уровнем
    //    3.3. Уведомить менеджера
    // 4. Если уровень не изменился: согласование остается в силе
    ValidateOnPlanChange(ctx context.Context, localEstimateID uuid.UUID, oldPlan, newPlan Percentage) ([]CrossValidationResult, error)
}

type CrossValidationResult struct {
    ShipmentID       uuid.UUID
    OldLevel         ApprovalLevel
    NewLevel         ApprovalLevel
    NewDeviation     Percentage
    RequiresReapproval bool
}
```

---

## 6. Business Rules

Все правила из ФМ с трассировкой к LS-BR-* / LS-FR-* / LS-WF-*.

### 6.1. Расчет рентабельности

| ID | Правило | Условие | Действие | Формула | Исключения |
|----|---------|---------|----------|---------|------------|
| BR-001 | Рентабельность позиции | При добавлении/изменении позиции | Расчет | (Цена - НПСС) / Цена * 100% | НПСС=0 -> блокировка позиции |
| BR-002 | (Накопленная + Заказ) | При расчете заказа | Расчет | (Выручка_отгруж + Выручка_заказа - Себест_отгруж - Себест_заказа) / (Выручка_отгруж + Выручка_заказа) * 100% | Нет отгрузок -> только рент. заказа |
| BR-003 | Рентабельность остатка | При расчете заказа | Расчет | SUM((Цена_i - НПСС_i) * Кол_i) / SUM(Цена_i * Кол_i) * 100% | Исключить заказы "На согласовании" и "Согласован" |
| BR-004 | Отклонение | При расчете заказа | Расчет | Рент_ЛС(план) - MAX(Накопленная+Заказ, Рент_остатка) | Округление до 2 знаков ДО сравнения с границами |
| BR-005 | Минимальная допустимая цена | При фиксации ЛС | Расчет | НПСС / (1 - Рент_ЛС_план / 100) | — |
| BR-006 | Выручка нетто | При учете отгрузки | Расчет | Сумма_отгрузки - Возвраты - Скидки | Возвраты уменьшают выручку |
| LS-BR-035 | Блокировка ЛС | Редактирование заказа по ЛС | Пессимистичная блокировка | Таймаут: 5 минут | Автоснятие, уведомление через 3 мин |
| LS-BR-075 | Автотриггер НПСС (курс) | Курс ЦБ изменился > 5% за 7 дней | Автопересчет НПСС | Изменение = |КурсСегодня - Курс7ДнейНазад| / Курс7ДнейНазад * 100 | Валюты: USD, EUR, CNY |
| LS-BR-075b | Автотриггер НПСС (закупка) | Закупочная цена отклонилась > 15% от НПСС | Пересмотр НПСС в 5 р.д. | |ЗакупочнаяЦена - НПСС| / НПСС * 100 > 15% | — |

### 6.2. Согласование

| ID | Правило | Условие | Действие | Параметры | Исключения |
|----|---------|---------|----------|-----------|------------|
| BR-010 | Автосогласование | Отклонение < 1.00 п.п. | Согласовать автоматически | Лимит: 5 000 руб/день на менеджера | При превышении лимита -> направить на РБЮ |
| BR-011 | Агрегированный лимит менеджера | При автосогласовании | Проверить дневной лимит | 20 000 руб/день на менеджера | Превышение -> направить на РБЮ |
| BR-012 | Агрегированный лимит БЮ | При автосогласовании | Проверить дневной лимит | 100 000 руб/день на БЮ | Превышение -> направить на РБЮ |
| BR-013 | Матрица согласования | Отклонение >= 1.00 п.п. | Определить уровень | 1.00-15.00 = РБЮ, 15.01-25.00 = ДП, > 25.00 = ГД | Стратегические клиенты: допустимое отклонение |
| BR-014 | SLA | При создании заявки | Установить дедлайн | P1: 4/8/24ч, P2: 24/48/72ч, <100тр: 2/4/12ч | Рабочие часы |
| BR-015 | Автоэскалация | SLA истек | Переназначить выше | РБЮ -> Дир.ДРП, ДП -> ГД, ГД -> автоотказ 48ч | Уведомление CFO при автоотказе ГД |
| BR-016 | Обоснование | Отклонение >= 1.00 п.п. | Требовать обоснование | Мин. 50 символов | — |
| BR-017 | Срок согласования | Согласование получено | Срок действия 5 рабочих дней | — | После истечения -> возврат в Черновик |
| BR-018 | Точка невозврата | Передан на склад | Фиксация | ПереданНаСклад = true | Согласование не аннулируется |
| BR-019 | Корректировка цены | Согласующий решает "С корректировкой" | Итерация корректировки | Макс. 5 итераций | При 6-й -> автоотказ |
| BR-020 | Перекрестный контроль | Изменение плана ЛС | Пересчет согласованных Заказов | Если уровень изменился -> аннулировать | Если уровень не изменился -> оставить |
| BR-021 | Аннулирование при >= 3 | >= 3 аннулирований | Эскалация на ДП | — | — |

### 6.3. Экстренные согласования

| ID | Правило | Условие | Действие | Параметры | Исключения |
|----|---------|---------|----------|-----------|------------|
| BR-030 | Лимит экстренных (менеджер) | Фиксация экстренного | Проверить лимит | 3/мес, пиковые (дек/авг): 5/мес | Превышение -> блокировка |
| BR-031 | Лимит экстренных (контрагент) | Фиксация экстренного | Проверить лимит | 5/мес, пиковые: 8/мес | Превышение -> блокировка |
| BR-032 | Уполномоченное лицо | Фиксация экстренного | Проверить справочник | Должен быть активен | Отсутствие -> блокировка |
| BR-033 | Постфактум-контроль 24ч | Через 24ч | Проверить подтверждение | — | Не подтверждено -> повторное уведомление |
| BR-034 | Постфактум-контроль 48ч | Через 48ч | Эскалация на ДП | — | Запись нарушения |
| BR-035 | Пиковые периоды | Декабрь, август | Увеличенные лимиты | Менеджер: 5, контрагент: 8, общий: 10/мес | — |

### 6.4. Резервный режим ELMA

| ID | Правило | Условие | Действие | Параметры | Исключения |
|----|---------|---------|----------|-----------|------------|
| BR-040 | Определение недоступности | Таймаут или 3 ошибки подряд | Активировать резервный режим | Таймаут подключения: 30 сек | Проверка каждые 5 мин |
| BR-041 | Автосогласование в fallback | ELMA недоступна, отклонение <= 5.00 п.п. | Автосогласование | — | Уведомление согласующему |
| BR-042 | Очередь FIFO | ELMA недоступна, отклонение > 5.00 п.п. | Постановка в очередь | P1 первыми, далее P2 | Уведомление менеджеру |
| BR-043 | Восстановление ELMA | ELMA доступна | Отправить очередь | P1 первыми, FIFO внутри приоритета | Автосогласованные: уведомить для постфактум контроля |

### 6.5. НПСС и ценообразование

| ID | Правило | Условие | Действие | Параметры | Исключения |
|----|---------|---------|----------|-----------|------------|
| BR-050 | Фиксация НПСС | Создание ЛС | Snapshot НПСС | Из SBS-58 на дату создания | Если НПСС=0 -> временная (посл. закупка * 1.1) |
| BR-051 | Возраст НПСС 0-30 дн | При расчете | Без ограничений | — | — |
| BR-052 | Возраст НПСС 31-60 дн | При расчете | Предупреждение | Информационное | — |
| BR-053 | Возраст НПСС 61-90 дн | При расчете | Требуется подтверждение РБЮ | — | — |
| BR-054 | Возраст НПСС > 90 дн | При расчете | Блокировка согласования | — | Автопродление ЛС с НПСС > 90 дн: блокировка остается |
| BR-055 | Формула НПСС | При расчете | ЦЗсредняя * ТТК_страна | ЦЗсредняя за 6 месяцев | SBS-58 |
| BR-056 | Товар от производства | При расчете НПСС | Использовать внутреннюю цену | Из SBS-130 | Fallback: цена из ПТУ |

### 6.6. Жизненный цикл ЛС

| ID | Правило | Условие | Действие | Параметры | Исключения |
|----|---------|---------|----------|-----------|------------|
| BR-060 | Автозакрытие | ЛС истекла | Статус -> Закрыта | — | Если есть заказы "На согласовании" -> ждать |
| BR-061 | Продление | ЛС истекает < 5 р.д. И есть дефицит | Автопродление | Макс. 2 продления | При НПСС > 90 дн: блокировка остается |
| BR-062 | Черновик > 7 дней | Заказ в статусе Черновик | Удаление | Проверка блокировки | Если заказ редактируется -> не удалять |
| BR-063 | Рекомендательный контроль | ЛС с план. рент. < 5% | Предупреждение | — | Не блокирует |

### 6.7. Нагрузка согласующих

| ID | Правило | Условие | Действие | Параметры | Исключения |
|----|---------|---------|----------|-----------|------------|
| BR-070 | Перелив (порог 30) | > 30 задач в очереди | Автоперелив на заместителя | Автоматический | — |
| BR-071 | Доп. согласующий (порог 50) | > 50 задач за день | Информационный сигнал руководителю | Ручное действие | — |

### 6.8. Санкции (Этап 2)

| ID | Правило | Условие | Действие | Параметры | Исключения |
|----|---------|---------|----------|-----------|------------|
| BR-080 | Санкция: снижение 3 п.п. | Выкуп < 50% | Снижение макс. скидки | 3 п.п. | Стратегические: отмена ДП макс. 3 раза/год |
| BR-081 | Санкция: снижение 10 п.п. | Выкуп < 30% | Снижение макс. скидки | 10 п.п. | — |
| BR-082 | Санкция: стандартные цены | Выкуп < 10% | Только стандартные цены | — | — |
| BR-083 | Реабилитация | 6 мес. без нарушений | Снятие санкции | — | — |
| BR-084 | Кумулятивность | Повторное нарушение | Суммирование санкций | — | — |

---

## 7. Sagas

### 7.1. ApprovalSaga (Saga согласования)

**Описание:** Полный цикл согласования от создания заявки до уведомления.

```
[1. CreateApprovalProcess]
        |
        +--> [CheckAutoApproval]
        |       |
        |    YES: [AutoApprove] --> [NotifyManager] --> [UpdateShipment] --> [Update1C] --> END
        |       |
        |    NO: [2. RouteToApprover]
        |              |
        |         [3. CreateELMATask] --fallback--> [3a. EnqueueFallback]
        |              |                                    |
        |         [4. WaitForDecision]              [4a. AutoApprove<=5pp]
        |              |                            [4b. QueueFIFO>5pp]
        |         +----+----+----+
        |         |    |    |    |
        |    Approved Rejected Correction Escalated
        |         |    |    |         |
        |         |    |    |    [Route to next level]
        |         |    |    |    [Goto 3]
        |         |    |    |
        |         |    |  [CheckIterationLimit]
        |         |    |    |         |
        |         |    |  <5: [Goto 2] >=5: [AutoReject]
        |         |    |
        |         |  [ReturnToDraft]
        |         |  [NotifyManager]
        |         |
        |    [5. UpdateShipment]
        |    [6. NotifyManager]
        |    [7. Update1C via Kafka]
        |    END

Compensation:
  Step 7 fail: retry 3x, then DLQ + alert
  Step 3 fail: activate fallback mode
  Step 5 fail: retry 3x, then manual intervention
  Timeout (SLA * 2): auto-reject + notify CFO
```

**Timeout:** SLA * 2 (максимум 144 часа для P2 ГД)

### 7.2. SanctionSaga (Saga санкций)

**Описание:** Обнаружение невыкупа -> предупреждение -> применение санкции.

```
[1. DetectUnderFulfillment]
        |
   fulfillmentRate < threshold?
        |
     NO: END
     YES:
        |
   [2. IssueWarning]
        |
   [3. GracePeriod (30 дней)]
        |
   Улучшение?
        |
     YES: END (warning cleared)
     NO:
        |
   [4. DetermineSanctionType]
        |-- <50%: discount_reduction_3pp
        |-- <30%: discount_reduction_10pp
        |-- <10%: standard_prices_only
        |
   [5. CheckStrategicClient]
        |-- strategic + cancel_count < 3: [OfferCancellation to DP]
        |
   [6. ApplySanction]
   [7. NotifyClient]
   [8. Update1C via Kafka]
   [9. StartRehabilitationTimer (6 months)]

Compensation:
  Step 8 fail: retry 3x, then DLQ
  DP cancels sanction: [CancelSanction] -> [Notify] -> [Update1C]
  Rehabilitation (6 months clean): [RemoveSanction] -> [Notify] -> [Update1C]
```

**Timeout:** Grace period 30 дней + rehabilitation 6 месяцев

### 7.3. PriceUpdateSaga (Saga обновления НПСС)

**Описание:** Автотриггер -> загрузка данных -> пересчет -> уведомление.

```
[1. DetectTrigger]
        |
   Trigger type?
        |
   ExchangeRate (>5% за 7 дней):
        |
   [2a. FetchCBRRates]
   [3a. CalculateChange]
   [4a. RecalculateNPSS (all import products)]
   [5a. NotifyFinancialService]
   [6a. InvalidateProfitabilityCache]
   [7a. Update affected LEs]
   END

   PurchasePrice (>15% deviation):
        |
   [2b. RecordDeviation]
   [3b. NotifyForReview (5 working days)]
   [4b. WaitForManualReview]
   [5b. UpdateNPSS (if confirmed)]
   [6b. InvalidateCache]
   END

Compensation:
  Step 2a fail (CBR unavailable): retry 3x, use cached rates, alert FD
  Step 4a fail: rollback NPSS changes, alert FD
  Step 4b timeout (5 days): escalate to FD
```

**Timeout:** Пересчет: 30 минут. Ручной пересмотр: 5 рабочих дней.

---

## 8. AI Analytics Aggregate

### 8.1. Трехуровневая аналитика

| Level | Тип | Модель | Триггер | Timeout | Cost/request |
|-------|-----|--------|---------|---------|--------------|
| 1 (Deterministic) | Статистика + правила | gonum/stat | Каждый расчет рентабельности | - | $0 |
| 2 (LLM) | Интерпретация аномалии | Sonnet 4.6 (cached) | Обнаружена аномалия Level 1 | 15s | ~$0.003 |
| 3 (Agentic) | Автономное расследование | Opus 4.6 | Level 2 confidence < 0.7 | 60s | ~$0.05 |

### 8.2. Доменная модель AI-аналитики

```go
// Anomaly -- агрегат аномалии.
type Anomaly struct {
    ID              uuid.UUID
    Level           AnomalyLevel // 1/2/3
    Score           float64      // Z-score или anomaly score
    Description     string
    AffectedEntity  string       // ls / shipment / client
    AffectedID      uuid.UUID
    DetectedAt      time.Time
    Status          AnomalyStatus

    // Level 2-3
    LLMExplanation  string
    Confidence      float64   // 0.0 - 1.0
    Recommendations []string

    // Level 3
    Investigation   *Investigation
}

type Investigation struct {
    ID              uuid.UUID
    AnomalyID       uuid.UUID
    StartedAt       time.Time
    CompletedAt     *time.Time
    RootCause       string
    EvidenceChain   []Evidence
    Recommendation  string
    ConfidenceScore float64
    Iterations      int // макс. 10
    Model           string // claude-opus-4-6
    TotalTokens     int
    CostUSD         float64
}

type Evidence struct {
    ToolUsed   string    // query_shipments, query_client_history, etc.
    Input      string    // JSON input
    Output     string    // JSON output
    ObtainedAt time.Time
}

type AnomalyLevel int

const (
    AnomalyLevelDeterministic AnomalyLevel = 1
    AnomalyLevelLLM           AnomalyLevel = 2
    AnomalyLevelAgentic       AnomalyLevel = 3
)

type AnomalyStatus string

const (
    AnomalyOpen         AnomalyStatus = "open"
    AnomalyInvestigating AnomalyStatus = "investigating"
    AnomalyResolved     AnomalyStatus = "resolved"
    AnomalyFalsePositive AnomalyStatus = "false_positive"
)
```

### 8.3. Level 1: Deterministic Rules

```go
// port/anomaly_detector.go

// AnomalyDetector -- порт: обнаружение аномалий.
type AnomalyDetector interface {
    // DetectZScore -- Z-score анализ отклонений.
    // Window: 90 дней, порог: +/- 2 сигма.
    DetectZScore(ctx context.Context, values []float64, current float64) (float64, bool)

    // DetectTrend -- ARIMA прогноз на 30 дней.
    DetectTrend(ctx context.Context, historicalData []TimeSeriesPoint) (*Forecast, error)

    // EvaluateRules -- проверка бизнес-правил.
    // Правила: резкое снижение маржи, аномальный объем, нетипичный клиент.
    EvaluateRules(ctx context.Context, shipmentID uuid.UUID) ([]RuleViolation, error)
}

type TimeSeriesPoint struct {
    Timestamp time.Time
    Value     float64
}

type Forecast struct {
    PredictedValues []TimeSeriesPoint
    UpperBound      []TimeSeriesPoint
    LowerBound      []TimeSeriesPoint
    Confidence      float64
}

type RuleViolation struct {
    RuleID      string
    Description string
    Severity    string // critical/high/medium/low
    Value       float64
    Threshold   float64
}
```

### 8.4. Level 2: LLM Interpretation (Sonnet)

```go
// port/ai_analyst.go

// AIAnalyst -- порт: LLM-анализ аномалий.
type AIAnalyst interface {
    // ExplainAnomaly -- объяснение аномалии с помощью LLM.
    // System prompt: FM context (~20K tokens, cached -> 90% discount).
    // Output: structured JSON.
    ExplainAnomaly(ctx context.Context, anomaly Anomaly, context AnomalyContext) (*AnomalyExplanation, error)

    // SummarizeReport -- суммаризация отчета.
    SummarizeReport(ctx context.Context, data ReportData) (string, error)

    // AnswerQuestion -- ответ на вопрос аналитика.
    AnswerQuestion(ctx context.Context, question string, context []ContextDocument) (string, error)
}

type AnomalyContext struct {
    RecentShipments   []ShipmentSummary
    ClientHistory     ClientHistorySummary
    PriceChanges      []PriceChangeRecord
    MarketConditions  string
}

type AnomalyExplanation struct {
    Explanation     string   `json:"explanation"`
    Confidence      float64  `json:"confidence"`
    Recommendations []string `json:"recommendations"`
    RequiresLevel3  bool     `json:"requires_level_3"` // confidence < 0.7
}
```

### 8.5. Level 3: Agentic Investigation (Opus)

```go
// port/ai_investigator.go

// AIInvestigator -- порт: автономное расследование аномалий.
type AIInvestigator interface {
    // Investigate -- автономное расследование.
    // Max iterations: 10, timeout: 60s.
    // Tools: query_shipments, query_client_history, query_price_changes,
    //        calculate_what_if, get_approval_history.
    Investigate(ctx context.Context, anomaly Anomaly) (*Investigation, error)
}

// InvestigationTool -- инструмент для агентного расследования.
type InvestigationTool interface {
    Name() string
    Description() string
    Execute(ctx context.Context, input json.RawMessage) (json.RawMessage, error)
}
```

### 8.6. Guardrails

```go
// AIGuardrails -- ограничения AI-аналитики.
type AIGuardrails struct {
    RateLimitSonnet    int     // 200 req/hour
    RateLimitOpus      int     // 50 req/hour
    TimeoutSonnet      time.Duration // 15s
    TimeoutOpus        time.Duration // 60s
    DailyCostCeiling   float64 // $50 (prod)
    CostAlertThreshold float64 // 60% ($30)
    ConfidenceThreshold float64 // 0.7 (below = escalate to Level 3)
    MaxIterations      int     // 10 (Level 3)
}
```

---

## 9. Read Models / Projections

| Projection | Источник | Назначение | Обновление |
|-----------|----------|------------|------------|
| `ShipmentDashboard` | Shipment events + ProfitabilityCalculated | Панель отгрузок для менеджера | Event-driven |
| `ApprovalQueue` | ApprovalProcess events | Рабочее место согласующего | Event-driven |
| `LSProfitabilitySummary` | ProfitabilityCalculated + ShipmentFulfilled | Сводка по ЛС (план vs факт) | Event-driven |
| `ManagerKPI` | ShipmentFulfilled + ApprovalDecisionMade + SanctionApplied | KPI менеджера | Scheduled (daily) |
| `ApproverWorkload` | ApprovalRoutedToApprover + ApprovalDecisionMade | Нагрузка согласующих (пороги 30/50) | Event-driven |
| `DailyEfficiencyDashboard` | All events | Дашборд эффективности для ФД (LS-RPT-070) | Scheduled (daily) |
| `NPSSAgeReport` | PriceSheetUpdated + timer | Возраст НПСС по позициям | Scheduled (daily) |
| `BaselineKPI` | Historical data | Базовый замер KPI (LS-RPT-073) | One-time |
| `PilotProgressReport` | All events (1 month window) | Промежуточный отчет пилота (LS-RPT-074) | One-time |
| `AnomalyDashboard` | AnomalyDetected + InvestigationCompleted | Панель аномалий (AI) | Event-driven |
| `CostTracking` | AI request events | Стоимость AI-аналитики | Event-driven |

---

## 10. Integration Contracts

### 10.1. Входящие (1С -> Go)

| Интеграция | Направление | Протокол | Контракт | Retry | DLQ |
|------------|-------------|----------|----------|-------|-----|
| 1С:УТ Заказы | IN | Kafka | `1c.order.created/updated.v1` | 3x (1s, 30s, 5min) | `1c.order.dlq` |
| 1С:УТ Отгрузки | IN | Kafka | `1c.shipment.posted/returned.v1` | 3x | `1c.shipment.dlq` |
| 1С:УТ НПСС | IN | Kafka | `1c.price.npss-updated.v1` | 3x | `1c.price.dlq` |
| 1С:УТ Закупки | IN | Kafka | `1c.price.purchase-changed.v1` | 3x | `1c.price.dlq` |
| 1С:УТ Контрагенты | IN | Kafka | `1c.client.updated.v1` | 3x | `1c.client.dlq` |
| 1С:УТ ЛС | IN | Kafka | `1c.ls.created/plan-changed.v1` | 3x | `1c.ls.dlq` |

### 10.2. Исходящие (Go -> 1С)

| Интеграция | Направление | Протокол | Контракт | Retry | DLQ |
|------------|-------------|----------|----------|-------|-----|
| Результат согласования | OUT | Kafka | `cmd.approval.result.v1` | 3x | `cmd.approval.dlq` |
| Санкция | OUT | Kafka | `cmd.sanction.applied.v1` | 3x | `cmd.sanction.dlq` |
| Блокировка отгрузки | OUT | Kafka | `cmd.block.shipment.v1` | 3x | `cmd.block.dlq` |

### 10.3. Внешние системы

| Интеграция | Направление | Протокол | Контракт | Retry | Circuit Breaker |
|------------|-------------|----------|----------|-------|-----------------|
| ELMA BPM | Bidirectional | REST API | JSON | 3x (таймаут 30 сек) | 5 failures -> open -> 30s -> half-open |
| WMS | Bidirectional | REST API | JSON | 3x | 5 failures -> open |
| ЦБ РФ | IN | REST API | XML | 3x (ежедневно 08:00) | Use cached rates on failure |
| Claude API (Sonnet) | OUT | REST API | JSON | 2x (timeout 15s) | Rate limit 200/hour |
| Claude API (Opus) | OUT | REST API | JSON | 2x (timeout 60s) | Rate limit 50/hour |
| AD (LDAP) | IN | LDAP/Kerberos | LDIF | 3x | Fallback to cached roles |
| Telegram Bot | OUT | REST API | JSON | 3x | Fallback to email |
| Email (SMTP) | OUT | SMTP | RFC 5322 | 3x | Fallback to 1С push |

---

## 11. Traceability Matrix

Трассировка каждого домен-объекта к требованиям ФМ.

### Aggregates -> ФМ

| Aggregate | ФМ Секция | Требования ФМ |
|-----------|-----------|---------------|
| LocalEstimate | п. 3.1, 3.2, 3.14 | ЛС, позиции, фиксация НПСС, продление |
| Shipment | п. 3.3-3.5, 3.8-3.13 | Заказ клиента, расчет рент., согласование, статусы |
| ApprovalProcess | п. 3.5-3.7, 3.11 | Матрица согласования, SLA, эскалация, корректировка |
| ProfitabilityCalculation | п. 3.3, 3.4 | Формулы рентабельности, отклонение |
| Client | п. 3.15, 3.16 | Стратегические клиенты, санкции |
| Sanction | п. 3.17, 3.18 (P2) | Санкции за невыкуп, реабилитация |
| PriceSheet | п. 3.2, 3.19 | НПСС, автотриггеры LS-BR-075 |
| EmergencyApproval | п. 3.7 | Экстренные согласования, постфактум-контроль |

### Business Rules -> LS-BR-*

| Domain Rule | LS-BR-* | Описание |
|-------------|---------|----------|
| BR-001 | LS-BR-001..003 | Формулы рентабельности |
| BR-004 | LS-BR-004 | Отклонение от плана |
| BR-005 | LS-BR-005 | Минимальная допустимая цена |
| BR-010..012 | LS-BR-010, LS-BR-072..074 | Автосогласование, агрегированные лимиты |
| BR-013 | LS-BR-011..013 | Матрица согласования |
| BR-014 | LS-WF-001..003 | SLA |
| BR-015 | LS-WF-004 | Автоэскалация |
| BR-016 | LS-BR-016 | Обоснование |
| BR-017 | LS-BR-017 | Срок согласования 5 р.д. |
| BR-018 | LS-BR-018 | Точка невозврата |
| BR-019 | LS-BR-019, LS-BR-076 | Корректировка цены, лимит 5 итераций |
| BR-020 | LS-BR-077 | Перекрестный контроль |
| BR-030..035 | LS-BR-030..034, LS-BR-071 | Экстренные согласования |
| BR-035 | LS-BR-035 | Блокировка ЛС (5 мин) |
| BR-040..043 | LS-FR-070..071, LS-BR-078 | Резервный режим ELMA |
| BR-050..056 | LS-BR-040..046 | НПСС, возраст, фиксация |
| BR-060..063 | LS-FR-060..063 | Жизненный цикл ЛС |
| BR-070..071 | LS-BR-079..080 | Нагрузка согласующих (пороги 30/50) |
| BR-075 | LS-BR-075 | Автотриггеры НПСС |
| BR-080..084 | LS-FR-050..058 (P2) | Санкции за невыкуп |

---

## Приложение A. Ошибки домена

```go
package domain

import "errors"

// Ошибки расчета
var (
    ErrNegativeMoney              = errors.New("money amount cannot be negative")
    ErrMoneyOverflow              = errors.New("money overflow: result exceeds int64 (> 92 quadrillion kopecks)")
    ErrNegativeMultiplier         = errors.New("money multiplier cannot be negative")
    ErrDivisionByZero             = errors.New("division by zero in profitability calculation")
    ErrNPSSIsZero                 = errors.New("NPSS is zero: line item blocked")
    ErrPriceIsZero                = errors.New("price is zero: line item blocked")
    ErrInvalidQuantity            = errors.New("invalid quantity format")
    ErrNonPositiveQuantity        = errors.New("quantity must be positive")
)

// Ошибки согласования
var (
    ErrReasonRequiredForRejection = errors.New("reason is required for rejection")
    ErrJustificationTooShort      = errors.New("justification must be at least 50 characters")
    ErrCorrectionIterationOutOfRange = errors.New("correction iteration must be 1-5")
    ErrZeroCorrectionPrice        = errors.New("correction price cannot be zero")
    ErrCorrectionLimitReached     = errors.New("correction iteration limit reached (5)")
    ErrApprovalExpired            = errors.New("approval has expired (5 business days)")
    ErrPointOfNoReturn            = errors.New("shipment already handed to warehouse")
    ErrMaxCancellationsReached    = errors.New("max cancellations reached (3), escalating to DP")
)

// Ошибки лимитов
var (
    ErrManagerDailyLimitExceeded  = errors.New("manager daily auto-approval limit exceeded (20000 RUB)")
    ErrBUDailyLimitExceeded       = errors.New("business unit daily auto-approval limit exceeded (100000 RUB)")
    ErrEmergencyLimitReached      = errors.New("emergency approval limit reached for this month")
    ErrAuthorizedPersonNotFound   = errors.New("authorized person not found or inactive")
)

// Ошибки ЛС
var (
    ErrMaxRenewalsReached         = errors.New("max LS renewals reached (2)")
    ErrMaxLineItems               = errors.New("max line items per LS reached (1000)")
    ErrMaxPendingApprovals        = errors.New("max pending approvals per LS reached (50)")
    ErrNPSSStale                  = errors.New("NPSS is stale (>90 days): approval blocked")
)

// Ошибки дат
var (
    ErrInvalidDateRange           = errors.New("end date must be after start date")
)

// Ошибки ELMA
var (
    ErrELMAUnavailable            = errors.New("ELMA BPM is unavailable, fallback mode active")
)
```

## Приложение B. Портовые интерфейсы (Repositories)

```go
package port

import (
    "context"
    "time"

    "github.com/google/uuid"
    "profitability-service/internal/domain"
)

// LocalEstimateRepository -- порт хранения ЛС.
type LocalEstimateRepository interface {
    Save(ctx context.Context, le *domain.LocalEstimate) error
    FindByID(ctx context.Context, id uuid.UUID) (*domain.LocalEstimate, error)
    FindByExternalID(ctx context.Context, externalID string) (*domain.LocalEstimate, error)
    FindActiveByClientID(ctx context.Context, clientID uuid.UUID) ([]domain.LocalEstimate, error)
    FindExpiring(ctx context.Context, withinDays int) ([]domain.LocalEstimate, error)
}

// ShipmentRepository -- порт хранения Заказов.
type ShipmentRepository interface {
    Save(ctx context.Context, s *domain.Shipment) error
    FindByID(ctx context.Context, id uuid.UUID) (*domain.Shipment, error)
    FindByExternalID(ctx context.Context, externalID string) (*domain.Shipment, error)
    FindByLSID(ctx context.Context, lsID uuid.UUID, statuses ...domain.ShipmentStatus) ([]domain.Shipment, error)
    FindApprovedNotHandedOver(ctx context.Context, lsID uuid.UUID) ([]domain.Shipment, error)
    FindStaleDrafts(ctx context.Context, olderThan time.Time) ([]domain.Shipment, error)
}

// ApprovalProcessRepository -- порт хранения процессов согласования.
type ApprovalProcessRepository interface {
    Save(ctx context.Context, ap *domain.ApprovalProcess) error
    FindByID(ctx context.Context, id uuid.UUID) (*domain.ApprovalProcess, error)
    FindByShipmentID(ctx context.Context, shipmentID uuid.UUID) (*domain.ApprovalProcess, error)
    FindPendingByApproverID(ctx context.Context, approverID uuid.UUID) ([]domain.ApprovalProcess, error)
    FindBreachedSLA(ctx context.Context, now time.Time) ([]domain.ApprovalProcess, error)
    CountPendingByApprover(ctx context.Context, approverID uuid.UUID) (int, error)
    CountDailyByApprover(ctx context.Context, approverID uuid.UUID, date time.Time) (int, error)
}

// PriceSheetRepository -- порт хранения НПСС.
type PriceSheetRepository interface {
    Save(ctx context.Context, ps *domain.PriceSheet) error
    FindByProductID(ctx context.Context, productID uuid.UUID, date time.Time) (*domain.PriceSheet, error)
    FindStale(ctx context.Context, olderThanDays int) ([]domain.PriceSheet, error)
    FindByTrigger(ctx context.Context, trigger domain.NPSSTrigger) ([]domain.PriceSheet, error)
}

// SanctionRepository -- порт хранения санкций.
type SanctionRepository interface {
    Save(ctx context.Context, s *domain.Sanction) error
    FindActiveByClientID(ctx context.Context, clientID uuid.UUID) ([]domain.Sanction, error)
    FindDueForRehabilitation(ctx context.Context, now time.Time) ([]domain.Sanction, error)
}

// EmergencyApprovalRepository -- порт хранения экстренных согласований.
type EmergencyApprovalRepository interface {
    Save(ctx context.Context, ea *domain.EmergencyApproval) error
    CountByManagerMonth(ctx context.Context, managerID uuid.UUID, month time.Time) (int, error)
    CountByClientMonth(ctx context.Context, clientID uuid.UUID, month time.Time) (int, error)
    FindUnconfirmed(ctx context.Context, olderThan time.Duration) ([]domain.EmergencyApproval, error)
}

// AggregationLimitRepository -- порт хранения лимитов автосогласования.
type AggregationLimitRepository interface {
    GetManagerDailyUsage(ctx context.Context, managerID uuid.UUID, date time.Time) (domain.Money, error)
    GetBUDailyUsage(ctx context.Context, buID uuid.UUID, date time.Time) (domain.Money, error)
    RecordUsage(ctx context.Context, managerID, buID uuid.UUID, amount domain.Money, date time.Time) error
}

// EventPublisher -- порт публикации доменных событий.
type EventPublisher interface {
    Publish(ctx context.Context, events ...domain.DomainEvent) error
}

// AnomalyRepository -- порт хранения аномалий.
type AnomalyRepository interface {
    Save(ctx context.Context, a *domain.Anomaly) error
    FindByID(ctx context.Context, id uuid.UUID) (*domain.Anomaly, error)
    FindOpen(ctx context.Context) ([]domain.Anomaly, error)
    FindByAffectedEntity(ctx context.Context, entityType string, entityID uuid.UUID) ([]domain.Anomaly, error)
}
```

---

**Итого:**

| Категория | Количество | Детали |
|-----------|-----------|--------|
| Bounded Contexts | 4 | Profitability, Workflow, Analytics, Integration |
| Aggregates | 8 | LocalEstimate, Shipment, ApprovalProcess, ProfitabilityCalculation, Client, Sanction, PriceSheet, EmergencyApproval |
| Value Objects | 9 | Money, Quantity, Percentage, SLADeadline, ProfitabilityThreshold, ApprovalDecisionValue, PriceCorrection, DateRange, AggregateLimit |
| Domain Events | 40+ | Profitability (6), Workflow (11), Integration (5), 1С inbound (9), Commands outbound (3), AI (3+) |
| Domain Services | 6 | ProfitabilityCalculator, ApprovalRouter, SLATracker, SanctionManager, ThresholdEvaluator, CrossValidator |
| Business Rules | 44 | BR-001..006 (расчет), BR-010..021 (согласование), BR-030..035 (экстренные), BR-040..043 (ELMA fallback), BR-050..056 (НПСС), BR-060..063 (ЛС), BR-070..071 (нагрузка), BR-080..084 (санкции) |
| Sagas | 3 | ApprovalSaga, SanctionSaga, PriceUpdateSaga |
| Read Models | 11 | Dashboard, Queue, Summary, KPI, Workload, etc. |
| AI Levels | 3 | Deterministic, LLM (Sonnet), Agentic (Opus) |
| Repository Ports | 9 | LS, Shipment, Approval, PriceSheet, Sanction, Emergency, Limits, Events, Anomaly |
