"""Local resource provider for workspace, task, and evidence URIs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from urllib.parse import unquote, urlparse

from algocode.domain.errors import NotFoundError
from algocode.domain.model import ArtifactRef, BenchmarkStatus
from algocode.resources.types import ResourceResult

MAX_RESOURCE_BYTES = 200_000


class LocalResourceProvider:
    """Resolve P0 resource URIs from local services and storage."""

    def __init__(
        self,
        *,
        artifact_store,
        task_service,
        baseline_service,
        candidate_service,
        benchmark_service,
    ) -> None:
        self._artifact_store = artifact_store
        self._task_service = task_service
        self._baseline_service = baseline_service
        self._candidate_service = candidate_service
        self._benchmark_service = benchmark_service

    async def resolve(
        self,
        uri: str,
        mode: str = "summary",
        *,
        workspace: str | Path | None = None,
    ) -> ResourceResult:
        if mode not in {"summary", "content"}:
            raise ValueError("resource mode must be summary or content")
        parsed = urlparse(uri)
        if parsed.scheme == "artifact":
            result = await self._resolve_artifact(parsed, uri)
        elif parsed.scheme == "resource":
            result = await self._resolve_resource(parsed, uri)
        elif parsed.scheme == "repo":
            if workspace is None:
                raise ValueError("repo:// resources require a workspace")
            result = await self._resolve_repo(parsed, uri, Path(workspace))
        else:
            raise ValueError(f"unsupported resource URI scheme: {parsed.scheme}")
        if mode == "summary" and result.content is not None:
            return ResourceResult(
                uri=result.uri,
                version=result.version,
                type=result.type,
                title=result.title,
                summary=result.summary,
                hash=result.hash,
                trust=result.trust,
                artifact_refs=result.artifact_refs,
                content=None,
                metadata=result.metadata,
            )
        return result

    async def _resolve_artifact(self, parsed, uri: str) -> ResourceResult:
        if parsed.netloc != "sha256":
            raise ValueError("artifact URI must be artifact://sha256/<digest>")
        digest = parsed.path.strip("/")
        ref = ArtifactRef(uri=f"artifact://sha256/{digest}", sha256=digest)
        description = self._artifact_store.description(ref)
        raw = (await self._artifact_store.read_bytes(ref))[:MAX_RESOURCE_BYTES]
        content = raw.decode(errors="replace")
        return ResourceResult(
            uri=uri,
            version=digest,
            type=str(description.get("mime_type", "application/octet-stream")),
            title=str(description.get("kind", "artifact")),
            summary=f"{description.get('kind', 'artifact')} artifact ({len(raw)} bytes)",
            hash=digest,
            trust="verified",
            artifact_refs=(uri,),
            content=content,
            metadata={
                "kind": description.get("kind"),
                "mime_type": description.get("mime_type"),
                "size": description.get("size"),
                "metadata": description.get("metadata", {}),
                "truncated": int(description.get("size", 0)) > MAX_RESOURCE_BYTES,
            },
        )

    async def _resolve_resource(self, parsed, uri: str) -> ResourceResult:
        parts = ([parsed.netloc] if parsed.netloc else []) + [
            part for part in parsed.path.split("/") if part
        ]
        if len(parts) == 3 and parts[0] == "task" and parts[2] == "baseline":
            task_id = parts[1]
            await self._task_service.get_task(task_id)
            baseline = await self._baseline_service.get_for_task(task_id)
            if baseline is None:
                raise NotFoundError(f"baseline for task {task_id} was not found")
            content = _json_content(_jsonable(asdict(baseline)))
            return ResourceResult(
                uri=uri,
                version=baseline.snapshot_hash,
                type="baseline",
                title=f"Baseline {baseline.id}",
                summary=(
                    f"baseline {baseline.id}, revision {baseline.revision.value}, "
                    f"snapshot {baseline.snapshot_hash}"
                ),
                hash=baseline.snapshot_hash,
                trust="verified",
                artifact_refs=tuple(
                    ref.uri
                    for ref in (
                        baseline.build_result_ref,
                        baseline.correctness_result_ref,
                        baseline.benchmark_result_ref,
                    )
                    if ref is not None
                ),
                content=content,
                metadata={"task_id": task_id, "baseline_id": baseline.id},
            )
        if len(parts) == 4 and parts[0] == "task" and parts[2] == "candidate":
            task_id, candidate_id = parts[1], parts[3]
            candidate = await self._candidate_service.get(candidate_id)
            if str(candidate.task_id) != task_id:
                raise NotFoundError(f"candidate {candidate_id} does not belong to task {task_id}")
            content = _json_content(_jsonable(asdict(candidate)))
            return ResourceResult(
                uri=uri,
                version=candidate.patch_hash or candidate.base_snapshot_hash,
                type="candidate",
                title=f"Candidate {candidate.id}",
                summary=(
                    f"candidate {candidate.id}, status {candidate.status.value}, "
                    f"workspace {candidate.workspace_ref}"
                ),
                hash=candidate.patch_hash or candidate.base_snapshot_hash,
                trust="verified",
                content=content,
                metadata={"task_id": task_id, "candidate_id": candidate.id},
            )
        if len(parts) == 3 and parts[0] == "experiment" and parts[2] == "benchmark":
            experiment_id = parts[1]
            run = await self._benchmark_service.get(experiment_id)
            result = await self._benchmark_service.read_result(run)
            comparison = await self._benchmark_service.read_comparison(run)
            payload = {
                "experiment": _jsonable(asdict(run)),
                "result": result,
                "comparison": comparison,
            }
            return ResourceResult(
                uri=uri,
                version=run.comparison_key,
                type="benchmark",
                title=f"Benchmark {run.id}",
                summary=(
                    f"benchmark {run.id}, target {run.target_kind}:{run.target_id}, "
                    f"status {run.status.value}"
                ),
                hash=run.comparison_key,
                trust="verified",
                artifact_refs=tuple(
                    ref.uri for ref in (run.result_ref, run.comparison_ref) if ref is not None
                ),
                content=_json_content(payload),
                metadata={
                    "experiment_id": run.id,
                    "task_id": str(run.task_id),
                    "status": run.status.value,
                    "completed": run.status is BenchmarkStatus.COMPLETED,
                },
            )
        raise ValueError(f"unsupported resource URI: {uri}")

    async def _resolve_repo(
        self,
        parsed,
        uri: str,
        workspace: Path,
    ) -> ResourceResult:
        relative = unquote(f"{parsed.netloc}{parsed.path}").lstrip("/")
        if not relative:
            raise ValueError("repo:// URI must include a path")
        root = workspace.resolve()
        target = (root / relative).resolve()
        if not target.is_relative_to(root):
            raise ValueError("repo path escapes the workspace")
        if not target.is_file():
            raise NotFoundError(f"repository path was not found: {relative}")
        raw = target.read_bytes()
        content_bytes = raw[:MAX_RESOURCE_BYTES]
        digest = hashlib.sha256(raw).hexdigest()
        content = content_bytes.decode(errors="replace")
        return ResourceResult(
            uri=uri,
            version=digest,
            type="repository-file",
            title=relative,
            summary=f"{relative} ({len(raw)} bytes)",
            hash=digest,
            trust="untrusted",
            content=content,
            metadata={
                "path": relative,
                "size": len(raw),
                "truncated": len(raw) > MAX_RESOURCE_BYTES,
            },
        )


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def _json_content(payload: object) -> str:
    return json.dumps(_jsonable(payload), ensure_ascii=False, indent=2, sort_keys=True)
