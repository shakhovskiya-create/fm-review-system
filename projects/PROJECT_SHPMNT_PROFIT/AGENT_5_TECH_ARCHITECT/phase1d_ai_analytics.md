# Phase 1D: AI Analytics Architecture

**Проект:** FM-LS-PROFIT (Контроль рентабельности отгрузок по ЛС)
**Версия ФМ:** 1.0.7
**Дата:** 02.03.2026
**Автор:** Шаховский А.С.
**Платформа:** Go 1.22+ (analytics-service)
**AI Models:** Sonnet 4.6 (analyst, 90%), Opus 4.6 (investigator, 10%)
**SDK:** anthropic-sdk-go

---

## Содержание

1. [Three-Level Architecture](#1-three-level-architecture)
2. [Level 1: Deterministic Analytics](#2-level-1-deterministic-analytics)
3. [Level 2: LLM Interpretation (Sonnet 4.6)](#3-level-2-llm-interpretation-sonnet-46)
4. [Level 3: Agentic Investigation (Opus 4.6)](#4-level-3-agentic-investigation-opus-46)
5. [Prompt Caching Strategy](#5-prompt-caching-strategy)
6. [AI Safety and Guardrails](#6-ai-safety-and-guardrails)
7. [Cost Model](#7-cost-model)
8. [Langfuse Integration](#8-langfuse-integration)
9. [Fallback Strategy](#9-fallback-strategy)

---

## 1. Three-Level Architecture

### 1.1. Escalation Flow

```
+---------------------------+     +---------------------------+     +---------------------------+
|  Level 1: Deterministic   |     |  Level 2: LLM Sonnet 4.6 |     |  Level 3: Agentic Opus 4.6|
|                           |     |                           |     |                           |
|  - Z-score (gonum/stat)   |     |  - Anomaly explanation    |     |  - Autonomous investigation|
|  - ARIMA forecast         |     |  - Report summarization   |     |  - Tool-based evidence    |
|  - Business rule engine   |     |  - Q&A about data         |     |  - Root cause analysis    |
|  - Aggregate monitoring   |     |                           |     |                           |
|                           |     |  Cost: ~$0.003/req        |     |  Cost: ~$0.05/req         |
|  Cost: $0/req             |     |  Timeout: 15s             |     |  Timeout: 60s             |
|  Latency: <100ms          |     |  Rate: 200/hour           |     |  Rate: 50/hour            |
+------------+--------------+     +------------+--------------+     +---------------------------+
             |                                 |                                 ^
             | anomaly detected                | confidence < 0.7               |
             +---------------->----------------+---------------->---------------+
                                               |
                                               | confidence >= 0.7
                                               v
                                     [Return explanation]
```

### 1.2. Decision Matrix

| Condition | Action | Next Level |
|-----------|--------|------------|
| Z-score < 2.0 AND no rule violations | No anomaly | -- |
| Z-score >= 2.0 OR rule violation detected | Create anomaly (Level 1) | Level 2 |
| Level 2 confidence >= 0.7 | Accept explanation | -- |
| Level 2 confidence < 0.7 | Escalate | Level 3 |
| Level 3 completed | Accept investigation | -- |
| Level 3 timeout (60s) | Fallback to Level 1 summary | -- |
| Daily budget >= 80% ($40) | Degrade to Level 1 only | -- |
| Daily budget >= 100% ($50) | Hard stop, Level 1 only | -- |

### 1.3. Request Flow (sequence)

```
[profitability-service]
        |
        | gRPC: CheckAnomaly(shipment_id, deviation, profitability)
        v
[analytics-service: Level 1]
        |
        | 1. Z-score analysis (90-day window)
        | 2. ARIMA trend check
        | 3. Business rule evaluation
        | 4. Aggregate monitoring update
        |
        +-- not anomaly --> return {is_anomaly: false}
        |
        +-- anomaly detected --> persist Anomaly (status: open)
        |
        | check budget: daily_cost < $40?
        +-- NO --> return {is_anomaly: true, level: "1", anomaly_id}
        |
        +-- YES --> async: dispatch Level 2
                            |
                    [Level 2: Sonnet 4.6]
                            |
                            | System prompt (cached ~20K tokens)
                            | User prompt (anomaly + context data)
                            |
                            +-- confidence >= 0.7 --> update Anomaly (explanation, recommendations)
                            |
                            +-- confidence < 0.7 --> check budget: daily_cost < $45?
                                                      |
                                              NO --> keep Level 2 result as-is
                                                      |
                                              YES --> dispatch Level 3
                                                        |
                                                [Level 3: Opus 4.6]
                                                        |
                                                        | Tool loop (max 10 iterations, 60s)
                                                        | Tools: query_shipments, query_client_history,
                                                        |        query_price_changes, calculate_what_if,
                                                        |        get_approval_history
                                                        |
                                                        +--> update Anomaly + Investigation
```

---

## 2. Level 1: Deterministic Analytics

### 2.1. Z-Score Anomaly Detection

**Algorithm:** Modified Z-score for profitability deviation detection.

**Formula:**
```
Z = (x - mu) / sigma

where:
  x     = current shipment profitability deviation (BR-004)
  mu    = mean deviation over sliding window
  sigma = standard deviation over sliding window

Window: 90 calendar days
Threshold: |Z| >= 2.0 (anomaly)
Minimum samples: 30 (below 30 -- skip Z-score, use rule engine only)
```

**Mathematical details:**

```
mu = (1/N) * SUM(x_i), i=1..N

sigma = sqrt((1/(N-1)) * SUM((x_i - mu)^2)), i=1..N

where N = count of profitability calculations in last 90 days
      x_i = deviation value for calculation i
```

**Segmentation:** Z-score is computed independently per:
- Per manager (manager_id)
- Per business unit (business_unit_id)
- Per client (client_id)
- Overall (system-wide)

An anomaly is flagged if ANY segment exceeds the threshold.

```go
// internal/analytics/zscore.go

package analytics

import (
	"context"
	"math"
	"time"

	"github.com/google/uuid"
	"gonum.org/v1/gonum/stat"
)

const (
	ZScoreWindow       = 90 * 24 * time.Hour // 90 days
	ZScoreThreshold    = 2.0
	MinSamplesForZScore = 30
)

// ZScoreDetector implements Z-score anomaly detection.
type ZScoreDetector struct {
	repo DeviationRepository
}

// DeviationRepository -- port for historical deviation data.
type DeviationRepository interface {
	// GetDeviations returns deviation values for the given entity
	// within the time window, ordered by timestamp ascending.
	GetDeviations(ctx context.Context, entityType string, entityID uuid.UUID,
		from, to time.Time) ([]float64, error)
}

// DetectZScore computes Z-score for a new deviation value against
// the 90-day historical window.
//
// Returns (z-score, isAnomaly).
// If fewer than MinSamplesForZScore values exist, returns (0, false).
func (d *ZScoreDetector) DetectZScore(
	ctx context.Context,
	values []float64,
	current float64,
) (float64, bool) {
	if len(values) < MinSamplesForZScore {
		return 0, false
	}

	mean := stat.Mean(values, nil)
	stddev := stat.StdDev(values, nil)

	// Avoid division by zero when all historical values are identical.
	if stddev == 0 {
		if current == mean {
			return 0, false
		}
		// Any deviation from a constant series is an anomaly.
		return math.Inf(1), true
	}

	zscore := (current - mean) / stddev
	return zscore, math.Abs(zscore) >= ZScoreThreshold
}
```

**Test cases (Z-score):**

| ID | Input (values) | Current | Expected Z | Anomaly? | Rationale |
|----|----------------|---------|------------|----------|-----------|
| Z-TC-01 | 30 values, all = 5.0 | 5.0 | 0.0 | No | Identical to history |
| Z-TC-02 | 30 values, mean=5.0, stddev=1.0 | 7.5 | 2.5 | Yes | Z=2.5 > 2.0 |
| Z-TC-03 | 30 values, mean=5.0, stddev=1.0 | 6.5 | 1.5 | No | Z=1.5 < 2.0 |
| Z-TC-04 | 30 values, mean=5.0, stddev=1.0 | 2.0 | -3.0 | Yes | Z=-3.0, |Z|>2.0 |
| Z-TC-05 | 29 values | any | 0.0 | No | Below minimum samples |
| Z-TC-06 | 30 values, all = 5.0 | 5.1 | +Inf | Yes | stddev=0, any deviation = anomaly |
| Z-TC-07 | 100 values, normal dist (5.0, 2.0) | 5.0 | ~0.0 | No | Near mean |
| Z-TC-08 | 100 values, normal dist (5.0, 2.0) | 10.0 | ~2.5 | Yes | Far above mean |

### 2.2. ARIMA Forecast

**Algorithm:** ARIMA(1,1,1) model for 30-day profitability trend prediction.

**Formulas:**

```
ARIMA(p, d, q) = ARIMA(1, 1, 1)

Differencing (d=1):
  Y_t = X_t - X_{t-1}

AR(1) component:
  Y_t = c + phi_1 * Y_{t-1} + epsilon_t

MA(1) component:
  Y_t = c + epsilon_t + theta_1 * epsilon_{t-1}

Combined ARIMA(1,1,1):
  (X_t - X_{t-1}) = c + phi_1 * (X_{t-1} - X_{t-2}) + epsilon_t + theta_1 * epsilon_{t-1}

Confidence interval (95%):
  Upper = forecast + 1.96 * sqrt(forecast_variance)
  Lower = forecast - 1.96 * sqrt(forecast_variance)

Input data: daily average profitability deviation, 90-day history
Output: 30-day predicted values with 95% confidence interval
Minimum data points: 60 days (for stable parameter estimation)
```

```go
// internal/analytics/forecast.go

package analytics

import (
	"context"
	"time"
)

// Forecast represents a 30-day profitability prediction.
type Forecast struct {
	PredictedValues []TimeSeriesPoint
	UpperBound      []TimeSeriesPoint // 95% confidence upper
	LowerBound      []TimeSeriesPoint // 95% confidence lower
	Confidence      float64           // overall model confidence (R-squared)
	ModelParams     ARIMAParams
}

type TimeSeriesPoint struct {
	Timestamp time.Time
	Value     float64
}

type ARIMAParams struct {
	P     int     // AR order (1)
	D     int     // differencing order (1)
	Q     int     // MA order (1)
	Phi   float64 // AR coefficient
	Theta float64 // MA coefficient
	C     float64 // constant
}

// Forecaster -- port for time series forecasting.
type Forecaster interface {
	// Forecast generates a 30-day prediction from historical data.
	// Requires minimum 60 data points.
	// Returns error if data insufficient or model fails to converge.
	Forecast(ctx context.Context, historicalData []TimeSeriesPoint) (*Forecast, error)
}
```

**Test cases (ARIMA):**

| ID | Input | Expected | Rationale |
|----|-------|----------|-----------|
| AR-TC-01 | 90 days, linear uptrend (1.0 -> 10.0) | Predicted: upward continuation | Trend detection |
| AR-TC-02 | 90 days, stable at 5.0 (+/- 0.1) | Predicted: 5.0 +/- narrow band | Stability detection |
| AR-TC-03 | 90 days, sudden drop last 7 days | Predicted: downward, wide CI | Shock detection |
| AR-TC-04 | 59 data points | Error: insufficient data | Minimum 60 required |
| AR-TC-05 | 90 days, seasonal pattern | Predicted: continuation of pattern | Seasonal detection |

### 2.3. Business Rule Engine (Threshold Rules)

All LS-BR-* business rules evaluated as deterministic conditions. Each rule produces a `RuleViolation` if triggered.

```go
// internal/analytics/rules.go

package analytics

import (
	"context"

	"github.com/google/uuid"
)

// RuleViolation represents a triggered business rule.
type RuleViolation struct {
	RuleID      string  // e.g. "margin_drop_7d"
	Description string
	Severity    string  // critical / high / medium / low
	Value       float64 // actual measured value
	Threshold   float64 // configured threshold
}

// RuleEngine evaluates deterministic business rules.
type RuleEngine interface {
	// EvaluateAll runs all rules for a given shipment and returns violations.
	EvaluateAll(ctx context.Context, shipmentID uuid.UUID) ([]RuleViolation, error)
}
```

**Rules catalog:**

| Rule ID | Description | Condition | Severity | Threshold | ФМ Reference |
|---------|-------------|-----------|----------|-----------|--------------|
| `margin_drop_7d` | Margin dropped >5 п.п. in 7 days | avg_deviation(7d) - avg_deviation(today) > 5.0 | high | 5.0 п.п. | BR-004 |
| `volume_anomaly` | Order volume >3x average | order_count(today) / avg_order_count(30d) > 3.0 | high | 3.0x | -- |
| `client_deviation` | Client deviates from historical pattern | |client_avg_margin - current_margin| > 2 * client_stddev | medium | 2 sigma | -- |
| `npss_age_warning` | НПСС age 31-60 days | npss_age IN [31, 60] | low | 30 days | BR-052 |
| `npss_age_confirm` | НПСС age 61-90 days | npss_age IN [61, 90] | medium | 60 days | BR-053 |
| `npss_age_block` | НПСС age >90 days | npss_age > 90 | critical | 90 days | BR-054 |
| `auto_approval_limit_mgr` | Manager daily auto-approval limit near ceiling | daily_auto_approved / 20000 > 0.8 | medium | 80% of 20,000 | BR-011 |
| `auto_approval_limit_bu` | BU daily auto-approval limit near ceiling | daily_auto_approved_bu / 100000 > 0.8 | medium | 80% of 100,000 | BR-012 |
| `approver_overload_30` | Approver queue >30 tasks | queue_count > 30 | high | 30 | BR-070 |
| `approver_overload_50` | Approver daily tasks >50 | daily_count > 50 | critical | 50 | BR-071 |
| `emergency_limit_mgr` | Manager emergency limit near cap | emergency_count >= (is_peak ? 4 : 2) | medium | peak: 5, normal: 3 | BR-030 |
| `emergency_limit_client` | Client emergency limit near cap | emergency_count >= (is_peak ? 7 : 4) | medium | peak: 8, normal: 5 | BR-031 |
| `sla_breach_risk` | SLA <25% remaining time | remaining_pct < 25% | high | 25% | BR-014 |
| `exchange_rate_trigger` | Currency changed >5% in 7 days | |rate_today - rate_7d_ago| / rate_7d_ago > 0.05 | high | 5% | LS-BR-075 |
| `purchase_price_trigger` | Purchase price deviates >15% from НПСС | |purchase - npss| / npss > 0.15 | high | 15% | LS-BR-075b |
| `cherry_picking_pattern` | Client fulfills only low-margin items | fulfilled_avg_margin < planned_margin * 0.7 AND fulfillment_rate < 0.6 | critical | 70% margin, 60% rate | -- |
| `correction_iterations` | Price correction approaching limit | iteration_count >= 4 | medium | 4 of 5 max | BR-019 |

**Test cases (Rule Engine):**

| ID | Rule | Input | Expected | Rationale |
|----|------|-------|----------|-----------|
| RE-TC-01 | margin_drop_7d | avg_7d_ago=15.0, today=9.5 | Violation (5.5 > 5.0) | Margin drop detected |
| RE-TC-02 | margin_drop_7d | avg_7d_ago=15.0, today=10.5 | No violation (4.5 < 5.0) | Within threshold |
| RE-TC-03 | volume_anomaly | avg_30d=10, today=31 | Violation (3.1x > 3.0x) | Volume spike |
| RE-TC-04 | npss_age_block | age=91 days | Violation (critical) | НПСС too old |
| RE-TC-05 | cherry_picking | margin=8.0, planned=15.0, rate=0.5 | Violation (53% < 70%, 50% < 60%) | Cherry-picking detected |
| RE-TC-06 | approver_overload_30 | queue=31 | Violation (31 > 30) | Overflow threshold |
| RE-TC-07 | auto_approval_limit_mgr | daily=16500 | Violation (82.5% > 80%) | Near ceiling |
| RE-TC-08 | exchange_rate_trigger | rate_today=95.0, rate_7d=90.0 | Violation (5.6% > 5%) | Currency change |
| RE-TC-09 | purchase_price_trigger | purchase=120, npss=100 | Violation (20% > 15%) | Purchase price deviation |
| RE-TC-10 | correction_iterations | count=4 | Violation (4 >= 4) | Near max iterations |

### 2.4. Aggregate Monitoring

Cumulative tracking of key metrics per entity over time.

```go
// internal/analytics/aggregate.go

package analytics

import (
	"context"
	"time"

	"github.com/google/uuid"
)

// AggregateMetrics holds cumulative tracking data for an entity.
type AggregateMetrics struct {
	EntityType    string    // "manager", "business_unit", "client"
	EntityID      uuid.UUID
	Period        time.Time // truncated to day

	// Profitability metrics
	TotalOrders        int
	TotalRevenue       float64
	TotalCostNPSS      float64
	AvgDeviation       float64
	MaxDeviation       float64
	MinDeviation       float64
	StdDevDeviation    float64

	// Approval metrics
	AutoApprovedCount  int
	AutoApprovedAmount float64 // RUB
	ManualApprovedCount int
	RejectedCount      int
	AvgApprovalTimeMin float64

	// Anomaly metrics
	AnomalyCount       int
	FalsePositiveCount int
}

// AggregateMonitor -- port for cumulative tracking.
type AggregateMonitor interface {
	// Record updates aggregate metrics when a new calculation occurs.
	Record(ctx context.Context, entityType string, entityID uuid.UUID,
		deviation float64, orderAmount float64) error

	// GetMetrics retrieves aggregate metrics for a period.
	GetMetrics(ctx context.Context, entityType string, entityID uuid.UUID,
		from, to time.Time) ([]AggregateMetrics, error)

	// GetTopAnomalous returns entities with highest anomaly rates.
	GetTopAnomalous(ctx context.Context, entityType string,
		limit int, from, to time.Time) ([]AggregateMetrics, error)
}
```

---

## 3. Level 2: LLM Interpretation (Sonnet 4.6)

### 3.1. System Prompt Template (FULL TEXT)

The system prompt is designed to be approximately 20,000 tokens and is cached across requests for a 90% cost reduction on input tokens.

```
You are an expert financial analyst for EKF Group, a major Russian electrical
equipment distributor. You analyze profitability anomalies in the shipment control
system (FM-LS-PROFIT).

## Domain Context

### Business Model
EKF Group sells electrical equipment through Local Estimates (LS / Локальные Сметы).
An LS is a price agreement with a client for a set of products with fixed prices.
Clients can make partial shipments (orders) against an LS over its lifetime.

The core problem is "cherry-picking" -- clients selectively order low-margin items
from an LS while leaving high-margin items unfulfilled, reducing overall profitability.

### Key Metrics

**Profitability of a line item:**
  profitability_item = (Price - NPSS) / Price * 100%
  where NPSS = Normative Planned Cost Price (from SBS-58 project)

**Cumulative + Order profitability:**
  profitability_cumulative_plus_order =
    (Revenue_shipped + Revenue_order - Cost_shipped - Cost_order) /
    (Revenue_shipped + Revenue_order) * 100%

**Remainder profitability:**
  profitability_remainder =
    SUM((Price_i - NPSS_i) * Qty_i) / SUM(Price_i * Qty_i) * 100%
  where i = unfulfilled items, excluding orders with status "pending_approval" or "approved"

**Deviation from plan:**
  deviation = planned_profitability - MAX(cumulative_plus_order, remainder_profitability)
  Rounded to 2 decimal places BEFORE comparing with thresholds.

**Net revenue:**
  net_revenue = shipment_amount - returns - discounts

### Approval Thresholds
- deviation < 1.00 pp: auto-approved (limits: 5,000 RUB/day per manager,
  20,000 RUB/day aggregate per manager, 100,000 RUB/day per BU)
- 1.00-15.00 pp: approved by RBU (Business Unit Head)
- 15.01-25.00 pp: approved by DP (Sales Director)
- > 25.00 pp: approved by GD (General Director)

### SLA (approval deadlines)
- P1 (orders < 100K RUB): RBU 2h, DP 4h, GD 12h
- P2 (orders 100K-1M RUB): RBU 24h, DP 48h, GD 72h
- P3 (orders > 1M RUB): individual
- Auto-escalation on SLA breach: RBU -> DRP Director, DP -> GD, GD -> auto-reject + CFO notification

### NPSS (Normative Planned Cost Price)
- Source: SBS-58 (average purchase price over 6 months * country transport cost coefficient)
- Products from own manufacturing: internal price from SBS-130
- NPSS age thresholds: 0-30d OK, 31-60d warning, 61-90d requires RBU confirmation, >90d blocks approval
- Auto-triggers: currency rate change >5% in 7 days, purchase price deviation >15% from NPSS

### Emergency Approvals
- Manager limit: 3/month (5 in peak months: December, August)
- Client limit: 5/month (8 in peak)
- Post-factum control: 24h confirmation required, 48h escalation to DP

### ELMA Fallback
- When ELMA BPM is unavailable: auto-approve deviations <= 5 pp, queue FIFO for > 5 pp
- Priority: P1 first, then P2 within FIFO

### Sanctions (Phase 2)
- Fulfillment < 50%: max discount reduced by 3 pp
- Fulfillment < 30%: max discount reduced by 10 pp
- Fulfillment < 10%: standard prices only
- Rehabilitation: 6 months without violations
- Strategic clients: DP can cancel sanction (max 3 times/year)

### Users
- Sales managers (~50): create LS, make orders, correct prices
- RBU (~10): approve deviations 1-15 pp
- Sales Director (DP, 1-2): approve 15-25 pp
- General Director (GD, 1): approve > 25 pp
- Financial Director (FD, 1): reports, monitoring
- Analysts (2-3): reports, NPSS monitoring

### Cross-Validation
When LS planned profitability changes:
1. Recalculate deviation for all approved orders (before warehouse handoff)
2. If approval level changed: revoke approval, re-route
3. If level unchanged: approval remains valid
4. >= 3 revocations on same LS: escalate to DP

## Your Task

When presented with an anomaly:
1. Analyze the anomaly data (Z-score, rule violations, affected entity)
2. Consider the context (recent shipments, client history, price changes)
3. Identify the most likely explanation
4. Assess severity and potential financial impact
5. Provide actionable recommendations

## Output Format

You MUST respond with valid JSON matching this schema:

{
  "explanation": "string -- clear explanation of the anomaly in Russian, 2-5 sentences",
  "confidence": "number -- 0.0 to 1.0, how confident you are in the explanation",
  "recommendations": ["string -- list of 1-5 actionable recommendations in Russian"],
  "requires_level_3": "boolean -- true if confidence < 0.7 and investigation needed",
  "severity": "string -- critical / high / medium / low",
  "financial_impact_rub": "number or null -- estimated impact in RUB if calculable",
  "affected_entities": [
    {
      "type": "string -- ls / shipment / client / manager",
      "id": "string -- UUID",
      "role": "string -- what role this entity plays in the anomaly"
    }
  ]
}

## Constraints
- Always respond in Russian for explanation and recommendations
- Never speculate without evidence -- if data is insufficient, set confidence < 0.7
- Never disclose internal system details (model names, architecture)
- Focus on business impact, not technical details
- If you cannot determine the cause, say so explicitly and set requires_level_3: true
```

### 3.2. Use Cases

| Use Case | Trigger | Input | Expected Output |
|----------|---------|-------|-----------------|
| UC-L2-01 | Anomaly explanation | Z-score, rule violations, context | JSON: explanation, confidence, recommendations |
| UC-L2-02 | Report summarization | Daily efficiency report data | Text summary in Russian |
| UC-L2-03 | Q&A about data | Analyst question + relevant context | Text answer in Russian |

### 3.3. Output Schema

```go
// internal/analytics/ai/types.go

package ai

// AnomalyExplanation -- structured output from Level 2.
type AnomalyExplanation struct {
	Explanation      string           `json:"explanation"`
	Confidence       float64          `json:"confidence"`
	Recommendations  []string         `json:"recommendations"`
	RequiresLevel3   bool             `json:"requires_level_3"`
	Severity         string           `json:"severity"`
	FinancialImpact  *float64         `json:"financial_impact_rub"`
	AffectedEntities []AffectedEntity `json:"affected_entities"`
}

type AffectedEntity struct {
	Type string `json:"type"` // ls, shipment, client, manager
	ID   string `json:"id"`
	Role string `json:"role"`
}

// ReportSummary -- structured output for report summarization.
type ReportSummary struct {
	Summary        string   `json:"summary"`
	KeyFindings    []string `json:"key_findings"`
	Trends         []string `json:"trends"`
	Recommendations []string `json:"recommendations"`
}

// QAResponse -- structured output for analyst Q&A.
type QAResponse struct {
	Answer     string   `json:"answer"`
	Confidence float64  `json:"confidence"`
	Sources    []string `json:"sources"` // references to data used
}
```

### 3.4. 10 Sample Prompts with Expected Outputs

**Sample 1: Cherry-picking detection**
```json
{
  "role": "user",
  "content": "Anomaly detected:\n- Type: cherry_picking_pattern\n- Z-score: 3.2\n- Client: OOO Electro-Trade (ID: a1b2c3)\n- LS: LS-2026-00142\n- Planned profitability: 18.5%\n- Fulfilled margin avg: 8.2%\n- Fulfillment rate: 45%\n- Last 5 orders: all low-margin items (cables, connectors)\n- Unfulfilled: high-margin items (switches, breakers)\n- Total LS value: 4,200,000 RUB"
}
```

Expected output:
```json
{
  "explanation": "Контрагент ООО «Электро-Трейд» систематически выкупает только низкомаржинальные позиции (кабели, коннекторы) из ЛС-2026-00142, оставляя высокомаржинальные товары (выключатели, автоматы). Средняя маржинальность выкупленного -- 8.2% при плане 18.5%, что на 10.3 п.п. ниже целевого показателя. При текущем темпе выкупа (45%) остаток ЛС будет содержать исключительно высокомаржинальные позиции, которые клиент, вероятно, не намерен выкупать.",
  "confidence": 0.92,
  "recommendations": [
    "Направить информацию руководителю БЮ для анализа паттерна закупок клиента",
    "Рассмотреть пересмотр условий ЛС при следующем продлении",
    "Проверить историю выкупа по другим ЛС данного клиента за последние 6 месяцев"
  ],
  "requires_level_3": false,
  "severity": "critical",
  "financial_impact_rub": 433200,
  "affected_entities": [
    {"type": "client", "id": "a1b2c3", "role": "Контрагент с паттерном выборочного выкупа"},
    {"type": "ls", "id": "ls-2026-00142", "role": "ЛС с аномальным выкупом"}
  ]
}
```

**Sample 2: NPSS age critical**
```json
{
  "role": "user",
  "content": "Anomaly detected:\n- Type: npss_age_block\n- Affected: 12 line items in LS-2026-00089\n- NPSS age: 95 days\n- Products: import (China)\n- CNY/RUB change last 90d: +8.3%\n- Last NPSS update: 2025-11-28\n- Current purchase prices: +12% vs NPSS"
}
```

Expected output:
```json
{
  "explanation": "В ЛС-2026-00089 обнаружено 12 позиций с НПСС старше 90 дней (95 дн.), что автоматически блокирует согласование. Это импортные товары из Китая, при этом курс юаня вырос на 8.3% за последние 90 дней, а фактические закупочные цены на 12% выше зафиксированной НПСС. Расчёт рентабельности по устаревшей НПСС занижает реальную себестоимость и создаёт иллюзию прибыльности.",
  "confidence": 0.95,
  "recommendations": [
    "Инициировать пересчёт НПСС по импортным позициям (автотриггер LS-BR-075: курс > 5%)",
    "Заблокировать согласование до обновления НПСС",
    "Проверить все ЛС с импортными позициями из Китая на аналогичную проблему"
  ],
  "requires_level_3": false,
  "severity": "critical",
  "financial_impact_rub": null,
  "affected_entities": [
    {"type": "ls", "id": "ls-2026-00089", "role": "ЛС с устаревшей НПСС"}
  ]
}
```

**Sample 3: Volume spike**
```json
{
  "role": "user",
  "content": "Anomaly detected:\n- Type: volume_anomaly\n- Z-score: 2.8\n- Manager: Ivanov A.S. (ID: m001)\n- Today orders: 35\n- 30-day average: 8.5 orders/day\n- All orders: small amounts (10K-50K RUB)\n- All auto-approved (deviation < 1 pp)\n- Daily auto-approval total: 18,500 RUB (limit: 20,000)"
}
```

Expected output:
```json
{
  "explanation": "Менеджер Иванов А.С. оформил 35 заказов за сегодня при среднем показателе 8.5 заказов/день (в 4.1 раза выше нормы). Все заказы -- мелкие суммы (10-50 тыс. руб.) с минимальным отклонением от плана, проходящие автосогласование. Суммарный объём автосогласований достиг 18,500 из 20,000 руб. дневного лимита. Паттерн может указывать на дробление крупного заказа для обхода порога согласования.",
  "confidence": 0.78,
  "recommendations": [
    "Проверить, относятся ли заказы к одному контрагенту или ЛС",
    "Проверить корреляцию по времени оформления (пакетное создание)",
    "При подтверждении дробления -- уведомить РБЮ для ручной проверки"
  ],
  "requires_level_3": false,
  "severity": "high",
  "financial_impact_rub": null,
  "affected_entities": [
    {"type": "manager", "id": "m001", "role": "Менеджер с аномальным количеством заказов"}
  ]
}
```

**Sample 4: Approver overload**
```json
{
  "role": "user",
  "content": "Anomaly detected:\n- Type: approver_overload_50\n- Approver: Petrov B.V. (RBU, BU-North)\n- Queue count: 52\n- Daily processed: 38\n- Avg processing time: 45 min\n- SLA breaches today: 3\n- Deputy: not assigned"
}
```

Expected output:
```json
{
  "explanation": "Согласующий Петров Б.В. (РБЮ, БЮ-Север) перегружен: в очереди 52 задачи, за день обработано 38. Среднее время обработки 45 минут. Зафиксировано 3 нарушения SLA за сегодня. Заместитель не назначен, механизм автоперелива (порог 30) не сработал из-за отсутствия заместителя.",
  "confidence": 0.97,
  "recommendations": [
    "Срочно назначить заместителя для БЮ-Север в справочнике согласующих",
    "Проанализировать причину скачка: рост заказов или отсутствие согласующего ранее",
    "Рассмотреть временное перераспределение задач на РБЮ смежных БЮ"
  ],
  "requires_level_3": false,
  "severity": "critical",
  "financial_impact_rub": null,
  "affected_entities": [
    {"type": "manager", "id": "petrov-bv", "role": "Перегруженный согласующий"}
  ]
}
```

**Sample 5: Unclear anomaly (escalation to Level 3)**
```json
{
  "role": "user",
  "content": "Anomaly detected:\n- Type: margin_drop_7d\n- Z-score: 2.1\n- Entity: BU-West\n- Avg deviation 7d ago: 3.2 pp\n- Current avg deviation: 8.8 pp\n- No obvious price changes\n- No NPSS updates\n- Client mix unchanged\n- Order volume normal"
}
```

Expected output:
```json
{
  "explanation": "Средняя девиация по БЮ-Запад выросла с 3.2 до 8.8 п.п. за 7 дней без очевидных причин. Цены, НПСС, состав клиентов и объём заказов не изменились. Возможные причины: изменение структуры заказов внутри ЛС (cherry-picking по нескольким клиентам одновременно), или внешний фактор, не отражённый в предоставленных данных.",
  "confidence": 0.45,
  "recommendations": [
    "Требуется детальное расследование с анализом каждого заказа за неделю",
    "Проверить изменения в товарной матрице и ассортименте"
  ],
  "requires_level_3": true,
  "severity": "high",
  "financial_impact_rub": null,
  "affected_entities": [
    {"type": "business_unit", "id": "bu-west", "role": "БЮ с необъяснимым ростом девиации"}
  ]
}
```

**Sample 6: Exchange rate trigger**
```json
{
  "role": "user",
  "content": "Anomaly detected:\n- Type: exchange_rate_trigger\n- Currency: USD\n- Rate 7d ago: 88.50\n- Rate today: 93.20\n- Change: +5.3%\n- Affected products: 340 items (import USA)\n- Active LS with these products: 28"
}
```

Expected output:
```json
{
  "explanation": "Курс USD вырос на 5.3% за 7 дней (с 88.50 до 93.20 руб.), превысив порог автотриггера НПСС (5%). Это затрагивает 340 импортных позиций (США) в 28 активных ЛС. НПСС этих позиций рассчитана по старому курсу и занижена, что создаёт риск убыточных отгрузок.",
  "confidence": 0.98,
  "recommendations": [
    "Запустить автоматический пересчёт НПСС для всех затронутых позиций (LS-BR-075)",
    "Временно приостановить автосогласование по ЛС с импортными позициями до пересчёта",
    "Уведомить финансовую службу о необходимости проверки результатов пересчёта"
  ],
  "requires_level_3": false,
  "severity": "high",
  "financial_impact_rub": null,
  "affected_entities": [
    {"type": "ls", "id": "multiple-28", "role": "28 ЛС с импортными позициями USD"}
  ]
}
```

**Sample 7: Auto-approval limit approaching**
```json
{
  "role": "user",
  "content": "Anomaly detected:\n- Type: auto_approval_limit_bu\n- BU: BU-South\n- Daily auto-approved: 85,000 RUB (limit: 100,000)\n- Time: 14:30 (4.5h remaining in business day)\n- Managers contributing: 5 (Sidorov 22K, Kozlov 18K, Orlova 17K, Novikov 15K, Guseva 13K)\n- All within individual limits (max 20K)"
}
```

Expected output:
```json
{
  "explanation": "БЮ-Юг израсходовал 85,000 из 100,000 руб. дневного агрегированного лимита автосогласований к 14:30 (осталось 4.5 часа рабочего дня). Все 5 менеджеров в рамках индивидуальных лимитов. Оставшийся запас 15,000 руб. может быть исчерпан, после чего все заказы с отклонением < 1 п.п. будут направляться на ручное согласование РБЮ.",
  "confidence": 0.93,
  "recommendations": [
    "Предупредить менеджеров БЮ-Юг о скором исчерпании лимита",
    "Подготовить РБЮ к возможному увеличению потока заявок после 15:00",
    "Проанализировать причину высокого объёма автосогласований (рост продаж или систематический паттерн)"
  ],
  "requires_level_3": false,
  "severity": "medium",
  "financial_impact_rub": null,
  "affected_entities": [
    {"type": "business_unit", "id": "bu-south", "role": "БЮ с высоким объёмом автосогласований"}
  ]
}
```

**Sample 8: ELMA fallback triggered**
```json
{
  "role": "user",
  "content": "Anomaly detected:\n- Type: elma_fallback_active\n- Duration: 25 minutes\n- Auto-approved (<=5pp): 8 orders\n- Queued (>5pp): 3 orders (P1: 1, P2: 2)\n- Queue waiting time: 12-25 min\n- ELMA health checks: 5 consecutive failures"
}
```

Expected output:
```json
{
  "explanation": "ELMA BPM недоступна 25 минут (5 последовательных ошибок подключения). Активирован резервный режим: 8 заказов с отклонением до 5 п.п. автосогласованы, 3 заказа с отклонением > 5 п.п. поставлены в очередь FIFO (1 заказ P1, 2 заказа P2). Время ожидания в очереди 12-25 минут.",
  "confidence": 0.99,
  "recommendations": [
    "Уведомить администраторов ELMA о недоступности системы",
    "Контролировать рост очереди -- при превышении 10 заказов эскалировать на ДП",
    "После восстановления ELMA проверить корректность автосогласованных заказов (постфактум контроль)"
  ],
  "requires_level_3": false,
  "severity": "high",
  "financial_impact_rub": null,
  "affected_entities": []
}
```

**Sample 9: Correction iteration limit**
```json
{
  "role": "user",
  "content": "Anomaly detected:\n- Type: correction_iterations\n- Shipment: ORD-2026-08721\n- LS: LS-2026-00201\n- Current iteration: 4 (max: 5)\n- Deviation history: 12.3 -> 8.7 -> 6.2 -> 4.1 pp\n- Manager: Kuznetsova E.A.\n- RBU comment on iter 4: 'С корректировкой цены -2%'"
}
```

Expected output:
```json
{
  "explanation": "Заказ ORD-2026-08721 прошёл 4 из 5 допустимых итераций корректировки цены. Менеджер Кузнецова Е.А. последовательно снижала отклонение: 12.3 -> 8.7 -> 6.2 -> 4.1 п.п. На последней итерации РБЮ запросил дополнительную корректировку -2%. Если после 5-й итерации отклонение останется выше 1 п.п., заказ будет автоматически отклонён.",
  "confidence": 0.96,
  "recommendations": [
    "Предупредить менеджера о последней доступной итерации",
    "Рекомендовать корректировку цены с запасом, чтобы гарантировать попадание в порог",
    "При автоотказе -- предложить менеджеру создать новый заказ с пересмотренными ценами"
  ],
  "requires_level_3": false,
  "severity": "medium",
  "financial_impact_rub": null,
  "affected_entities": [
    {"type": "shipment", "id": "ord-2026-08721", "role": "Заказ на предпоследней итерации корректировки"},
    {"type": "manager", "id": "kuznetsova-ea", "role": "Менеджер, корректирующий цену"}
  ]
}
```

**Sample 10: Cross-validation trigger**
```json
{
  "role": "user",
  "content": "Anomaly detected:\n- Type: cross_validation_revocation\n- LS: LS-2026-00175\n- Plan changed: 22.0% -> 18.5% (-3.5 pp)\n- Affected approved orders: 4\n- Orders requiring re-approval: 2 (level changed)\n- Orders keeping approval: 2 (level unchanged)\n- Total affected amount: 1,850,000 RUB"
}
```

Expected output:
```json
{
  "explanation": "Плановая рентабельность ЛС-2026-00175 снижена с 22.0% до 18.5% (-3.5 п.п.), что запустило перекрёстный контроль 4 согласованных заказов. У 2 заказов требуемый уровень согласования изменился (вероятно, с РБЮ на ДП или выше) -- их согласование аннулировано. 2 заказа сохранили согласование, так как уровень не изменился. Общая сумма затронутых заказов: 1,850,000 руб.",
  "confidence": 0.94,
  "recommendations": [
    "Уведомить менеджера о необходимости повторного согласования 2 заказов",
    "Проверить причину изменения плана ЛС (пересчёт НПСС, ручная корректировка)",
    "При >= 3 аннулировании по данной ЛС -- эскалировать на ДП для ревью"
  ],
  "requires_level_3": false,
  "severity": "high",
  "financial_impact_rub": 1850000,
  "affected_entities": [
    {"type": "ls", "id": "ls-2026-00175", "role": "ЛС с изменённым планом"}
  ]
}
```

---

## 4. Level 3: Agentic Investigation (Opus 4.6)

### 4.1. System Prompt (FULL TEXT)

```
You are an autonomous financial investigator for EKF Group's profitability control
system (FM-LS-PROFIT). Your task is to conduct thorough investigations of anomalies
that could not be explained with high confidence by the initial analysis.

## Investigation Protocol

1. EXAMINE the anomaly data -- understand what was detected and why initial analysis
   was inconclusive
2. QUERY relevant shipments to find patterns in recent orders
3. CHECK client history for behavioral changes
4. ANALYZE price and NPSS changes that could explain the anomaly
5. RUN what-if scenarios to test hypotheses
6. REVIEW approval history for process anomalies
7. SYNTHESIZE findings into a root cause with evidence chain
8. PROVIDE confidence score and actionable recommendation

## Rules

- Maximum 10 tool calls per investigation
- Focus on FACTUAL EVIDENCE, not speculation
- If evidence is insufficient after exhausting tools, state confidence < 0.5
  and recommend manual review
- Always consider multiple hypotheses before concluding
- Prioritize financial impact assessment
- Respond in Russian

## Domain Knowledge

(same domain context as Level 2 system prompt -- see section 3.1)

## Output Format

After completing your investigation, provide a final answer as valid JSON:

{
  "root_cause": "string -- identified root cause in Russian, 3-10 sentences",
  "evidence_chain": [
    {
      "step": "number -- investigation step",
      "finding": "string -- what was found",
      "significance": "string -- why it matters"
    }
  ],
  "recommendation": "string -- actionable recommendation in Russian, 2-5 sentences",
  "confidence_score": "number -- 0.0 to 1.0",
  "financial_impact_rub": "number or null",
  "requires_manual_review": "boolean -- true if confidence < 0.5"
}
```

### 4.2. Tool Definitions (JSON Schema)

```json
[
  {
    "name": "query_shipments",
    "description": "Query shipments/orders filtered by LS, client, manager, date range, or status. Returns summary data including profitability, deviation, amounts, and approval status.",
    "input_schema": {
      "type": "object",
      "properties": {
        "local_estimate_id": {
          "type": "string",
          "description": "UUID of the Local Estimate (LS). Optional."
        },
        "client_id": {
          "type": "string",
          "description": "UUID of the client. Optional."
        },
        "manager_id": {
          "type": "string",
          "description": "UUID of the manager. Optional."
        },
        "status": {
          "type": "string",
          "enum": ["draft", "pending_calculation", "pending_approval", "approved", "rejected", "shipped", "returned"],
          "description": "Filter by shipment status. Optional."
        },
        "date_from": {
          "type": "string",
          "format": "date",
          "description": "Start date (inclusive). Format: YYYY-MM-DD. Optional."
        },
        "date_to": {
          "type": "string",
          "format": "date",
          "description": "End date (inclusive). Format: YYYY-MM-DD. Optional."
        },
        "limit": {
          "type": "integer",
          "default": 50,
          "maximum": 200,
          "description": "Max number of results. Default: 50."
        }
      },
      "required": []
    }
  },
  {
    "name": "query_client_history",
    "description": "Get client's historical data: order volumes, frequency, average margin, fulfillment rates, active sanctions, and behavioral patterns over the specified period.",
    "input_schema": {
      "type": "object",
      "properties": {
        "client_id": {
          "type": "string",
          "description": "UUID of the client."
        },
        "months": {
          "type": "integer",
          "default": 6,
          "minimum": 1,
          "maximum": 24,
          "description": "Number of months of history to retrieve. Default: 6."
        }
      },
      "required": ["client_id"]
    }
  },
  {
    "name": "query_price_changes",
    "description": "Get price and NPSS changes for specific products. Returns history of NPSS updates, purchase price changes, currency rate impacts, and any auto-triggers that fired.",
    "input_schema": {
      "type": "object",
      "properties": {
        "product_ids": {
          "type": "array",
          "items": {"type": "string"},
          "description": "UUIDs of products to check. Max 50."
        },
        "date_from": {
          "type": "string",
          "format": "date",
          "description": "Start date. Format: YYYY-MM-DD."
        }
      },
      "required": ["product_ids", "date_from"]
    }
  },
  {
    "name": "calculate_what_if",
    "description": "Run a what-if scenario: calculate profitability with modified parameters (different prices, quantities, or excluded items). Returns recalculated deviation and approval level.",
    "input_schema": {
      "type": "object",
      "properties": {
        "local_estimate_id": {
          "type": "string",
          "description": "UUID of the LS for the scenario."
        },
        "scenario": {
          "type": "object",
          "properties": {
            "modified_items": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "product_id": {"type": "string"},
                  "new_price": {"type": "number", "description": "Modified price in RUB"},
                  "new_quantity": {"type": "integer", "description": "Modified quantity"}
                },
                "required": ["product_id"]
              },
              "description": "Items with modified prices or quantities."
            },
            "excluded_shipment_ids": {
              "type": "array",
              "items": {"type": "string"},
              "description": "Shipments to exclude from cumulative calculation."
            }
          }
        }
      },
      "required": ["local_estimate_id", "scenario"]
    }
  },
  {
    "name": "get_approval_history",
    "description": "Get the complete approval history for a shipment or LS: all approval requests, decisions, escalations, corrections, SLA breaches, and comments.",
    "input_schema": {
      "type": "object",
      "properties": {
        "shipment_id": {
          "type": "string",
          "description": "UUID of the shipment. Optional (provide either shipment_id or local_estimate_id)."
        },
        "local_estimate_id": {
          "type": "string",
          "description": "UUID of the LS. Optional."
        }
      },
      "required": []
    }
  }
]
```

### 4.3. Orchestration Pseudocode

```go
// internal/analytics/ai/investigator.go

package ai

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/anthropics/anthropic-sdk-go"
	"github.com/google/uuid"
)

const (
	MaxIterations       = 10
	InvestigationTimeout = 60 * time.Second
	InvestigatorModel   = "claude-opus-4-6-20250514"
)

// Investigator orchestrates Level 3 agentic investigations.
type Investigator struct {
	client *anthropic.Client
	tools  []anthropic.ToolParam
	repo   InvestigationRepository
	audit  AuditLogger
}

// Investigate runs an autonomous investigation loop.
//
// Algorithm:
//  1. Build initial messages: system prompt + anomaly context
//  2. Loop (max 10 iterations, 60s timeout):
//     a. Call Opus 4.6 with tools
//     b. If response contains tool_use: execute tool, append result, continue
//     c. If response is text (end_turn): parse as Investigation result, break
//     d. If timeout: return partial result with confidence 0.3
//  3. Persist Investigation with evidence chain
//  4. Log to audit (model, tokens, cost, latency)
func (inv *Investigator) Investigate(ctx context.Context, anomaly Anomaly) (*Investigation, error) {
	ctx, cancel := context.WithTimeout(ctx, InvestigationTimeout)
	defer cancel()

	investigation := &Investigation{
		ID:        uuid.New(),
		AnomalyID: anomaly.ID,
		StartedAt: time.Now(),
		Model:     InvestigatorModel,
	}

	// Build system prompt with cached FM context.
	systemPrompt := inv.buildSystemPrompt()

	// Build initial user message with anomaly data.
	userMessage := inv.buildAnomalyPrompt(anomaly)

	messages := []anthropic.MessageParam{
		anthropic.NewUserMessage(
			anthropic.NewTextBlock(userMessage),
		),
	}

	var totalInputTokens, totalOutputTokens, totalCachedTokens int

	for iteration := 0; iteration < MaxIterations; iteration++ {
		select {
		case <-ctx.Done():
			// Timeout -- return partial result.
			investigation.Status = "timeout"
			investigation.ConfidenceScore = 0.3
			investigation.RootCause = "Investigation timed out. Partial findings available in evidence chain."
			investigation.Recommendation = "Requires manual review due to timeout."
			investigation.CompletedAt = ptrTime(time.Now())
			investigation.Iterations = iteration
			return investigation, nil
		default:
		}

		resp, err := inv.client.Messages.New(ctx, anthropic.MessageNewParams{
			Model:     anthropic.F(InvestigatorModel),
			MaxTokens: anthropic.Int(4096),
			System: anthropic.F([]anthropic.TextBlockParam{
				{
					Text:         anthropic.String(systemPrompt),
					CacheControl: &anthropic.CacheControlEphemeralParam{},
				},
			}),
			Tools:    anthropic.F(inv.tools),
			Messages: anthropic.F(messages),
		})
		if err != nil {
			investigation.Status = "failed"
			return investigation, fmt.Errorf("claude API call failed at iteration %d: %w", iteration, err)
		}

		// Track token usage.
		totalInputTokens += int(resp.Usage.InputTokens)
		totalOutputTokens += int(resp.Usage.OutputTokens)
		if resp.Usage.CacheReadInputTokens != nil {
			totalCachedTokens += int(*resp.Usage.CacheReadInputTokens)
		}

		// Process response content blocks.
		assistantContent := resp.Content
		messages = append(messages, anthropic.NewAssistantMessage(assistantContent...))

		if resp.StopReason == anthropic.MessageStopReasonEndTurn {
			// Model finished -- extract final answer from last text block.
			for _, block := range resp.Content {
				if block.Type == anthropic.ContentBlockTypeText {
					result, parseErr := parseInvestigationResult(block.Text)
					if parseErr != nil {
						investigation.Status = "failed"
						return investigation, fmt.Errorf("failed to parse result: %w", parseErr)
					}
					investigation.RootCause = result.RootCause
					investigation.Recommendation = result.Recommendation
					investigation.ConfidenceScore = result.ConfidenceScore
					investigation.Status = "completed"
					investigation.CompletedAt = ptrTime(time.Now())
					investigation.Iterations = iteration + 1
					break
				}
			}
			break
		}

		if resp.StopReason == anthropic.MessageStopReasonToolUse {
			// Execute each tool call and append results.
			var toolResults []anthropic.ContentBlockParam

			for _, block := range resp.Content {
				if block.Type == anthropic.ContentBlockTypeToolUse {
					toolOutput, execErr := inv.executeTool(ctx, block.Name, block.Input)

					evidence := Evidence{
						ToolUsed:   block.Name,
						Input:      string(block.Input),
						Output:     toolOutput,
						ObtainedAt: time.Now(),
					}
					investigation.EvidenceChain = append(investigation.EvidenceChain, evidence)

					if execErr != nil {
						toolResults = append(toolResults, anthropic.NewToolResultBlock(
							block.ID,
							fmt.Sprintf("Error: %s", execErr.Error()),
							true, // is_error
						))
					} else {
						toolResults = append(toolResults, anthropic.NewToolResultBlock(
							block.ID,
							toolOutput,
							false,
						))
					}
				}
			}

			messages = append(messages, anthropic.NewUserMessage(toolResults...))
		}
	}

	// Calculate cost.
	investigation.TotalTokens = totalInputTokens + totalOutputTokens
	investigation.CostUSD = calculateCost(InvestigatorModel, totalInputTokens, totalOutputTokens, totalCachedTokens)

	// Persist and audit.
	if err := inv.repo.Save(ctx, investigation); err != nil {
		return investigation, fmt.Errorf("failed to persist investigation: %w", err)
	}

	inv.audit.Log(ctx, AuditEntry{
		RequestType: "level_3",
		Model:       InvestigatorModel,
		InputTokens: totalInputTokens,
		OutputTokens: totalOutputTokens,
		CachedTokens: totalCachedTokens,
		CostUSD:     investigation.CostUSD,
		LatencyMs:   int(time.Since(investigation.StartedAt).Milliseconds()),
		AnomalyID:   &anomaly.ID,
	})

	return investigation, nil
}

func ptrTime(t time.Time) *time.Time { return &t }
```

### 4.4. 5 Investigation Scenarios with Expected Tool Call Sequences

**Scenario 1: Unexplained margin drop in a business unit**

Trigger: Level 2 confidence = 0.45. BU-West margin dropped 5.6 pp in 7 days, no obvious cause.

| Step | Tool Call | Input | Expected Finding |
|------|-----------|-------|------------------|
| 1 | `query_shipments` | `{manager_id: null, date_from: "7d_ago", date_to: "today", limit: 100}` filtered to BU-West | 45 shipments, 12 with deviation > 10 pp |
| 2 | `query_shipments` | `{client_id: "client-X", date_from: "7d_ago"}` -- top deviating client from step 1 | 8 orders from client-X, all high-deviation |
| 3 | `query_client_history` | `{client_id: "client-X", months: 6}` | Client historically low-deviation; recent change in behavior |
| 4 | `query_price_changes` | `{product_ids: [top 10 products from step 2], date_from: "30d_ago"}` | NPSS for 4 products unchanged for 85 days |
| 5 | `calculate_what_if` | `{ls_id: "ls-of-client-X", scenario: {modified_items: [{product_ids, new_price: updated_npss}]}}` | With updated NPSS, deviation drops from 12 to 4 pp |

Expected conclusion: Root cause = stale NPSS on 4 import products combined with client ordering these specific items. Confidence: 0.85.

**Scenario 2: Manager splitting orders to bypass approval**

Trigger: Level 2 confidence = 0.62. Manager created 35 orders in one day, all auto-approved.

| Step | Tool Call | Input | Expected Finding |
|------|-----------|-------|------------------|
| 1 | `query_shipments` | `{manager_id: "mgr-001", date_from: "today", status: "approved"}` | 35 orders, all < 50K RUB, deviation < 1 pp |
| 2 | `query_shipments` | `{manager_id: "mgr-001", date_from: "today"}` -- check all, group by client | 30 of 35 orders belong to same client |
| 3 | `query_client_history` | `{client_id: "client-Y", months: 3}` | Client normally orders 2-3 large orders/month |
| 4 | `get_approval_history` | `{local_estimate_id: "ls-of-client-Y"}` | LS has planned margin 14%, no prior issues |
| 5 | `calculate_what_if` | `{ls_id: "ls-of-client-Y", scenario: {merge 30 orders into 1}}` | Merged order: deviation = 8.5 pp -- would require RBU approval |

Expected conclusion: Manager is splitting a large order into 30 small ones to keep each below auto-approval threshold. Confidence: 0.91. Recommendation: flag for RBU review, consider aggregate order analysis rule.

**Scenario 3: Cross-validation cascade**

Trigger: Level 2 confidence = 0.55. LS plan changed, 5 orders revoked, but the cause of plan change is unclear.

| Step | Tool Call | Input | Expected Finding |
|------|-----------|-------|------------------|
| 1 | `get_approval_history` | `{local_estimate_id: "ls-Z"}` | Plan changed from 22% to 16% at 14:00 today |
| 2 | `query_shipments` | `{local_estimate_id: "ls-Z"}` | 12 total orders, 5 had approval revoked |
| 3 | `query_price_changes` | `{product_ids: [top items in ls-Z], date_from: "7d_ago"}` | NPSS updated for 8 products due to purchase price trigger |
| 4 | `query_client_history` | `{client_id: "client-Z", months: 12}` | Client has 3 prior LS, all with similar pattern |
| 5 | `calculate_what_if` | `{ls_id: "ls-Z", scenario: {use old NPSS for the 8 products}}` | With old NPSS, plan = 21.8%, close to original 22% |

Expected conclusion: Purchase price auto-trigger (LS-BR-075b) updated NPSS for 8 products, which changed LS planned profitability from 22% to 16%. This cascaded into cross-validation revocation of 5 approved orders. Confidence: 0.88.

**Scenario 4: SLA breach pattern**

Trigger: Level 2 confidence = 0.50. Multiple SLA breaches in one BU, but no single obvious cause.

| Step | Tool Call | Input | Expected Finding |
|------|-----------|-------|------------------|
| 1 | `query_shipments` | `{status: "pending_approval", date_from: "7d_ago"}` filtered to BU-East | 18 pending, 6 with SLA breached |
| 2 | `get_approval_history` | `{shipment_id: "sla-breached-1"}` | Assigned to approver A, no action for 26h |
| 3 | `get_approval_history` | `{shipment_id: "sla-breached-2"}` | Same approver A, no action for 30h |
| 4 | `query_shipments` | `{date_from: "14d_ago", date_to: "7d_ago"}` filtered to same approver | Approver A processed normally 2 weeks ago |
| 5 | `get_approval_history` | `{local_estimate_id: "any-recent-ls-in-bu-east"}` | Approver A last login 3 days ago |

Expected conclusion: Approver A appears to be absent (vacation/sick leave) without a deputy configured. Overflow threshold (30) not triggered because tasks are distributed across multiple LS. Confidence: 0.82. Recommendation: assign deputy immediately, process queued tasks manually.

**Scenario 5: False positive investigation**

Trigger: Level 2 confidence = 0.40. Z-score = 2.3 on overall system, but no rule violations.

| Step | Tool Call | Input | Expected Finding |
|------|-----------|-------|------------------|
| 1 | `query_shipments` | `{date_from: "today", limit: 200}` | 180 orders today, deviation range 0.5-14.0 pp |
| 2 | `query_shipments` | `{date_from: "7d_ago", date_to: "yesterday"}` | Avg 120 orders/day, similar deviation range |
| 3 | `query_client_history` | `{client_id: "top-revenue-client", months: 1}` | Normal ordering pattern |
| 4 | `query_price_changes` | `{product_ids: [top-sold-10], date_from: "30d_ago"}` | No price changes |
| 5 | `calculate_what_if` | `{ls_id: "largest-active-ls", scenario: {}}` | Normal profitability |

Expected conclusion: The Z-score spike is caused by a natural increase in order volume (end of quarter), not a structural anomaly. Historical 90-day window includes a quieter period, inflating the Z-score. Confidence: 0.75. Mark as false positive. Recommendation: adjust Z-score window to account for seasonal patterns.

---

## 5. Prompt Caching Strategy

### 5.1. Architecture

```
+------------------+     +--------------------+     +-------------------+
|  System Prompt   |     |  Tool Definitions  |     |  User Prompt      |
|  (~20K tokens)   |     |  (~2K tokens)      |     |  (~1-3K tokens)   |
|                  |     |                    |     |                   |
|  FM domain rules |     |  5 tool schemas    |     |  Anomaly data     |
|  Business context|     |                    |     |  Recent context   |
|  Output format   |     |                    |     |  Specific question|
+--------+---------+     +---------+----------+     +--------+----------+
         |                         |                          |
         |   CACHED (breakpoint 1) |  CACHED (breakpoint 2)  |  NOT CACHED
         +-------------------------+--------------------------+
                    |                                         |
              cache_read: $0.30/MTok (Sonnet)          input: $3/MTok (Sonnet)
              cache_read: $0.50/MTok (Opus)            input: $5/MTok (Opus)
```

### 5.2. Implementation

```go
// internal/analytics/ai/caching.go

package ai

import (
	"github.com/anthropics/anthropic-sdk-go"
)

// CachedPromptBuilder constructs API requests with optimal cache breakpoints.
type CachedPromptBuilder struct {
	systemPrompt string // ~20K tokens, stable
	toolDefs     []anthropic.ToolParam // ~2K tokens, stable
}

// BuildLevel2Request creates a Sonnet 4.6 request with cached system prompt.
//
// Cache strategy:
//   - Breakpoint 1: end of system prompt (20K tokens, cached)
//   - Breakpoint 2: end of tool definitions (2K tokens, cached)
//   - User message: anomaly-specific data (1-3K tokens, NOT cached)
//
// With caching:
//   - First request: 20K tokens written to cache (1.25x base price)
//   - Subsequent requests (within 5 min): 20K read from cache (0.1x base price)
//   - Only user prompt tokens charged at full price
func (b *CachedPromptBuilder) BuildLevel2Request(
	anomalyPrompt string,
) anthropic.MessageNewParams {
	return anthropic.MessageNewParams{
		Model:     anthropic.F("claude-sonnet-4-6-20250514"),
		MaxTokens: anthropic.Int(2048),
		System: anthropic.F([]anthropic.TextBlockParam{
			{
				Text:         anthropic.String(b.systemPrompt),
				CacheControl: &anthropic.CacheControlEphemeralParam{},
			},
		}),
		Messages: anthropic.F([]anthropic.MessageParam{
			anthropic.NewUserMessage(
				anthropic.NewTextBlock(anomalyPrompt),
			),
		}),
	}
}

// BuildLevel3Request creates an Opus 4.6 request with cached system prompt and tools.
//
// Cache strategy:
//   - Breakpoint 1: end of system prompt (20K tokens, cached)
//   - Tools: included in request, cached as part of prefix
//   - User message: anomaly data + conversation history (NOT cached initially,
//     but multi-turn conversation cached automatically with automatic caching)
func (b *CachedPromptBuilder) BuildLevel3Request(
	anomalyPrompt string,
	conversationHistory []anthropic.MessageParam,
) anthropic.MessageNewParams {
	messages := make([]anthropic.MessageParam, 0, len(conversationHistory)+1)
	if len(conversationHistory) == 0 {
		messages = append(messages, anthropic.NewUserMessage(
			anthropic.NewTextBlock(anomalyPrompt),
		))
	} else {
		messages = append(messages, conversationHistory...)
	}

	return anthropic.MessageNewParams{
		Model:     anthropic.F("claude-opus-4-6-20250514"),
		MaxTokens: anthropic.Int(4096),
		System: anthropic.F([]anthropic.TextBlockParam{
			{
				Text:         anthropic.String(b.systemPrompt),
				CacheControl: &anthropic.CacheControlEphemeralParam{},
			},
		}),
		Tools:    anthropic.F(b.toolDefs),
		Messages: anthropic.F(messages),
	}
}
```

### 5.3. Cost Calculation Table

**Pricing (per million tokens, from Anthropic docs):**

| Component | Sonnet 4.6 | Opus 4.6 |
|-----------|-----------|---------|
| Base input | $3.00 / MTok | $5.00 / MTok |
| Cache write (5 min TTL) | $3.75 / MTok | $6.25 / MTok |
| Cache read | $0.30 / MTok | $0.50 / MTok |
| Output | $15.00 / MTok | $25.00 / MTok |

**Minimum cacheable tokens:**
- Sonnet 4.6: 2,048 tokens
- Opus 4.6: 4,096 tokens

Our system prompt is ~20,000 tokens, well above minimums.

**Per-request cost breakdown (Level 2 -- Sonnet 4.6):**

| Component | Tokens | Cache Status | Price/MTok | Cost |
|-----------|--------|-------------|------------|------|
| System prompt | 20,000 | Cache HIT (read) | $0.30 | $0.0060 |
| User prompt | 2,000 | Not cached | $3.00 | $0.0060 |
| Output | 500 | -- | $15.00 | $0.0075 |
| **Total (cached)** | **22,500** | | | **$0.0195** |

| Component | Tokens | Cache Status | Price/MTok | Cost |
|-----------|--------|-------------|------------|------|
| System prompt | 20,000 | Cache WRITE | $3.75 | $0.0750 |
| User prompt | 2,000 | Not cached | $3.00 | $0.0060 |
| Output | 500 | -- | $15.00 | $0.0075 |
| **Total (cold start)** | **22,500** | | | **$0.0885** |

**Savings:** $0.0885 - $0.0195 = $0.069 per request (78% savings on cached requests).

**Per-request cost breakdown (Level 3 -- Opus 4.6):**

Assumes average investigation: 5 iterations, ~3K tokens user context per iteration, ~1K output per iteration.

| Component | Tokens | Cache Status | Price/MTok | Cost |
|-----------|--------|-------------|------------|------|
| System prompt | 20,000 | Cache HIT | $0.50 | $0.0100 |
| Tools definition | 2,000 | Cache HIT (prefix) | $0.50 | $0.0010 |
| Conversation (5 iter avg) | 20,000 | Partial cache | ~$2.50 avg | $0.0500 |
| Output (5 iterations) | 5,000 | -- | $25.00 | $0.1250 |
| **Total (cached, avg)** | **47,000** | | | **$0.1860** |

### 5.4. Cache TTL Strategy

| Scenario | TTL | Rationale |
|----------|-----|-----------|
| Normal operations | 5 min (default) | Anomalies arrive in bursts; 5 min covers typical burst window |
| Batch report generation | 5 min | Reports generated sequentially, each reuses cache from prior |
| Q&A session (analyst) | 5 min | Interactive; each question within 5 min of previous |
| Nightly batch analysis | No caching | One-off; no reuse benefit |

5-minute TTL is sufficient for all use cases. The cache refreshes automatically on each hit, so during active periods the effective TTL is unlimited.

---

## 6. AI Safety and Guardrails

### 6.1. Configuration

```go
// internal/analytics/ai/guardrails.go

package ai

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// GuardrailConfig holds all AI safety parameters.
type GuardrailConfig struct {
	// Rate limiting
	RateLimitSonnet    int           // 200 req/hour
	RateLimitOpus      int           // 50 req/hour

	// Timeouts
	TimeoutSonnet      time.Duration // 15s
	TimeoutOpus        time.Duration // 60s

	// Cost controls
	DailyCostCeiling   float64       // $50.00 (prod)
	CostAlertThreshold float64       // $30.00 (60% of ceiling)
	CostDegradeThreshold float64     // $40.00 (80% of ceiling)

	// Quality controls
	ConfidenceThreshold float64      // 0.7 (below = escalate)
	MaxIterations       int          // 10 (Level 3)

	// Content controls
	MaxOutputTokens     int          // 4096
	PIIPatterns         []string     // regex patterns for PII detection
}

// DefaultGuardrailConfig returns production defaults.
func DefaultGuardrailConfig() GuardrailConfig {
	return GuardrailConfig{
		RateLimitSonnet:      200,
		RateLimitOpus:        50,
		TimeoutSonnet:        15 * time.Second,
		TimeoutOpus:          60 * time.Second,
		DailyCostCeiling:     50.00,
		CostAlertThreshold:   30.00,
		CostDegradeThreshold: 40.00,
		ConfidenceThreshold:  0.7,
		MaxIterations:        10,
		MaxOutputTokens:      4096,
		PIIPatterns: []string{
			`\b\d{3}-\d{3}-\d{3}\s?\d{2}\b`,         // SNILS
			`\b\d{10,12}\b`,                            // INN
			`\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b`, // Email
			`\b\+?7\d{10}\b`,                           // Phone
		},
	}
}
```

### 6.2. Guardrails Table

| Guardrail | Parameter | Value | Action on Breach | Test Case |
|-----------|-----------|-------|------------------|-----------|
| Rate limit (Sonnet) | 200 req/hour | Sliding window, per-service instance | Reject request, return Level 1 result | GR-TC-01: Send 201st request within 1 hour; verify HTTP 429 returned, Level 1 fallback used |
| Rate limit (Opus) | 50 req/hour | Sliding window, per-service instance | Reject request, return Level 2 result | GR-TC-02: Send 51st Opus request within 1 hour; verify rejection, Level 2 result used instead |
| Timeout (Sonnet) | 15 seconds | Per-request context deadline | Cancel request, return Level 1 result | GR-TC-03: Mock slow API (20s delay); verify timeout at 15s, graceful fallback to Level 1 |
| Timeout (Opus) | 60 seconds | Per-request context deadline | Cancel request, return partial result | GR-TC-04: Mock slow API (90s delay); verify timeout at 60s, partial investigation saved |
| Content filter (PII) | SNILS, INN, email, phone patterns | Post-processing regex scan | Redact PII from output, log warning | GR-TC-05: LLM output contains phone "+79161234567"; verify it is replaced with "[REDACTED]" |
| Content filter (no "I don't know") | Detect empty/evasive answers | Check output for actionable content | Set requires_level_3=true or fallback | GR-TC-06: LLM returns "I don't know"; verify system sets confidence=0.0, requires_level_3=true |
| Confidence threshold | 0.7 | Parsed from structured output | Escalate to Level 3 | GR-TC-07: Level 2 returns confidence=0.65; verify Level 3 investigation triggered |
| Confidence threshold (no escalation) | 0.7 | Same | Do NOT escalate | GR-TC-08: Level 2 returns confidence=0.72; verify no Level 3 triggered |
| Cost alert | $30/day (60%) | Accumulated daily cost check | Send alert to FD via notification-service | GR-TC-09: Simulate $30.01 daily spend; verify Telegram/email alert sent |
| Cost degradation | $40/day (80%) | Accumulated daily cost check | Disable Level 2/3, Level 1 only | GR-TC-10: Simulate $40.01 daily spend; verify all new requests get Level 1 only |
| Cost ceiling (hard) | $50/day (100%) | Accumulated daily cost check | Hard stop all AI requests | GR-TC-11: Simulate $50.01; verify all Level 2/3 requests rejected with error |
| Max iterations (L3) | 10 | Counter in investigation loop | Force conclusion with available evidence | GR-TC-12: Mock investigation requiring 15 tools; verify stops at 10, returns partial result |
| Output size | 4096 tokens | max_tokens parameter | Truncation by API | GR-TC-13: Request generating very long output; verify truncated at 4096 tokens |
| Model validation | Sonnet/Opus only | Config check at startup | Reject invalid model names | GR-TC-14: Set AI_MODEL_ANALYST="claude-haiku-4-5"; verify startup error |
| Audit logging | Every AI request | Post-response hook | Log to ai_audit_log table | GR-TC-15: Make 1 Level 2 request; verify exactly 1 row in ai_audit_log with correct fields |
| Retry (Sonnet) | 2 retries | Exponential backoff 1s, 3s | After 2 failures: fallback to Level 1 | GR-TC-16: Mock API 503 3 times; verify 2 retries then Level 1 fallback |
| Retry (Opus) | 2 retries | Exponential backoff 2s, 6s | After 2 failures: return Level 2 result as-is | GR-TC-17: Mock API 503 3 times; verify 2 retries then Level 2 result kept |

### 6.3. Rate Limiter Implementation

```go
// internal/analytics/ai/ratelimit.go

package ai

import (
	"sync"
	"time"
)

// SlidingWindowRateLimiter implements a sliding window rate limiter.
type SlidingWindowRateLimiter struct {
	mu        sync.Mutex
	window    time.Duration
	maxCount  int
	timestamps []time.Time
}

func NewRateLimiter(maxCount int, window time.Duration) *SlidingWindowRateLimiter {
	return &SlidingWindowRateLimiter{
		window:   window,
		maxCount: maxCount,
	}
}

// Allow checks if a request is allowed under the rate limit.
// Returns true if allowed, false if rate limit exceeded.
func (rl *SlidingWindowRateLimiter) Allow() bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()

	now := time.Now()
	cutoff := now.Add(-rl.window)

	// Remove expired timestamps.
	valid := rl.timestamps[:0]
	for _, ts := range rl.timestamps {
		if ts.After(cutoff) {
			valid = append(valid, ts)
		}
	}
	rl.timestamps = valid

	if len(rl.timestamps) >= rl.maxCount {
		return false
	}

	rl.timestamps = append(rl.timestamps, now)
	return true
}
```

### 6.4. Cost Tracker

```go
// internal/analytics/ai/cost_tracker.go

package ai

import (
	"context"
	"sync"
	"time"
)

// CostTracker monitors daily AI spending.
type CostTracker struct {
	mu          sync.RWMutex
	dailyCost   float64
	lastResetAt time.Time
	config      GuardrailConfig
	notifier    CostNotifier
	alertSent   bool
}

// CostNotifier -- port for sending cost alerts.
type CostNotifier interface {
	SendCostAlert(ctx context.Context, currentCost, ceiling float64) error
}

// RecordCost adds the cost of an AI request to the daily total.
// Returns the action to take based on current spending.
func (ct *CostTracker) RecordCost(ctx context.Context, costUSD float64) CostAction {
	ct.mu.Lock()
	defer ct.mu.Unlock()

	// Reset daily counter at midnight MSK.
	now := time.Now()
	mskLoc, _ := time.LoadLocation("Europe/Moscow")
	todayMSK := now.In(mskLoc).Truncate(24 * time.Hour)
	if ct.lastResetAt.Before(todayMSK) {
		ct.dailyCost = 0
		ct.alertSent = false
		ct.lastResetAt = todayMSK
	}

	ct.dailyCost += costUSD

	// Check thresholds.
	if ct.dailyCost >= ct.config.DailyCostCeiling {
		return CostActionHardStop
	}
	if ct.dailyCost >= ct.config.CostDegradeThreshold {
		return CostActionDegrade
	}
	if ct.dailyCost >= ct.config.CostAlertThreshold && !ct.alertSent {
		ct.alertSent = true
		go ct.notifier.SendCostAlert(ctx, ct.dailyCost, ct.config.DailyCostCeiling)
		return CostActionAlert
	}
	return CostActionNone
}

// CanUseLevel returns whether a given AI level is allowed.
func (ct *CostTracker) CanUseLevel(level int) bool {
	ct.mu.RLock()
	defer ct.mu.RUnlock()

	if ct.dailyCost >= ct.config.DailyCostCeiling {
		return false // hard stop: no AI at all
	}
	if ct.dailyCost >= ct.config.CostDegradeThreshold && level >= 2 {
		return false // degrade: Level 1 only
	}
	if ct.dailyCost >= ct.config.DailyCostCeiling*0.9 && level >= 3 {
		return false // 90% threshold: no Level 3
	}
	return true
}

type CostAction int

const (
	CostActionNone     CostAction = iota
	CostActionAlert    // 60% ($30): send notification
	CostActionDegrade  // 80% ($40): Level 1 only
	CostActionHardStop // 100% ($50): reject all AI requests
)
```

---

## 7. Cost Model

### 7.1. Expected Request Volumes (Production)

Based on FM-LS-PROFIT user data: ~50 managers, ~10 RBU, 50-70 concurrent users.

| Metric | Daily | Monthly (22 work days) |
|--------|-------|----------------------|
| Profitability calculations (Level 1 trigger) | ~500 | ~11,000 |
| Anomalies detected (Level 1) | ~25 (5% anomaly rate) | ~550 |
| Level 2 requests (anomaly explanation) | ~25 | ~550 |
| Level 3 investigations (confidence < 0.7) | ~5 (20% escalation rate) | ~110 |
| Analyst Q&A requests | ~5 | ~110 |
| Report summarizations | ~2 | ~44 |
| **Total AI requests (Level 2 + 3)** | **~32** | **~704** |

### 7.2. Per-Scenario Cost Breakdown

| Scenario | Level | Requests/day | Cost/request | Daily Cost | Monthly Cost |
|----------|-------|-------------|-------------|------------|-------------|
| Anomaly explanation | 2 (Sonnet) | 25 | $0.0195 | $0.49 | $10.73 |
| Analyst Q&A | 2 (Sonnet) | 5 | $0.0195 | $0.10 | $2.15 |
| Report summary | 2 (Sonnet) | 2 | $0.0250 | $0.05 | $1.10 |
| Investigation | 3 (Opus) | 5 | $0.1860 | $0.93 | $20.46 |
| **Total** | | **37** | | **$1.57** | **$34.44** |

### 7.3. Cost Comparison: With vs Without Caching

| Component | Without Caching | With Caching | Savings |
|-----------|----------------|-------------|---------|
| Level 2 (25 req/day, Sonnet) | $0.0560 * 25 = $1.40 | $0.0195 * 25 = $0.49 | $0.91 (65%) |
| Level 3 (5 req/day, Opus) | $0.2750 * 5 = $1.38 | $0.1860 * 5 = $0.93 | $0.45 (33%) |
| **Daily total** | **$2.78** | **$1.57** | **$1.21 (44%)** |
| **Monthly total** | **$61.16** | **$34.44** | **$26.72 (44%)** |

Without caching cost/request (Level 2): system prompt 20K * $3/MTok + user 2K * $3/MTok + output 500 * $15/MTok = $0.06 + $0.006 + $0.0075 = $0.0735.

Corrected without caching daily (Level 2): $0.0735 * 25 = $1.84.
Corrected without caching daily (Level 3): system 20K * $5/MTok + tools 2K * $5/MTok + conv 20K * $5/MTok + output 5K * $25/MTok = $0.10 + $0.01 + $0.10 + $0.125 = $0.335 * 5 = $1.68.
Corrected daily total without caching: $1.84 + $1.68 = $3.52.
Monthly without caching: $77.44.
Actual savings: $77.44 - $34.44 = $43.00/month (56%).

### 7.4. Budget Alerts

| Threshold | Daily Spend | Action | Notification |
|-----------|------------|--------|--------------|
| Normal | $0 - $29.99 | All levels active | -- |
| Alert | $30.00 (60%) | All levels active | Telegram + email to FD |
| Degraded | $40.00 (80%) | Level 1 only, Level 2/3 disabled | Telegram + email to FD + DP |
| Hard stop | $50.00 (100%) | All AI disabled, deterministic only | Telegram + email to FD + DP + GD |

**Projected daily spend: $1.57 (3.1% of $50 ceiling).** The budget has significant headroom for growth.

### 7.5. Worst-Case Scenarios

| Scenario | Calculation | Daily Cost | Outcome |
|----------|------------|------------|---------|
| Normal day | 25 L2 + 5 L3 | $1.57 | Well within budget |
| High anomaly day | 100 L2 + 20 L3 | $5.67 | Within budget |
| Attack/bug (runaway) | 200 L2/hour * 8h | $31.20 (L2 only) | Rate limit caps at 200/hr; alert at $30, degrade at $40 |
| Full rate (Sonnet) | 200/hr * 8h = 1600 | $31.20 | Hits alert, then degrade |
| Full rate (Opus) | 50/hr * 8h = 400 | $74.40 | Hits alert ($30), degrade ($40), hard stop ($50) -- actual spend capped at $50 |

The guardrails ensure daily spend never exceeds $50 regardless of request volume.

---

## 8. Langfuse Integration

### 8.1. What to Log

Every AI interaction is logged to Langfuse for observability, cost tracking, and quality monitoring.

```go
// internal/analytics/ai/langfuse.go

package ai

import (
	"context"
	"time"

	"github.com/google/uuid"
)

// AuditEntry represents a single AI request audit record.
type AuditEntry struct {
	RequestType  string     // level_2, level_3, ask, summarize
	Model        string     // claude-sonnet-4-6-20250514, claude-opus-4-6-20250514
	InputTokens  int
	OutputTokens int
	CachedTokens int
	CostUSD      float64
	LatencyMs    int
	AnomalyID    *uuid.UUID // nil for Q&A, summarize
	UserID       *uuid.UUID // nil for automated requests
}

// AuditLogger -- port for AI audit logging.
type AuditLogger interface {
	// Log records an AI request to the audit trail (DB + Langfuse).
	Log(ctx context.Context, entry AuditEntry) error
}
```

### 8.2. Trace Structure

```
Langfuse Trace: "ai-analytics-{anomaly_id}"
|
+-- Generation: "level-1-detection"
|   |-- Input: shipment data, deviation
|   |-- Output: {is_anomaly, z_score, rule_violations}
|   |-- Metadata: {latency_ms, entity_type, entity_id}
|
+-- Generation: "level-2-explanation" (if anomaly detected)
|   |-- Input: anomaly context (system prompt cached)
|   |-- Output: AnomalyExplanation JSON
|   |-- Metadata: {model, input_tokens, output_tokens, cached_tokens, cost_usd, latency_ms}
|   |-- Scores: {confidence: 0.0-1.0}
|
+-- Span: "level-3-investigation" (if confidence < 0.7)
    |-- Generation: "investigation-iter-1"
    |   |-- Input: anomaly + conversation
    |   |-- Output: tool_use (query_shipments)
    |   |-- Metadata: {model, tokens, cost}
    |
    |-- Span: "tool-execution-query_shipments"
    |   |-- Input: {filters}
    |   |-- Output: {results}
    |   |-- Metadata: {latency_ms}
    |
    |-- Generation: "investigation-iter-2"
    |   |-- ...
    |
    |-- Generation: "investigation-final"
    |   |-- Output: Investigation JSON
    |   |-- Scores: {confidence: 0.0-1.0}
    |   |-- Metadata: {total_iterations, total_tokens, total_cost}
```

### 8.3. Metrics Dashboard (Langfuse)

| Metric | Source | Aggregation | Alert |
|--------|--------|------------|-------|
| Daily AI cost | ai_audit_log.cost_usd | SUM per day | > $30 |
| Avg Level 2 latency | ai_audit_log (level_2) | AVG latency_ms | > 10,000ms |
| Avg Level 3 latency | ai_audit_log (level_3) | AVG latency_ms | > 45,000ms |
| Level 3 escalation rate | count(level_3) / count(level_2) | % per day | > 30% |
| Cache hit rate | cached_tokens / (input_tokens + cached_tokens) | % per day | < 80% |
| False positive rate | count(false_positive) / count(anomalies) | % per week | > 40% |
| Avg confidence (Level 2) | AnomalyExplanation.confidence | AVG per day | < 0.6 |
| Request error rate | count(errors) / count(requests) | % per hour | > 5% |
| Tokens per investigation | investigation.total_tokens | AVG per day | > 100,000 |

---

## 9. Fallback Strategy

### 9.1. Degradation Chain

```
Level 3 (Opus) unavailable/timeout/budget
        |
        v
Level 2 (Sonnet) -- use best available explanation
        |
        | unavailable/timeout/budget
        v
Level 1 (Deterministic) -- Z-score + rules only
        |
        | system failure
        v
Level 0 (Passthrough) -- no anomaly detection, log warning
```

### 9.2. Fallback Triggers and Actions

| From | To | Trigger | Action | User Impact |
|------|----|---------|--------|-------------|
| Level 3 -> Level 2 | Opus timeout (60s) | Return Level 2 explanation as-is | Investigation not available; explanation still provided |
| Level 3 -> Level 2 | Opus rate limit (50/hr) | Queue for next hour or skip | Same as above |
| Level 3 -> Level 2 | Opus API error (after 2 retries) | Log error, return Level 2 | Same as above |
| Level 3 -> Level 1 | Budget >= 80% ($40) | Disable Level 3 entirely | Only Z-score and rule results |
| Level 2 -> Level 1 | Sonnet timeout (15s) | Return Level 1 rule violations only | No explanation, raw anomaly data only |
| Level 2 -> Level 1 | Sonnet rate limit (200/hr) | Return Level 1 result | Same as above |
| Level 2 -> Level 1 | Sonnet API error (after 2 retries) | Log error, return Level 1 | Same as above |
| Level 2 -> Level 1 | Budget >= 80% ($40) | Disable Level 2 entirely | Deterministic only for rest of day |
| All AI -> Level 1 | Budget >= 100% ($50) | Hard stop, reject all AI | Deterministic detection continues |
| Level 1 -> Level 0 | Database unavailable | Log warning, passthrough | No anomaly detection at all |

### 9.3. Fallback Response Format

When falling back, the system returns a standardized response indicating the degradation.

```go
// internal/analytics/ai/fallback.go

package ai

// FallbackResponse wraps a degraded response with metadata.
type FallbackResponse struct {
	OriginalLevel   int    // level that was requested
	ActualLevel     int    // level that was used
	FallbackReason  string // "timeout", "rate_limit", "budget", "api_error"
	DeterministicResult *DeterministicResult // always populated
	LLMResult       *AnomalyExplanation      // populated if Level 2 succeeded
	InvestigationResult *Investigation         // populated if Level 3 succeeded
}

type DeterministicResult struct {
	ZScore         float64
	IsAnomaly      bool
	RuleViolations []RuleViolation
	ForecastTrend  string // "up", "down", "stable", "insufficient_data"
}
```

---

## Appendix A: Environment Variables

```bash
# AI Model Configuration
AI_MODEL_ANALYST=claude-sonnet-4-6-20250514
AI_MODEL_INVESTIGATOR=claude-opus-4-6-20250514

# Prompt Caching
AI_PROMPT_CACHE_ENABLED=true
AI_PROMPT_CACHE_TTL=5m     # 5-minute TTL (default)

# Rate Limiting
AI_RATE_LIMIT_SONNET=200   # requests per hour
AI_RATE_LIMIT_OPUS=50      # requests per hour

# Timeouts
AI_TIMEOUT_SONNET=15s
AI_TIMEOUT_OPUS=60s

# Cost Controls
AI_DAILY_COST_CEILING=50.00
AI_COST_ALERT_THRESHOLD=0.6    # 60% = $30
AI_COST_DEGRADE_THRESHOLD=0.8  # 80% = $40

# Quality Controls
AI_CONFIDENCE_THRESHOLD=0.7
AI_MAX_ITERATIONS=10

# Langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-xxx
LANGFUSE_SECRET_KEY=sk-lf-xxx
LANGFUSE_HOST=https://langfuse.example.com

# Anthropic
ANTHROPIC_API_KEY=sk-ant-xxx
```

## Appendix B: Database Schema Extensions

Additional tables for AI cost tracking (extends analytics-service schema from phase1b).

```sql
-- migrations/analytics/002_ai_daily_costs.up.sql

-- Daily cost aggregation (materialized from ai_audit_log)
CREATE TABLE ai_daily_costs (
    date DATE PRIMARY KEY,
    total_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    level_2_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    level_3_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    qa_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    summarize_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_requests INT NOT NULL DEFAULT 0,
    level_2_requests INT NOT NULL DEFAULT 0,
    level_3_requests INT NOT NULL DEFAULT 0,
    total_input_tokens BIGINT NOT NULL DEFAULT 0,
    total_output_tokens BIGINT NOT NULL DEFAULT 0,
    total_cached_tokens BIGINT NOT NULL DEFAULT 0,
    cache_hit_rate DOUBLE PRECISION, -- cached / (input + cached)
    avg_confidence DOUBLE PRECISION,
    degraded_at TIMESTAMPTZ, -- when daily cost hit 80%
    hard_stopped_at TIMESTAMPTZ, -- when daily cost hit 100%
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Hourly rate limit tracking
CREATE TABLE ai_rate_limit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model VARCHAR(50) NOT NULL,
    hour_bucket TIMESTAMPTZ NOT NULL, -- truncated to hour
    request_count INT NOT NULL DEFAULT 0,
    rejected_count INT NOT NULL DEFAULT 0,
    UNIQUE (model, hour_bucket)
);

CREATE INDEX idx_rate_limit_hour ON ai_rate_limit_log(hour_bucket);
```
