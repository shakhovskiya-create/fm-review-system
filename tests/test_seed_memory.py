"""
Tests for seed_memory.py — Knowledge Graph seeding script.

Validates entity definitions, relation consistency, project discovery,
deduplication, and JSONL output format.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from scripts.seed_memory import (
    AGENTS,
    BUSINESS,
    CICD,
    DECISIONS,
    DOCUMENTS,
    HOOKS,
    INFRA,
    MCP_SERVERS,
    MODULES,
    PATCHES,
    PIPELINE,
    PROJECT_ROOT,
    RELATIONS,
    RULES,
    SCRIPTS,
    SKILLS,
    discover_projects,
    write_memory,
)

ALL_ENTITIES = (AGENTS + [PIPELINE] + SCRIPTS + HOOKS + MCP_SERVERS + SKILLS
                + MODULES + DECISIONS + RULES + CICD + DOCUMENTS + INFRA + PATCHES + BUSINESS)


class TestAgentDefinitions:
    """Validate AGENTS list structure."""

    def test_agents_defined(self):
        """12 agents: Agent0-8 + Agent9 (SE Go) + Agent10 (SE 1C) + Orchestrator_Helper."""
        assert len(AGENTS) == 12

    def test_each_agent_has_name(self):
        for agent in AGENTS:
            assert "name" in agent

    def test_each_agent_has_entity_type(self):
        for agent in AGENTS:
            assert agent["entityType"] == "agent"

    def test_each_agent_has_observations(self):
        for agent in AGENTS:
            assert "observations" in agent
            assert len(agent["observations"]) >= 2

    def test_agent_names_unique(self):
        names = [a["name"] for a in AGENTS]
        assert len(names) == len(set(names))

    def test_fm_agent_names_match_ids(self):
        """FM agents (first 11) follow Agent{N}_{Name} convention."""
        fm_agents = [a for a in AGENTS if a["name"].startswith("Agent")]
        assert len(fm_agents) == 11
        for i, agent in enumerate(fm_agents):
            assert agent["name"].startswith(f"Agent{i}_")

    def test_orchestrator_exists(self):
        """Orchestrator_Helper is defined."""
        names = [a["name"] for a in AGENTS]
        assert "Orchestrator_Helper" in names


class TestPipelineDefinition:
    def test_pipeline_name(self):
        assert PIPELINE["name"] == "FM_Pipeline"

    def test_pipeline_entity_type(self):
        assert PIPELINE["entityType"] == "pipeline"

    def test_pipeline_has_observations(self):
        assert len(PIPELINE["observations"]) >= 3


class TestRelations:
    def test_relations_not_empty(self):
        assert len(RELATIONS) >= 8

    def test_relation_tuples_have_three_elements(self):
        for rel in RELATIONS:
            assert len(rel) == 3, f"Relation {rel} should be a 3-tuple"

    def test_all_relation_sources_exist(self):
        """All 'from' entities exist in ALL_ENTITIES."""
        valid_names = {e["name"] for e in ALL_ENTITIES}
        for from_name, _, _ in RELATIONS:
            assert from_name in valid_names, f"Unknown source: {from_name}"

    def test_all_relation_targets_exist(self):
        """All 'to' entities exist in ALL_ENTITIES."""
        valid_names = {e["name"] for e in ALL_ENTITIES}
        for _, to_name, _ in RELATIONS:
            assert to_name in valid_names, f"Unknown target: {to_name}"

    def test_relation_types_are_strings(self):
        for _, _, rel_type in RELATIONS:
            assert isinstance(rel_type, str)
            assert rel_type.replace("_", "").isalpha()  # alphanumeric, optional snake_case

    def test_no_self_relations(self):
        for from_name, to_name, _ in RELATIONS:
            assert from_name != to_name, f"Self-relation: {from_name}"


class TestDiscoverProjects:
    def test_discovers_existing_projects(self):
        """Should discover PROJECT_SHPMNT_PROFIT if it exists."""
        projects = discover_projects()
        project_names = [p["name"] for p in projects]
        projects_dir = PROJECT_ROOT / "projects"
        if (projects_dir / "PROJECT_SHPMNT_PROFIT").is_dir():
            assert "PROJECT_SHPMNT_PROFIT" in project_names

    def test_project_entity_type(self):
        projects = discover_projects()
        for p in projects:
            assert p["entityType"] == "project"

    def test_project_has_observations(self):
        projects = discover_projects()
        for p in projects:
            assert len(p["observations"]) >= 1
            assert p["observations"][0].startswith("Directory:")

    def test_discovers_page_id(self):
        """Should include PAGE_ID in observations if file exists."""
        projects = discover_projects()
        for p in projects:
            project_dir = PROJECT_ROOT / "projects" / p["name"]
            page_id_file = project_dir / "CONFLUENCE_PAGE_ID"
            if page_id_file.exists():
                obs_text = " ".join(p["observations"])
                assert "PAGE_ID" in obs_text

    def test_empty_with_no_projects(self, tmp_path):
        """Returns empty list when no PROJECT_* dirs exist."""
        with patch("scripts.seed_memory.PROJECT_ROOT", tmp_path):
            result = discover_projects()
            assert result == []


class TestWriteMemory:
    def test_writes_entities(self, tmp_path):
        memory_file = tmp_path / ".claude-memory" / "memory.jsonl"
        entities = [
            {"name": "TestEntity", "entityType": "test", "observations": ["obs1"]}
        ]
        with patch("scripts.seed_memory.MEMORY_FILE", memory_file):
            added = write_memory(entities, [])
        assert added == 1
        assert memory_file.exists()
        data = json.loads(memory_file.read_text().strip())
        assert data["name"] == "TestEntity"

    def test_writes_relations(self, tmp_path):
        memory_file = tmp_path / ".claude-memory" / "memory.jsonl"
        entities = [
            {"name": "A", "entityType": "test", "observations": []},
            {"name": "B", "entityType": "test", "observations": []},
        ]
        relations = [("A", "B", "relates_to")]
        with patch("scripts.seed_memory.MEMORY_FILE", memory_file):
            write_memory(entities, relations)
        lines = memory_file.read_text().strip().split("\n")
        assert len(lines) == 3  # 2 entities + 1 relation
        rel = json.loads(lines[2])
        assert rel["from"] == "A"
        assert rel["to"] == "B"
        assert rel["relationType"] == "relates_to"

    def test_deduplication_entities(self, tmp_path):
        """Running write_memory twice does not duplicate entities."""
        memory_file = tmp_path / ".claude-memory" / "memory.jsonl"
        entities = [
            {"name": "Dup", "entityType": "test", "observations": ["v1"]}
        ]
        with patch("scripts.seed_memory.MEMORY_FILE", memory_file):
            write_memory(entities, [])
            write_memory(entities, [])
        lines = [l for l in memory_file.read_text().strip().split("\n") if l]
        assert len(lines) == 1

    def test_deduplication_relations(self, tmp_path):
        """Running write_memory twice does not duplicate relations."""
        memory_file = tmp_path / ".claude-memory" / "memory.jsonl"
        entities = [
            {"name": "X", "entityType": "test", "observations": []},
            {"name": "Y", "entityType": "test", "observations": []},
        ]
        relations = [("X", "Y", "links_to")]
        with patch("scripts.seed_memory.MEMORY_FILE", memory_file):
            write_memory(entities, relations)
            write_memory(entities, relations)
        lines = [l for l in memory_file.read_text().strip().split("\n") if l]
        assert len(lines) == 3  # 2 entities + 1 relation (not 6)

    def test_reset_clears_file(self, tmp_path):
        """reset=True deletes existing file before writing."""
        memory_file = tmp_path / ".claude-memory" / "memory.jsonl"
        memory_file.parent.mkdir(parents=True)
        memory_file.write_text('{"name": "Old", "entityType": "old", "observations": []}\n')
        entities = [
            {"name": "New", "entityType": "test", "observations": []}
        ]
        with patch("scripts.seed_memory.MEMORY_FILE", memory_file):
            write_memory(entities, [], reset=True)
        lines = [l for l in memory_file.read_text().strip().split("\n") if l]
        assert len(lines) == 1
        assert json.loads(lines[0])["name"] == "New"

    def test_creates_directory(self, tmp_path):
        """Creates .claude-memory/ directory if it doesn't exist."""
        memory_file = tmp_path / ".claude-memory" / "memory.jsonl"
        with patch("scripts.seed_memory.MEMORY_FILE", memory_file):
            write_memory([], [])
        assert memory_file.parent.exists()

    def test_valid_jsonl_format(self, tmp_path):
        """Every line in output is valid JSON."""
        memory_file = tmp_path / ".claude-memory" / "memory.jsonl"
        entities = AGENTS[:3]
        relations = RELATIONS[:2]
        with patch("scripts.seed_memory.MEMORY_FILE", memory_file):
            write_memory(entities, relations)
        for line in memory_file.read_text().strip().split("\n"):
            json.loads(line)  # Should not raise

    def test_mcp_format_has_type_field(self, tmp_path):
        """MCP server-memory requires 'type' field in every JSONL entry."""
        memory_file = tmp_path / ".claude-memory" / "memory.jsonl"
        entities = AGENTS[:2]
        relations = RELATIONS[:1]
        with patch("scripts.seed_memory.MEMORY_FILE", memory_file):
            write_memory(entities, relations)
        for line in memory_file.read_text().strip().split("\n"):
            obj = json.loads(line)
            assert "type" in obj, f"Missing 'type' field: {obj}"
            assert obj["type"] in ("entity", "relation"), f"Invalid type: {obj['type']}"

    def test_entity_records_have_type_entity(self, tmp_path):
        """Entity records must have type='entity'."""
        memory_file = tmp_path / ".claude-memory" / "memory.jsonl"
        with patch("scripts.seed_memory.MEMORY_FILE", memory_file):
            write_memory(AGENTS[:1], [])
        obj = json.loads(memory_file.read_text().strip())
        assert obj["type"] == "entity"
        assert obj["name"] == AGENTS[0]["name"]

    def test_relation_records_have_type_relation(self, tmp_path):
        """Relation records must have type='relation'."""
        memory_file = tmp_path / ".claude-memory" / "memory.jsonl"
        with patch("scripts.seed_memory.MEMORY_FILE", memory_file):
            write_memory(AGENTS, RELATIONS[:1])
        lines = memory_file.read_text().strip().split("\n")
        # Last line should be the relation
        rel = json.loads(lines[-1])
        assert rel["type"] == "relation"
        assert "from" in rel and "to" in rel
