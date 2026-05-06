#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv

SKILL_SCRIPT_DIR = Path("/Users/gabrielsgaspar/.codex/skills/literature-review/scripts")
sys.path.insert(0, str(SKILL_SCRIPT_DIR))

from common import (  # noqa: E402
    REVIEW_DATA_COLUMNS,
    batch_create,
    batch_retrieve,
    batch_upload_jsonl,
    compute_centrality,
    file_content,
    get_paths,
    iso_now,
    load_config,
    load_master_index,
    load_note,
    merge_note_with_master,
    note_has_verified_api_summary,
    read_csv,
    write_csv,
)
from ensure_api_summaries import (  # noqa: E402
    apply_summary,
    build_batch_requests,
    load_openai_file_cache,
    parse_batch_output_line,
    save_openai_file_cache,
    write_batch_jsonl,
)


VAULT_ROOT = Path("/Users/gabrielsgaspar/Library/Mobile Documents/iCloud~md~obsidian/Documents/Research")
ZOTERO_ROOT = Path("/Users/gabrielsgaspar/Zotero")
PREVIOUS_RUN = VAULT_ROOT / "data" / "literature_review" / "literature2-seed-references"
SEED_SELECTED = PREVIOUS_RUN / "selected_papers.csv"
RUN_LABEL = "literature2-connected-50-api"
CONFIG_PATH = Path("resources/literature_review/connected_50_config.yaml")


RESEARCH_CONTEXT = """
The paper studies the impact of biometric voter registration in Brazil on voter
composition, voting, trust in institutions, institutional legitimacy, and
welfare. This follow-up batch should summarize papers that are citation-connected
to the papers used in the literature review, prioritizing election
administration, voter registration costs, voter ID laws, turnout, composition,
representation, welfare, state capacity, and institutional trust.
"""


def write_config() -> dict[str, Any]:
    cfg = {
        "vault_root": str(VAULT_ROOT),
        "zotero_root": str(ZOTERO_ROOT),
        "research_description": RESEARCH_CONTEXT.strip(),
        "context_paths": ["paper/sections/literature2.tex", "paper/references/references2.bib"],
        "review_output_path": "/tmp/connected_50_unused_review.tex",
        "bib_output_path": "/tmp/connected_50_unused_refs.bib",
        "additions_output_path": "/tmp/connected_50_unused_additions.csv",
        "api_mode": "batch_wait",
        "summary_model": "gpt-4o-mini",
        "review_model": "gpt-4o-mini",
        "max_relevant_papers": 50,
        "max_review_papers": 0,
        "max_openalex_additions": 0,
        "relevance_threshold": 0.0,
        "min_verified_papers_for_review": 0,
        "batch_completion_window": "24h",
        "batch_poll_seconds": 30,
        "batch_max_wait_seconds": 7200,
        "force_resummarize_statuses": ["local_structured_draft_no_llm_key", "not_started"],
        "accepted_api_summary_status_prefixes": ["api_structured", "llm_structured"],
        "review_run_label": RUN_LABEL,
        "prefer_existing_network": True,
        "openalex_mailto": "",
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return cfg


def load_seed_work_ids() -> set[str]:
    if not SEED_SELECTED.exists():
        raise FileNotFoundError(f"Missing previous literature selection file: {SEED_SELECTED}")
    seeds = pd.read_csv(SEED_SELECTED)
    ids = {str(x).strip() for x in seeds["work_id"].dropna() if str(x).strip()}
    if not ids:
        raise RuntimeError(f"No seed work IDs found in {SEED_SELECTED}")
    return ids


def graph_distances(edges_path: Path, seed_ids: set[str]) -> dict[str, int]:
    adjacency: dict[str, set[str]] = {}
    for row in read_csv(edges_path):
        src = (row.get("source_work_id") or row.get("source") or row.get("from_work_id") or "").strip()
        dst = (row.get("target_work_id") or row.get("target") or row.get("to_work_id") or "").strip()
        if not src or not dst:
            continue
        adjacency.setdefault(src, set()).add(dst)
        adjacency.setdefault(dst, set()).add(src)

    distance: dict[str, int] = {}
    queue: deque[str] = deque()
    for seed in seed_ids:
        if seed in adjacency:
            distance[seed] = 0
            queue.append(seed)

    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, ()):
            if neighbor not in distance:
                distance[neighbor] = distance[current] + 1
                queue.append(neighbor)
    return distance


