from __future__ import annotations

import os
from pathlib import Path


def resolve_scan_root(path: Path) -> Path:
    candidate = path.expanduser()
    if candidate.is_symlink():
        raise ValueError(f"scan path must not be a symbolic link: {candidate}")
    if not candidate.exists():
        raise ValueError(f"scan path does not exist: {candidate}")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ValueError(f"scan path cannot be resolved: {candidate}: {error}") from None
    if not (resolved.is_file() or resolved.is_dir()):
        raise ValueError(f"scan path must be a regular file or directory: {candidate}")
    return resolved


def display_path(path: Path, root: Path) -> str:
    base = root if root.is_dir() else root.parent
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def iter_regular_files(
    root: Path,
    suffixes: set[str],
    excluded_parts: set[str],
    *,
    skipped_symlinks: list[str] | None = None,
) -> list[Path]:
    root = resolve_scan_root(root)
    if root.is_file():
        return [root] if root.suffix in suffixes else []

    files: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root, followlinks=False):
        base_path = Path(current_root)
        retained_directories: list[str] = []
        for name in dirnames:
            path = base_path / name
            if name in excluded_parts:
                continue
            if path.is_symlink():
                if skipped_symlinks is not None:
                    skipped_symlinks.append(display_path(path, root))
                continue
            retained_directories.append(name)
        dirnames[:] = retained_directories

        for filename in filenames:
            path = base_path / filename
            if path.suffix not in suffixes:
                continue
            if path.is_symlink():
                if skipped_symlinks is not None:
                    skipped_symlinks.append(display_path(path, root))
                continue
            if path.is_file():
                files.append(path)
    return sorted(files)


def read_required_text(path: Path, *, label: str, allow_empty: bool = True) -> str:
    candidate = path.expanduser()
    if candidate.is_symlink():
        raise ValueError(f"{label} must not be a symbolic link: {candidate}")
    if not candidate.exists():
        raise ValueError(f"{label} does not exist: {candidate}")
    if not candidate.is_file():
        raise ValueError(f"{label} must be a regular file: {candidate}")
    try:
        text = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ValueError(f"{label} could not be read as UTF-8: {candidate}: {error}") from None
    if not allow_empty and not text.strip():
        raise ValueError(f"{label} is empty: {candidate}")
    return text
