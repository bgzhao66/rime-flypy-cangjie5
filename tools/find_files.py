
#!/usr/bin/env python3
"""
Cross-platform file finder, similar to the basic functionality of Unix find.

Examples:
    python find_files.py --dir src --name "*.cpp"
    python find_files.py --dir . --name "*.h" --type f
    python find_files.py --dir src --name "*.cpp" --exclude-dir build
"""

import argparse
import fnmatch
import os
import sys
from pathlib import Path
from typing import Iterator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recursively find files matching a filename pattern."
    )

    parser.add_argument(
        "--dir",
        default=".",
        metavar="DIR",
        help="Root directory to search (default: current directory).",
    )

    parser.add_argument(
        "--name",
        default="*",
        metavar="NAME_PATTERN",
        help='Filename pattern using shell wildcards, e.g. "*.cpp" (default: "*").',
    )

    parser.add_argument(
        "--type",
        choices=("f", "d", "a"),
        default="f",
        help="Entry type: f=files, d=directories, a=all (default: f).",
    )

    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        metavar="NAME",
        help="Directory name to exclude. Can be specified multiple times.",
    )

    parser.add_argument(
        "--hidden",
        action="store_true",
        help="Include hidden files and directories (default: include them).",
    )

    parser.add_argument(
        "--absolute",
        action="store_true",
        help="Output absolute paths instead of paths relative to --dir.",
    )

    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Use case-sensitive filename matching on every platform.",
    )

    return parser.parse_args()


def matches_name(name: str, pattern: str, case_sensitive: bool) -> bool:
    if case_sensitive:
        return fnmatch.fnmatchcase(name, pattern)

    return fnmatch.fnmatch(name.casefold(), pattern.casefold())


def iter_entries(
    root: Path,
    pattern: str,
    entry_type: str,
    exclude_dirs: set[str],
    include_hidden: bool,
    case_sensitive: bool,
) -> Iterator[Path]:
    """
    Recursively yield matching files/directories.

    Directory symlinks are not followed, avoiding symlink loops.
    """

    def walk_error(error: OSError) -> None:
        print(f"find_files.py: {error}", file=sys.stderr)

    for current, dirs, files in os.walk(
        root,
        topdown=True,
        followlinks=False,
        onerror=walk_error,
    ):
        current_path = Path(current)

        # Prune excluded directories before descending into them.
        dirs[:] = [
            name
            for name in dirs
            if name not in exclude_dirs
            and (
                include_hidden
                or not name.startswith(".")
            )
        ]

        if entry_type in ("d", "a"):
            for name in dirs:
                if matches_name(name, pattern, case_sensitive):
                    yield current_path / name

        if entry_type in ("f", "a"):
            for name in files:
                if not include_hidden and name.startswith("."):
                    continue

                if matches_name(name, pattern, case_sensitive):
                    yield current_path / name


def main() -> int:
    args = parse_args()
    root = Path(args.dir).expanduser()

    if not root.exists():
        print(
            f"find_files.py: directory does not exist: {root}",
            file=sys.stderr,
        )
        return 2

    if not root.is_dir():
        print(
            f"find_files.py: not a directory: {root}",
            file=sys.stderr,
        )
        return 2

    root = root.resolve()
    output_root = root if args.absolute else Path(args.dir).expanduser()

    try:
        for path in iter_entries(
            root=root,
            pattern=args.name,
            entry_type=args.type,
            exclude_dirs=set(args.exclude_dir),
            include_hidden=args.hidden,
            case_sensitive=args.case_sensitive,
        ):
            if args.absolute:
                result = path.resolve()
            else:
                result = Path(os.path.relpath(path, Path.cwd()))

            print(result)

    except BrokenPipeError:
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())

