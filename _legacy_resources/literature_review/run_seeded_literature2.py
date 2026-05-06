#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from rapidfuzz import fuzz, process

SKILL_SCRIPT_DIR = Path("/Users/gabrielsgaspar/.codex/skills/literature-review/scripts")
sys.path.insert(0, str(SKILL_SCRIPT_DIR))

from common import (  # noqa: E402
    REVIEW_DATA_COLUMNS,
    batch_create,
    batch_retrieve,
    batch_upload_jsonl,
    discover_notes,
    ensure_bibtex,
    file_content,
    get_paths,
    iso_now,
    load_config,
    load_master_index,
    load_note,
    merge_note_with_master,
    note_has_verified_api_summary,
    read_csv,
    save_openai_file_cache,
    text_profile,
    write_csv,
)
from ensure_api_summaries import (  # noqa: E402
    apply_summary,
    build_batch_requests,
    load_openai_file_cache,
    parse_batch_output_line,
    write_batch_jsonl,
)
from generate_review import (  # noqa: E402
    additions_candidates,
    build_review_payload,
    render_latex,
    write_references_bib,
)


SEED_BIB = Path("paper/references/references.bib")

# Seed papers that directly speak to the project's substantive literatures.
# Estimator, data-source, and very distant theory references stay in the seed
# audit, but are not candidates for the final literature review.
RELEVANT_SEED_CITEKEYS = {
    "forquesatoRodrigues2023",
    "Fujiwara2015VotingTechnoloPolitica",
    "Zucco2016TradingOldErrors",
    "Muralidharan2016BuildingStateCapacity",
    "Bossuroy2024BiometriMonitoriService",
    "Fraga2021WhoVoterLaws",
    "Hajnal2017VoterIdentifiLaws",
    "Grimmer2021TheDurableDifferen",
    "Ansolabehere2005TheIntroducVoter",
    "Rosenstone1978TheEffectRegistra",
    "Nagler1991TheEffectRegistra",
    "Holbein2014MakingYoungVoters",
    "Kim2022AutomatiVoterReregist",
    "Hajnal2005WhereTurnoutMatters",
    "cox2015",
    "frankMartinezComa2023",
    "gaeblerEtAl2020",
    "Marx2021VoterMobilisaAnd",
    "Bubeck2017ProcessCandidatThe",
    "Ferrer2023HowPartisanLocal",
    "ferrazFinan2011",
    "Karim2025VoterBuyingPolitici",
    "Deshpande2019WhoScreenedOut",
    "Nichols1982TargetinTransferThrough",
    "Borgers2004CostlyVoting",
    "Krasa2008MandatorVotingBetter",
    "Meltzer1981RationalTheoryThe",
    "besleyCoate1997",
}


def split_bib_entries(text: str) -> list[str]:
    entries: list[str] = []
    idx = 0
    while True:
        at = text.find("@", idx)
        if at < 0:
            break
        brace = text.find("{", at)
        if brace < 0:
            break
        depth = 0
        pos = brace
        while pos < len(text):
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
                if depth == 0:
                    entries.append(text[at : pos + 1])
                    idx = pos + 1
                    break
            pos += 1
        else:
            break
    return entries


def parse_bib_entry(entry: str) -> dict[str, str]:
    match = re.match(r"@\w+\s*\{\s*([^,]+),", entry, flags=re.S)
    citekey = match.group(1).strip() if match else ""
    body = entry[entry.find(",") + 1 : -1]
    fields: dict[str, str] = {}
    pos = 0
    while pos < len(body):
        field_match = re.search(r"([A-Za-z][A-Za-z0-9_\-]*)\s*=\s*", body[pos:])
        if not field_match:
            break
        name = field_match.group(1).lower()
        start = pos + field_match.end()
        while start < len(body) and body[start].isspace():
            start += 1
        if start >= len(body):
            break
        if body[start] == "{":
            depth = 0
            end = start
            while end < len(body):
                if body[end] == "{":
                    depth += 1
                elif body[end] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                end += 1
            value = body[start + 1 : end]
            pos = end + 1
        elif body[start] == '"':
            end = start + 1
            while end < len(body) and body[end] != '"':
                end += 1
            value = body[start + 1 : end]
            pos = end + 1
        else:
            end = start
            while end < len(body) and body[end] not in ",\n":
                end += 1
            value = body[start:end]
            pos = end
        fields[name] = re.sub(r"\s+", " ", value.replace("\n", " ")).strip()
    return {"citekey": citekey, "bibtex_entry": entry.strip(), **fields}