def load_records(paths: dict[str, Path]) -> list[dict[str, Any]]:
    _, _, by_note = load_master_index(paths)
    records: list[dict[str, Any]] = []
    for note_path in sorted(paths["papers_dir"].glob("*.md")):
        note = load_note(note_path)
        records.append(merge_note_with_master(note, by_note.get(str(note_path.resolve()))))
    return records


def select_connected_records(cfg: dict[str, Any], paths: dict[str, Path], limit: int) -> list[dict[str, Any]]:
    accepted = list(cfg.get("accepted_api_summary_status_prefixes", []))
    seed_ids = load_seed_work_ids()
    distances = graph_distances(paths["citation_edges"], seed_ids)
    centrality = compute_centrality(paths)
    records = load_records(paths)
    candidates: list[dict[str, Any]] = []

    for record in records:
        work_id = str(record.get("work_id", "")).strip()
        note_path = Path(str(record.get("note_path", ""))).expanduser()
        pdf_path = Path(str(record.get("pdf_path", ""))).expanduser()
        if not work_id or work_id not in distances:
            continue
        if work_id in seed_ids:
            continue
        if note_has_verified_api_summary(record, accepted):
            continue
        if not note_path.exists() or not pdf_path.exists():
            continue
        record["graph_distance_from_literature2"] = distances[work_id]
        record["centrality_score"] = centrality.get(work_id, 0.0)
        record["relevance_score"] = 1 / (1 + distances[work_id]) + 0.05 * float(record["centrality_score"])
        candidates.append(record)

    candidates.sort(
        key=lambda r: (
            int(r.get("graph_distance_from_literature2", 999)),
            -float(r.get("centrality_score", 0.0)),
            str(r.get("summary_status", "")) == "not_started",
            str(r.get("title", "")),
        )
    )
    return candidates[:limit]


def write_selection(paths: dict[str, Path], records: list[dict[str, Any]]) -> None:
    rows = []
    for record in records:
        rows.append({
            "work_id": record.get("work_id", ""),
            "title": record.get("title", ""),
            "authors": record.get("authors", ""),
            "year": record.get("year", ""),
            "journal": record.get("journal", ""),
            "doi": record.get("doi", ""),
            "openalex_id": record.get("openalex_id", ""),
            "note_path": record.get("note_path", ""),
            "pdf_path": record.get("pdf_path", ""),
            "summary_status": record.get("summary_status", ""),
            "summary_model": record.get("summary_model", ""),
            "summary_source": record.get("summary_source", ""),
            "summary_verified": "false",
            "summary_generated_at": record.get("summary_generated_at", ""),
            "relevance_score": f"{float(record.get('relevance_score', 0.0)):.6f}",
            "topic_score": "",
            "centrality_score": f"{float(record.get('centrality_score', 0.0)):.6f}",
            "selected_for_review": "false",
            "graph_distance_from_literature2": record.get("graph_distance_from_literature2", ""),
        })
    write_csv(paths["selected_papers"], rows, REVIEW_DATA_COLUMNS + ["graph_distance_from_literature2"])

    jobs = [{
        "work_id": r.get("work_id", ""),
        "title": r.get("title", ""),
        "note_path": r.get("note_path", ""),
        "pdf_path": r.get("pdf_path", ""),
        "graph_distance_from_literature2": r.get("graph_distance_from_literature2", ""),
        "summary_status_before": r.get("summary_status", ""),
        "summary_model_before": r.get("summary_model", ""),
        "queued_for_api_refresh": "true",
    } for r in records]
    write_csv(paths["summary_jobs"], jobs)


def run_batch(cfg: dict[str, Any], paths: dict[str, Path], records: list[dict[str, Any]]) -> int:
    from common import gather_context_text

    model = str(cfg.get("summary_model", "gpt-4o-mini"))
    cache = load_openai_file_cache(paths["openai_file_cache"])
    requests = build_batch_requests(records, cache, model, gather_context_text(cfg))
    write_batch_jsonl(paths["batch_input"], requests)
    save_openai_file_cache(paths["openai_file_cache"], cache)

    uploaded = batch_upload_jsonl(paths["batch_input"])
    batch = batch_create(uploaded["id"], endpoint="/v1/responses", completion_window=str(cfg.get("batch_completion_window", "24h")))
    paths["batch_state"].write_text(json.dumps(batch, indent=2), encoding="utf-8")
    print(f"Submitted batch {batch['id']} with {len(requests)} requests.")

    deadline = time.time() + int(cfg.get("batch_max_wait_seconds", 7200))
    poll_seconds = int(cfg.get("batch_poll_seconds", 30))
    while time.time() < deadline:
        state = batch_retrieve(batch["id"])
        paths["batch_state"].write_text(json.dumps(state, indent=2), encoding="utf-8")
        print("Batch status:", state.get("status"), state.get("request_counts"))
        if state.get("status") == "completed":
            output_file_id = state.get("output_file_id")
            if not output_file_id:
                raise RuntimeError("Completed batch has no output_file_id.")
            content = file_content(output_file_id)
            paths["batch_output"].write_text(content, encoding="utf-8")
            work_index = {(r.get("work_id") or Path(r["note_path"]).stem.replace(" ", "_")): r for r in records}
            applied = 0
            for line in content.splitlines():
                if not line.strip():
                    continue
                custom_id, parsed = parse_batch_output_line(line)
                record = work_index.get(custom_id)
                if not record:
                    continue
                apply_summary(paths, record, parsed, model)
                applied += 1
            return applied
        if state.get("status") in {"failed", "cancelled", "expired"}:
            raise RuntimeError(f"Batch ended with status {state.get('status')}")
        time.sleep(poll_seconds)

    raise TimeoutError(f"Batch did not finish within wait limit. Resume from {paths['batch_state']}")


