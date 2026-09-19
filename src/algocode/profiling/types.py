"""Profile evidence types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ProfileSample:
    function: str
    file: str = ""
    line: int = 0
    total_time: float = 0.0
    cumulative_time: float = 0.0
    calls: int = 0


@dataclass(frozen=True, slots=True)
class ProfileReport:
    language: str
    tool: str
    available: bool
    command: tuple[str, ...] = field(default_factory=tuple)
    duration_seconds: float = 0.0
    samples: tuple[ProfileSample, ...] = field(default_factory=tuple)
    error: str = ""

    def summary(self) -> str:
        if not self.available:
            return f"Profiler unavailable ({self.tool}): {self.error or 'no profile was produced'}"
        return (
            f"Profiler {self.tool} collected {len(self.samples)} hotspot entries "
            f"in {self.duration_seconds:.3f}s."
        )

    def text(self, *, limit: int = 20) -> str:
        if not self.available:
            return self.summary()
        lines = [self.summary()]
        lines.append("Top hotspots by cumulative time:")
        for sample in self.samples[:limit]:
            location = sample.file
            if sample.line:
                location = f"{location}:{sample.line}"
            lines.append(
                f"- {sample.function} ({location}) "
                f"cum={sample.cumulative_time:.4f}s "
                f"self={sample.total_time:.4f}s calls={sample.calls}"
            )
        return "\n".join(lines)

    def payload(self, *, limit: int = 20) -> dict[str, object]:
        return {
            "language": self.language,
            "tool": self.tool,
            "available": self.available,
            "command": list(self.command),
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "text": self.text(limit=limit),
            "samples": [
                {
                    "function": sample.function,
                    "file": sample.file,
                    "line": sample.line,
                    "total_time": sample.total_time,
                    "cumulative_time": sample.cumulative_time,
                    "calls": sample.calls,
                }
                for sample in self.samples[:limit]
            ],
        }