def normalize_text(value: str) -> str:
    text = (value or "").lower()
    text = re.sub(r"\\['`^\"~=.cCvVuHkKrR]\{?([a-zA-Z])\}?", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", text)
    text = re.sub(r"[{}\\]", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def load_seed_entries() -> list[dict[str, str]]:
    return [parse_bib_entry(entry) for entry in split_bib_entries(SEED_BIB.read_text(encoding="utf-8"))]


def load_network_records(paths: dict[str, Path]) -> list[dict[str, Any]]:
    _, _, by_note = load_master_index(paths)
    records: list[dict[str, Any]] = []
    for note_path in discover_notes(paths["vault_root"]):
        note = load_note(note_path)
        record = merge_note_with_master(note, by_note.get(str(note_path.resolve())))
        bibtex, citekey = ensure_bibtex(record, record.get("bibtex", ""))
        record["citekey"] = citekey
        record["bibtex"] = bibtex
        record["normalized_title"] = normalize_text(str(record.get("title", "")))
        records.append(record)
    return records


def match_seed_to_network(seed_entries: list[dict[str, str]], records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_doi = {normalize_text(str(r.get("doi", ""))): r for r in records if normalize_text(str(r.get("doi", "")))}
    by_citekey = {str(r.get("citekey", "")): r for r in records if r.get("citekey")}
    title_choices = [(r["normalized_title"], r) for r in records if r.get("normalized_title")]

    matched_rows: list[dict[str, Any]] = []
    for seed in seed_entries:
        record = None
        match_method = "missing"
        match_score = 0.0
        seed_doi = normalize_text(seed.get("doi", ""))
        seed_title = normalize_text(seed.get("title", ""))
        if seed_doi and seed_doi in by_doi:
            record = by_doi[seed_doi]
            match_method = "doi"
            match_score = 100.0
        elif seed.get("citekey") in by_citekey:
            record = by_citekey[seed["citekey"]]
            match_method = "citekey"
            match_score = 100.0
        elif seed_title and title_choices:
            best = process.extractOne(seed_title, [choice[0] for choice in title_choices], scorer=fuzz.token_set_ratio)
            if best and float(best[1]) >= 82:
                record = title_choices[int(best[2])][1]
                match_method = "title_fuzzy"
                match_score = float(best[1])

        row: dict[str, Any] = {
            "seed_citekey": seed.get("citekey", ""),
            "seed_title": seed.get("title", ""),
            "seed_year": seed.get("year", ""),
            "match_method": match_method,
            "match_score": f"{match_score:.1f}",
            "selected_relevant": str(seed.get("citekey", "") in RELEVANT_SEED_CITEKEYS).lower(),
        }
        if record:
            row.update({
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
                "summary_generated_at": record.get("summary_generated_at", ""),
                "bibtex": record.get("bibtex", ""),
                "_record": record,
            })
        matched_rows.append(row)
    return matched_rows


def selected_records(matched_rows: list[dict[str, Any]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    topic_counter = text_profile(cfg.get("research_description", ""))
    records: list[dict[str, Any]] = []
    for row in matched_rows:
        if row.get("selected_relevant") != "true" or "_record" not in row:
            continue
        record = dict(row["_record"])
        record["seed_citekey"] = row["seed_citekey"]
        record["seed_title"] = row["seed_title"]
        text = " ".join([
            str(record.get("title", "")),
            str(record.get("journal", "")),
            str(record.get("sections", {}).get("Summary", "")),
            str(record.get("sections", {}).get("Research Question", "")),
            str(record.get("sections", {}).get("Contribution", "")),
            str(record.get("sections", {}).get("Key Findings", "")),
        ])
        record["topic_score"] = 1.0 if not text.strip() else min(1.0, len(set(text_profile(text)) & set(topic_counter)) / 25)
        record["centrality_score"] = float(record.get("cited_by_count") or 0) / 5000
        record["relevance_score"] = 0.7 * float(record["topic_score"]) + 0.3 * min(1.0, float(record["centrality_score"]))
        records.append(record)
    records.sort(key=lambda r: (str(r.get("seed_citekey", "")) not in {
        "forquesatoRodrigues2023",
        "Fraga2021WhoVoterLaws",
        "Hajnal2017VoterIdentifiLaws",
        "Grimmer2021TheDurableDifferen",
        "Fujiwara2015VotingTechnoloPolitica",
        "Zucco2016TradingOldErrors",
        "Muralidharan2016BuildingStateCapacity",
        "Marx2021VoterMobilisaAnd",
    }, -float(r.get("relevance_score", 0.0))))
    return records


def write_seed_artifacts(paths: dict[str, Path], matched_rows: list[dict[str, Any]], records: list[dict[str, Any]], accepted: list[str]) -> None:
    run_dir = paths["run_dir"]
    audit_rows = []
    for row in matched_rows:
        out = {k: v for k, v in row.items() if not k.startswith("_") and k != "bibtex"}
        audit_rows.append(out)
    write_csv(run_dir / "seed_match_audit.csv", audit_rows)

    selected_rows = []
    for record in records:
        verified = note_has_verified_api_summary(record, accepted)
        selected_rows.append({
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
            "summary_verified": str(verified).lower(),
            "summary_generated_at": record.get("summary_generated_at", ""),
            "relevance_score": f"{float(record.get('relevance_score', 0.0)):.6f}",
            "topic_score": f"{float(record.get('topic_score', 0.0)):.6f}",
            "centrality_score": f"{float(record.get('centrality_score', 0.0)):.6f}",
            "selected_for_review": "true",
        })
    write_csv(paths["selected_papers"], selected_rows, REVIEW_DATA_COLUMNS)


def queue_records(records: list[dict[str, Any]], accepted: list[str]) -> list[dict[str, Any]]:
    queue = []
    for record in records:
        if note_has_verified_api_summary(record, accepted):
            continue
        pdf_path = str(record.get("pdf_path", "")).strip()
        if pdf_path and Path(pdf_path).expanduser().exists():
            queue.append(record)
    return queue


def run_batch(cfg: dict[str, Any], paths: dict[str, Path], queue: list[dict[str, Any]]) -> int:
    if not queue:
        write_csv(paths["summary_jobs"], [])
        return 0

    summary_jobs = [{
        "work_id": r.get("work_id", ""),
        "title": r.get("title", ""),
        "note_path": r.get("note_path", ""),
        "pdf_path": r.get("pdf_path", ""),
        "summary_status_before": r.get("summary_status", ""),
        "summary_model_before": r.get("summary_model", ""),
        "queued_for_api_refresh": "true",
    } for r in queue]
    write_csv(paths["summary_jobs"], summary_jobs, [
        "work_id", "title", "note_path", "pdf_path",
        "summary_status_before", "summary_model_before", "queued_for_api_refresh",
    ])

    from common import gather_context_text

    model = str(cfg.get("summary_model", "gpt-4o-mini"))
    cache = load_openai_file_cache(paths["openai_file_cache"])
    requests = build_batch_requests(queue, cache, model, gather_context_text(cfg))
    write_batch_jsonl(paths["batch_input"], requests)
    save_openai_file_cache(paths["openai_file_cache"], cache)
    uploaded = batch_upload_jsonl(paths["batch_input"])
    batch = batch_create(uploaded["id"], endpoint="/v1/responses", completion_window=str(cfg.get("batch_completion_window", "24h")))
    paths["batch_state"].write_text(json.dumps(batch, indent=2), encoding="utf-8")
    print(f"Submitted batch {batch['id']} with {len(requests)} requests.")

    deadline = time.time() + int(cfg.get("batch_max_wait_seconds", 1800))
    poll_seconds = int(cfg.get("batch_poll_seconds", 30))
    while time.time() < deadline:
        state = batch_retrieve(batch["id"])
        paths["batch_state"].write_text(json.dumps(state, indent=2), encoding="utf-8")
        status = state.get("status")
        print(f"Batch status: {status}")
        if status == "completed":
            output_file_id = state.get("output_file_id")
            if not output_file_id:
                raise RuntimeError("Completed batch has no output_file_id.")
            content = file_content(output_file_id)
            paths["batch_output"].write_text(content, encoding="utf-8")
            work_index = {(r.get("work_id") or Path(r["note_path"]).stem.replace(" ", "_")): r for r in queue}
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
        if status in {"failed", "cancelled", "expired"}:
            raise RuntimeError(f"Batch ended with status {status}")
        time.sleep(poll_seconds)
    print(f"Batch still running: {batch['id']}")
    return 0


def bibtex_from_openalex_addition(row: dict[str, Any]) -> str:
    author = str(row.get("authors", "")).replace(";", " and")
    title = str(row.get("title", ""))
    year = str(row.get("year", ""))
    journal = str(row.get("journal", ""))
    doi = str(row.get("doi", ""))
    lastname = re.sub(r"[^A-Za-z0-9]", "", (author.split(" and ")[0].split()[-1] if author else "Work"))
    first_title_word = re.sub(r"[^A-Za-z0-9]", "", (title.split()[0] if title else "Paper"))
    key = f"{lastname}{year}{first_title_word}"
    fields = [f"@article{{{key},", f"  title = {{{title}}},"]
    if author:
        fields.append(f"  author = {{{author}}},")
    if year:
        fields.append(f"  year = {{{year}}},")
    if journal:
        fields.append(f"  journal = {{{journal}}},")
    if doi:
        fields.append(f"  doi = {{{doi}}},")
    fields.append("}")
    return "\n".join(fields)


def append_recommended_additions_to_bib(paths: dict[str, Path], max_additions: int = 10) -> int:
    additions = read_csv(paths["additions_output"])[:max_additions]
    if not additions:
        return 0
    existing = paths["bib_output"].read_text(encoding="utf-8") if paths["bib_output"].exists() else ""
    extra_entries = [bibtex_from_openalex_addition(row) for row in additions]
    paths["bib_output"].write_text(existing.rstrip() + "\n\n% Recommended additions from OpenAlex\n\n" + "\n\n".join(extra_entries) + "\n", encoding="utf-8")
    return len(extra_entries)


def refresh_records(paths: dict[str, Path], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    seed_entries = load_seed_entries()
    records = load_network_records(paths)
    matched = match_seed_to_network(seed_entries, records)
    selected = selected_records(matched, cfg)
    accepted = list(cfg.get("accepted_api_summary_status_prefixes", []))
    write_seed_artifacts(paths, matched, selected, accepted)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--skip-summaries", action="store_true")
    args = parser.parse_args()

    load_dotenv(Path(".env"), override=False)
    cfg = load_config(args.config)
    paths = get_paths(cfg)
    paths["run_dir"].mkdir(parents=True, exist_ok=True)

    selected = refresh_records(paths, cfg)
    accepted = list(cfg.get("accepted_api_summary_status_prefixes", []))
    queue = queue_records(selected, accepted)
    before_verified = sum(note_has_verified_api_summary(record, accepted) for record in selected)
    print(f"Selected seed-network papers: {len(selected)}")
    print(f"Verified before refresh: {before_verified}")
    print(f"Queued for API refresh: {len(queue)}")
    if args.audit_only:
        return

    applied = 0
    if not args.skip_summaries:
        applied = run_batch(cfg, paths, queue)

    # Reload notes after API refreshes, then write the review from verified papers only.
    selected = refresh_records(paths, cfg)
    verified = [record for record in selected if note_has_verified_api_summary(record, accepted)]
    verified.sort(key=lambda r: (str(r.get("seed_citekey", "")) not in {
        "forquesatoRodrigues2023",
        "Fraga2021WhoVoterLaws",
        "Hajnal2017VoterIdentifiLaws",
        "Grimmer2021TheDurableDifferen",
        "Fujiwara2015VotingTechnoloPolitica",
        "Zucco2016TradingOldErrors",
        "Muralidharan2016BuildingStateCapacity",
        "Marx2021VoterMobilisaAnd",
    }, -float(r.get("relevance_score", 0.0))))
    verified = verified[: int(cfg.get("max_review_papers", 22))]
    if len(verified) < int(cfg.get("min_verified_papers_for_review", 8)):
        raise RuntimeError(f"Only {len(verified)} verified seed papers available after refresh.")

    payload = build_review_payload(cfg, verified)
    latex_text, citekeys = render_latex(payload)
    paths["review_output"].write_text(latex_text, encoding="utf-8")
    write_references_bib(paths["bib_output"], verified, citekeys)

    additions = additions_candidates(cfg, verified)
    write_csv(paths["additions_output"], additions, [
        "openalex_id", "openalex_url", "title", "journal", "authors", "year", "doi", "score", "source_reason",
    ])
    addition_bib_count = append_recommended_additions_to_bib(paths, max_additions=min(10, len(additions)))

    report = {
        "generated_at": iso_now(),
        "seed_entries": len(load_seed_entries()),
        "selected_seed_network_papers": len(selected),
        "verified_before_refresh": before_verified,
        "api_summaries_applied": applied,
        "verified_used_for_review_input": len(verified),
        "citekeys_used_in_literature_review": citekeys,
        "recommended_additions": len(additions),
        "recommended_additions_appended_to_bib": addition_bib_count,
        "review_output_path": str(paths["review_output"]),
        "bib_output_path": str(paths["bib_output"]),
        "additions_output_path": str(paths["additions_output"]),
    }
    (paths["run_dir"] / "seeded_review_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
