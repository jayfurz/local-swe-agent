"""Workspace-rooted tools exposed to the model.

Each tool has a plain implementation (``*_impl``) that takes the workspace root
explicitly — unit-testable without the SDK — and a thin ``@function_tool``
wrapper that pulls the root from the run context. Implementations never raise:
they return ``error: ...`` strings so the model can read the failure and adapt.

File tools refuse paths that resolve outside the workspace root. ``bash`` runs
with the workspace as cwd but is NOT sandboxed.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agents import RunContextWrapper, function_tool

MAX_OUTPUT_CHARS = 30_000
MAX_MATCHES = 200
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache"}


@dataclass
class Workspace:
    root: Path


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    head = text[: limit // 2]
    tail = text[-(limit // 2) :]
    dropped = len(text) - len(head) - len(tail)
    return f"{head}\n... [{dropped} chars truncated] ...\n{tail}"


def _resolve(root: Path, path: str) -> Path:
    candidate = Path(path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    root = root.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"path {path!r} is outside the workspace {root}")
    return resolved


def bash_impl(root: Path, command: str, timeout_s: int = 120) -> str:
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return f"error: command timed out after {timeout_s}s"
    except OSError as e:
        return f"error: {e}"
    out = proc.stdout
    if proc.stderr:
        if out and not out.endswith("\n"):
            out += "\n"
        out += "[stderr]\n" + proc.stderr
    body = _truncate(out.strip("\n")) or "(no output)"
    return f"exit code: {proc.returncode}\n{body}"


def read_file_impl(root: Path, path: str, offset: int = 1, limit: int = 2000) -> str:
    try:
        target = _resolve(root, path)
        if not target.is_file():
            return f"error: {path} is not a file"
        lines = target.read_text(errors="replace").splitlines()
    except (ValueError, OSError) as e:
        return f"error: {e}"
    offset = max(offset, 1)
    selected = lines[offset - 1 : offset - 1 + limit]
    if not selected:
        return f"(file has {len(lines)} lines; nothing at offset {offset})"
    body = "\n".join(f"{n:>6}\t{line}" for n, line in enumerate(selected, start=offset))
    shown_up_to = offset - 1 + len(selected)
    if shown_up_to < len(lines):
        body += f"\n... ({len(lines)} lines total; showing {offset}-{shown_up_to})"
    return _truncate(body)


def write_file_impl(root: Path, path: str, content: str) -> str:
    try:
        target = _resolve(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    except (ValueError, OSError) as e:
        return f"error: {e}"
    return f"wrote {len(content)} chars to {path}"


def edit_file_impl(
    root: Path, path: str, old_string: str, new_string: str, replace_all: bool = False
) -> str:
    try:
        target = _resolve(root, path)
        if not target.is_file():
            return f"error: {path} is not a file"
        text = target.read_text(errors="replace")
    except (ValueError, OSError) as e:
        return f"error: {e}"
    count = text.count(old_string)
    if count == 0:
        return f"error: old_string not found in {path}"
    if count > 1 and not replace_all:
        return f"error: old_string occurs {count} times in {path}; make it unique or set replace_all=true"
    replaced = text.replace(old_string, new_string) if replace_all else text.replace(old_string, new_string, 1)
    try:
        target.write_text(replaced)
    except OSError as e:
        return f"error: {e}"
    n = count if replace_all else 1
    return f"replaced {n} occurrence{'s' if n != 1 else ''} in {path}"


def list_dir_impl(root: Path, path: str = ".") -> str:
    try:
        target = _resolve(root, path)
        if not target.is_dir():
            return f"error: {path} is not a directory"
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name))
    except (ValueError, OSError) as e:
        return f"error: {e}"
    if not entries:
        return "(empty directory)"
    return "\n".join(e.name + ("/" if e.is_dir() else "") for e in entries)


def glob_files_impl(root: Path, pattern: str) -> str:
    root = root.resolve()
    try:
        matches = []
        for p in sorted(root.glob(pattern)):
            if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
                continue
            matches.append(str(p.relative_to(root)) + ("/" if p.is_dir() else ""))
            if len(matches) >= MAX_MATCHES:
                matches.append(f"... (capped at {MAX_MATCHES} matches)")
                break
    except (ValueError, OSError) as e:
        return f"error: {e}"
    return "\n".join(matches) if matches else "(no matches)"


def grep_impl(root: Path, pattern: str, path: str = ".", include: str | None = None) -> str:
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return f"error: invalid regex: {e}"
    try:
        target = _resolve(root, path)
    except ValueError as e:
        return f"error: {e}"
    if target.is_file():
        files = [target]
    elif target.is_dir():
        files = [
            p
            for p in sorted(target.rglob(include or "*"))
            if p.is_file() and not any(part in SKIP_DIRS for part in p.relative_to(target).parts)
        ]
    else:
        return f"error: {path} does not exist"
    root = root.resolve()
    hits: list[str] = []
    for f in files:
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        if "\x00" in text[:1024]:
            continue
        for n, line in enumerate(text.splitlines(), start=1):
            if rx.search(line):
                hits.append(f"{f.relative_to(root)}:{n}: {line.strip()}")
                if len(hits) >= MAX_MATCHES:
                    hits.append(f"... (capped at {MAX_MATCHES} matches)")
                    return _truncate("\n".join(hits))
    return _truncate("\n".join(hits)) if hits else "(no matches)"


@function_tool
def bash(ctx: RunContextWrapper[Workspace], command: str, timeout_s: int = 120) -> str:
    """Run a shell command in the workspace root and return exit code + output.

    Args:
        command: Shell command to execute (via `sh -c`).
        timeout_s: Kill the command after this many seconds.
    """
    return bash_impl(ctx.context.root, command, timeout_s)


@function_tool
def read_file(ctx: RunContextWrapper[Workspace], path: str, offset: int = 1, limit: int = 2000) -> str:
    """Read a file, returning numbered lines.

    Args:
        path: File path relative to the workspace root.
        offset: 1-based line number to start from.
        limit: Maximum number of lines to return.
    """
    return read_file_impl(ctx.context.root, path, offset, limit)


@function_tool
def write_file(ctx: RunContextWrapper[Workspace], path: str, content: str) -> str:
    """Create or overwrite a file with the given content (parent dirs created).

    Args:
        path: File path relative to the workspace root.
        content: Full file content to write.
    """
    return write_file_impl(ctx.context.root, path, content)


@function_tool
def edit_file(
    ctx: RunContextWrapper[Workspace],
    path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    """Replace an exact string in a file.

    Args:
        path: File path relative to the workspace root.
        old_string: Exact text to find (must be unique unless replace_all).
        new_string: Replacement text.
        replace_all: Replace every occurrence instead of requiring uniqueness.
    """
    return edit_file_impl(ctx.context.root, path, old_string, new_string, replace_all)


@function_tool
def list_dir(ctx: RunContextWrapper[Workspace], path: str = ".") -> str:
    """List a directory (directories first, marked with a trailing /).

    Args:
        path: Directory path relative to the workspace root.
    """
    return list_dir_impl(ctx.context.root, path)


@function_tool
def glob_files(ctx: RunContextWrapper[Workspace], pattern: str) -> str:
    """Find files matching a glob pattern (supports **), relative to the workspace root.

    Args:
        pattern: Glob pattern, e.g. `**/*.py` or `src/**/test_*.py`.
    """
    return glob_files_impl(ctx.context.root, pattern)


@function_tool
def grep(ctx: RunContextWrapper[Workspace], pattern: str, path: str = ".", include: str | None = None) -> str:
    """Search file contents with a regex; returns `file:line: text` matches.

    Args:
        pattern: Python regular expression to search for.
        path: File or directory to search, relative to the workspace root.
        include: Optional filename glob filter when searching a directory, e.g. `*.py`.
    """
    return grep_impl(ctx.context.root, pattern, path, include)


ALL_TOOLS = [bash, read_file, write_file, edit_file, list_dir, glob_files, grep]
