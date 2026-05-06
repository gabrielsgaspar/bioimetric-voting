#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

NETWORK_SCRIPT_DIR = Path("/Users/gabrielsgaspar/.codex/skills/literature-network/scripts")
sys.path.insert(0, str(NETWORK_SCRIPT_DIR))

import init_from_zotero_fulltexts as litnet  # noqa: E402
from common import MASTER_COLUMNS, PDF_COLUMNS, citation_note_stem, add_year_suffix  # noqa: E402
from write_obsidian_notes import render as render_note_template  # noqa: E402


VAULT_ROOT = Path("/Users/gabrielsgaspar/Library/Mobile Documents/iCloud~md~obsidian/Documents/Research")
ZOTERO_ROOT = Path("/Users/gabrielsgaspar/Zotero")
RUN_LABEL = "zotero-missing-two-hop-20260501"
RUN_DIR = VAULT_ROOT / "data" / "literature_review" / RUN_LABEL
MAX_HOPS = 2
MAX_FORWARD_CITATIONS_PER_WORK = 75


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader), list(reader.fieldnames or [])


def write_csv_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup_dir = VAULT_ROOT / "data" / "backups" / RUN_LABEL
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / path.name
    shutil.copy2(path, backup)
    return backup


def norm_doi(value: str) -> str:
    return litnet.normalize_doi(value or "")


def norm_title(value: str) -> str:
    return litnet.normalize_text(value or "")


def zotero_missing_items(master_rows: list[dict[str, str]]) -> tuple[list[litnet.ZoteroItem], list[litnet.ZoteroItem], int]:
    items_raw = litnet.zotero_items_with_pdf(ZOTERO_ROOT, set(), "zotero_pdf_all")
    items, duplicate_count = litnet.dedupe_zotero_items(items_raw)
    master_dois = {norm_doi(row.get("doi", "")) for row in master_rows if norm_doi(row.get("doi", ""))}
    master_titles = {norm_title(row.get("title", "")) for row in master_rows if norm_title(row.get("title", ""))}
    master_keys: set[str] = set()
    for row in master_rows:
        for key in str(row.get("zotero_item_key", "")).split(";"):
            if key.strip():
                master_keys.add(key.strip())

    missing: list[litnet.ZoteroItem] = []
    present: list[litnet.ZoteroItem] = []
    for item in items:
        keys = {key.strip() for key in item.key.split(";") if key.strip()}
        exists = bool(keys & master_keys) or (item.doi and item.doi in master_dois) or norm_title(item.title) in master_titles
        (present if exists else missing).append(item)
    return missing, items, duplicate_count


def fieldnames_union(existing: list[str], canonical: list[str]) -> list[str]:
    out = list(existing or canonical)
    for field in canonical:
        if field not in out:
            out.append(field)
    return out


