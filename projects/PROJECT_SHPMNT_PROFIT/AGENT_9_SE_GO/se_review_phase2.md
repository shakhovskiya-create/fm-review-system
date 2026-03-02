# SE Review Phase 2: Architecture of profitability-service

**Reviewer:** Agent 9 (Senior Engineer -- Go + React)
**Project:** FM-LS-PROFIT / PROJECT_SHPMNT_PROFIT
**FM Version:** 1.0.7
**Date:** 2026-03-02
**Scope:** Full BIG review across all 4 sections (Architecture, Code Quality, Tests, Performance)
**Input Documents:**
- `phase1a_domain_model.md` (2102 lines) -- DDD domain model
- `phase1b_go_architecture.md` (2814 lines) -- Go microservices + OpenAPI + DB
- `phase1c_react_architecture.md` (2198 lines) -- React frontend
- `phase1d_ai_analytics.md` (2050 lines) -- AI analytics 3-level
- `phase1e_integration_architecture.md` (2274 lines) -- 17 integrations

---

## 1. Executive Summary

**Verdict: CONDITIONAL PASS**

The architecture is well-designed with proper DDD boundaries, Clean Architecture, and comprehensive coverage of the FM-LS-PROFIT business domain. The team has made strong choices (sqlc, franz-go, connect-go, outbox pattern, temporal tables). However, there are several issues requiring correction before development begins.

| Severity | Count |
|----------|-------|
| CRITICAL | 2 |
| HIGH | 8 |
| MEDIUM | 14 |
| LOW | 7 |
| **Total** | **31** |

**Blocking issues (CRITICAL):** Must be resolved before Sprint 27 (scaffold phase).

**HIGH issues:** Must be resolved before or during Sprint 27. Failure to address will cause rework.

---

## 2. Findings Table

