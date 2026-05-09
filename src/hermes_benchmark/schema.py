"""Result schema for Hermes Swarm Benchmark.

A single source of truth for the JSON written by sub-agents and consumed by
the report renderer. Keep this small and stable — anything else lives in
metadata fields.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class AgentResult:
    """Result for a single (agent, test) pair, written by the sub-agent."""

    agent: str
    test: str
    started_at: float
    completed_at: float
    wall_s: float
    passed: bool
    output: str = ""
    error: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "AgentResult":
        return cls(
            agent=str(d["agent"]),
            test=str(d["test"]),
            started_at=float(d["started_at"]),
            completed_at=float(d["completed_at"]),
            wall_s=float(d["wall_s"]),
            passed=bool(d["passed"]),
            output=str(d.get("output", "")),
            error=d.get("error"),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TestResult:
    """Aggregated result across all agents for a single test."""

    # Tell pytest not to try to collect this dataclass as a test class.
    __test__ = False

    name: str
    agents: list[AgentResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.agents)

    @property
    def passed(self) -> int:
        return sum(1 for a in self.agents if a.passed)

    @property
    def wall_s(self) -> float:
        if not self.agents:
            return 0.0
        return max(a.completed_at for a in self.agents) - min(
            a.started_at for a in self.agents
        )

    @property
    def throughput(self) -> float:
        return self.passed / self.wall_s if self.wall_s > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "total": self.total,
            "passed": self.passed,
            "wall_s": round(self.wall_s, 3),
            "throughput": round(self.throughput, 3),
            "agents": [a.to_dict() for a in self.agents],
        }


@dataclass
class BenchmarkReport:
    """Top-level report: a list of TestResults plus run metadata."""

    tests: list[TestResult] = field(default_factory=list)
    agent_count: int = 0
    orchestrator: str = "none"
    model: Optional[str] = None

    @property
    def grand_wall_s(self) -> float:
        return max((t.wall_s for t in self.tests), default=0.0)

    @property
    def grand_passed(self) -> int:
        return sum(t.passed for t in self.tests)

    @property
    def grand_total(self) -> int:
        return sum(t.total for t in self.tests)

    def to_dict(self) -> dict:
        return {
            "agent_count": self.agent_count,
            "orchestrator": self.orchestrator,
            "model": self.model,
            "grand_wall_s": round(self.grand_wall_s, 3),
            "grand_passed": self.grand_passed,
            "grand_total": self.grand_total,
            "tests": [t.to_dict() for t in self.tests],
        }
