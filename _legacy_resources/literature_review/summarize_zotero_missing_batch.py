#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

REVIEW_SCRIPT_DIR = Path("/Users/gabrielsgaspar/.codex/skills/literature-review/scripts")
sys.path.insert(0, str(REVIEW_SCRIPT_DIR))

from common import (  # noqa: E402
    batch_create,
    batch_retrieve,
    batch_upload_jsonl,
    file_content,
    gather_context_text,
    get_paths,
    iso_now,
    load_config,
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
RUN_LABEL = "zotero-missing-two-hop-20260501"
EXPANSION_DIR = VAULT_ROOT / "data" / "literature_review" / RUN_LABEL
CONFIG_PATH = Path("resources/literature_review/zotero_missing_summary_config.yaml")


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def write_config() -> dict[str, Any]:
    cfg = {
        "vault_root": str(VAULT_ROOT),
        "zotero_root": "/Users/gabrielsgaspar/Zotero",
        "research_description": (
            "The paper studies biometric voter registration, voter ID laws, voter composition, "
            "turnout, political representation, institutional trust, electoral integrity, and welfare. "
            "This batch summarizes newly added Zotero PDF-backed papers after a two-hop citation expansion."
        ),
        "context_paths": [
            "/Users/gabrielsgaspar/Projects/bioimetric-voting/paper/sections/literature2.tex",
            "/Users/gabrielsgaspar/Projects/bioimetric-voting/paper/references/references2.bib",
        ],
        "review_output_path": "/tmp/zotero_missing_unused_review.tex",
        "bib_output_path": "/tmp/zotero_missing_unused_refs.bib",
        "additions_output_path": "/tmp/zotero_missing_unused_additions.csv",
        "api_mode": "batch_wait",
        "summary_model": "gpt-4o-mini",
        "review_model": "gpt-4o-mini",
        "max_relevant_papers": 10,
        "max_review_papers": 10,
        "max_openalex_additions": 0,
        "relevance_threshold": 0.0,
        "min_verified_papers_for_review": 0,
        "batch_completion_window": "24h",
        "batch_poll_seconds": 20,
        "batch_max_wait_seconds": 1800,
        "accepted_api_summary_status_prefixes": ["api_structured", "llm_structured"],
        "review_run_label": RUN_LABEL + "-api-summary",
        "prefer_existing_network": True,
        "openalex_mailto": "",
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return cfg


def load_records() -> list[dict[str, Any]]:
    rows = read_csv(EXPANSION_DIR / "new_pdf_records.csv")
    rows = [row for row in rows if row.get("work_id") and Path(row.get("note_path", "")).exists()]
    return rows


def usage_from_output(path: Path) -> dict[str, int]:
    usage = Counter()
    if not path.exists():
        return dict(usage)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        body = json.loads(line).get("response", {}).get("body", {})
        item_usage = body.get("usage") or {}
        for key in ["input_tokens", "output_tokens", "total_tokens"]:
            usage[key] += int(item_usage.get(key) or 0)
    return dict(usage)


def main() -> None:
    load_dotenv(Path(".env"), override=False)
    cfg = load_config(CONFIG_PATH) if CONFIG_PATH.exists() else load_config(write_config_path())


def write_config_path() -> Path:
    write_config()
    return CONFIG_PATH


if __name__ == "__main__":
    load_dotenv(Path(".env"), override=False)
    write_config()
    cfg = load_config(CONFIG_PATH)
    paths = get_paths(cfg)
    records = load_records()
    if not records:
        raise SystemExit("No new PDF records found to summarize.")
    cache = load_openai_file_cache(paths["openai_file_cache"])
    requests = build_batch_requests(records, cache, str(cfg["summary_model"]), gather_context_text(cfg))
    write_batch_jsonl(paths["batch_input"], requests)
    save_openai_file_cache(paths["openai_file_cache"], cache)
    uploaded = batch_upload_jsonl(paths["batch_input"])
    batch = batch_create(uploaded["id"], endpoint="/v1/responses", completion_window=str(cfg["batch_completion_window"]))
    paths["batch_state"].write_text(json.dumps(batch, indent=2), encoding="utf-8")
    print(f"Submitted batch {batch['id']} with {len(requests)} requests.")
    deadline = time.time() + int(cfg["batch_max_wait_seconds"])
    while time.time() < deadline:
        state = batch_retrieve(batch["id"])
        paths["batch_state"].write_text(json.dumps(state, indent=2), encoding="utf-8")
        print("Batch status:", state.get("status"), state.get("request_counts"))
        if state.get("status") == "completed":
            output = file_content(state["output_file_id"]) if state.get("output_file_id") else ""
            paths["batch_output"].write_text(output, encoding="utf-8")
            error = file_content(state["error_file_id"]) if state.get("error_file_id") else ""
            if error:
                paths["batch_error"].write_text(error, encoding="utf-8")
            by_id = {row.get("work_id"): row for row in records}
            applied = 0
            for line in output.splitlines():
                if not line.strip():
                    continue
                custom_id, parsed = parse_batch_output_line(line)
                record = by_id.get(custom_id)
                if not record:
                    continue
                apply_summary(paths, record, parsed, str(cfg["summary_model"]))
                applied += 1
            usage = usage_from_output(paths["batch_output"])
            estimated_cost = usage.get("input_tokens", 0) / 1_000_000 * 0.075 + usage.get("output_tokens", 0) / 1_000_000 * 0.30
            report = {
                "generated_at": iso_now(),
                "records_submitted": len(records),
                "api_summaries_applied": applied,
                "batch_id": state.get("id"),
                "request_counts": state.get("request_counts"),
                "batch_usage_tokens": usage,
                "estimated_batch_summary_cost_usd": round(estimated_cost, 4),
                "cost_note": "Rough estimate using common gpt-4o-mini Batch API rates; actual account billing may differ.",
                "batch_state_path": str(paths["batch_state"]),
                "batch_output_path": str(paths["batch_output"]),
            }
            (paths["run_dir"] / "summary_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2))
            raise SystemExit(0)
        if state.get("status") in {"failed", "cancelled", "expired"}:
            raise RuntimeError(f"Batch ended with status {state.get('status')}")
        time.sleep(int(cfg["batch_poll_seconds"]))
    raise TimeoutError("Batch did not finish before timeout.")
