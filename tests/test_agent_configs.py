"""
Tests for agent configuration validation.

Validates all 9 subagent frontmatter files (.claude/agents/agent-*.md)
have required fields, consistent settings, and follow system conventions.
"""
import json
import os
import re
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent
AGENTS_DIR = PROJECT_ROOT / ".claude" / "agents"
HOOKS_DIR = PROJECT_ROOT / ".claude" / "hooks"
SETTINGS_FILE = PROJECT_ROOT / ".claude" / "settings.json"
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

AGENT_FILES = sorted(AGENTS_DIR.glob("agent-*.md"))

REQUIRED_FRONTMATTER = ["name", "description", "tools", "maxTurns", "model", "memory"]
VALID_MODELS = {"opus", "sonnet", "haiku"}
VALID_PERMISSION_MODES = {"default", "acceptEdits", "plan", "bypassPermissions"}
ANALYSIS_AGENTS = {"agent-1-architect", "agent-2-simulator", "agent-3-defender", "agent-4-qa-tester"}
WRITING_AGENTS = {"agent-0-creator", "agent-5-tech-architect", "agent-6-presenter",
                  "agent-7-publisher", "agent-8-bpmn-designer"}


def parse_frontmatter(file_path: Path) -> dict:
    """Parse YAML frontmatter from a markdown file."""
    content = file_path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?\n)---", content, re.DOTALL)
    if not match:
        raise ValueError(f"No frontmatter found in {file_path.name}")
    return yaml.safe_load(match.group(1))


class TestAgentFileDiscovery:
    def test_nine_agents_exist(self):
        """All 9 agent files exist in .claude/agents/."""
        assert len(AGENT_FILES) == 9, f"Expected 9 agents, found {len(AGENT_FILES)}"

    def test_agent_numbering(self):
        """Agents are numbered 0-8 consecutively."""
        numbers = []
        for f in AGENT_FILES:
            match = re.match(r"agent-(\d+)-", f.name)
            assert match, f"File {f.name} does not match agent-N-name.md pattern"
            numbers.append(int(match.group(1)))
        assert sorted(numbers) == list(range(9))


class TestFrontmatter:
    @pytest.fixture(params=[f.name for f in AGENT_FILES], ids=[f.stem for f in AGENT_FILES])
    def agent_config(self, request):
        """Parse frontmatter for each agent."""
        file_path = AGENTS_DIR / request.param
        return parse_frontmatter(file_path), file_path

    def test_required_fields_present(self, agent_config):
        """All required frontmatter fields are present."""
        config, path = agent_config
        for field in REQUIRED_FRONTMATTER:
            assert field in config, f"{path.name} missing '{field}'"

    def test_model_is_valid(self, agent_config):
        """Model field is a recognized Claude model."""
        config, path = agent_config
        assert config["model"] in VALID_MODELS, \
            f"{path.name} has invalid model '{config['model']}'"

    def test_memory_is_project(self, agent_config):
        """All agents use project-scoped memory."""
        config, path = agent_config
        assert config["memory"] == "project", \
            f"{path.name} should have memory: project"

    def test_max_turns_in_range(self, agent_config):
        """maxTurns is between 10 and 30."""
        config, path = agent_config
        turns = config["maxTurns"]
        assert 10 <= turns <= 30, \
            f"{path.name} maxTurns={turns}, expected 10-30"

    def test_has_permission_mode(self, agent_config):
        """permissionMode is set for all agents."""
        config, path = agent_config
        assert "permissionMode" in config, \
            f"{path.name} missing permissionMode"
        assert config["permissionMode"] in VALID_PERMISSION_MODES, \
            f"{path.name} invalid permissionMode '{config['permissionMode']}'"


class TestLeastPrivilege:
    """Test that analysis-only agents cannot write files."""

    @pytest.fixture(params=list(ANALYSIS_AGENTS))
    def analysis_agent(self, request):
        """Get config for analysis-only agents (1,2,3,4)."""
        file_path = next(f for f in AGENT_FILES if request.param in f.name)
        return parse_frontmatter(file_path), file_path

    @pytest.fixture(params=list(WRITING_AGENTS))
    def writing_agent(self, request):
        """Get config for agents that need write access (0,5,6,7,8)."""
        file_path = next(f for f in AGENT_FILES if request.param in f.name)
        return parse_frontmatter(file_path), file_path

    def test_analysis_agents_no_write(self, analysis_agent):
        """Analysis agents should not have Write in tools."""
        config, path = analysis_agent
        tools = config.get("tools", "")
        assert "Write" not in tools, \
            f"{path.name} is analysis-only but has Write tool"

    def test_analysis_agents_no_edit(self, analysis_agent):
        """Analysis agents should not have Edit in tools."""
        config, path = analysis_agent
        tools = config.get("tools", "")
        assert "Edit" not in tools, \
            f"{path.name} is analysis-only but has Edit tool"

    def test_analysis_agents_disallowed_tools(self, analysis_agent):
        """Analysis agents should have disallowedTools: Write, Edit."""
        config, path = analysis_agent
        disallowed = config.get("disallowedTools", "")
        assert "Write" in disallowed and "Edit" in disallowed, \
            f"{path.name} should have disallowedTools: Write, Edit"

    def test_writing_agents_have_write(self, writing_agent):
        """Writing agents should have Write and Edit tools."""
        config, path = writing_agent
        tools = config.get("tools", "")
        assert "Write" in tools, \
            f"{path.name} needs Write tool but doesn't have it"
        assert "Edit" in tools, \
            f"{path.name} needs Edit tool but doesn't have it"