| ID | Severity | Category | Finding | Recommendation | Source |
|----|----------|----------|---------|----------------|--------|
| SE-001 | CRITICAL | Security | Money value object allows negative amounts silently in arithmetic operations (Add can overflow int64; Multiply with negative factor bypasses validation) | Add overflow checks in Add/Multiply; make Subtract return error (already done); disallow negative factor in Multiply | phase1a, 3.1 |
| SE-002 | CRITICAL | Data Model | float64 for Quantity in domain and DB (DOUBLE PRECISION) causes IEEE 754 rounding errors in financial calculations. Shipment 100.1 * 85.00 = 8508.499... not 8508.50 | Use int64 with fixed-point representation (e.g., milligrams for weight, units*1000 for quantity) or shopspring/decimal. Change DB to NUMERIC(15,3) | phase1a, 2.1-2.2; phase1b, 2.3 |
| SE-003 | HIGH | Architecture | ApprovalProcess aggregate in Workflow context references ShipmentID and LocalEstimateID directly (UUID coupling). If profitability-service renames or restructures, workflow breaks | Use domain-level identifiers (ExternalID strings) at the boundary. Internal UUIDs should not cross bounded context boundaries | phase1a, 2.3 |
| SE-004 | HIGH | API | REST endpoints use offset-based pagination for anomalies (/api/v1/anomalies has page param) but cursor-based for shipments. Inconsistent pagination strategy | Standardize on cursor-based pagination for all list endpoints. Offset-based is inefficient for large datasets and has consistency issues under concurrent writes | phase1c, 5.5; phase1b, 4.1 |
| SE-005 | HIGH | Security | No CSRF protection documented for state-changing operations. Next.js App Router with cookies requires CSRF tokens for POST/PUT/DELETE. SameSite=Lax is insufficient for subdomain attacks | Add CSRF token (double-submit cookie pattern or Synchronizer Token) for all mutation endpoints. Consider X-CSRF-Token header | phase1c, 10; phase1b, 7.3 |
| SE-006 | HIGH | Data Model | Percentage value object stores basis * 100 (i.e., hundredths of basis points = ten-thousandths of percent), but DB stores BIGINT described as "basis points". Mismatch creates confusion -- is DB value 1500 = 15.00% or 15.0000%? | Standardize: DB stores basis points (1bp = 0.01%). Document clearly: DB BIGINT 1500 = 15.00%. Align Percentage.basis to actual basis points (not basis*100). If higher precision needed, document it explicitly | phase1a, 3.2; phase1b, 2.3 |
| SE-007 | HIGH | Architecture | api-gateway proxies REST->gRPC for all services, but frontend calls REST directly. This means api-gateway must translate REST to gRPC AND back to REST response. No BFF (Backend For Frontend) layer defined for aggregating multiple service calls (e.g., dashboard requires 4 API calls) | Document the REST-to-gRPC translation layer in api-gateway. Consider adding a GraphQL or BFF endpoint for dashboard aggregation to reduce frontend waterfall requests | phase1b, 7; phase1c, 2.3 |
| SE-008 | HIGH | Performance | Dashboard page makes 5 parallel API calls with different polling intervals (30s, 60s, 120s, 300s). 50-70 concurrent users = 50*5/60 = ~4 req/sec constant background load per user. Total: ~200-350 req/sec just for polling | Implement Server-Sent Events (SSE) or WebSocket for real-time dashboard updates. Push-based model reduces polling load by 90%+. Already have Kafka events -- bridge them to SSE | phase1c, 2.3 |
| SE-009 | HIGH | Integration | 1C extension sends events synchronously during document posting (inside transaction). If integration-service is slow (>10s timeout), it blocks the 1C user's posting operation | Reduce HTTP timeout to 3-5s. Consider async-only approach: 1C writes to local queue (register) immediately, background job sends. The current code does this as fallback but should be the primary path | phase1e, 2.2 |
| SE-010 | HIGH | Security | Refresh token rotation strategy not specified. JWT access token TTL 15min is good, but refresh token 7d without rotation means a leaked refresh token is valid for a week | Implement refresh token rotation: each use of refresh token issues new refresh+access pair. Invalidate old refresh token. Store refresh token hash in DB for revocation | phase1b, 7.1 |
| SE-011 | MEDIUM | Architecture | LocalEstimate aggregate holds LineItems[] directly (up to 1000 items). Loading full aggregate for every operation loads all 1000 items into memory | Consider lazy loading LineItems or splitting into separate repository method. For read-only operations (summary view), use a read model / projection that pre-calculates totals | phase1a, 2.1 |
| SE-012 | MEDIUM | Architecture | Outbox poller polls every 100ms across 5 services = 50 polls/second against DB. Under low load this is wasteful | Use PostgreSQL LISTEN/NOTIFY to trigger polling on insert. Fall back to 100ms polling only during high throughput | phase1b, 10.2 |
| SE-013 | MEDIUM | Data Model | mdm_clients has composite PK (id, valid_from) but FK references from other tables use just client_id (UUID). This means FKs cannot enforce referential integrity against temporal tables | Accept this as a trade-off of temporal design. Document it. Add application-level validation. Consider a separate current_clients view or materialized view for FK targets | phase1b, 5.6 |
| SE-014 | MEDIUM | API | Error responses mention RFC 7807 but no concrete implementation shown. No error type enum defined. Frontend error handling strategy references generic error boundaries but no specific error mapping | Define concrete error types: `validation_error`, `conflict`, `not_found`, `forbidden`, `rate_limited`, `internal`. Include `type` URI, `title`, `detail`, `instance`, `errors[]` for validation | phase1b, 7.3; phase1c, 12 |
| SE-015 | MEDIUM | Security | AI system prompts contain detailed business logic (thresholds, formulas). If user can influence user prompt content via /api/v1/ai/ask, prompt injection could extract system prompt or modify behavior | Add input sanitization for AI chat endpoint. Use separate system prompt for Q&A vs anomaly analysis. Rate limit AI chat more aggressively (10 req/hour per user). Log all AI interactions | phase1d, 3.1; phase1b, 4.1 |
| SE-016 | MEDIUM | React | Batch approval sends individual POST per selected item using Promise.allSettled. 20 batch approvals = 20 API calls. If one fails mid-batch, state is inconsistent | Add server-side batch endpoint: POST /api/v1/approvals/batch-decide. Single transaction, atomic success/failure. Frontend sends array of IDs in one call | phase1c, 4.5 |
| SE-017 | MEDIUM | Data Model | auto_approval_counters has no TTL or cleanup strategy. Daily rows accumulate: 60 managers * 365 days = 21,900 rows/year. Acceptable but should be documented | Add cleanup job: DELETE rows older than 90 days (only current day needed for limit checks, history available in audit log). Add to scheduled jobs list | phase1b, 2.3 |
| SE-018 | MEDIUM | React | AI chat page uses raw fetch() with ReadableStream for SSE but no abort controller for cleanup. If user navigates away during streaming, the connection leaks | Add AbortController to useAIChat hook. Cleanup in useEffect return. Handle abort error gracefully | phase1c, 5.4 |
| SE-019 | MEDIUM | Integration | ELMA circuit breaker parameters (5 failures, 30s open, 1 test) are too aggressive for a BPM system. 5 failures could be triggered by 5 simultaneous timeout responses during peak | Increase threshold to 10 failures over 60 seconds (sliding window, not consecutive). Increase open state to 60s. Allow 3 half-open test requests | phase1e, 4; phase1b, 3.4 |
| SE-020 | MEDIUM | Data Model | notification_throttle table uses hour_bucket TIMESTAMPTZ for rate limiting. No cleanup strategy -- grows indefinitely | Add cleanup: DELETE rows older than 24 hours. Consider using Redis sorted sets with TTL instead of DB table for sub-second rate limiting | phase1b, 6.5 |
| SE-021 | MEDIUM | Architecture | SLA timer checks every 15 minutes (09:00-18:00 MSK). A P1 task with 2h SLA created at 17:45 has only 15 min of business hours remaining. The 15-min granularity means SLA breach could be detected up to 14 min late | Reduce SLA check interval to 1 minute for P1 tasks. Keep 15-min for P2. Use dedicated cron job with priority-based scheduling | phase1b, 3.6 |
| SE-022 | MEDIUM | React | ShipmentDrawer fetches shipment detail + profitability in sequence (enabled: only when drawer is open). This creates a waterfall: drawer opens -> fetch shipment -> fetch profitability | Prefetch both in parallel when drawer opens. Use React Suspense with parallel data fetching. Consider a combined endpoint /api/v1/shipments/{id}/full | phase1c, 3.3 |
| SE-023 | MEDIUM | API | gRPC protobuf uses string for UUIDs and timestamps. No validation at protobuf level -- invalid UUID or malformed timestamp passes through | Add protobuf field validation (buf validate plugin). Alternatively, add explicit validation in gRPC handlers before domain logic | phase1b, 2.2 |
| SE-024 | MEDIUM | Architecture | PriceSheet aggregate lives in Profitability context but is managed by integration-service (MDM). The cache in profitability-service (price_sheet_cache) duplicates data with different structure | Clarify ownership: integration-service owns PriceSheet. profitability-service consumes via gRPC + Redis cache. Remove PriceSheet from Profitability bounded context in domain model. Keep only a ValueObject reference | phase1a, 2.7; phase1b, 2.3 |
| SE-025 | LOW | Code Quality | Domain event collection in aggregates uses unexported `events []DomainEvent` field. No method shown for retrieving and clearing events (standard DDD pattern: ClearEvents + Events methods) | Add `func (le *LocalEstimate) Events() []DomainEvent` and `func (le *LocalEstimate) ClearEvents()` methods. Show pattern in domain model document | phase1a, 2.1 |
| SE-026 | LOW | Code Quality | Money.Subtract returns error for negative result but Money.Add does not check overflow. int64 max = 9,223,372,036,854,775,807 kopecks = 92,233,720,368,547,757.07 RUB. Unlikely but should be documented | Document max representable amount. Add overflow check in Add if paranoid (amount > math.MaxInt64 - other.amount) | phase1a, 3.1 |
| SE-027 | LOW | React | Export implementation uses html2canvas for PDF -- this produces raster images, not vector. Quality degrades on zoom. Large tables may exceed canvas limits | Consider @react-pdf/renderer for vector PDF generation. For Excel, SheetJS approach is fine. Document that PDF export is "screenshot quality" in limitations | phase1c, 6.5 |
| SE-028 | LOW | Data Model | kafka_dedup table has no retention policy. Every message ever processed stays in the table. At 50 events/sec peak = 4.3M rows/day | Add scheduled cleanup: DELETE WHERE processed_at < now() - interval '7 days'. 7 days is safe because Kafka retention is also 7 days | phase1b, 5.6 |
| SE-029 | LOW | Integration | 1C retry queue allows up to 100 attempts over ~6 days. If integration-service is down for 6+ days, events are lost (status=expired) | 100 attempts / 6 days is reasonable for the use case. Document this as a known limitation. Add monitoring alert when any event reaches attempt 50. Consider extending to 200 attempts for CRITICAL events | phase1e, 2.3 |
| SE-030 | LOW | React | Feature flags page in Settings but no feature flag infrastructure described (no LaunchDarkly, no custom FF service, no DB table for flags) | Add feature_flags table to analytics or integration DB. Simple key-value with JSON schema for rules. Or use environment variables for Phase 1 and defer FF infrastructure to Phase 2 | phase1c, 7 |
| SE-031 | LOW | Documentation | SLA matrix in Level 2 system prompt says "P1 (orders < 100K RUB)" and "P2 (orders 100K-1M RUB)" but FM defines P1 as "> 500K or emergency" and P2 as "standard". The AI prompt has incorrect priority definitions | Fix Level 2 system prompt to match FM priority definitions exactly. P1 = > 500K or emergency; separate SLA tier for < 100K orders regardless of priority | phase1d, 3.1 |

