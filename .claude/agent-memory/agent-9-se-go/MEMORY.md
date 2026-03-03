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

## Critical Patterns Found
- Silent `_, _` error swallowing on `vo.NewMoneyFromDecimal()`, `vo.NewQuantityFromFloat()` in DB scan methods -- recurring across ALL repos
- No optimistic concurrency control despite `version` column in all tables
- Outbox poller uses `fmt.Sprintf` for table name (SQL injection risk)
- SLA `isSmallOrder` flag not persisted, hardcoded false on reconstruction

## Key Domain Conventions
- Money: shopspring/decimal, stored as NUMERIC(18,2), accessed via `.Rubles()`
- Percentage: basis points (int64), stored as BIGINT, `BasisPoints()` / `NewPercentageFromBasisPoints()`
- Quantity: shopspring/decimal with 6dp, stored as NUMERIC(18,6)
- All repos use pgx/v5 + pgxpool
- Kafka: franz-go (kgo), manual commit, CooperativeStickyBalancer
- Redis: go-redis/v9, Lua scripts for distributed locks
