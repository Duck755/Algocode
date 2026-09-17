"""Git-backed repository and workspace operations."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from algocode.domain.model import GitRevision
from algocode.workspace.types import ApplyResult, Workspace, WorkspaceKind


class GitError(RuntimeError):
    """Raised when a Git operation cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class CommandOutput:
    command: tuple[str, ...]
    exit_code: int
    stdout: bytes
    stderr: bytes


@dataclass(frozen=True, slots=True)
class UntrackedFile:
    relative_path: str
    content: bytes
    is_symlink: bool = False


@dataclass(frozen=True, slots=True)
class RepositorySnapshot:
    revision: str
    patch: bytes
    untracked: tuple[UntrackedFile, ...]
    snapshot_hash: str


class GitRepository:
    """Execute Git operations against one repository root."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    @classmethod
    async def discover(cls, path: str | Path) -> GitRepository:
        candidate = Path(path).resolve()
        output = await _run_git(("rev-parse", "--show-toplevel"), cwd=candidate)
        if output.exit_code != 0:
            message = output.stderr.decode(errors="replace").strip()
            raise GitError(message or f"{candidate} is not inside a Git repository")
        return cls(Path(output.stdout.decode(errors="replace").strip()))

    @classmethod
    async def initialize(cls, path: str | Path) -> GitRepository:
        root = Path(path).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        output = await _run_git(("init", "-b", "main"), cwd=root)
        if output.exit_code != 0:
            raise GitError(output.stderr.decode(errors="replace").strip())
        return cls(root)

    async def has_head(self) -> bool:
        output = await _run_git(("rev-parse", "--verify", "HEAD"), cwd=self.root)
        return output.exit_code == 0

    async def commit_all(
        self,
        message: str,
        *,
        author_name: str = "Algocode",
        author_email: str = "algocode@local",
    ) -> bool:
        status = await _run_git(("status", "--porcelain"), cwd=self.root)
        if status.exit_code != 0:
            raise GitError(status.stderr.decode(errors="replace").strip())
        if not status.stdout and await self.has_head():
            return False
        add = await _run_git(("add", "-A"), cwd=self.root)
        if add.exit_code != 0:
            raise GitError(add.stderr.decode(errors="replace").strip())
        commit = await _run_git(
            (
                "-c",
                f"user.name={author_name}",
                "-c",
                f"user.email={author_email}",
                "commit",
                "--allow-empty",
                "-m",
                message,
            ),
            cwd=self.root,
        )
        if commit.exit_code != 0:
            raise GitError(commit.stderr.decode(errors="replace").strip())
        return True

    async def head_revision(self) -> str:
        output = await _run_git(("rev-parse", "HEAD"), cwd=self.root)
        if output.exit_code != 0:
            raise GitError(output.stderr.decode(errors="replace").strip())
        return output.stdout.decode(errors="replace").strip()

    async def capture_snapshot(self, path: Path | None = None) -> RepositorySnapshot:
        root = (path or self.root).resolve()
        revision = await self.head_revision_for(root)
        patch_output = await _run_git(("diff", "HEAD", "--binary", "--no-ext-diff"), cwd=root)
        if patch_output.exit_code != 0:
            raise GitError(patch_output.stderr.decode(errors="replace").strip())
        untracked = await self._capture_untracked(root)
        return RepositorySnapshot(
            revision=revision,
            patch=patch_output.stdout,
            untracked=untracked,
            snapshot_hash=_snapshot_hash(revision, patch_output.stdout, untracked),
        )

    async def changed_files(self, path: Path | None = None) -> tuple[str, ...]:
        root = (path or self.root).resolve()
        tracked = await _run_git(
            ("diff", "--name-only", "-z", "HEAD"),
            cwd=root,
        )
        untracked = await _run_git(
            ("ls-files", "--others", "--exclude-standard", "-z"),
            cwd=root,
        )
        if tracked.exit_code != 0 or untracked.exit_code != 0:
            stderr = tracked.stderr if tracked.exit_code != 0 else untracked.stderr
            raise GitError(stderr.decode(errors="replace").strip())
        names = {
            os.fsdecode(name)
            for output in (tracked.stdout, untracked.stdout)
            for name in output.split(b"\0")
            if name
        }
        return tuple(sorted(names))

    async def head_revision_for(self, path: Path) -> str:
        output = await _run_git(("rev-parse", "HEAD"), cwd=path)
        if output.exit_code != 0:
            raise GitError(output.stderr.decode(errors="replace").strip())
        return output.stdout.decode(errors="replace").strip()

    async def create_worktree(self, destination: Path, revision: str) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise GitError(f"worktree destination already exists: {destination}")
        output = await _run_git(
            ("worktree", "add", "--detach", "--force", str(destination), revision),
            cwd=self.root,
        )
        if output.exit_code != 0:
            raise GitError(output.stderr.decode(errors="replace").strip())

    async def apply_patch(
        self,
        patch: bytes,
        *,
        check_only: bool = False,
        reverse: bool = False,
    ) -> CommandOutput:
        args = ["apply", "--binary", "--whitespace=nowarn"]
        if check_only:
            args.append("--check")
        if reverse:
            args.append("--reverse")
        args.append("-")
        return await _run_git(tuple(args), cwd=self.root, input_bytes=patch)

    async def materialize_snapshot(
        self,
        destination: Path,
        snapshot: RepositorySnapshot,
    ) -> tuple[str, ...]:
        if snapshot.patch:
            output = await _run_git(
                ("apply", "--binary", "--whitespace=nowarn", "-"),
                cwd=destination,
                input_bytes=snapshot.patch,
            )
            if output.exit_code != 0:
                raise GitError(output.stderr.decode(errors="replace").strip())
        return _materialize_untracked(destination, snapshot.untracked)

    async def _capture_untracked(self, root: Path) -> tuple[UntrackedFile, ...]:
        output = await _run_git(
            ("ls-files", "--others", "--exclude-standard", "-z"),
            cwd=root,
        )
        if output.exit_code != 0:
            raise GitError(output.stderr.decode(errors="replace").strip())
        names = sorted(os.fsdecode(name) for name in output.stdout.split(b"\0") if name)
        files: list[UntrackedFile] = []
        for relative_path in names:
            source = _safe_join(root, relative_path)
            if source.is_symlink():
                files.append(
                    UntrackedFile(
                        relative_path=relative_path,
                        content=os.fsencode(os.readlink(source)),
                        is_symlink=True,
                    )
                )
            elif source.is_file():
                files.append(
                    UntrackedFile(
                        relative_path=relative_path,
                        content=source.read_bytes(),
                    )
                )
        return tuple(files)


class GitWorkspaceManager:
    """Create isolated baseline and candidate workspaces from Git snapshots."""

    def __init__(self, repository: GitRepository, data_dir: str | Path) -> None:
        self.repository = repository
        self.data_dir = Path(data_dir).expanduser()
        self.worktrees_dir = self.data_dir / "worktrees"
        self.rollback_dir = self.data_dir / "rollbacks"

    async def prepare_baseline(self, task_id: str, base_revision: str) -> Workspace:
        return await self._create_workspace(
            task_id=task_id,
            base_revision=base_revision,
            kind=WorkspaceKind.BASELINE,
        )

    async def create_candidate(
        self,
        task_id: str,
        base_revision: str,
        source_workspace: Path | None = None,
    ) -> Workspace:
        return await self._create_workspace(
            task_id=task_id,
            base_revision=base_revision,
            kind=WorkspaceKind.CANDIDATE,
            source_workspace=source_workspace,
        )

    async def freeze(self, workspace: Workspace) -> str:
        snapshot = await self.repository.capture_snapshot(workspace.path)
        return snapshot.snapshot_hash

    async def diff(self, workspace: Workspace) -> str:
        snapshot = await self.repository.capture_snapshot(workspace.path)
        untracked = "\n".join(f"untracked: {item.relative_path}" for item in snapshot.untracked)
        patch = snapshot.patch.decode(errors="replace")
        return f"{patch}\n{untracked}".strip()

    async def apply(self, workspace: Workspace) -> ApplyResult:
        if workspace.kind is not WorkspaceKind.CANDIDATE:
            raise GitError("only candidate workspaces can be applied")
        current_revision = await self.repository.head_revision()
        if current_revision != workspace.base_revision.value:
            raise GitError("candidate is stale because the user repository revision changed")
        snapshot = await self.repository.capture_snapshot(workspace.path)
        _validate_untracked_targets(self.repository.root, snapshot.untracked)
        if snapshot.patch:
            output = await _run_git(
                ("apply", "--binary", "--whitespace=nowarn", "-"),
                cwd=self.repository.root,
                input_bytes=snapshot.patch,
            )
            if output.exit_code != 0:
                raise GitError(output.stderr.decode(errors="replace").strip())
        try:
            created_paths = _materialize_untracked(self.repository.root, snapshot.untracked)
        except Exception:
            if snapshot.patch:
                await _run_git(
                    ("apply", "--reverse", "--binary", "--whitespace=nowarn", "-"),
                    cwd=self.repository.root,
                    input_bytes=snapshot.patch,
                )
            raise
        applied_snapshot = await self.repository.capture_snapshot(self.repository.root)
        self.rollback_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "workspace_id": workspace.id,
            "base_revision": workspace.base_revision.value,
            "patch_base64": base64.b64encode(snapshot.patch).decode("ascii"),
            "created_paths": list(created_paths),
            "applied_snapshot_hash": applied_snapshot.snapshot_hash,
        }
        self._manifest_path(workspace.id).write_text(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True),
            encoding="utf-8",
        )
        return ApplyResult(
            workspace_id=workspace.id,
            applied=True,
            reverse_patch_available=True,
        )

    async def rollback(self, workspace: Workspace) -> None:
        manifest_path = self._manifest_path(workspace.id)
        if not manifest_path.exists():
            raise GitError(f"no rollback manifest exists for workspace {workspace.id}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        current = await self.repository.capture_snapshot(self.repository.root)
        if current.snapshot_hash != manifest["applied_snapshot_hash"]:
            raise GitError("repository changed after apply; automatic rollback is unsafe")
        patch = base64.b64decode(manifest["patch_base64"])
        if patch:
            output = await _run_git(
                ("apply", "--reverse", "--binary", "--whitespace=nowarn", "-"),
                cwd=self.repository.root,
                input_bytes=patch,
            )
            if output.exit_code != 0:
                raise GitError(output.stderr.decode(errors="replace").strip())
        for relative_path in manifest["created_paths"]:
            target = _safe_join(self.repository.root, relative_path)
            if target.is_symlink() or target.is_file():
                target.unlink()
        manifest_path.unlink(missing_ok=True)

    async def remove_workspace(self, workspace: Workspace) -> None:
        output = await _run_git(
            ("worktree", "remove", "--force", str(workspace.path)),
            cwd=self.repository.root,
        )
        if output.exit_code != 0:
            raise GitError(output.stderr.decode(errors="replace").strip())

    async def _create_workspace(
        self,
        *,
        task_id: str,
        base_revision: str,
        kind: WorkspaceKind,
        source_workspace: Path | None = None,
    ) -> Workspace:
        current_revision = await self.repository.head_revision()
        if current_revision != base_revision:
            raise GitError(
                f"base revision {base_revision} does not match repository HEAD {current_revision}"
            )
        snapshot_source = source_workspace or self.repository.root
        snapshot = await self.repository.capture_snapshot(snapshot_source)
        workspace_id = f"ws_{uuid4().hex}"
        destination = self.worktrees_dir / kind.value / _safe_component(task_id) / workspace_id
        await self.repository.create_worktree(destination, base_revision)
        await self.repository.materialize_snapshot(destination, snapshot)
        return Workspace(
            id=workspace_id,
            kind=kind,
            path=destination,
            base_revision=GitRevision(base_revision),
            base_snapshot_hash=snapshot.snapshot_hash,
        )

    def _manifest_path(self, workspace_id: str) -> Path:
        return self.rollback_dir / f"{_safe_component(workspace_id)}.json"


async def _run_git(
    args: tuple[str, ...],
    *,
    cwd: Path,
    input_bytes: bytes | None = None,
) -> CommandOutput:
    git = shutil.which("git")
    if git is None:
        raise GitError("git executable not found on PATH")
    process = await asyncio.create_subprocess_exec(
        git,
        *args,
        cwd=cwd,
        stdin=asyncio.subprocess.PIPE if input_bytes is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate(input_bytes)
    return CommandOutput(
        command=args,
        exit_code=process.returncode if process.returncode is not None else 1,
        stdout=stdout,
        stderr=stderr,
    )


def _snapshot_hash(
    revision: str,
    patch: bytes,
    untracked: tuple[UntrackedFile, ...],
) -> str:
    digest = hashlib.sha256()
    for chunk in (revision.encode(), patch):
        _update_digest(digest, chunk)
    for item in untracked:
        _update_digest(digest, item.relative_path.replace("\\", "/").encode())
        _update_digest(digest, b"symlink" if item.is_symlink else b"file")
        _update_digest(digest, item.content)
    return digest.hexdigest()


def _update_digest(digest: hashlib._Hash, data: bytes) -> None:
    digest.update(len(data).to_bytes(8, "big"))
    digest.update(data)


def _materialize_untracked(
    destination: Path,
    untracked: tuple[UntrackedFile, ...],
) -> tuple[str, ...]:
    _validate_untracked_targets(destination, untracked)
    created: list[str] = []
    for item in untracked:
        target = _safe_join(destination, item.relative_path)
        if target.exists() or target.is_symlink():
            if target.is_symlink() and item.is_symlink:
                if os.fsencode(os.readlink(target)) == item.content:
                    continue
            elif target.is_file() and not item.is_symlink and target.read_bytes() == item.content:
                continue
            raise GitError(f"refusing to overwrite existing path: {item.relative_path}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if item.is_symlink:
            os.symlink(os.fsdecode(item.content), target)
        else:
            target.write_bytes(item.content)
        created.append(item.relative_path)
    return tuple(created)


def _safe_join(root: Path, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise GitError(f"unsafe repository-relative path: {relative_path}")
    target = (root / path).resolve()
    resolved_root = root.resolve()
    if not target.is_relative_to(resolved_root):
        raise GitError(f"path escapes repository root: {relative_path}")
    return target


def _validate_untracked_targets(
    destination: Path,
    untracked: tuple[UntrackedFile, ...],
) -> None:
    for item in untracked:
        target = _safe_join(destination, item.relative_path)
        if not (target.exists() or target.is_symlink()):
            continue
        if target.is_symlink() and item.is_symlink:
            if os.fsencode(os.readlink(target)) == item.content:
                continue
        elif target.is_file() and not item.is_symlink and target.read_bytes() == item.content:
            continue
        raise GitError(f"refusing to overwrite existing path: {item.relative_path}")


def _safe_component(value: str) -> str:
    safe = "".join(character for character in value if character.isalnum() or character in "-_")
    if not safe:
        raise ValueError("identifier cannot be converted to a safe path component")
    return safe