---

## 3. Per-Review Section Analysis

### 3.1. Architecture Review (#178)

**Status: CONDITIONAL PASS (0 CRITICAL, 3 HIGH, 5 MEDIUM)**

**What is good:**
- Clean Architecture boundaries are well-defined. Domain layer has zero external imports -- only stdlib and UUID.
- Each service owns its data (separate PostgreSQL databases). No cross-service DB access.
- Bounded contexts (Profitability, Workflow, Analytics, Integration) map cleanly to services.
- gRPC for inter-service sync calls, Kafka for async events -- correct choice for this scale.
- connect-go for gRPC is a modern choice allowing both gRPC and HTTP/JSON clients.
- Outbox pattern for reliable event publishing -- correct and well-documented.
- Wire for DI -- compile-time DI, idiomatic Go.

**Issues:**
- **SE-003 (HIGH):** Cross-context UUID coupling in ApprovalProcess.
- **SE-007 (HIGH):** Missing BFF/aggregation layer for frontend.
- **SE-011 (MEDIUM):** Large aggregate loading (1000 line items).
- **SE-012 (MEDIUM):** Outbox polling at 100ms is wasteful under low load.
- **SE-013 (MEDIUM):** FK integrity impossible with temporal tables.
- **SE-021 (MEDIUM):** SLA timer granularity too coarse for P1.
- **SE-024 (MEDIUM):** PriceSheet ownership ambiguity.
- **SE-025 (LOW):** Missing Events()/ClearEvents() pattern.

