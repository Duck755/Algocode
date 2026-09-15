"""Domain enumeration types."""

from enum import StrEnum


class Language(StrEnum):
    AUTO = "auto"
    CPP = "cpp"
    PYTHON = "python"


class TaskStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPhase(StrEnum):
    CREATE = "create"
    ANALYZE = "analyze"
    BASELINE = "baseline"
    PLAN = "plan"
    GENERATE_CANDIDATE = "generate_candidate"
    IMPLEMENT = "implement"
    VERIFY = "verify"
    BENCHMARK = "benchmark"
    COMPARE = "compare"
    DECIDE = "decide"
    REPORT = "report"


class CandidateStatus(StrEnum):
    GENERATED = "generated"
    EDITING = "editing"
    FROZEN = "frozen"
    VERIFYING = "verifying"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SELECTED = "selected"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"
    STALE = "stale"


class ExperimentStatus(StrEnum):
    CREATED = "created"
    PREPARED = "prepared"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID = "invalid"
    CANCELLED = "cancelled"


class DecisionOutcome(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INCONCLUSIVE = "inconclusive"


class CorrectnessMode(StrEnum):
    CASES = "cases"
    ORACLE = "oracle"
    STRESS = "stress"
    HYBRID = "hybrid"


class ComparisonMode(StrEnum):
    EXACT = "exact"
    LINE_TRIM = "line-trim"
    TOKEN_NORMALIZED = "token-normalized"
    FLOAT_ABSOLUTE = "float-absolute"
    FLOAT_RELATIVE = "float-relative"
    CHECKER_COMMAND = "checker-command"


class FailureKind(StrEnum):
    OUTPUT_MISMATCH = "output_mismatch"
    PROCESS_CRASH = "process_crash"
    TIMEOUT = "timeout"
    RESOURCE_LIMIT = "resource_limit"
    ORACLE_FAILED = "oracle_failed"
    CHECKER_FAILED = "checker_failed"
    GENERATOR_FAILED = "generator_failed"
    NON_DETERMINISTIC = "non_deterministic"
    PROTECTED_FILE_CHANGED = "protected_file_changed"
    INPUT_INVALID = "input_invalid"
    INCONCLUSIVE = "inconclusive"


class CorrectnessStatus(StrEnum):
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class BenchmarkScope(StrEnum):
    PROCESS = "process"
    STDIN = "stdin"
    FUNCTION = "function"


class BenchmarkMetric(StrEnum):
    WALL_TIME = "wall_time"
    CPU_TIME = "cpu_time"
    PEAK_MEMORY = "peak_memory"
    PAGE_FAULTS = "page_faults"


class BenchmarkStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID = "invalid"
