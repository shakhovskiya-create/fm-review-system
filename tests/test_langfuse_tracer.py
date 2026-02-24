import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

import pytest

from fm_review.langfuse_tracer import (
    get_last_offset,
    save_offset,
    parse_transcript,
    detect_agent,
    calculate_cost,
    send_to_langfuse,
    SessionStats,
    main,
    STATE_DIR,
    DEFAULT_PRICING
)


@pytest.fixture
def tmp_state_dir(tmp_path):
    with patch("fm_review.langfuse_tracer.STATE_DIR", tmp_path / ".langfuse_state"):
        yield tmp_path / ".langfuse_state"


class TestOffsetManagement:
    def test_get_last_offset_missing(self, tmp_state_dir):
        assert get_last_offset("dummy.jsonl") == 0

    def test_save_and_get_offset(self, tmp_state_dir):
        save_offset("dummy.jsonl", 42)
        assert get_last_offset("dummy.jsonl") == 42
        assert (tmp_state_dir / "dummy.offset").exists()

    def test_get_last_offset_invalid(self, tmp_state_dir):
        tmp_state_dir.mkdir(parents=True, exist_ok=True)
        (tmp_state_dir / "dummy.offset").write_text("invalid")
        assert get_last_offset("dummy.jsonl") == 0


class TestDetectAgent:
    def test_detect_agent_from_file_reference(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("Some text reading AGENT_7_PUBLISHER...")
        aid, name = detect_agent(str(transcript))
        assert aid == 7
        assert name == "Publisher"

    def test_detect_agent_from_mentions(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("Hello I am Agent 3 and I do things")
        aid, name = detect_agent(str(transcript))
        assert aid == 3
        assert name == "Defender"

    def test_detect_agent_interactive(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("Just a normal conversation")
        aid, name = detect_agent(str(transcript))
        assert aid is None
        assert name == "interactive"

    def test_detect_agent_missing_file(self):
        aid, name = detect_agent("nonexistent.jsonl")
        assert aid is None
        assert name == "interactive"


class TestParseTranscript:
    def test_parse_transcript_empty(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("")
        stats, offset = parse_transcript(str(transcript))
        assert offset == 0
        assert stats.turn_count == 0

    def test_parse_transcript_user_project(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        entry = {"type": "user", "message": {"content": "Hello PROJECT_SHPMNT_PROFIT"}}
        transcript.write_text(json.dumps(entry) + "\n")
        stats, offset = parse_transcript(str(transcript))
        assert offset == 1
        assert stats.project == "PROJECT_SHPMNT_PROFIT"

    def test_parse_transcript_assistant_usage(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        entry = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "id": "msg_1",
                "model": "claude-sonnet-4-6",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "cache_creation_input_tokens": 10,
                    "cache_read_input_tokens": 5
                },
                "content": [
                    {"type": "tool_use", "name": "Bash"},
                    {"type": "tool_use", "name": "Read"}
                ]
            }
        }
        transcript.write_text(json.dumps(entry) + "\n")
        stats, offset = parse_transcript(str(transcript))
        assert offset == 1
        assert stats.input_tokens == 100
        assert stats.output_tokens == 50
        assert stats.cache_creation_tokens == 10
        assert stats.cache_read_tokens == 5
        assert stats.turn_count == 1
        assert stats.model == "claude-sonnet-4-6"
        assert stats.tool_calls == {"Bash": 1, "Read": 1}

    def test_parse_transcript_deduplicates_messages(self, tmp_path):
        transcript = tmp_path / "t.jsonl"
        entry = {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "id": "msg_1",
                "usage": {"input_tokens": 100}
            }
        }
        # Write same message ID twice
        transcript.write_text(json.dumps(entry) + "\n" + json.dumps(entry) + "\n")
        stats, offset = parse_transcript(str(transcript))
        assert offset == 2
        assert stats.input_tokens == 100
        assert stats.turn_count == 1


class TestCalculateCost:
    def test_calculate_cost_sonnet(self):
        stats = SessionStats(
            model="claude-sonnet-4-6",
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_creation_tokens=1_000_000,
            cache_read_tokens=1_000_000
        )
        cost = calculate_cost(stats)
        assert cost == 3.0 + 15.0 + 3.75 + 0.30

    def test_calculate_cost_default(self):
        stats = SessionStats(
            model="unknown-model",
            input_tokens=1_000_000,
            output_tokens=0,
            cache_creation_tokens=0,
            cache_read_tokens=0
        )
        cost = calculate_cost(stats)
        assert cost == DEFAULT_PRICING["input"]


class TestSendToLangfuse:
    @patch("langfuse.get_client")
    def test_send_to_langfuse(self, mock_get_client):
        mock_client = MagicMock()
        mock_root = MagicMock()
        mock_gen = MagicMock()
        mock_tool_span = MagicMock()

        mock_get_client.return_value = mock_client
        mock_client.start_span.return_value = mock_root
        mock_root.start_generation.return_value = mock_gen
        mock_root.start_span.return_value = mock_tool_span

        stats = SessionStats(
            agent_id=1,
            agent_name="Architect",
            model="claude-sonnet-4-6",
            project="PROJECT_TEST",
            input_tokens=100,
            tool_calls={"Read": 2}
        )

        send_to_langfuse(stats, 0.05, "sess_123")

        mock_get_client.assert_called_once()
        mock_client.start_span.assert_called_with(name="agent-1-Architect")
        mock_root.update_trace.assert_called_once()
        mock_root.start_generation.assert_called_once()
        mock_root.start_span.assert_called_with(name="tool:Read", metadata={"call_count": 2})
        mock_root.end.assert_called_once()
        mock_client.flush.assert_called_once()

    @patch("langfuse.get_client")
    def test_send_to_langfuse_interactive(self, mock_get_client):
        mock_client = MagicMock()
        mock_root = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.start_span.return_value = mock_root

        stats = SessionStats(agent_id=None)
        send_to_langfuse(stats, 0.0, "sess_123")

        mock_client.start_span.assert_called_with(name="interactive")


class TestMain:
    @patch("sys.stdin.read")
    @patch("sys.exit")
    def test_main_stop_hook_active(self, mock_exit, mock_read):
        mock_read.return_value = json.dumps({"stop_hook_active": True})
        main()
        mock_exit.assert_called_with(0)

    @patch("sys.stdin.read")
    @patch("sys.exit")
    def test_main_missing_transcript(self, mock_exit, mock_read):
        mock_read.return_value = json.dumps({"transcript_path": ""})
        main()
        mock_exit.assert_called_with(0)

    @patch("sys.stdin.read")
    @patch("sys.exit")
    @patch("os.environ.get")
    def test_main_missing_langfuse_key(self, mock_env_get, mock_exit, mock_read, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("")
        mock_read.return_value = json.dumps({"transcript_path": str(transcript)})
        mock_env_get.return_value = None
        main()
        mock_exit.assert_called_with(0)

    @patch("sys.stdin.read")
    @patch("sys.exit")
    @patch("os.environ.get")
    @patch("fm_review.langfuse_tracer.parse_transcript")
    @patch("fm_review.langfuse_tracer.save_offset")
    def test_main_no_turns(self, mock_save, mock_parse, mock_env_get, mock_exit, mock_read, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("")
        mock_read.return_value = json.dumps({"transcript_path": str(transcript)})
        mock_env_get.return_value = "key"
        
        stats = SessionStats(turn_count=0)
        mock_parse.return_value = (stats, 5)
        
        main()
        
        mock_save.assert_called_with(str(transcript), 5)
        mock_exit.assert_called_with(0)

    @patch("sys.stdin.read")
    @patch.dict("os.environ", {"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_BASE_URL": "http://lf"})
    @patch("fm_review.langfuse_tracer.parse_transcript")
    @patch("fm_review.langfuse_tracer.detect_agent")
    @patch("fm_review.langfuse_tracer.calculate_cost")
    @patch("fm_review.langfuse_tracer.send_to_langfuse")
    @patch("fm_review.langfuse_tracer.save_offset")
    @patch("fm_review.langfuse_tracer.get_last_offset")
    def test_main_success(self, mock_get_offset, mock_save, mock_send, mock_calc, mock_detect, mock_parse, mock_read, tmp_path):
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("")
        mock_read.return_value = json.dumps({"transcript_path": str(transcript), "session_id": "sess_1"})

        mock_get_offset.return_value = 0
        stats = SessionStats(turn_count=1)
        mock_parse.return_value = (stats, 5)
        mock_detect.return_value = (1, "Architect")
        mock_calc.return_value = 0.5

        main()

        mock_detect.assert_called_with(str(transcript))
        mock_send.assert_called_with(stats, 0.5, "sess_1")
        mock_save.assert_called_with(str(transcript), 5)

    @patch("sys.stdin.read", side_effect=Exception("Crash"))
    @patch("sys.exit")
    def test_main_exception_handled(self, mock_exit, mock_read):
        main()
        mock_exit.assert_called_with(0)