def summarize_usage(paths: dict[str, Path]) -> dict[str, int]:
    usage = Counter()
    if not paths["batch_output"].exists():
        return dict(usage)
    for line in paths["batch_output"].read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        body = json.loads(line).get("response", {}).get("body", {})
        item_usage = body.get("usage") or {}
        for key in ["input_tokens", "output_tokens", "total_tokens"]:
            usage[key] += int(item_usage.get(key) or 0)
    return dict(usage)


def verify_updated(paths: dict[str, Path], records: list[dict[str, Any]]) -> dict[str, Any]:
    refreshed = []
    failures = []
    for record in records:
        note_path = Path(str(record.get("note_path", "")))
        note = load_note(note_path)
        status = str(note.frontmatter.get("summary_status", ""))
        model = str(note.frontmatter.get("summary_model", ""))
        verified = str(note.frontmatter.get("summary_verified", "")).lower() in {"true", "1", "yes"}
        source = str(note.frontmatter.get("summary_source", ""))
        if status == "api_structured_verified" and model == "gpt-4o-mini" and verified and source == "openai_api_responses":
            refreshed.append(str(note_path))
        else:
            failures.append({
                "note_path": str(note_path),
                "summary_status": status,
                "summary_model": model,
                "summary_verified": note.frontmatter.get("summary_verified", ""),
                "summary_source": source,
            })
    return {"refreshed": refreshed, "failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()

    load_dotenv(Path(".env"), override=False)
    cfg = write_config()
    cfg = load_config(CONFIG_PATH)
    paths = get_paths(cfg)
    records = select_connected_records(cfg, paths, args.limit)
    if len(records) < args.limit:
        raise RuntimeError(f"Only found {len(records)} eligible connected records; requested {args.limit}.")
    write_selection(paths, records)

    print(f"Selected {len(records)} connected non-API notes with PDFs.")
    print("Distance counts:", dict(Counter(int(r["graph_distance_from_literature2"]) for r in records)))
    print("Status counts:", dict(Counter(str(r.get("summary_status", "")) for r in records)))
    if args.audit_only:
        return

    applied = run_batch(cfg, paths, records)
    usage = summarize_usage(paths)
    verification = verify_updated(paths, records)

    estimated_batch_cost = (usage.get("input_tokens", 0) / 1_000_000) * 0.075 + (
        usage.get("output_tokens", 0) / 1_000_000
    ) * 0.30
    report = {
        "generated_at": iso_now(),
        "run_label": RUN_LABEL,
        "selected_count": len(records),
        "api_summaries_applied": applied,
        "distance_counts": dict(Counter(str(r["graph_distance_from_literature2"]) for r in records)),
        "status_counts_before": dict(Counter(str(r.get("summary_status", "")) for r in records)),
        "batch_usage_tokens": usage,
        "estimated_batch_summary_cost_usd": round(estimated_batch_cost, 4),
        "cost_note": "Rough estimate using common gpt-4o-mini Batch API rates; actual account billing may differ.",
        "verification": {
            "refreshed_count": len(verification["refreshed"]),
            "failure_count": len(verification["failures"]),
            "failures": verification["failures"],
        },
        "selected_papers_path": str(paths["selected_papers"]),
        "summary_jobs_path": str(paths["summary_jobs"]),
        "batch_state_path": str(paths["batch_state"]),
        "batch_output_path": str(paths["batch_output"]),
    }
    (paths["run_dir"] / "connected_50_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
