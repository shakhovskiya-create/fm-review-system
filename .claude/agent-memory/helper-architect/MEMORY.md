# Helper-Architect Agent Memory

## Hook Architecture
- Hooks live in `.claude/hooks/`, registered in `.claude/settings.json`
- SubagentStart hooks receive JSON on stdin with `subagent_name` and `prompt` fields
- Exit 0 = proceed (stdout prepended to agent prompt), Exit 2 = block
- Hook timeout in settings.json must cover all network calls within the script
- `timeout` command wraps gh API calls for graceful degradation

## subagent-context.sh (SubagentStart)
- Injects project context + GitHub Issues to subagents
- **Issue gate**: blocks agents without `status:in-progress` issue (exit 2)
- Whitelist: `helper-architect` (IS_ORCHESTRATOR=true), `--skip-issue-check` in prompt
- Graceful degradation: gh API failure/timeout -> WARNING + exit 0
- Single `gh issue list` call, jq parses `status:in-progress` from labels array
- Hook timeout: 10s (settings.json), gh API timeout: 4s (timeout command)

## Testing Patterns
- `test_hooks.py` uses `run_hook()` helper that sets CLAUDE_PROJECT_DIR
- Mock `gh` CLI via tmp_path scripts prepended to PATH
- `_setup_project_dir()` creates `.claude/` dir for marker file writes
- Tests verify exit codes (0 vs 2) and stdout messages (BLOCK/WARNING)

## Key Paths
- Settings: `.claude/settings.json` (hook registration + timeouts)
- Hooks dir: `.claude/hooks/`
- Tests: `tests/test_hooks.py`
- gh-tasks.sh: `scripts/gh-tasks.sh` (create/start/done/block/list)
