#!/usr/bin/env python3
"""Generate and statically validate every fixed classic game template."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


MODES = ["memory", "tictactoe", "flappy", "shooter", "puzzle"]


def run(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(command, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the full polished classic game template set.")
    parser.add_argument("knowledge_json", help="Path to a representative knowledge.json file.")
    parser.add_argument("--out", required=True, help="Output directory for generated validation games.")
    parser.add_argument("--force", action="store_true", help="Replace the output directory if it exists.")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    knowledge_json = Path(args.knowledge_json).resolve()
    out_root = Path(args.out).resolve()
    if out_root.exists():
        if not args.force:
            raise FileExistsError(f"Output already exists: {out_root}")
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []

    whack_out = out_root / "whack-a-mole"
    results.append(run([
        sys.executable,
        str(script_dir / "build_whack_a_mole.py"),
        str(knowledge_json),
        "--out",
        str(whack_out),
        "--title",
        "Template Check Whack",
        "--force",
    ]))
    results.append(run([
        sys.executable,
        str(script_dir / "validate_html_game.py"),
        str(whack_out),
        "--knowledge-json",
        str(knowledge_json),
    ]))

    for mode in MODES:
        mode_out = out_root / mode
        results.append(run([
            sys.executable,
            str(script_dir / "build_standalone_classic.py"),
            str(knowledge_json),
            "--mode",
            mode,
            "--out",
            str(mode_out),
            "--title",
            f"Template Check {mode}",
            "--force",
        ]))
        results.append(run([
            sys.executable,
            str(script_dir / "validate_html_game.py"),
            str(mode_out),
            "--knowledge-json",
            str(knowledge_json),
        ]))

    failures = [item for item in results if item["returncode"] != 0]
    print(json.dumps({
        "status": "fail" if failures else "pass",
        "out": str(out_root),
        "checked": ["whack-a-mole", *MODES],
        "failures": failures,
        "results": results,
    }, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
