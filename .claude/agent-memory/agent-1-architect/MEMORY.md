# Agent 1 (Architect/Auditor) Memory

## Active Projects
- PROJECT_SHPMNT_PROFIT: PAGE_ID=83951683, FM version latest

## Common Audit Findings (from patches)
1. **Boundary conditions missing** — rules define happy path but not edge cases (0 qty, negative amounts, max limits)
2. **Broken cross-references** — section A references section B but B doesn't reference back
3. **Misleading names** — field/entity name suggests one thing, actual semantics differ
4. **Note contradictions** — exception note contradicts the main business rule
5. **Missing terminal states** — approval workflows lack explicit reject/cancel/timeout states
6. **Untestable approval cycles** — approval flow has no max iteration or timeout

## Audit Severity Scale
- CRITICAL: breaks business logic, data corruption risk
- HIGH: significant gap, workaround exists
- MEDIUM: inconsistency, cosmetic, improvement
- LOW: style, documentation quality

## Output Contract
- audit_summary.json: schema v2.2 (schemas/agent-contracts.json)
- audit_findings.json: array of {id, severity, section, description, recommendation}
- AUDIT-REPORT-vX.Y.Z-YYYY-MM-DD.md: human-readable report
