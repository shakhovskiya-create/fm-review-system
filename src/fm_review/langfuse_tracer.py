#!/usr/bin/env python3
"""
Langfuse tracer for Claude Code sessions.

Stop hook script: parses Claude Code JSONL transcript and sends
traces to Langfuse for cost/usage/agent observability.

Usage (called by .claude/hooks/langfuse-trace.sh):
    echo '{"session_id":"...","transcript_path":"..."}' | python3 langfuse_tracer.py

Requires: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL in env.
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# USD per million tokens (Feb 2026)
MODEL_PRICING = {
    "claude-opus-4-6": {
        "input": 15.0,
        "output": 75.0,
        "cache_creation": 18.75,
        "cache_read": 1.50,
    },
    "claude-sonnet-4-6": {
        "input": 3.0,
        "output": 15.0,
        "cache_creation": 3.75,
        "cache_read": 0.30,
    },
}

DEFAULT_PRICING = {"input": 3.0, "output": 15.0, "cache_creation": 3.75, "cache_read": 0.30}

AGENT_NAMES = {
    0: "Creator",
    1: "Architect",
    2: "RoleSimulator",
    3: "Defender",
    4: "QATester",
    5: "TechArchitect",
    6: "Presenter",
    7: "Publisher",
    8: "BPMNDesigner",
}

STATE_DIR = Path(__file__).parent.parent / ".langfuse_state"


@dataclass
class SessionStats:
    session_id: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    tool_calls: dict = field(default_factory=dict)
    turn_count: int = 0
    agent_id: int | None = None
    agent_name: str = "interactive"
    project: str = ""


def get_last_offset(transcript_path: str) -> int:
    """Get the last processed line offset for incremental parsing."""
    state_file = STATE_DIR / (Path(transcript_path).stem + ".offset")
    if state_file.exists():
        try:
            return int(state_file.read_text().strip())
        except (ValueError, OSError):
            return 0
    return 0


def save_offset(transcript_path: str, offset: int):
    """Save the current line offset for next invocation."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_file = STATE_DIR / (Path(transcript_path).stem + ".offset")
    state_file.write_text(str(offset))


def parse_transcript(transcript_path: str, start_offset: int = 0) -> tuple[SessionStats, int]:
    """Parse JSONL transcript from offset. Returns stats and new offset."""
    stats = SessionStats()
    seen_message_ids = set()
    line_count = 0

    with open(transcript_path) as f:
        for i, line in enumerate(f):
            line_count = i + 1
            if i < start_offset:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            entry_type = entry.get("type", "")
            msg = entry.get("message", {})

            # Extract session context from user messages
            if entry_type == "user" and not stats.project:
                content = msg.get("content", "")
                if isinstance(content, str):
                    m = re.search(r"PROJECT_(\w+)", content)
                    if m:
                        stats.project = f"PROJECT_{m.group(1)}"

            # Process assistant messages (LLM responses)
            if entry_type == "assistant" and msg.get("role") == "assistant":
                msg_id = msg.get("id", "")

                # Deduplicate: same message.id appears multiple times (streaming)
                if msg_id and msg_id in seen_message_ids:
                    continue
                if msg_id:
                    seen_message_ids.add(msg_id)

                # Model
                model = msg.get("model", "")
                if model:
                    stats.model = model

                # Token usage
                usage = msg.get("usage", {})
                if usage and usage.get("input_tokens", 0) > 0:
                    stats.input_tokens += usage.get("input_tokens", 0)
                    stats.output_tokens += usage.get("output_tokens", 0)
                    stats.cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
                    stats.cache_read_tokens += usage.get("cache_read_input_tokens", 0)
                    stats.turn_count += 1

                # Tool calls
                content = msg.get("content", [])
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool = block.get("name", "unknown")
                            stats.tool_calls[tool] = stats.tool_calls.get(tool, 0) + 1

    return stats, line_count


def detect_agent(transcript_path: str) -> tuple[int | None, str]:
    """Detect which agent is running from transcript content."""
    try:
        with open(transcript_path) as f:
            # Read first 50KB to detect agent
            sample = f.read(50_000)
    except OSError:
        return None, "interactive"

    # Pattern 1: Agent file references (AGENT_N_NAME)
    m = re.search(r"AGENT_(\d)_(\w+)", sample)
    if m:
        agent_id = int(m.group(1))
        return agent_id, AGENT_NAMES.get(agent_id, m.group(2))

    # Pattern 2: Agent mentions in text
    for aid, name in AGENT_NAMES.items():
        if f"Agent {aid}" in sample or f"agent-{aid}" in sample:
            return aid, name

    return None, "interactive"