**Recommendations:**
1. Add BFF endpoint for dashboard data aggregation (reduces 5 calls to 1).
2. Document temporal table FK trade-off explicitly in architecture docs.
3. Split PriceSheet: aggregate in Integration context, value object reference in Profitability.

---

### 3.2. API Contract Review (#179)

**Status: PASS (0 CRITICAL, 1 HIGH, 3 MEDIUM)**

**What is good:**
- RESTful naming with consistent /api/v1/ prefix.
- snake_case in JSON (Go struct tags + sqlc handle mapping).
- PascalCase in Go types.
- Versioning via URL path (/api/v1/).
- Comprehensive endpoint coverage -- all FM requirements mapped to API endpoints.
- OpenAPI protobuf definitions are clear and well-structured.
- Kafka topic naming convention (`{source}.{domain}.{event}.v{N}`) is excellent.

**Issues:**
- **SE-004 (HIGH):** Inconsistent pagination (cursor vs offset across endpoints).
- **SE-014 (MEDIUM):** RFC 7807 error format mentioned but not concretely defined.
- **SE-016 (MEDIUM):** Batch operations use individual calls instead of batch endpoint.
- **SE-023 (MEDIUM):** No protobuf-level UUID/timestamp validation.

**Recommendations:**
1. Standardize cursor-based pagination for all list endpoints.
2. Define concrete RFC 7807 error type registry.
3. Add `POST /api/v1/approvals/batch-decide` for atomic batch operations.

---

### 3.3. Data Model Review (#180)

**Status: CONDITIONAL PASS (1 CRITICAL, 1 HIGH, 4 MEDIUM, 2 LOW)**

**What is good:**
- 3NF achieved across all service databases.
- Proper indices on all FK columns and query columns.
- Partial indices with WHERE clauses for common query patterns (excellent).
- Temporal tables with valid_from/valid_to for MDM -- correct design.
- Outbox tables consistent across all 5 services.
- basis points for percentages, kopecks for money -- proper integer-based financial storage.
- Composite indices for common access patterns (e.g., `idx_local_estimates_expires`).

**Issues:**
- **SE-002 (CRITICAL):** float64/DOUBLE PRECISION for quantity in financial calculations.
- **SE-006 (HIGH):** Percentage storage unit mismatch between domain and DB.
- **SE-017 (MEDIUM):** No cleanup for auto_approval_counters.
- **SE-020 (MEDIUM):** No cleanup for notification_throttle.
- **SE-028 (LOW):** No cleanup for kafka_dedup.
- **SE-013 (MEDIUM):** Temporal table FK trade-off.

**No cross-service joins found** -- each service queries only its own database.

**No missing indices detected** for common query patterns. However, adding a composite index on `shipments(local_estimate_id, status)` would benefit the remainder calculation query which filters by both columns.

**Recommendations:**
1. **MUST FIX:** Replace DOUBLE PRECISION with NUMERIC(15,3) for quantity columns.
2. Standardize Percentage storage -- document that DB BIGINT = basis points (hundredths of percent).
3. Add cleanup jobs for all counter/dedup tables.
4. Add composite index `idx_shipments_le_status ON shipments(local_estimate_id, status)`.

---

### 3.4. Security Review (#181)

**Status: CONDITIONAL PASS (1 CRITICAL, 2 HIGH, 2 MEDIUM)**

**What is good:**
- JWT RS256 -- asymmetric signing, correct choice for microservices.
- RBAC with role checks on every endpoint.
- AD group -> role mapping is clean and maintainable.
- sqlc generates parameterized queries -- SQL injection protection by design.
- React auto-escaping for XSS protection.
- CSP headers defined (though `unsafe-inline` for styles should be removed when possible).
- CORS whitelist to single origin (`https://profit.ekf.su`).
- Infisical for secrets management -- never in code.
- API key rotation for 1C integration with 48h overlap period.
- mdm_audit_log is append-only with trigger preventing UPDATE/DELETE -- excellent integrity guarantee.

