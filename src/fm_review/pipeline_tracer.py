"""
Pipeline tracer and agent result model.

PipelineTracer wraps Langfuse for optional observability.
AgentResult is the standard return type from agent execution.
"""
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AgentResult:
    agent_id: int
    status: str  # completed | partial | failed | dry_run | timeout | budget_exceeded | injection_detected
    summary_path: Path | None = None
    duration_seconds: float = 0.0
    exit_code: int = 0
    cost_usd: float = 0.0
    num_turns: int = 0
    session_id: str = ""
    error: str = ""


class PipelineTracer:
    """Optional Langfuse tracing for pipeline runs.

    Creates a root trace for the pipeline with child spans for each agent.
    Disabled silently if LANGFUSE_PUBLIC_KEY is not set.
    """

    def __init__(self, project: str, model: str, parallel: bool = False):
        self.project = project
        self.model = model
        self.parallel = parallel
        self.enabled = False
        self.langfuse = None
        self.root = None
        self._init()

    def _init(self):
        if not os.environ.get("LANGFUSE_PUBLIC_KEY"):
            return
        # Ensure LANGFUSE_HOST is set (SDK v3 uses HOST, not BASE_URL)
        if not os.environ.get("LANGFUSE_HOST") and os.environ.get("LANGFUSE_BASE_URL"):
            os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]
        try:
            from langfuse import get_client
            self.langfuse = get_client()
            self.enabled = True
        except ImportError:
            pass

    def start_pipeline(self) -> None:
        """Create root trace for the pipeline run."""
        if not self.enabled:
            return
        mode = "parallel" if self.parallel else "sequential"
        self.root = self.langfuse.start_span(name=f"pipeline-{self.project}")
        self.root.update_trace(
            name=f"pipeline-{self.project}",
            user_id=os.environ.get("USER", "unknown"),
            metadata={
                "project": self.project,
                "model": self.model,
                "mode": mode,
            },
            tags=[f"project:{self.project}", f"model:{self.model}", "pipeline", mode],
        )

    def start_agent(self, agent_id: int, agent_name: str):
        """Create a child span for an agent run. Returns span or None."""
        if not self.enabled or not self.root:
            return None
        span = self.root.start_span(
            name=f"agent-{agent_id}-{agent_name}",
            metadata={"agent_id": agent_id, "agent_name": agent_name},
        )
        return span

    def end_agent(self, span, result: AgentResult) -> None:
        """End an agent span with result metadata."""
        if not span:
            return
        status_level = "ERROR" if result.status in ("failed", "timeout", "budget_exceeded") else "DEFAULT"
        span.update(
            metadata={
                "status": result.status,
                "cost_usd": result.cost_usd,
                "duration_seconds": result.duration_seconds,
                "num_turns": result.num_turns,
                "session_id": result.session_id,
                "error": result.error or None,
            },
            level=status_level,
        )
        # Add generation for cost tracking
        if result.cost_usd > 0:
            gen = span.start_generation(
                name=f"agent-{result.agent_id}-llm",
                model=self.model,
                metadata={"total_cost_usd": result.cost_usd},
            )
            gen.end()
        span.end()

    def start_quality_gate(self):
        """Create a child span for Quality Gate."""
        if not self.enabled or not self.root:
            return None
        return self.root.start_span(
            name="quality-gate",
            metadata={"type": "quality_gate"},
        )

    def end_quality_gate(self, span, exit_code: int, status: str) -> None:
        """End Quality Gate span."""
        if not span:
            return
        level = "ERROR" if exit_code == 1 else "WARNING" if exit_code == 2 else "DEFAULT"
        span.update(
            metadata={"exit_code": exit_code, "status": status},
            level=level,
        )
        span.end()

    def finish(self, total_cost: float, total_duration: float, results: dict) -> None:
        """End root trace and flush."""
        if not self.enabled or not self.root:
            return
        completed = sum(1 for r in results.values() if r.get("status") == "completed")
        failed = sum(1 for r in results.values() if r.get("status") == "failed")
        self.root.update(
            metadata={
                "total_cost_usd": total_cost,
                "total_duration_seconds": total_duration,
                "agents_completed": completed,
                "agents_failed": failed,
            },
        )
        self.root.end()
        try:
            self.langfuse.flush()
        except Exception:
            pass
