# Agent 2 Simulator Memory

## Project: PROJECT_SHPMNT_PROFIT (FM-LS-PROFIT)

### UX Simulation History
- **v1.0.2** (2026-02-16): 5 problems (3 HIGH + 2 MEDIUM). Key: no SLA countdown, low auto-agreement limit, low emergency limit
- **v1.0.3** (2026-02-17): All 5 v1.0.2 problems fixed (SLA countdown, 5000/day limit, 10/month emergency, 5min blocking, explicit SLA)
- **v1.0.4** (2026-02-25): 4 problems (2 MEDIUM + 2 LOW). New: threshold 30/50 UI, cross-control notification template, dashboard alert, LS-BR-035 15min vs 5min

### Key Patterns
- Always compare with previous simulation version
- Check Agent 1 audit findings for overlap (UX-LOW-002 = CRIT-001 of audit v1.0.4)
- Aggregated limits (20K/manager, 100K/BU) added in v1.0.3 — important for sales scenario simulation
- Cross-control of scales (п. 3.15) added in v1.0.4 — rare but confusing event for managers

### Confluence Access
- Page ID: 83951683, REST API with Bearer token via load-secrets.sh
- Parse HTML -> strip tags -> regex search for key passages

### Roles Simulated
- Manager (sales): primary focus, 8-10 steps, 5 scenarios (positive, negative, urgent, peak, cross-control)
- Approver (РБЮ): 3-5 steps, overflow threshold focus
- CFO (ФД): dashboard, reports, anomaly detection