**Issues:**
- **SE-001 (CRITICAL):** Money arithmetic lacks overflow protection.
- **SE-005 (HIGH):** No CSRF protection for mutation endpoints.
- **SE-010 (HIGH):** Refresh token rotation not implemented.
- **SE-015 (MEDIUM):** AI prompt injection risk via /api/v1/ai/ask.
- No HIGH/CRITICAL security vulnerabilities in data-at-rest or transport (HTTPS enforced, HSTS configured).

**No input validation gaps found** for user-facing endpoints -- Zod on frontend, struct tags on backend, sqlc for DB queries.

**Recommendations:**
1. **MUST FIX:** Add overflow checks to Money value object.
2. Implement CSRF double-submit cookie pattern.
3. Implement refresh token rotation with DB-stored hashes.
4. Add input sanitization for AI chat endpoint.

---

### 3.5. Performance Review (#182)

**Status: PASS (0 CRITICAL, 1 HIGH, 3 MEDIUM)**

**What is good:**
- Redis caching for НПСС with 1h TTL and event-driven invalidation.
- Connection pooling mentioned (min 5, max 20 per service).
- Cursor-based pagination for shipments (no OFFSET scan).
- Rate limiting per-user with token bucket.
- Prometheus metrics exposed for monitoring.
- React: staleTime configuration, selective field loading, virtualized tables for 100+ rows.

**Latency budget analysis (documented in Phase 1B):**
- API Gateway: 10ms (JWT validation, routing)
- Service logic: 50ms (calculation, DB queries)
- DB query: 30ms (indexed queries)
- Network: 10ms (internal)
- **Total: 100ms p50** -- reasonable for 50-70 users.

**Issues:**
- **SE-008 (HIGH):** Dashboard polling creates 200-350 req/sec background load.
- **SE-012 (MEDIUM):** Outbox poller 100ms wasteful under low load.
- **SE-022 (MEDIUM):** Shipment drawer waterfall (sequential fetches).
- **SE-011 (MEDIUM):** Full aggregate loading (1000 items).

**Kafka consumer lag monitoring** is mentioned but not detailed. DLQ alerting is defined (alert if >0 messages in DLQ) -- good.

**DB connection pool sizing** (min 5, max 20) is appropriate for 50-70 concurrent users spread across 6 services.

**Recommendations:**
1. Replace dashboard polling with SSE/WebSocket push model.
2. Add LISTEN/NOTIFY for outbox to reduce idle DB polls.
3. Add combined endpoint for shipment drawer to avoid waterfall.

---

### 3.6. AI Architecture Review (#183)

**Status: PASS (0 CRITICAL, 0 HIGH, 2 MEDIUM, 1 LOW)**

**What is good:**
- Three-level escalation (deterministic -> Sonnet -> Opus) is cost-optimal.
- Level 1 at $0/request handles 90%+ of checks -- excellent.
- Prompt caching for Level 2 system prompt (~20K tokens) saves 90% on input costs.
- Budget ceiling enforced at middleware ($50/day hard stop).
- Fallback chain: Level 3 timeout -> Level 2 result -> Level 1 summary -> deterministic.
- AI audit log captures every request with cost, latency, tokens.
- Langfuse integration for observability.
- No PII in AI prompts -- entity IDs are UUIDs, not names (note: approver_name appears in some tool outputs; should be hashed).

**All guardrails have implementation plan:**
- Cost: daily ceiling with 60%/80%/100% thresholds.
- Prompt injection: structured JSON output schema enforced.
- Rate limiting: 200/hour Level 2, 50/hour Level 3.
- Timeouts: 15s Level 2, 60s Level 3.
- Max iterations: 10 tool calls for Level 3.

**Issues:**
- **SE-015 (MEDIUM):** Prompt injection via /api/v1/ai/ask (Q&A endpoint).
- **SE-031 (LOW):** SLA matrix in Level 2 prompt has incorrect priority definitions.
- **SE-019 (MEDIUM):** Circuit breaker for ELMA is too aggressive (cross-ref with integration review).

**Recommendations:**
1. Fix priority definitions in AI system prompt to match FM exactly.
2. Hash approver_name before sending to AI tools (PII protection).
3. Add separate system prompt for Q&A use case (less business context exposure).

---

### 3.7. Integration Review (#184)

**Status: PASS (0 CRITICAL, 1 HIGH, 2 MEDIUM, 1 LOW)**

