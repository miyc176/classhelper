#!/usr/bin/env python3
"""Strict completeness and grounding checks for course knowledge JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


FINAL_COVERAGE = {"covered", "no_instructional_content"}
IMPORTANCE = {"重点", "次重点", "拓展"}


def clean(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "")).lower()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(data: dict, workflow: dict | None, require_complete: bool, manifest: dict | None = None, manifest_hash: str = "") -> tuple[list[str], list[str], dict]:
    errors: list[str] = []
    warnings: list[str] = []
    inventory = data.get("source_inventory") or []
    audit = data.get("coverage_audit") or []
    points = data.get("knowledge_points") or []
    if not data.get("course_title"):
        errors.append("course_title is required.")
    if not inventory:
        errors.append("source_inventory is empty.")
    if not audit:
        errors.append("coverage_audit is empty.")
    if not points:
        errors.append("knowledge_points is empty.")

    source_ids = [str(item.get("source_id", "")) for item in inventory]
    if len(source_ids) != len(set(source_ids)):
        errors.append("source_inventory contains duplicate source_id values.")
    source_set = set(source_ids)
    for item in inventory:
        if require_complete and item.get("extraction_status") != "complete":
            errors.append(f"Source {item.get('source_id')} is not completely extracted.")

    if manifest is not None:
        if data.get("material_extraction_sha256") != manifest_hash:
            errors.append("material_extraction_sha256 does not match the current material-extraction.json.")
        manifest_sources = {
            str(item.get("source_id")): (str(item.get("path", "")), str(item.get("sha1", "")))
            for item in manifest.get("source_inventory") or []
        }
        knowledge_sources = {
            str(item.get("source_id")): (str(item.get("path", "")), str(item.get("sha1", "")))
            for item in inventory
        }
        if manifest_sources != knowledge_sources:
            errors.append("source_inventory does not exactly match the extraction manifest paths and hashes.")

    point_ids = [str(point.get("id", "")) for point in points]
    point_set = set(point_ids)
    if len(point_ids) != len(point_set):
        errors.append("knowledge_points contains duplicate ids.")
    normalized = Counter(clean(point.get("statement")) for point in points)
    duplicates = [value for value, count in normalized.items() if value and count > 1]
    if duplicates:
        errors.append(f"Duplicate knowledge statements found: {len(duplicates)}.")

    covered_ids: set[str] = set()
    audit_keys: set[tuple[str, str]] = set()
    audit_status: dict[tuple[str, str], str] = {}
    for item in audit:
        source_id = str(item.get("source_id", ""))
        unit = str(item.get("unit", ""))
        key = (source_id, unit)
        if key in audit_keys:
            errors.append(f"Duplicate coverage unit: {source_id} {unit}.")
        audit_keys.add(key)
        audit_status[key] = str(item.get("status", ""))
        if source_id not in source_set:
            errors.append(f"Coverage unit references unknown source: {source_id}.")
        status = item.get("status")
        if status not in FINAL_COVERAGE:
            message = f"Coverage unit {source_id} {unit} is unresolved: {status}."
            (errors if require_complete else warnings).append(message)
        ids = [str(value) for value in item.get("knowledge_ids") or []]
        if status == "covered" and not ids:
            errors.append(f"Covered unit has no knowledge ids: {source_id} {unit}.")
        if status == "no_instructional_content" and not str(item.get("notes", "")).strip():
            errors.append(f"No-content unit needs a concrete note: {source_id} {unit}.")
        for knowledge_id in ids:
            if knowledge_id not in point_set:
                errors.append(f"Coverage unit references unknown knowledge id: {knowledge_id}.")
            covered_ids.add(knowledge_id)

    if manifest is not None:
        expected_units = {
            (str(item.get("source_id", "")), str(item.get("unit", "")))
            for item in manifest.get("coverage_audit") or []
        }
        actual_units = {(str(item.get("source_id", "")), str(item.get("unit", ""))) for item in audit}
        missing_units = sorted(expected_units - actual_units)
        extra_units = sorted(actual_units - expected_units)
        if missing_units:
            errors.append("Coverage audit omitted manifest units: " + ", ".join(f"{source} {unit}" for source, unit in missing_units))
        if extra_units:
            errors.append("Coverage audit contains units absent from the manifest: " + ", ".join(f"{source} {unit}" for source, unit in extra_units))

    type_counts: Counter[str] = Counter()
    importance_counts: Counter[str] = Counter()
    for point in points:
        point_id = str(point.get("id", "[missing]"))
        for field in ["id", "topic", "type", "statement", "evidence", "teaching_value", "importance", "importance_basis"]:
            if not point.get(field):
                errors.append(f"{point_id} missing required field: {field}.")
        if point.get("scope_status") != "in_scope":
            errors.append(f"{point_id} must be in_scope or excluded from knowledge_points.")
        if point.get("importance") not in IMPORTANCE:
            errors.append(f"{point_id} has invalid importance: {point.get('importance')}.")
        refs = point.get("source_refs") or []
        if not refs:
            errors.append(f"{point_id} has no source_refs.")
        for ref in refs:
            ref_source = str(ref.get("source_id", ""))
            ref_locator = str(ref.get("locator", ""))
            if ref_source not in source_set:
                errors.append(f"{point_id} references unknown source: {ref.get('source_id')}.")
            if not ref.get("locator") or not ref.get("modality"):
                errors.append(f"{point_id} has an incomplete source reference.")
            elif (ref_source, ref_locator) not in audit_status:
                errors.append(f"{point_id} source reference is absent from coverage audit: {ref_source} {ref_locator}.")
            elif audit_status[(ref_source, ref_locator)] != "covered":
                errors.append(f"{point_id} references a source unit not marked covered: {ref_source} {ref_locator}.")
        if point_id not in covered_ids:
            errors.append(f"{point_id} is not connected to any covered source unit.")
        type_counts[str(point.get("type", "unknown"))] += 1
        importance_counts[str(point.get("importance", "unknown"))] += 1

    if workflow:
        if workflow.get("materials", {}).get("status") != "confirmed":
            errors.append("User has not confirmed the material inventory.")
        focus_ids = workflow.get("focus", {}).get("knowledge_ids") or []
        if workflow.get("focus", {}).get("status") == "confirmed":
            for focus_id in focus_ids:
                if focus_id not in point_set:
                    errors.append(f"Confirmed focus id is missing from knowledge: {focus_id}.")

    stats = {
        "sources": len(inventory),
        "coverage_units": len(audit),
        "knowledge_points": len(points),
        "type_counts": dict(type_counts),
        "importance_counts": dict(importance_counts),
    }
    return errors, warnings, stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate complete source-grounded course knowledge.")
    parser.add_argument("knowledge_json")
    parser.add_argument("--workflow-state")
    parser.add_argument("--inventory-manifest", help="Original material-extraction.json used to build knowledge JSON.")
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    data = json.loads(Path(args.knowledge_json).read_text(encoding="utf-8"))
    workflow = json.loads(Path(args.workflow_state).read_text(encoding="utf-8")) if args.workflow_state else None
    manifest_path = Path(args.inventory_manifest).resolve() if args.inventory_manifest else None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path else None
    errors, warnings, stats = validate(data, workflow, not args.allow_incomplete, manifest, sha256(manifest_path) if manifest_path else "")
    print(json.dumps({"status": "fail" if errors else "pass", "errors": errors, "warnings": warnings, "stats": stats}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
