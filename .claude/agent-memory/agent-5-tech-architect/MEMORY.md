# Agent 5 Tech Architect - Memory

## Project: PROJECT_SHPMNT_PROFIT (FM-LS-PROFIT)

### Architecture versions
- v1.0.6: 77 objects, estimate 2293h, 10-50 users
- v1.0.4: 143 objects, estimate 2758h, 50-70 users (+66 objects, +20% effort)

### Key files
- Architecture: `projects/PROJECT_SHPMNT_PROFIT/AGENT_5_TECH_ARCHITECT/ARCHITECTURE-v1.0.4.md`
- TZ: `projects/PROJECT_SHPMNT_PROFIT/AGENT_5_TECH_ARCHITECT/TZ-v1.0.4.md`
- Feasibility: `projects/PROJECT_SHPMNT_PROFIT/AGENT_5_TECH_ARCHITECT/feasibility_review.json`
- Summary: `projects/PROJECT_SHPMNT_PROFIT/AGENT_5_TECH_ARCHITECT/full_summary.json`

### Patterns learned
- Large architecture files (>25000 tokens) must be read with offset/limit in 3 chunks (~300 lines each)
- Always read previous version files before creating new ones to maintain consistency
- feasibility_review.json is a separate artifact from full_summary.json
- Not all findings need architectural changes -- document "not_applicable" for editorial/doc issues
- Confluence PAGE_IDs: FM=83951683, TZ=86048834, Architecture=86048854

### Schema compliance
- full_summary.json follows `agentSummary` schema from `schemas/agent-contracts.json`
- Required fields: agent, command, timestamp, fmVersion, project, status
- Agent 5 specific: counts (by object type), estimate, outputFiles