def merge_preserving_summary(existing: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    if not existing:
        return {key: new.get(key, "") for key in MASTER_COLUMNS}
    out = dict(existing)
    for key, value in new.items():
        if key.startswith("_"):
            continue
        if key in {"summary_status", "summary_model", "summary_generated_at", "paper_type", "extraction_status", "summary_quality_flags", "note_path", "note_type"}:
            continue
        if value not in ("", None):
            if key == "hop_distance":
                try:
                    old_hop = int(out.get(key) or 999)
                    new_hop = int(value)
                    if new_hop < old_hop:
                        out[key] = value
                except Exception:
                    out[key] = out.get(key, value)
            elif not out.get(key) or key in {"has_pdf", "pdf_status", "pdf_path", "pdf_source", "in_zotero", "zotero_item_key", "attachment_count"}:
                out[key] = value
    if new.get("has_pdf") == "true":
        for key in ["has_pdf", "pdf_status", "pdf_path", "pdf_source", "in_zotero", "zotero_item_key", "attachment_count"]:
            out[key] = new.get(key, out.get(key, ""))
    return out


def unique_note_path(rec: dict[str, Any], existing_paths: set[Path]) -> Path:
    stem = citation_note_stem(rec)
    candidate = VAULT_ROOT / "papers" / f"{stem}.md"
    if candidate.resolve() not in existing_paths and not candidate.exists():
        return candidate
    for index in range(26):
        suffixed = VAULT_ROOT / "papers" / f"{add_year_suffix(stem, chr(ord('a') + index))}.md"
        if suffixed.resolve() not in existing_paths and not suffixed.exists():
            return suffixed
    raise RuntimeError(f"Could not find unique note path for {rec.get('title')}")


def write_new_note(rec: dict[str, Any], existing_paths: set[Path]) -> Path:
    template = (NETWORK_SCRIPT_DIR.parent / "assets" / "paper_note_template.md").read_text(encoding="utf-8")
    note_path = unique_note_path(rec, existing_paths)
    note_row = dict(rec)
    note_row.setdefault("topic_label", "zotero_missing_two_hop")
    note_row["note_type"] = "full_text"
    note_row["summary_status"] = "not_started"
    note_row["summary_model"] = ""
    note_row["summary_generated_at"] = ""
    note_row["summary_quality_flags"] = "Awaiting API structured summary"
    note_path.write_text(render_note_template(template, note_row), encoding="utf-8")
    existing_paths.add(note_path.resolve())
    return note_path


def record_for_work(work: dict[str, Any], cfg: dict[str, Any], hop: int, seed: bool, discovered_from: str, zotero_item: litnet.ZoteroItem | None) -> dict[str, Any]:
    rec = litnet.record_from_work(work, cfg, hop=hop, seed_flag=seed, discovered_from=discovered_from, zotero_item=zotero_item)
    rec["scope_decision"] = "in_scope"
    rec["scope_reason"] = "Incremental Zotero-missing/two-hop expansion using zotero_pdf_all scope."
    rec["eligible_for_expansion"] = "true" if hop < MAX_HOPS else "false"
    return rec


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    data_dir = VAULT_ROOT / "data"
    master_path = data_dir / "papers_master.csv"
    edges_path = data_dir / "citation_edges.csv"
    pdf_path = data_dir / "pdf_status.csv"
    for path in [master_path, edges_path, pdf_path]:
        backup_file(path)

    master_rows, master_fields = read_csv_rows(master_path)
    edge_rows, edge_fields = read_csv_rows(edges_path)
    pdf_rows, pdf_fields = read_csv_rows(pdf_path)
    master_fields = fieldnames_union(master_fields, MASTER_COLUMNS)
    edge_fields = fieldnames_union(edge_fields, litnet.EDGE_COLUMNS)
    pdf_fields = fieldnames_union(pdf_fields, PDF_COLUMNS)

    records: dict[str, dict[str, Any]] = {row["work_id"]: dict(row) for row in master_rows if row.get("work_id")}
    existing_paths = {Path(row["note_path"]).resolve() for row in master_rows if row.get("note_path")}
    missing_items, all_zotero_items, duplicate_zotero_count = zotero_missing_items(master_rows)
    zotero_by_doi = {item.doi: item for item in all_zotero_items if item.doi}
    zotero_by_title = {norm_title(item.title): item for item in all_zotero_items}

    cfg = {
        "scope_mode": "zotero_pdf_all",
        "topic_label": "zotero_missing_two_hop",
    }
    new_pdf_records: list[dict[str, Any]] = []
    unresolved: list[dict[str, str]] = []
    queue: deque[tuple[str, int]] = deque()

    for item in missing_items:
        work = litnet.resolve_by_doi(item.doi) if item.doi else None
        if not work:
            work = litnet.search_by_title(item.title)
        if not work:
            unresolved.append({"zotero_item_key": item.key, "title": item.title, "doi": item.doi, "reason": "openalex_unresolved"})
            continue
        rec = record_for_work(work, cfg, hop=0, seed=True, discovered_from="zotero_missing_pdf_seed", zotero_item=item)
        work_id = rec["work_id"]
        if work_id in records:
            records[work_id] = merge_preserving_summary(records[work_id], rec)
        else:
            note_path = write_new_note(rec, existing_paths)
            rec["note_path"] = str(note_path)
            rec["note_type"] = "full_text"
            rec["summary_status"] = "not_started"
            records[work_id] = {key: rec.get(key, "") for key in MASTER_COLUMNS}
            new_pdf_records.append(records[work_id])
        queue.append((work_id, 0))

    edge_seen = {
        (row.get("source_work_id", ""), row.get("target_work_id", ""), row.get("edge_type", "cites"))
        for row in edge_rows
    }
    expanded: set[tuple[str, int]] = set()
    added_connected_ids: set[str] = set()

    while queue:
        current_id, depth = queue.popleft()
        if depth >= MAX_HOPS or (current_id, depth) in expanded:
            continue
        expanded.add((current_id, depth))
        current_work = litnet.resolve_by_openalex_id(current_id)
        if not current_work:
            continue
        candidates: list[tuple[dict[str, Any], str]] = []
        for work in litnet.resolve_reference_batch(current_work.get("referenced_works") or []):
            candidates.append((work, "cites"))
        for work in litnet.fetch_forward_citations(current_id, set(), "zotero_pdf_all", MAX_FORWARD_CITATIONS_PER_WORK):
            candidates.append((work, "cited_by"))

        for work, direction in candidates:
            doi = norm_doi(work.get("doi") or "")
            z_item = zotero_by_doi.get(doi) or zotero_by_title.get(norm_title(work.get("display_name") or ""))
            child = record_for_work(work, cfg, hop=depth + 1, seed=False, discovered_from=current_id, zotero_item=z_item)
            child_id = child["work_id"]
            if child_id not in records:
                if child.get("has_pdf") == "true":
                    note_path = write_new_note(child, existing_paths)
                    child["note_path"] = str(note_path)
                    child["note_type"] = "full_text"
                    child["summary_status"] = "not_started"
                    new_pdf_records.append({key: child.get(key, "") for key in MASTER_COLUMNS})
                else:
                    child["note_path"] = ""
                    child["note_type"] = "none"
                    child["summary_status"] = "waiting_for_pdf"
                records[child_id] = {key: child.get(key, "") for key in MASTER_COLUMNS}
                added_connected_ids.add(child_id)
            else:
                records[child_id] = merge_preserving_summary(records[child_id], child)

            if direction == "cites":
                edge = (current_id, child_id, "cites")
                discovered_hop = depth + 1
            else:
                edge = (child_id, current_id, "cites")
                discovered_hop = depth + 1
            if edge not in edge_seen:
                edge_rows.append({
                    "source_work_id": edge[0],
                    "target_work_id": edge[1],
                    "edge_type": edge[2],
                    "discovered_in_hop": discovered_hop,
                })
                edge_seen.add(edge)

            if depth + 1 < MAX_HOPS:
                queue.append((child_id, depth + 1))

    new_master_rows = [{field: rec.get(field, "") for field in master_fields} for rec in records.values()]
    new_master_rows.sort(key=lambda r: (int(r.get("hop_distance") or 99), str(r.get("year", "")), str(r.get("title", ""))))
    write_csv_rows(master_path, new_master_rows, master_fields)
    write_csv_rows(edges_path, edge_rows, edge_fields)

    pdf_by_work = {row.get("work_id", ""): dict(row) for row in pdf_rows if row.get("work_id")}
    for rec in records.values():
        pdf_by_work[rec.get("work_id", "")] = {
            "work_id": rec.get("work_id", ""),
            "title": rec.get("title", ""),
            "authors": rec.get("authors", ""),
            "year": rec.get("year", ""),
            "journal": rec.get("journal", ""),
            "zotero_item_key": rec.get("zotero_item_key", ""),
            "has_pdf": rec.get("has_pdf", "false"),
            "pdf_status": rec.get("pdf_status", ""),
            "last_seen_attachment_path": rec.get("pdf_path", ""),
            "pdf_source": rec.get("pdf_source", ""),
        }
    write_csv_rows(pdf_path, list(pdf_by_work.values()), pdf_fields)

    write_csv_rows(RUN_DIR / "new_pdf_records.csv", new_pdf_records, MASTER_COLUMNS)
    write_csv_rows(RUN_DIR / "unresolved_zotero_items.csv", unresolved, ["zotero_item_key", "title", "doi", "reason"])

    report = {
        "generated_at": now_iso(),
        "zotero_pdf_items_missing_from_network": len(missing_items),
        "zotero_duplicate_pdf_items": duplicate_zotero_count,
        "new_pdf_records_added": len(new_pdf_records),
        "new_connected_records_added": len(added_connected_ids),
        "total_master_records_after": len(new_master_rows),
        "total_edges_after": len(edge_rows),
        "max_hops": MAX_HOPS,
        "max_forward_citations_per_work": MAX_FORWARD_CITATIONS_PER_WORK,
        "new_pdf_records_path": str(RUN_DIR / "new_pdf_records.csv"),
        "unresolved_zotero_items_path": str(RUN_DIR / "unresolved_zotero_items.csv"),
        "backups_dir": str(VAULT_ROOT / "data" / "backups" / RUN_LABEL),
    }
    (RUN_DIR / "expansion_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
