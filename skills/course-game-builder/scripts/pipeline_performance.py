#!/usr/bin/env python3
"""Record and summarize deterministic and AI-assisted course pipeline timing."""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


STAGES = {
    "material_parsing",
    "rendering",
    "ocr_visual_analysis",
    "knowledge_engineering",
    "knowledge_report",
    "question_generation",
    "excel_generation",
    "game_generation",
    "validation",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def timestamp() -> float:
    return time.time()


def empty_report(course_title: str) -> dict:
    return {
        "schema_version": "1.0",
        "run_id": uuid.uuid4().hex,
        "course_title": course_title,
        "started_at": now(),
        "started_timestamp": timestamp(),
        "completed_at": None,
        "stages": {name: {"status": "pending", "invocations": []} for name in sorted(STAGES)},
        "summary": {},
    }


def load(path: Path, course_title: str = "") -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return empty_report(course_title)


def summarize(report: dict) -> dict:
    invocations = [item for stage in report.get("stages", {}).values() for item in stage.get("invocations", [])]
    cache_hits = sum(int(item.get("metrics", {}).get("cache_hits", 0) or 0) for item in invocations)
    cache_misses = sum(int(item.get("metrics", {}).get("cache_misses", 0) or 0) for item in invocations)
    pages_total = max([int(item.get("metrics", {}).get("pages_total", 0) or 0) for item in invocations] or [0])
    pages_reprocessed = max([int(item.get("metrics", {}).get("pages_reprocessed", 0) or 0) for item in invocations] or [0])
    stage_seconds = {
        name: round(sum(float(item.get("duration_seconds", 0)) for item in stage.get("invocations", [])), 3)
        for name, stage in report.get("stages", {}).items()
    }
    denominator = cache_hits + cache_misses
    return {
        "elapsed_seconds": round(timestamp() - float(report.get("started_timestamp", timestamp())), 3),
        "stage_seconds": stage_seconds,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_hit_rate": round(cache_hits / denominator, 4) if denominator else None,
        "pages_total": pages_total,
        "pages_reprocessed": pages_reprocessed,
        "stages_completed": sum(stage.get("status") == "completed" for stage in report.get("stages", {}).values()),
        "active_stages": [name for name, stage in report.get("stages", {}).items() if stage.get("status") == "running"],
        "unrecorded_stages": [name for name, stage in report.get("stages", {}).items() if stage.get("status") == "pending"],
    }


def save(path: Path, report: dict) -> None:
    report["summary"] = summarize(report)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def scalar(value: str) -> object:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def parse_metrics(value: str, pairs: list[str] | None = None) -> dict:
    parsed: dict = {}
    if value:
        candidate = json.loads(value)
        if not isinstance(candidate, dict):
            raise ValueError("--metrics-json must be a JSON object.")
        parsed.update(candidate)
    for pair in pairs or []:
        key, separator, item_value = pair.partition("=")
        if not separator or not key.strip():
            raise ValueError(f"Invalid --metric value: {pair}; expected key=value.")
        parsed[key.strip()] = scalar(item_value.strip())
    return parsed


def record_stage(path: Path, stage: str, duration_seconds: float, metrics: dict | None = None, course_title: str = "") -> dict:
    if stage not in STAGES:
        raise ValueError(f"Unknown stage: {stage}")
    report = load(path, course_title)
    if report.get("completed_at"):
        raise ValueError("Performance run is already complete; initialize a new run before recording more stages.")
    stage_data = report.setdefault("stages", {}).setdefault(stage, {"status": "pending", "invocations": []})
    stage_data["invocations"].append({
        "started_at": None,
        "completed_at": now(),
        "duration_seconds": round(max(0.0, duration_seconds), 3),
        "metrics": metrics or {},
    })
    stage_data["status"] = "completed"
    stage_data.pop("active_started_at", None)
    stage_data.pop("active_started_timestamp", None)
    save(path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage pipeline-performance.json.")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--course-title", required=True)
    init.add_argument("--out", required=True)
    for command in ["start", "finish", "record", "complete", "status"]:
        item = sub.add_parser(command)
        item.add_argument("performance_file")
        if command in {"start", "finish", "record"}:
            item.add_argument("--stage", required=True, choices=sorted(STAGES))
        if command in {"finish", "record"}:
            item.add_argument("--metrics-json", default="{}")
            item.add_argument("--metric", action="append", default=[], help="Repeatable key=value metric; safer in shells than JSON.")
        if command == "record":
            item.add_argument("--duration-seconds", required=True, type=float)
    args = parser.parse_args()

    if args.command == "init":
        path = Path(args.out).resolve()
        report = empty_report(args.course_title)
        save(path, report)
    else:
        path = Path(args.performance_file).resolve()
        report = load(path)
        if args.command == "start":
            if report.get("completed_at"):
                raise ValueError("Performance run is already complete; initialize a new run first.")
            stage = report.setdefault("stages", {}).setdefault(args.stage, {"status": "pending", "invocations": []})
            if stage.get("status") == "running":
                raise ValueError(f"Stage is already running: {args.stage}")
            stage["status"] = "running"
            stage["active_started_at"] = now()
            stage["active_started_timestamp"] = timestamp()
            save(path, report)
        elif args.command == "finish":
            stage = report.setdefault("stages", {}).setdefault(args.stage, {"status": "pending", "invocations": []})
            if stage.get("status") != "running" or not stage.get("active_started_timestamp"):
                raise ValueError(f"Stage was not started: {args.stage}")
            duration = timestamp() - float(stage["active_started_timestamp"])
            started_at = stage.get("active_started_at")
            stage["invocations"].append({
                "started_at": started_at, "completed_at": now(),
                "duration_seconds": round(duration, 3), "metrics": parse_metrics(args.metrics_json, args.metric),
            })
            stage["status"] = "completed"
            stage.pop("active_started_at", None)
            stage.pop("active_started_timestamp", None)
            save(path, report)
        elif args.command == "record":
            report = record_stage(path, args.stage, args.duration_seconds, parse_metrics(args.metrics_json, args.metric))
        elif args.command == "complete":
            running = [name for name, stage in report.get("stages", {}).items() if stage.get("status") == "running"]
            if running:
                raise ValueError("Cannot complete while stages are running: " + ", ".join(running))
            report["completed_at"] = now()
            save(path, report)
        elif args.command == "status":
            save(path, report)

    report = load(path)
    print(json.dumps({"status": "pass", "performance_file": str(path), "summary": report.get("summary", {})}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
