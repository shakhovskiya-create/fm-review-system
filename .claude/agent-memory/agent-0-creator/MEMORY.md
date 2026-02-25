# Agent 0 (Creator) Memory

## Active Projects
- PROJECT_SHPMNT_PROFIT: PAGE_ID=83951683, FM version latest

## Key Lessons from Patches
- ALWAYS define boundary conditions for every business rule (patch: boundary-conditions)
- ALWAYS ensure cross-references between sections are bidirectional (patch: broken-crossref)
- NEVER use misleading field/entity names — name must match semantics (patch: misleading-name)
- CHECK that notes/exceptions don't contradict the main rule (patch: note-contradiction)
- ALWAYS describe terminal states for approval workflows (patch: missing-terminal-state)

## FM Structure Requirements
- Meta block: version, date, status, author (Shahovsky A.S.)
- Code system table: code prefix + description pairs
- Each business rule: ID, description, formula, boundary conditions, exceptions
- History table: one row per version

## Confluence Format
- Tables: class="confluenceTable", th with background-color #f4f5f7
- Panels: ac:structured-macro name="warning"|"note"
- No blue headers (rgb 59,115,175 prohibited)
- Author always "Shahovsky A.S." — never mention AI/agents