**What is good:**
- All 17 integrations documented with protocol, direction, frequency, FM reference.
- Kafka partitioning by aggregate_id (order_id, product_id, client_id, ls_id) -- ensures ordering within partition.
- Idempotency via kafka_dedup table with message_id.
- DLQ defined for all topics with monitoring alert.
- Outbox pattern guarantees same-transaction atomicity.
- 1C extension uses proper подписки на события (event subscriptions) for УТ 10.2.
- Retry queue in 1C with exponential backoff (30s -> 2h over 100 attempts).
- Event routing map in integration-service is clean and extensible.
- JSON Schema validation for all 9 inbound event payloads.

**1C compatibility confirmed:**
- Platform 8.3: extensions (.cfe) available, HTTP services available.
- УТ 10.2: ordinary forms (not managed forms) -- no managed application module needed.
- Event subscriptions work in extension modules.
- Constants for configuration (URL, port, API key, kill switch).

**Issues:**
- **SE-009 (HIGH):** Synchronous HTTP call during document posting blocks 1C user.
- **SE-019 (MEDIUM):** ELMA circuit breaker too aggressive.
- **SE-029 (LOW):** 100-attempt retry limit means 6-day outage loses events.
- **SE-028 (LOW):** kafka_dedup table has no cleanup.

**Outbox pattern details:**
- Polling interval: 100ms (adequate for event-driven flow).
- Batch size: 100.
- Max retries: 10 before DLQ.
- Cleanup: events older than 7 days deleted (documented).

**All 17 integrations pass review** with the caveats noted above.

---

### 3.8. Coverage Targets Review (#185)

**Status: PASS (targets approved with adjustments)**

**Proposed targets:**
- `domain/` 95% coverage with table-driven tests -- **APPROVED.** Domain is pure functions and value objects. Table-driven tests with testify are the standard Go pattern. 95% is achievable.
- Total 88% coverage -- **APPROVED with note.** 88% is ambitious for a microservices project with infrastructure code (Kafka consumers, HTTP handlers). Exclude generated code (sqlc, Wire, protobuf) from coverage calculation.
- Mutation testing for `domain/` -- **APPROVED.** Use go-mutesting or gremlins. Focus on business rule functions (ProfitabilityCalculator, ThresholdEvaluator, ApprovalRouter).
- Load test thresholds for 50-70 users -- **APPROVED with adjustments:**
  - p50 < 100ms: reasonable.
  - p95 < 500ms: reasonable.
  - p99 < 1000ms: reasonable.
  - Max concurrent connections: 200 (accounts for polling + active requests).
  - Kafka consumer lag: < 100 messages sustained, < 1000 burst.

**Test categories recommended:**
- Unit tests: domain logic, value objects, calculators (table-driven, testify).
- Integration tests: repository + DB (testcontainers-go for PostgreSQL, Kafka).
- Contract tests: gRPC service contracts (buf breaking check).
- E2E tests: critical user flows via API (Playwright for frontend, httptest for backend).
- Load tests: k6 with 100 VU, 5-minute ramp-up, 10-minute sustained.

---

### 3.9. AI Eval Suite Design (#186)

**30 test cases defined below with expected results.**

**Scoring methodology:**
- Anomaly detection accuracy: automated (compare detected vs labeled ground truth).
- Explanation quality: human eval 1-5 scale (clarity, accuracy, actionability).
- Baseline targets: >=95% accuracy on anomaly detection, >=4.0/5.0 on explanation quality.

#### 3.9.1. Anomaly Detection Test Cases (10)

| # | ID | Type | Input Summary | Expected: Anomaly? | Expected Z-score range | Rationale |
|---|-----|------|---------------|--------------------|-----------------------|-----------|
| 1 | AD-TC-01 | cherry_picking | Client fulfills 45% of LS, avg margin 8% vs plan 18% | Yes | >= 3.0 | Classic cherry-picking pattern |
| 2 | AD-TC-02 | volume_anomaly | Manager 35 orders/day vs avg 8.5 | Yes | >= 2.5 | 4.1x volume spike |
| 3 | AD-TC-03 | npss_age_block | 12 items with НПСС 95 days old, import China | Yes | N/A (rule) | НПСС > 90 days rule |
| 4 | AD-TC-04 | exchange_rate | USD +5.3% in 7 days | Yes | N/A (rule) | LS-BR-075 trigger |
| 5 | AD-TC-05 | margin_drop_7d | BU avg deviation 3.2->8.8 pp in 7 days | Yes | >= 2.0 | 5.6 pp drop > 5 pp threshold |
| 6 | AD-TC-06 | normal_operation | Manager 9 orders/day, avg margin within 1 pp | No | < 2.0 | Normal operations |
| 7 | AD-TC-07 | seasonal_peak | December: volume 2x normal, margin stable | No (volume rule fires, but margin OK) | < 2.0 for margin | Seasonal volume is expected |
| 8 | AD-TC-08 | approver_overload | Queue 52 tasks, daily processed 38 | Yes | N/A (rule) | > 50 threshold |
| 9 | AD-TC-09 | auto_limit_approach | BU daily 85K of 100K limit at 14:30 | Yes | N/A (rule) | 85% > 80% warning |
| 10 | AD-TC-10 | npss_fresh | All items НПСС < 30 days, margin stable | No | < 2.0 | Everything normal |

