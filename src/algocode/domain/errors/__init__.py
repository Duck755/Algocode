"""Domain and application errors."""


class AlgocodeError(Exception):
    """Base exception for Algocode errors."""


class DomainError(AlgocodeError):
    """Base exception for invalid domain operations."""


class InvariantViolation(DomainError):
    """Raised when a domain invariant would be violated."""


class ConcurrencyError(DomainError):
    """Raised when an event append violates optimistic concurrency."""


class EventConflictError(DomainError):
    """Raised when an event identity or sequence conflicts with durable history."""


class NotFoundError(DomainError):
    """Raised when an application resource does not exist."""


class BaselineError(AlgocodeError):
    """Raised when a baseline cannot be captured or restored."""


class BaselineBuildFailed(BaselineError):
    """Raised when the baseline build exits unsuccessfully."""


class CorrectnessError(AlgocodeError):
    """Raised when correctness cannot be executed safely."""


class ResourceBusyError(AlgocodeError):
    """Raised when an exclusive resource lock is already held."""


class BenchmarkError(AlgocodeError):
    """Raised when a benchmark cannot be executed or compared safely."""


class DecisionError(AlgocodeError):
    """Raised when a decision or apply operation violates task invariants."""


class ConfigError(AlgocodeError):
    """Raised when configuration is invalid or inconsistent."""


__all__ = [
    "AlgocodeError",
    "BaselineBuildFailed",
    "BaselineError",
    "BenchmarkError",
    "ConcurrencyError",
    "ConfigError",
    "CorrectnessError",
    "DecisionError",
    "DomainError",
    "EventConflictError",
    "NotFoundError",
    "ResourceBusyError",
    "InvariantViolation",
]
