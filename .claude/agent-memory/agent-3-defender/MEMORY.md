# Agent 3 Defender - Memory

## Classification Patterns (FM-LS-PROFIT)

- **Deduplication first:** Agent 2 UX findings frequently duplicate Agent 1 audit findings (e.g., UX-LOW-002 = CRIT-001). Agent 4 open questions (Q1-Q3) often directly map to Agent 1 CRIT/HIGH findings. Always deduplicate before classifying.
- **Agent 5 feasibility = validation:** If Agent 5 says "not_applicable" it means the finding is documentary (grammar, style, references) and doesn't affect architecture. Use this to confirm type G classification.
- **UX findings vs FM scope:** Agent 2 UX findings about UI widget details (templates, visual layouts) are typically type B (conscious choice) -- they belong in TZ/architecture, not FM. FM describes processes, not screen templates.
- **Speed impact = always 0 for documentary changes:** Grammar fixes, number corrections, and clarification of existing text never add steps for users.

## Project-Specific Context

- FM-LS-PROFIT v1.0.4: 20 findings from pipeline, 17 unique after dedup, 11 changes for /apply
- Two problematic thresholds: 30 (overflow to deputy) vs 50 (assign additional approver) -- always clarify both
- NPSS race condition (Q3/GAP-02): covered by pessimistic lock (LS-BR-035) + NPSS fixation at LS creation
- Agent hierarchy for conflict resolution: Agent 1 > Agent 5 > Agent 2 > Agent 4 (COMMON_RULES rule 19)

## Workflow Notes

- gh-tasks.sh WARNING about files from other agents' artifacts in git diff is expected and benign
- Always answer Agent 4 open questions explicitly in the defense report (they need concrete values for test cases)