#### 3.9.2. Explanation Quality Test Cases (10)

| # | ID | Anomaly Type | Input Summary | Expected Explanation Must Contain | Quality Threshold |
|---|-----|-------------|---------------|----------------------------------|------------------|
| 11 | EQ-TC-01 | cherry_picking | Sample 1 from phase1d | "выборочный выкуп", "низкомаржинальные", financial impact estimate | >= 4.0/5.0 |
| 12 | EQ-TC-02 | npss_stale | Sample 2 from phase1d | "НПСС старше 90 дней", "блокирует согласование", currency impact | >= 4.0/5.0 |
| 13 | EQ-TC-03 | volume_spike | Sample 3 from phase1d | "дробление", "обход порога", limit utilization | >= 4.0/5.0 |
| 14 | EQ-TC-04 | approver_overload | Sample 4 from phase1d | "перегружен", "SLA нарушения", "заместитель не назначен" | >= 4.5/5.0 |
| 15 | EQ-TC-05 | unclear_anomaly | Sample 5 from phase1d | confidence < 0.7, requires_level_3 = true | >= 3.5/5.0 |
| 16 | EQ-TC-06 | exchange_rate | Sample 6 from phase1d | "курс", "автотриггер", "пересчёт НПСС" | >= 4.0/5.0 |
| 17 | EQ-TC-07 | bu_limit | Sample 7 from phase1d | "агрегированный лимит", "исчерпание" | >= 4.0/5.0 |
| 18 | EQ-TC-08 | elma_fallback | Sample 8 from phase1d | "резервный режим", "очередь FIFO", "автосогласование" | >= 4.0/5.0 |
| 19 | EQ-TC-09 | correction_limit | Sample 9 from phase1d | "итерация корректировки", "автоотказ" | >= 4.0/5.0 |
| 20 | EQ-TC-10 | cross_validation | Sample 10 from phase1d | "перекрёстный контроль", "аннулировано", "план изменён" | >= 4.0/5.0 |

#### 3.9.3. Investigation Quality Test Cases (5)

| # | ID | Scenario | Input | Expected Investigation Must Include | Max Tool Calls |
|---|-----|----------|-------|-------------------------------------|---------------|
| 21 | IQ-TC-01 | Unknown margin drop | BU-West margin drop, no obvious cause | query_shipments + query_client_history, identify if client mix changed | <= 7 |
| 22 | IQ-TC-02 | Suspected collusion | Two managers, same client, alternating orders to stay under auto-approval | query_shipments (both managers), query_client_history, evidence of pattern | <= 8 |
| 23 | IQ-TC-03 | NPSS vs purchase price | Margin drop correlates with recent purchase price increase | query_price_changes, calculate_what_if with updated prices | <= 5 |
| 24 | IQ-TC-04 | Seasonal pattern | Year-end volume spike with margin dip | query_shipments (12 month history), identify seasonal pattern | <= 6 |
| 25 | IQ-TC-05 | Insufficient data | New client, 2 orders total, Z-score=2.1 | Confidence < 0.5, requires_manual_review = true, explains data insufficiency | <= 3 |

#### 3.9.4. Edge Case Test Cases (5)

| # | ID | Scenario | Input | Expected Behavior | Notes |
|---|-----|----------|-------|-------------------|-------|
| 26 | EC-TC-01 | Zero stddev | 30 identical values, current differs | Z-score = +Inf, anomaly = true | Division by zero handling |
| 27 | EC-TC-02 | Budget exhausted | Daily cost at $50, new anomaly detected | Level 1 result only, no LLM call | Hard stop enforcement |
| 28 | EC-TC-03 | Level 3 timeout | Investigation takes > 60s | Return partial results from completed tool calls, confidence penalty | Graceful degradation |
| 29 | EC-TC-04 | Concurrent anomalies | 5 anomalies detected in same second | All 5 processed, no race condition on counters | Concurrency safety |
| 30 | EC-TC-05 | Empty history | First day of operation, 0 historical data | Skip Z-score (< 30 samples), rule engine only | Cold start handling |

---

## 4. Corrections Required (for Agent 5 to fix)

### CRITICAL (must fix before development)

