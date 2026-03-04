# Agent 9 Memory -- SE Go+React

## Project: profitability-service
- Repo: `/home/dev/projects/claude-agents/profitability-service/`
- Domain: `internal/domain/` (entities, value objects, services)
- Adapters: `internal/adapter/` (postgres, kafka, redis, outbox, http)
- Ports: `internal/port/` (repository.go, event.go, service.go)

## Review History
- **Sprint 26 (SE Phase 2):** CONDITIONAL PASS, 31 findings (2C/8H/14M/7L). See `se_review_phase2.md`
- **Sprint 28 Stage 1 (Infra Adapters):** CONDITIONAL PASS, 31 findings (2C/5H/15M/9L). See `se_review_sprint28_stage1.md`
- **Sprint 28 TZ+Arch Review:** CONDITIONAL PASS, 18 findings (1C/4H/8M/5L). See `se_review_tz_go_v1.md`
  - CRIT-001: float64/double in gRPC proto for financial values (must use int64 bp/cents)
  - SE-001 (Money overflow) and SE-002 (float64 Quantity) from Sprint 26: RESOLVED
  - isSmallOrder still NOT persisted in DB (HIGH-001)
- **Sprint 28 Stage 2 (External Adapters+AI):** CONDITIONAL PASS, 28 findings (2C/6H/12M/8L). See `se_review_sprint28_stage2.md`
  - CRIT-001-S2: Prompt injection via unsanitized user data in Claude prompts (HistoricalData)
  - CRIT-002-S2: InvestigateAnomaly has zero data context -- hallucination risk
  - HIGH-001-S2: WMS Quantity truncated from decimal to int
  - HIGH-004-S2: Outbox publishes to Kafka BEFORE DB commit
  - HIGH-006-S2: RegisterChatID/RegisterRecipient concurrent map write (panic risk)
- **Sprint 28 Stage 2 Re-Review:** CONDITIONAL PASS (7/8 resolved). See `se_review_sprint28_stage2_recheck.md`
  - CRIT-001-S2: RESOLVED (structured JSON in <data> tags + anti-injection prompt + JSON validation)
  - CRIT-002-S2: RESOLVED (InvestigationContext struct added to port + adapter + usecase)
  - HIGH-001-S2: RESOLVED (Quantity string, .String() method)
  - HIGH-002-S2: RESOLVED (shared circuitbreaker package with tests)
  - HIGH-003-S2: RESOLVED (http.Client{Timeout: max(Sonnet,Opus)})
  - HIGH-004-S2: RESOLVED (at-least-once documented, message_id for dedup)
  - HIGH-005-S2: RESOLVED (ErrThrottled sentinel, HIGH exempt from throttle)
  - HIGH-006-S2: PARTIALLY_RESOLVED (Telegram fixed, Email RegisterRecipient still no mutex)
- **Sprint 29 (AI Analytics L1-L3 + Audit):** CONDITIONAL PASS, 22 findings (2C/4H/9M/7L). See `se_review_sprint29.md`
  - CRIT-001-S29: float64 for financial amounts in rules.go (must use vo.Money)
  - CRIT-002-S29: extractJSON not called in parseAnomalyResults -- markdown JSON causes failure
  - HIGH-003-S29: callAPIWithRetry is dead code -- no retry on transient errors
  - HIGH-006-S2: NOW FULLY RESOLVED (Email RegisterRecipient has sync.RWMutex)
- **Sprint 29 Re-Review (Iteration 2):** **PASS**, 13/22 resolved, 7 remaining (4M/3L). See `se_review_sprint29_r2.md`
  - ALL CRITICAL RESOLVED: CRIT-001-S29 (vo.Money), CRIT-002-S29 (extractJSON wired in)
  - ALL HIGH RESOLVED: HIGH-001 (DRY extractJSON), HIGH-002 (strings.Contains), HIGH-003 (callAPIWithRetry live), HIGH-004 (documented + 5s backoff)
  - Remaining: MED-005 (TOCTOU cosmetic), MED-006 (ring buffer leak), MED-007 (sendAllChannels semantics), MED-008 (misleading log), LOW-002/003/005

## Critical Patterns Found
- Silent `_, _` error swallowing on `vo.NewMoneyFromDecimal()`, `vo.NewQuantityFromFloat()` in DB scan methods -- recurring across ALL repos
- No optimistic concurrency control despite `version` column in all tables
- Outbox poller SQL injection risk: RESOLVED (table name regex validation added in Stage 2)
- SLA `isSmallOrder` flag not persisted, hardcoded false on reconstruction
- Prompt injection: RESOLVED -- now uses structured JSON in <data> tags with anti-injection system prompt
- DRY violation: doWithRetry/doRequest duplicated across 3 HTTP adapters (ELMA, WMS, CBR ~210 lines)
- Quantity.Float64() -> int truncation: RESOLVED -- WMS now uses string serialization
- Email RegisterRecipient concurrent map write: RESOLVED in Sprint 29 (sync.RWMutex added)
- Shared circuitbreaker package: `internal/adapter/circuitbreaker/` -- reusable for ELMA, WMS, CBR
- float64 for financial amounts: RESOLVED in Sprint 29 R2 (rules.go + aggregated_monitor.go now use vo.Money)
- extractJSON: RESOLVED in Sprint 29 R2 (wired into parseAnomalyResults + parseInvestigationReport; domain copy made robust)
- callAPIWithRetry: RESOLVED in Sprint 29 R2 (called from DetectAnomalies + InvestigateAnomaly)
- Ring buffer `auditLog[1:]` memory leak: NOT RESOLVED (low-priority, ~35MB/day accumulation)

## Key Domain Conventions
- Money: shopspring/decimal, stored as NUMERIC(18,2), accessed via `.Rubles()`
- Percentage: basis points (int64), stored as BIGINT, `BasisPoints()` / `NewPercentageFromBasisPoints()`
- Quantity: shopspring/decimal with 6dp, stored as NUMERIC(18,6)
- All repos use pgx/v5 + pgxpool
- Kafka: franz-go (kgo), manual commit, CooperativeStickyBalancer
- Redis: go-redis/v9, Lua scripts for distributed locks