class TestMCPServers:
    """Test MCP server configuration for agents that need Confluence."""

    def test_agent_0_has_confluence(self):
        """Agent 0 (Creator) should have confluence MCP server."""
        config = parse_frontmatter(AGENTS_DIR / "agent-0-creator.md")
        assert "mcpServers" in config, "agent-0 missing mcpServers"
        assert "confluence" in config["mcpServers"], "agent-0 missing confluence server"

    def test_agent_7_has_confluence(self):
        """Agent 7 (Publisher) should have confluence MCP server."""
        config = parse_frontmatter(AGENTS_DIR / "agent-7-publisher.md")
        assert "mcpServers" in config, "agent-7 missing mcpServers"
        assert "confluence" in config["mcpServers"], "agent-7 missing confluence server"

    def test_agent_7_has_quality_gate_skill(self):
        """Agent 7 should have quality-gate skill preloaded."""
        config = parse_frontmatter(AGENTS_DIR / "agent-7-publisher.md")
        skills = config.get("skills", [])
        assert "quality-gate" in skills, "agent-7 should have quality-gate skill"


class TestHooks:
    def test_settings_json_valid(self):
        """settings.json is valid JSON."""
        content = SETTINGS_FILE.read_text(encoding="utf-8")
        data = json.loads(content)
        assert "hooks" in data

    def test_all_hook_scripts_exist(self):
        """All hook scripts referenced in settings.json exist."""
        content = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        hooks = content.get("hooks", {})
        for event_type, event_hooks in hooks.items():
            for hook_group in event_hooks:
                for hook in hook_group.get("hooks", []):
                    cmd = hook.get("command", "")
                    # Extract script path from command
                    script_name = cmd.split("/")[-1].strip('"')
                    if script_name:
                        script_path = HOOKS_DIR / script_name
                        assert script_path.exists(), \
                            f"Hook script {script_name} not found (event: {event_type})"

    def test_hook_scripts_executable(self):
        """All hook scripts have execute permission."""
        for script in HOOKS_DIR.glob("*.sh"):
            assert os.access(script, os.X_OK), \
                f"{script.name} is not executable"

    def test_required_hook_events(self):
        """Required hook events are configured."""
        content = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        hooks = content.get("hooks", {})
        required_events = ["SessionStart", "SubagentStart", "SubagentStop", "PreToolUse", "PostToolUse", "Stop"]
        for event in required_events:
            assert event in hooks, f"Missing hook event: {event}"


class TestSkills:
    def test_evolve_skill_exists(self):
        """Evolve skill SKILL.md exists."""
        skill_file = SKILLS_DIR / "evolve" / "SKILL.md"
        assert skill_file.exists(), "evolve skill not found"

    def test_quality_gate_skill_exists(self):
        """Quality gate skill SKILL.md exists."""
        skill_file = SKILLS_DIR / "quality-gate" / "SKILL.md"
        assert skill_file.exists(), "quality-gate skill not found"

    def test_evolve_not_on_readonly_agents(self):
        """Evolve skill must NOT be assigned to agents with disallowedTools: Write, Edit."""
        for agent_file in AGENT_FILES:
            config = parse_frontmatter(agent_file)
            disallowed = config.get("disallowedTools", "")
            if "Write" in disallowed or "Edit" in disallowed:
                skills = config.get("skills", [])
                assert "evolve" not in skills, \
                    f"{agent_file.name} has evolve skill but disallowedTools includes Write/Edit"

    def test_skill_tool_compatibility(self):
        """Skills requiring Write/Edit should not be on agents that disallow them.

        The evolve skill modifies agent files, so it needs Write + Edit.
        No agent with disallowedTools: Write, Edit should have it.
        """
        write_requiring_skills = {"evolve"}
        for agent_file in AGENT_FILES:
            config = parse_frontmatter(agent_file)
            disallowed = config.get("disallowedTools", "")
            has_write_block = "Write" in disallowed or "Edit" in disallowed
            if has_write_block:
                skills = set(config.get("skills", []))
                conflict = skills & write_requiring_skills
                assert not conflict, \
                    f"{agent_file.name} has conflicting skills {conflict} with disallowedTools"


class TestProjectTemplate:
    def test_template_exists(self):
        """PROJECT_CONTEXT.md template exists."""
        template = PROJECT_ROOT / "templates" / "PROJECT_CONTEXT.md"
        assert template.exists()

    def test_template_has_placeholders(self):
        """Template contains required placeholders."""
        template = PROJECT_ROOT / "templates" / "PROJECT_CONTEXT.md"
        content = template.read_text(encoding="utf-8")
        required = ["{{NAME}}", "{{FM_CODE}}", "{{FM_PAGE_ID}}", "{{GOAL}}"]
        for placeholder in required:
            assert placeholder in content, \
                f"Template missing placeholder: {placeholder}"
