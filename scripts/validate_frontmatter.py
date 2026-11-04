#!/usr/bin/env python3
"""Validate YAML front matter against schema/frontmatter.schema.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "frontmatter.schema.json"


def read_front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError("missing YAML front matter")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("unterminated YAML front matter")
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise ValueError("front matter is not a mapping")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--dir", action="append", type=Path, default=[])
    parser.add_argument("--file-list", type=Path)
    parser.add_argument("--skip", action="append", default=["README.md"])
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    paths = list(args.paths)
    if args.file_list:
        paths.extend(
            Path(line.strip())
            for line in args.file_list.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    for directory in args.dir:
        if not directory.exists():
            raise SystemExit(f"directory not found: {directory}")
        paths.extend(sorted(directory.rglob("*.md")))
    paths = [path for path in paths if path.name not in set(args.skip)]
    if not paths:
        raise SystemExit("no Markdown files given; pass paths or --dir")

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    failed = 0
    for path in paths:
        try:
            data = read_front_matter(path)
            errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
            if errors:
                failed += 1
                print(f"FAIL {path}")
                for error in errors:
                    location = ".".join(str(p) for p in error.path) or "(root)"
                    print(f"  {location}: {error.message}")
            elif not args.quiet:
                print(f"OK   {path}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {path}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
