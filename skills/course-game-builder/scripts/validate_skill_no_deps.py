#!/usr/bin/env python3
"""Dependency-free skill structure validation for environments without PyYAML."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_simple_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.DOTALL)
    if not match:
        raise ValueError("Invalid or missing YAML frontmatter block.")
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"Unsupported frontmatter line: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        data[key] = value
    return data


def validate(skill_dir: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return ["SKILL.md not found."], warnings
    text = skill_md.read_text(encoding="utf-8")
    try:
        frontmatter = parse_simple_frontmatter(text)
    except ValueError as exc:
        return [str(exc)], warnings

    allowed = {"name", "description"}
    extra = set(frontmatter) - allowed
    if extra:
        errors.append(f"Unexpected frontmatter keys: {', '.join(sorted(extra))}")
    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")
    if not name:
        errors.append("Missing name.")
    if not description:
        errors.append("Missing description.")
    if name and not re.match(r"^[a-z0-9-]+$", name):
        errors.append(f"Name is not hyphen-case: {name}")
    if len(name) > 64:
        errors.append("Name is longer than 64 characters.")
    if len(description) > 1024:
        errors.append("Description is longer than 1024 characters.")
    if "<" in description or ">" in description:
        errors.append("Description contains angle brackets.")
    if "[TODO" in text or "TODO:" in text:
        warnings.append("SKILL.md contains TODO text.")
    if not (skill_dir / "agents" / "openai.yaml").exists():
        warnings.append("agents/openai.yaml is missing.")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Codex skill without third-party dependencies.")
    parser.add_argument("skill_dir")
    args = parser.parse_args()
    errors, warnings = validate(Path(args.skill_dir).resolve())
    print(json.dumps({"status": "fail" if errors else "pass", "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