1. **SE-002: Replace float64/DOUBLE PRECISION for quantity.** Change all quantity fields in Go structs and SQL schemas to fixed-point representation. Options:
   - Option A (recommended): Use `int64` with multiplier 1000 (milliunit representation). Quantity 100.5 = 100500. Change DB to `BIGINT`.
   - Option B: Use `shopspring/decimal` in Go and `NUMERIC(15,3)` in DB.
   - Do NOT use `float64` for financial quantity calculations.

2. **SE-001: Fix Money value object arithmetic.** Add overflow check in `Add()`:
   ```go
   func (m Money) Add(other Money) (Money, error) {
       result := m.amount + other.amount
       if (other.amount > 0 && result < m.amount) || (other.amount < 0 && result > m.amount) {
           return Money{}, ErrMoneyOverflow
       }
       return Money{amount: result}, nil
   }
   ```
   Also change `Multiply` to disallow negative factors (or make it explicit with `Negate()` method).

### HIGH (must fix before Sprint 27)

3. **SE-006: Standardize Percentage representation.** Document clearly: `Percentage.basis` = basis points * 100 (ten-thousandths of percent) OR basis points (hundredths of percent). Align DB storage description. Current code has `NewPercentage(15.00)` creating `basis=1500`. Is 1500 = 15.00% (basis points) or 0.1500% (basis points * 100)? Clarify.

4. **SE-004: Standardize pagination.** Change anomaly list endpoint to cursor-based. Update phase1c React code for AI insights page to use cursor-based pagination.

5. **SE-005: Add CSRF protection.** Document CSRF strategy in api-gateway security section.

6. **SE-010: Document refresh token rotation.** Add rotation strategy to auth flow section.

7. **SE-009: Make 1C event sending async-first.** Change primary path to always write to retry queue, then send from background job. Current synchronous-first approach risks blocking 1C users.

8. **SE-003: Decouple cross-context identifiers.** Use ExternalID (string) instead of UUID at bounded context boundaries.

---

## 5. Approved (no changes needed)

The following design decisions are approved and should NOT be changed:

1. **Service decomposition (6 services):** Correct granularity for the domain. Not too many, not too few.
2. **Tech stack (chi, sqlc, franz-go, Wire, connect-go):** All production-grade, well-maintained, idiomatic Go.
3. **Outbox pattern for event publishing:** Correct pattern for transactional consistency with Kafka.
4. **Temporal tables for MDM:** Correct approach for maintaining history of client/product/price data.
5. **Three-level AI architecture:** Cost-optimal escalation from deterministic to Sonnet to Opus.
6. **Kafka topic naming convention:** Clear, consistent, extensible.
7. **SLA matrix from FM:** Correctly translated to code (slaMatrix function).
8. **Value objects (Money, Percentage, SLADeadline):** Proper DDD immutable value objects.
9. **React architecture (Next.js 15 App Router + TanStack Query + Zustand):** Modern, well-chosen stack.
10. **Atomic Design component hierarchy:** Clean separation of concerns in UI components.
11. **RBAC per endpoint with AD group mapping:** Correct for corporate environment.
12. **Graceful shutdown pattern:** Documented with proper drain sequence.
13. **44 Kafka topics (9 inbound, 24 internal, 3 outbound, 8 DLQ):** Comprehensive coverage.
14. **Circuit breaker for ELMA** (concept approved; parameters need adjustment per SE-019).
15. **AI cost monitoring with daily ceiling and Langfuse integration.**
16. **mdm_audit_log append-only with trigger protection:** Excellent integrity guarantee.
17. **1C extension approach (.cfe):** Correct for УТ 10.2 on platform 8.3.
18. **JSON Schema validation for all inbound event payloads.**

---

## 6. Summary by Issue

| Issue | Category | Findings | Verdict |
|-------|----------|----------|---------|
| #178 | Architecture | 0C/3H/5M/1L = 9 | CONDITIONAL PASS |
| #179 | API Contracts | 0C/1H/3M/0L = 4 | PASS |
| #180 | Data Model | 1C/1H/4M/2L = 8 | CONDITIONAL PASS |
| #181 | Security | 1C/2H/2M/0L = 5 | CONDITIONAL PASS |
| #182 | Performance | 0C/1H/3M/0L = 4 | PASS |
| #183 | AI Architecture | 0C/0H/2M/1L = 3 | PASS |
| #184 | Integration | 0C/1H/2M/1L = 4 | PASS |
| #185 | Coverage | 0C/0H/0M/0L = 0 | PASS (approved) |
| #186 | AI Eval Suite | 0C/0H/0M/0L = 0 | PASS (30 test cases defined) |
| **Total** | | **2C/8H/14M/7L = 31** (some findings cross multiple issues) | **CONDITIONAL PASS** |

**Condition for PASS:** Fix 2 CRITICAL + 8 HIGH findings before Sprint 27 scaffold phase begins.
