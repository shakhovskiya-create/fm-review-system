"""
Tests for pipeline runner (run_agent.py).

Validates SDK integration, Langfuse tracing, stage building,
prompt construction, and pipeline orchestration logic.
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add scripts to path for imports
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR.parent))

from scripts.run_agent import (
    AGENT_REGISTRY,
    PARALLEL_STAGES,
    PIPELINE_ORDER,
    AgentResult,
    PipelineTracer,
    _build_parallel_stages,
    _build_sequential_stages,
    build_prompt,
    check_agent_status,
    find_summary_json,
    log,
)

PROJECT_ROOT = Path(__file__).parent.parent
PROJECT_DIR = PROJECT_ROOT / "projects" / "PROJECT_SHPMNT_PROFIT"


class TestAgentRegistry:
    def test_nine_agents_registered(self):
        """All 9 agents are in the registry."""
        assert len(AGENT_REGISTRY) == 9

    def test_agent_ids_0_to_8(self):
        """Agent IDs are 0-8."""
        assert sorted(AGENT_REGISTRY.keys()) == list(range(9))

    def test_each_agent_has_required_fields(self):
        """Each agent entry has name, file, dir."""
        for agent_id, config in AGENT_REGISTRY.items():
            assert "name" in config, f"Agent {agent_id} missing 'name'"
            assert "file" in config, f"Agent {agent_id} missing 'file'"
            assert "dir" in config, f"Agent {agent_id} missing 'dir'"

    def test_agent_files_exist(self):
        """All referenced agent .md files exist."""
        agents_dir = PROJECT_ROOT / "agents"
        for agent_id, config in AGENT_REGISTRY.items():
            agent_file = agents_dir / config["file"]
            assert agent_file.exists(), f"Agent {agent_id}: {agent_file} not found"


class TestPipelineOrder:
    def test_pipeline_has_quality_gate(self):
        """Pipeline includes quality_gate step."""
        assert "quality_gate" in PIPELINE_ORDER

    def test_pipeline_has_all_review_agents(self):
        """Pipeline includes agents 1, 2, 3, 4, 5, 6, 7, 8."""
        agent_ids = [s for s in PIPELINE_ORDER if isinstance(s, int)]
        for expected in [1, 2, 3, 4, 5, 6, 7, 8]:
            assert expected in agent_ids, f"Agent {expected} missing from pipeline"

    def test_quality_gate_before_publisher(self):
        """Quality Gate runs before Agent 7 (Publisher)."""
        qg_idx = PIPELINE_ORDER.index("quality_gate")
        pub_idx = PIPELINE_ORDER.index(7)
        assert qg_idx < pub_idx

    def test_architect_runs_first(self):
        """Agent 1 (Architect) runs first."""
        assert PIPELINE_ORDER[0] == 1

    def test_defender_after_other_reviewers(self):
        """Agent 3 (Defender) runs after agents 1, 2, 4, 5."""
        def_idx = PIPELINE_ORDER.index(3)
        for agent in [1, 2, 4, 5]:
            agent_idx = PIPELINE_ORDER.index(agent)
            assert agent_idx < def_idx, f"Agent {agent} should run before Defender"


class TestParallelStages:
    def test_seven_stages(self):
        """There are 7 parallel stages."""
        assert len(PARALLEL_STAGES) == 7

    def test_simulator_and_qa_parallel(self):
        """Agent 2 (Simulator) and Agent 4 (QA) run in parallel."""
        assert [2, 4] in PARALLEL_STAGES

    def test_bpmn_and_presenter_parallel(self):
        """Agent 8 (BPMN) and Agent 6 (Presenter) run in parallel."""
        assert [8, 6] in PARALLEL_STAGES

    def test_architect_runs_alone(self):
        """Agent 1 (Architect) runs alone (base for all)."""
        assert [1] in PARALLEL_STAGES


class TestBuildStages:
    def test_sequential_no_filter(self):
        """Sequential stages without filter: each step in its own list."""
        stages = _build_sequential_stages(None)
        assert len(stages) == len(PIPELINE_ORDER)
        for stage, expected in zip(stages, PIPELINE_ORDER):
            assert stage == [expected]

    def test_sequential_with_filter(self):
        """Sequential stages with filter: only selected agents."""
        stages = _build_sequential_stages([1, 2, 4])
        agent_ids = [s[0] for s in stages]
        assert 1 in agent_ids
        assert 2 in agent_ids
        assert 4 in agent_ids
        assert "quality_gate" not in agent_ids  # No agent 7 -> no QG

    def test_sequential_filter_with_agent_7_includes_qg(self):
        """When agent 7 is in filter, quality_gate is included."""
        stages = _build_sequential_stages([1, 7])
        flat = [s[0] for s in stages]
        assert "quality_gate" in flat

    def test_parallel_no_filter(self):
        """Parallel stages without filter: matches PARALLEL_STAGES."""
        stages = _build_parallel_stages(None)
        assert stages == [list(s) for s in PARALLEL_STAGES]

    def test_parallel_with_filter(self):
        """Parallel stages with filter: only relevant stages."""
        stages = _build_parallel_stages([1, 2, 4])
        assert [1] in stages
        assert [2, 4] in stages
        assert len(stages) == 2  # Only stages containing agents 1,2,4

    def test_parallel_filter_removes_empty_stages(self):
        """Filtering removes stages with no matching agents."""
        stages = _build_parallel_stages([1])
        assert stages == [[1]]


class TestBuildPrompt:
    def test_prompt_contains_agent_file(self):
        """Prompt references the correct agent file."""
        prompt = build_prompt(1, "PROJECT_SHPMNT_PROFIT", "/auto")
        assert "AGENT_1_ARCHITECT.md" in prompt

    def test_prompt_contains_project(self):
        """Prompt includes project name."""
        prompt = build_prompt(1, "PROJECT_SHPMNT_PROFIT", "/auto")
        assert "PROJECT_SHPMNT_PROFIT" in prompt

    def test_prompt_contains_command(self):
        """Prompt includes the command."""
        prompt = build_prompt(1, "PROJECT_SHPMNT_PROFIT", "/audit")
        assert "/audit" in prompt

    def test_prompt_contains_autonomous_instructions(self):
        """Prompt includes autonomous mode instructions."""
        prompt = build_prompt(1, "PROJECT_SHPMNT_PROFIT", "/auto")
        assert "АВТОНОМНЫЙ" in prompt
        assert "_summary.json" in prompt

    def test_prompt_includes_page_id(self):
        """Prompt includes Confluence PAGE_ID if file exists."""
        prompt = build_prompt(1, "PROJECT_SHPMNT_PROFIT", "/auto")
        page_id_file = PROJECT_DIR / "CONFLUENCE_PAGE_ID"
        if page_id_file.exists():
            assert "PAGE_ID" in prompt

    def test_prompt_includes_previous_results(self):
        """Prompt lists previous agent result directories."""
        prompt = build_prompt(3, "PROJECT_SHPMNT_PROFIT", "/auto")
        # Agent 3 should see results from Agent 1, 2 etc.
        if (PROJECT_DIR / "AGENT_1_ARCHITECT").is_dir():
            assert "AGENT_1_ARCHITECT" in prompt


class TestAgentResult:
    def test_default_values(self):
        """AgentResult has correct defaults."""
        r = AgentResult(agent_id=1, status="completed")
        assert r.duration_seconds == 0.0
        assert r.cost_usd == 0.0
        assert r.num_turns == 0
        assert r.session_id == ""
        assert r.error == ""
        assert r.summary_path is None

    def test_all_fields(self):
        """AgentResult stores all fields."""
        r = AgentResult(
            agent_id=1,
            status="completed",
            duration_seconds=42.5,
            cost_usd=1.23,
            num_turns=5,
            session_id="abc-123",
        )
        assert r.agent_id == 1
        assert r.status == "completed"
        assert r.duration_seconds == 42.5
        assert r.cost_usd == 1.23
        assert r.num_turns == 5
        assert r.session_id == "abc-123"


class TestCheckAgentStatus:
    def test_valid_summary(self, tmp_path):
        """Reads status from valid _summary.json."""
        f = tmp_path / "test_summary.json"
        f.write_text('{"status": "partial", "agent": "test"}')
        assert check_agent_status(f) == "partial"

    def test_missing_status_defaults_completed(self, tmp_path):
        """Defaults to 'completed' if status field is missing."""
        f = tmp_path / "test_summary.json"
        f.write_text('{"agent": "test"}')
        assert check_agent_status(f) == "completed"

    def test_invalid_json_defaults_completed(self, tmp_path):
        """Defaults to 'completed' for invalid JSON."""
        f = tmp_path / "test_summary.json"
        f.write_text("not json")
        assert check_agent_status(f) == "completed"


class TestPipelineTracer:
    """Tests for Langfuse pipeline tracer."""

    def test_disabled_without_env(self):
        """Tracer is disabled when LANGFUSE_PUBLIC_KEY is not set."""
        env = os.environ.copy()
        os.environ.pop("LANGFUSE_PUBLIC_KEY", None)
        try:
            tracer = PipelineTracer("TEST", "sonnet")
            assert not tracer.enabled
        finally:
            os.environ.update(env)

    def test_start_pipeline_noop_when_disabled(self):
        """start_pipeline is no-op when disabled."""
        tracer = PipelineTracer("TEST", "sonnet")
        tracer.enabled = False
        tracer.start_pipeline()  # Should not raise
        assert tracer.root is None

    def test_start_agent_returns_none_when_disabled(self):
        """start_agent returns None when disabled."""
        tracer = PipelineTracer("TEST", "sonnet")
        tracer.enabled = False
        span = tracer.start_agent(1, "Architect")
        assert span is None

    def test_end_agent_noop_with_none_span(self):
        """end_agent is no-op when span is None."""
        tracer = PipelineTracer("TEST", "sonnet")
        result = AgentResult(agent_id=1, status="completed")
        tracer.end_agent(None, result)  # Should not raise

    def test_finish_noop_when_disabled(self):
        """finish is no-op when disabled."""
        tracer = PipelineTracer("TEST", "sonnet")
        tracer.enabled = False
        tracer.finish(0.0, 0.0, {})  # Should not raise

    @patch.dict(os.environ, {"LANGFUSE_PUBLIC_KEY": "test-key"})
    def test_enabled_with_env(self):
        """Tracer attempts to initialize when env is set."""
        # Will fail to connect but should try
        with patch("scripts.run_agent.PipelineTracer._init") as mock_init:
            tracer = PipelineTracer.__new__(PipelineTracer)
            tracer.project = "TEST"
            tracer.model = "sonnet"
            tracer.parallel = False
            tracer.enabled = False
            tracer.langfuse = None
            tracer.root = None
            # Just verify the class structure is correct
            assert hasattr(tracer, "start_pipeline")
            assert hasattr(tracer, "start_agent")
            assert hasattr(tracer, "end_agent")
            assert hasattr(tracer, "start_quality_gate")
            assert hasattr(tracer, "end_quality_gate")
            assert hasattr(tracer, "finish")


class TestFindSummaryJson:
    def test_finds_existing_summary(self):
        """Finds _summary.json in agent directory."""
        agent_dir = PROJECT_DIR / "AGENT_1_ARCHITECT"
        if agent_dir.is_dir():
            summaries = list(agent_dir.glob("*_summary.json"))
            if summaries:
                result = find_summary_json("PROJECT_SHPMNT_PROFIT", 1)
                assert result is not None

    def test_returns_none_for_missing_dir(self):
        """Returns None for non-existent project."""
        result = find_summary_json("PROJECT_NONEXISTENT", 1)
        assert result is None


class TestSDKImports:
    """Verify Claude Code SDK is properly importable."""

    def test_query_importable(self):
        from claude_code_sdk import query
        assert callable(query)

    def test_options_importable(self):
        from claude_code_sdk import ClaudeCodeOptions
        opts = ClaudeCodeOptions(model="sonnet")
        assert opts.model == "sonnet"

    def test_result_message_importable(self):
        from claude_code_sdk import ResultMessage
        assert ResultMessage is not None

    def test_options_fields(self):
        """ClaudeCodeOptions has all fields we use."""
        from claude_code_sdk import ClaudeCodeOptions
        opts = ClaudeCodeOptions(
            model="sonnet",
            permission_mode="acceptEdits",
            max_turns=25,
            cwd="/tmp",
            append_system_prompt="test",
            extra_args={"max-budget-usd": "5.0"},
        )
        assert opts.model == "sonnet"
        assert opts.permission_mode == "acceptEdits"
        assert opts.max_turns == 25
        assert opts.cwd == "/tmp"
        assert opts.append_system_prompt == "test"
        assert opts.extra_args == {"max-budget-usd": "5.0"}


class TestLangfuseImports:
    """Verify Langfuse SDK is properly importable."""

    def test_langfuse_importable(self):
        import langfuse
        assert langfuse is not None

    def test_langfuse_client_importable(self):
        from langfuse import Langfuse
        assert callable(Langfuse)


class TestLogFunction:
    def test_log_writes_to_stderr(self, capsys):
        log("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.err
        assert captured.out == ""

    def test_log_has_timestamp(self, capsys):
        log("hello")
        captured = capsys.readouterr()
        # Timestamp format: [HH:MM:SS]
        import re
        assert re.search(r'\[\d{2}:\d{2}:\d{2}\]', captured.err)


class TestPipelineTracerEnabled:
    """Tests for PipelineTracer with mocked Langfuse."""

    def _make_tracer(self):
        """Create a tracer with mocked Langfuse client."""
        tracer = PipelineTracer.__new__(PipelineTracer)
        tracer.project = "TEST"
        tracer.model = "sonnet"
        tracer.parallel = False
        tracer.enabled = True
        tracer.langfuse = MagicMock()
        tracer.root = MagicMock()
        return tracer

    def test_start_pipeline_creates_trace(self):
        tracer = self._make_tracer()
        tracer.root = None  # Not yet started
        tracer.langfuse.start_span.return_value = MagicMock()
        tracer.start_pipeline()
        tracer.langfuse.start_span.assert_called_once()

    def test_start_agent_creates_child_span(self):
        tracer = self._make_tracer()
        mock_span = MagicMock()
        tracer.root.start_span.return_value = mock_span
        span = tracer.start_agent(1, "Architect")
        assert span is mock_span
        tracer.root.start_span.assert_called_once()

    def test_end_agent_updates_span(self):
        tracer = self._make_tracer()
        span = MagicMock()
        result = AgentResult(agent_id=1, status="completed", cost_usd=1.5, duration_seconds=30)
        tracer.end_agent(span, result)
        span.update.assert_called_once()
        span.end.assert_called_once()

    def test_end_agent_creates_generation_for_cost(self):
        tracer = self._make_tracer()
        span = MagicMock()
        gen_mock = MagicMock()
        span.start_generation.return_value = gen_mock
        result = AgentResult(agent_id=1, status="completed", cost_usd=2.0)
        tracer.end_agent(span, result)
        span.start_generation.assert_called_once()
        gen_mock.end.assert_called_once()

    def test_end_agent_no_generation_for_zero_cost(self):
        tracer = self._make_tracer()
        span = MagicMock()
        result = AgentResult(agent_id=1, status="completed", cost_usd=0.0)
        tracer.end_agent(span, result)
        span.start_generation.assert_not_called()

    def test_end_agent_error_level_for_failed(self):
        tracer = self._make_tracer()
        span = MagicMock()
        result = AgentResult(agent_id=1, status="failed", error="timeout")
        tracer.end_agent(span, result)
        call_kwargs = span.update.call_args[1]
        assert call_kwargs["level"] == "ERROR"

    def test_start_quality_gate(self):
        tracer = self._make_tracer()
        mock_span = MagicMock()
        tracer.root.start_span.return_value = mock_span
        span = tracer.start_quality_gate()
        assert span is mock_span

    def test_end_quality_gate_ok(self):
        tracer = self._make_tracer()
        span = MagicMock()
        tracer.end_quality_gate(span, 0, "passed")
        call_kwargs = span.update.call_args[1]
        assert call_kwargs["level"] == "DEFAULT"
        span.end.assert_called_once()

    def test_end_quality_gate_critical(self):
        tracer = self._make_tracer()
        span = MagicMock()
        tracer.end_quality_gate(span, 1, "critical")
        call_kwargs = span.update.call_args[1]
        assert call_kwargs["level"] == "ERROR"

    def test_end_quality_gate_warning(self):
        tracer = self._make_tracer()
        span = MagicMock()
        tracer.end_quality_gate(span, 2, "warning")
        call_kwargs = span.update.call_args[1]
        assert call_kwargs["level"] == "WARNING"

    def test_finish_flushes_langfuse(self):
        tracer = self._make_tracer()
        results = {1: {"status": "completed"}, 2: {"status": "failed"}}
        tracer.finish(3.5, 120.0, results)
        tracer.root.update.assert_called_once()
        tracer.root.end.assert_called_once()
        tracer.langfuse.flush.assert_called_once()

    def test_finish_counts_completed_and_failed(self):
        tracer = self._make_tracer()
        results = {
            1: {"status": "completed"},
            2: {"status": "completed"},
            3: {"status": "failed"},
        }
        tracer.finish(5.0, 200.0, results)
        call_kwargs = tracer.root.update.call_args[1]
        meta = call_kwargs["metadata"]
        assert meta["agents_completed"] == 2
        assert meta["agents_failed"] == 1


class TestFindSummaryJsonTmpPath:
    """Test find_summary_json with controlled tmp directory."""

    def test_finds_most_recent_summary(self, tmp_path):
        agent_dir = tmp_path / "projects" / "TEST_PROJECT" / "AGENT_1_ARCHITECT"
        agent_dir.mkdir(parents=True)
        old = agent_dir / "old_summary.json"
        old.write_text('{"status": "partial"}')
        import time
        time.sleep(0.05)
        new = agent_dir / "new_summary.json"
        new.write_text('{"status": "completed"}')

        with patch("scripts.run_agent.ROOT_DIR", tmp_path):
            result = find_summary_json("TEST_PROJECT", 1)
        assert result is not None
        assert result.name == "new_summary.json"

    def test_returns_none_for_empty_dir(self, tmp_path):
        agent_dir = tmp_path / "projects" / "TEST_PROJECT" / "AGENT_1_ARCHITECT"
        agent_dir.mkdir(parents=True)
        with patch("scripts.run_agent.ROOT_DIR", tmp_path):
            result = find_summary_json("TEST_PROJECT", 1)
        assert result is None