def calculate_cost(stats: SessionStats) -> float:
    """Calculate USD cost from token counts."""
    pricing = MODEL_PRICING.get(stats.model, DEFAULT_PRICING)
    cost = (
        stats.input_tokens * pricing["input"] / 1_000_000
        + stats.output_tokens * pricing["output"] / 1_000_000
        + stats.cache_creation_tokens * pricing["cache_creation"] / 1_000_000
        + stats.cache_read_tokens * pricing["cache_read"] / 1_000_000
    )
    return round(cost, 6)


def send_to_langfuse(stats: SessionStats, cost: float, session_id: str):
    """Send trace to Langfuse (SDK v3 API)."""
    from langfuse import get_client

    langfuse = get_client()

    trace_name = (
        f"agent-{stats.agent_id}-{stats.agent_name}"
        if stats.agent_id is not None
        else "interactive"
    )

    tags = []
    if stats.agent_id is not None:
        tags.append(f"agent:{stats.agent_id}")
    else:
        tags.append("interactive")
    if stats.model:
        tags.append(f"model:{stats.model}")
    if stats.project:
        tags.append(f"project:{stats.project}")

    # v3: create root span, then set trace metadata via update_trace()
    pricing = MODEL_PRICING.get(stats.model, DEFAULT_PRICING)

    root = langfuse.start_span(name=trace_name)
    root.update_trace(
        name=trace_name,
        session_id=session_id,
        user_id="shahovsky",
        metadata={
            "project": stats.project,
            "model": stats.model,
            "turn_count": stats.turn_count,
            "tool_calls": stats.tool_calls,
            "cost_usd": cost,
        },
        tags=tags,
    )

    # Generation: aggregate LLM usage
    gen = root.start_generation(
        name="claude-code-session",
        model=stats.model,
        usage_details={
            "input": stats.input_tokens,
            "output": stats.output_tokens,
            "cache_creation_input_tokens": stats.cache_creation_tokens,
            "cache_read_input_tokens": stats.cache_read_tokens,
        },
        cost_details={
            "input": stats.input_tokens * pricing["input"] / 1_000_000,
            "output": stats.output_tokens * pricing["output"] / 1_000_000,
        },
        metadata={"total_cost_usd": cost},
    )
    gen.end()

    # Spans for tool usage
    for tool_name, count in stats.tool_calls.items():
        tool_span = root.start_span(name=f"tool:{tool_name}", metadata={"call_count": count})
        tool_span.end()

    root.end()
    langfuse.flush()


def main():
    """Entry point: read hook input from stdin, parse transcript, send to Langfuse."""
    try:
        # Read hook input
        input_data = json.loads(sys.stdin.read())
        session_id = input_data.get("session_id", "")
        transcript_path = input_data.get("transcript_path", "")

        # Safety: don't run if stop_hook_active (prevents infinite loops)
        if input_data.get("stop_hook_active", False):
            sys.exit(0)

        # Validate
        if not transcript_path or not Path(transcript_path).exists():
            sys.exit(0)
        if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
            sys.exit(0)

        # SDK v3 uses LANGFUSE_HOST, ensure it's set from LANGFUSE_BASE_URL fallback
        if not os.environ.get("LANGFUSE_HOST") and os.environ.get("LANGFUSE_BASE_URL"):
            os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

        # Incremental parsing
        last_offset = get_last_offset(transcript_path)
        stats, new_offset = parse_transcript(transcript_path, last_offset)

        # Nothing new to report
        if stats.turn_count == 0:
            save_offset(transcript_path, new_offset)
            sys.exit(0)

        # Detect agent (only on first parse)
        if last_offset == 0:
            stats.agent_id, stats.agent_name = detect_agent(transcript_path)
        else:
            # Re-detect from full transcript
            stats.agent_id, stats.agent_name = detect_agent(transcript_path)

        # Calculate cost and send
        cost = calculate_cost(stats)
        send_to_langfuse(stats, cost, session_id)

        # Save offset for next invocation
        save_offset(transcript_path, new_offset)

    except Exception:
        # Never block Claude Code
        sys.exit(0)


if __name__ == "__main__":
    main()
