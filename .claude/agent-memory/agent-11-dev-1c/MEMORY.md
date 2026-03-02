# Agent 11 Dev 1C -- Memory

## Project: PROJECT_SHPMNT_PROFIT

### Platform
- 1C:UT 10.2 on platform 8.3 -- ordinary forms ONLY, no managed forms
- Extensions (.cfe) available, HTTP services available
- Compatibility mode 8.3.9
- No async (Promise/Await), no client/server directives

### Naming Conventions
- Prefix: `ekf_` (organization-wide, lowercase)
- Extension name: `КонтрольРентабельностиИнтеграция`
- Common modules: `ekf_ИнтеграцияСервер`, `ekf_ИнтеграцияФоновые`, `ekf_ИнтеграцияКоллбэкСервер`
- Info registers: `ekf_ОчередьОтправкиСобытий`, `ekf_ОбработанныеКоллбэки`
- HTTP service: `ekf_КонтрольРентабельностиКоллбэк`

### Document Names in UT 10.2
- Order: `ЗаказПокупателя` (NOT `ЗаказКлиента` -- that is UT 11.x)
- Shipment: `РеализацияТоваровИУслуг`
- Return: `ВозвратТоваровОтПокупателя`

### Integration Architecture
- Outbound: 1C -> HTTP POST -> integration-service -> Kafka (9 topics)
- Inbound: Kafka -> integration-service -> HTTP PUT -> 1C callback (3 topics)
- Retry queue: exponential backoff, max 100 attempts (~6 days), then expired
- Idempotency: UUID message_id (outbound), request_id (inbound callback)
- Kill switch: constant `ekf_ИнтеграцияАктивна`

### Spec Source
- Integration spec: `AGENT_5_TECH_ARCHITECT/phase1e_integration_architecture.md`
- 9 inbound event schemas in section 2.6
- 3 outbound callback schemas in section 3.2

### Completed Work
- [2026-03-02] Phase 1.5 extension code generated (issues #173, #174, #175)
  - Output: `AGENT_11_DEV_1C/phase1_5_extension.md`
  - 14 metadata objects, 32 test scenarios
  - Callback business logic scaffolded only (Phase 2 for full implementation)

### GitHub API Note
- gh-tasks.sh uses GraphQL which has separate rate limit from REST API
- When GraphQL rate limit exhausted, use REST API directly: `gh api repos/OWNER/REPO/issues/N -X PATCH -f state=closed`
