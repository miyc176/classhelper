#!/usr/bin/env python3
"""Inventory course materials and extract machine-readable text plus visual review tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


SUPPORTED = {".pptx", ".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


@dataclass
class ExtractedSource:
    source_id: str
    path: str
    kind: str
    extraction_status: str = "complete"
    notes: str = ""
    page_or_slide_count: int = 0
    text_units: list[dict[str, Any]] = field(default_factory=list)
    visual_units: list[dict[str, Any]] = field(default_factory=list)


def stable_id(index: int) -> str:
    return f"src_{index:03d}"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as handle:
      for chunk in iter(lambda: handle.read(1024 * 1024), b""):
          h.update(chunk)
    return h.hexdigest()


def write_visual_copy(source_id: str, locator: str, image_name: str, data: bytes, out_dir: Path) -> str:
    safe_locator = re.sub(r"[^a-zA-Z0-9_-]+", "-", locator).strip("-").lower() or "visual"
    target_dir = out_dir / "visuals" / source_id
    target_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(image_name).suffix or ".bin"
    target = target_dir / f"{safe_locator}-{len(list(target_dir.iterdir())) + 1:03d}{suffix}"
    target.write_bytes(data)
    return str(target)


def xml_text(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return ""
    texts = [node.text for node in root.iter() if node.tag.endswith("}t") and node.text]
    return clean_text(" ".join(texts))


def extract_pptx(path: Path, source_id: str, out_dir: Path) -> ExtractedSource:
    source = ExtractedSource(source_id, str(path), "pptx")
    try:
        from pptx import Presentation

        prs = Presentation(str(path))
        source.page_or_slide_count = len(prs.slides)
        for idx, slide in enumerate(prs.slides, start=1):
            parts: list[str] = []
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    parts.append(shape.text)
                if getattr(shape, "has_table", False):
                    for row in shape.table.rows:
                        parts.append(" | ".join(cell.text for cell in row.cells))
            text = clean_text(" ".join(parts))
            if text:
                source.text_units.append({
                    "locator": f"slide {idx}",
                    "modality": "text",
                    "text": text,
                })
    except Exception as exc:
        source.extraction_status = "partial"
        source.notes = f"python-pptx extraction failed: {exc}"

    try:
        with zipfile.ZipFile(path) as zf:
            for name in sorted(zf.namelist()):
                if name.startswith("ppt/notesSlides/") and name.endswith(".xml"):
                    text = xml_text(zf.read(name))
                    if text:
                        source.text_units.append({
                            "locator": Path(name).stem.replace("notesSlide", "notes slide "),
                            "modality": "notes",
                            "text": text,
                        })
                if name.startswith("ppt/media/"):
                    copied = write_visual_copy(source_id, "embedded", Path(name).name, zf.read(name), out_dir)
                    source.visual_units.append({
                        "locator": Path(name).name,
                        "modality": "embedded_image",
                        "extracted_path": copied,
                        "review_status": "needs_visual_inspection",
                    })
    except Exception as exc:
        source.extraction_status = "partial"
        source.notes = (source.notes + "; " if source.notes else "") + f"pptx package scan failed: {exc}"
    return source


def extract_docx(path: Path, source_id: str, out_dir: Path) -> ExtractedSource:
    source = ExtractedSource(source_id, str(path), "docx")
    try:
        from docx import Document

        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        text = clean_text(" ".join(parts))
        if text:
            source.text_units.append({"locator": "document body", "modality": "text", "text": text})
    except Exception as exc:
        source.extraction_status = "partial"
        source.notes = f"python-docx extraction failed: {exc}"

    try:
        with zipfile.ZipFile(path) as zf:
            for name in sorted(zf.namelist()):
                if name.startswith("word/media/"):
                    copied = write_visual_copy(source_id, "embedded", Path(name).name, zf.read(name), out_dir)
                    source.visual_units.append({
                        "locator": Path(name).name,
                        "modality": "embedded_image",
                        "extracted_path": copied,
                        "review_status": "needs_visual_inspection",
                    })
    except Exception as exc:
        source.extraction_status = "partial"
        source.notes = (source.notes + "; " if source.notes else "") + f"docx package scan failed: {exc}"
    return source


def extract_pdf(path: Path, source_id: str, out_dir: Path) -> ExtractedSource:
    source = ExtractedSource(source_id, str(path), "pdf")
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            source.page_or_slide_count = len(pdf.pages)
            for idx, page in enumerate(pdf.pages, start=1):
                text = clean_text(page.extract_text() or "")
                if text:
                    source.text_units.append({"locator": f"page {idx}", "modality": "text", "text": text})
                for image_idx, image in enumerate(page.images, start=1):
                    source.visual_units.append({
                        "locator": f"page {idx} image {image_idx}",
                        "modality": "pdf_image_or_region",
                        "bbox": [image.get("x0"), image.get("top"), image.get("x1"), image.get("bottom")],
                        "review_status": "needs_rendered_page_inspection",
                    })
    except Exception as exc:
        source.extraction_status = "partial"
        source.notes = f"pdfplumber extraction failed: {exc}"
    return source


def extract_plain(path: Path, source_id: str) -> ExtractedSource:
    source = ExtractedSource(source_id, str(path), path.suffix.lower().lstrip("."))
    try:
        text = clean_text(path.read_text(encoding="utf-8", errors="ignore"))
        if text:
            source.text_units.append({"locator": "file", "modality": "text", "text": text})
    except Exception as exc:
        source.extraction_status = "blocked"
        source.notes = f"text read failed: {exc}"
    return source


def extract_image(path: Path, source_id: str, out_dir: Path) -> ExtractedSource:
    source = ExtractedSource(source_id, str(path), path.suffix.lower().lstrip("."))
    target_dir = out_dir / "visuals" / source_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name
    if path.resolve() != target.resolve():
        shutil.copy2(path, target)
    source.visual_units.append({
        "locator": "image",
        "modality": "standalone_image",
        "extracted_path": str(target),
        "review_status": "needs_visual_inspection",
    })
    source.page_or_slide_count = 1
    return source


def extract_file(path: Path, source_id: str, out_dir: Path) -> ExtractedSource:
    ext = path.suffix.lower()
    if ext == ".pptx":
        return extract_pptx(path, source_id, out_dir)
    if ext == ".docx":
        return extract_docx(path, source_id, out_dir)
    if ext == ".pdf":
        return extract_pdf(path, source_id, out_dir)
    if ext in {".txt", ".md"}:
        return extract_plain(path, source_id)
    if ext in IMAGE_EXTS:
        return extract_image(path, source_id, out_dir)
    return ExtractedSource(source_id, str(path), ext.lstrip(".") or "other", "blocked", "Unsupported file type")


def discover(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(path for path in input_path.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED)


def build_report(files: list[Path], out_dir: Path) -> dict[str, Any]:
    sources = [extract_file(path, stable_id(index), out_dir) for index, path in enumerate(files, start=1)]
    inventory = []
    text_units = []
    visual_units = []
    coverage_audit = []

    for source in sources:
        inventory.append({
            "source_id": source.source_id,
            "path": source.path,
            "kind": source.kind,
            "sha1": sha1(Path(source.path)),
            "page_or_slide_count": source.page_or_slide_count,
            "extraction_status": source.extraction_status,
            "notes": source.notes,
        })
        for unit in source.text_units:
            text_units.append({"source_id": source.source_id, **unit})
        for unit in source.visual_units:
            visual_units.append({"source_id": source.source_id, **unit})

        locators = {unit["locator"] for unit in source.text_units}
        locators.update(unit["locator"] for unit in source.visual_units)
        if not locators:
            coverage_audit.append({
                "source_id": source.source_id,
                "unit": "file",
                "status": "blocked" if source.extraction_status == "blocked" else "no_machine_readable_content",
                "knowledge_ids": [],
                "notes": source.notes or "No text or visual unit was extracted.",
            })
        else:
            for locator in sorted(locators):
                has_visual = any(unit["locator"] == locator for unit in source.visual_units)
                coverage_audit.append({
                    "source_id": source.source_id,
                    "unit": locator,
                    "status": "needs_visual_review" if has_visual else "needs_knowledge_extraction",
                    "knowledge_ids": [],
                    "notes": "Inspect visual content before marking covered." if has_visual else "",
                })

    return {
        "schema_version": "1.0",
        "source_inventory": inventory,
        "text_units": text_units,
        "visual_units": visual_units,
        "coverage_audit": coverage_audit,
        "agent_next_steps": [
            "Inspect every visual_units entry and rendered page/slide when available.",
            "Convert text_units and visual observations into references/knowledge-schema.md knowledge_points.",
            "Replace coverage_audit statuses with covered/no_instructional_content/blocked before game generation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory course materials for course-game-builder.")
    parser.add_argument("input", help="File or directory containing course materials.")
    parser.add_argument("--out", required=True, help="Output directory for extraction artifacts.")
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    files = discover(input_path)
    if not files:
        print(json.dumps({"status": "fail", "error": f"No supported files found in {input_path}"}, ensure_ascii=False, indent=2))
        return 1

    report = build_report(files, out_dir)
    report_path = out_dir / "material-extraction.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": "pass", "report": str(report_path), "sources": len(report["source_inventory"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
