from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.tse_bvr_common import CLEAN_DIR, INTERIM_DIR, ensure_directories


# Manually confirmed within-state spelling variants.
MANUAL_OVERRIDES: dict[tuple[str, str], str] = {
    ("MT", "santo antonio do leverger"): "5107800",
    ("PE", "iguaraci"): "2606903",
    ("RO", "machadinho do oeste"): "1100130",
    ("SE", "amparo de sao francisco"): "2800100",
}
TSE_IBGE_CROSSWALK_PATH = Path("data/raw/ibge/bd-tse_mun_ids.csv")


def _normalize_code(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    return text


def match_rows() -> pd.DataFrame:
    ensure_directories()

    tse = pd.read_csv(INTERIM_DIR / "tse_parsed_rows.csv")
    ibge = pd.read_csv(CLEAN_DIR / "ibge_municipalities.csv", dtype={"municipality_id": str})
    crosswalk = pd.read_csv(TSE_IBGE_CROSSWALK_PATH, dtype=str)
    tse["zone_key"] = tse["zone"].fillna("").astype(str)
    tse["tse_municipality_id"] = tse.get("tse_municipality_id", "").map(_normalize_code)
    crosswalk["year"] = crosswalk["year"].astype(str)
    crosswalk["tse_municipality_id"] = crosswalk["tse_municipality_id"].map(_normalize_code)
    crosswalk["municipality_id"] = crosswalk["municipality_id"].map(_normalize_code)

    review_rows = []
    for _, row in tse.iterrows():
        state_matches = ibge[ibge["state"] == row["state"]].copy()
        exact = state_matches[state_matches["municipality_name"] == row["normalized_name_tse"]]

        matched_name = None
        municipality_id = None
        match_method = None
        confidence = None
        reviewer_notes = ""

        override_key = (row["state"], row["normalized_name_tse"])
        if row["tse_municipality_id"]:
            code_match = crosswalk[
                (crosswalk["year"] == str(int(row["year_first_treat"])))
                & (crosswalk["state"] == row["state"])
                & (crosswalk["tse_municipality_id"] == row["tse_municipality_id"])
            ]
            if len(code_match) == 1:
                municipality_id = code_match.iloc[0]["municipality_id"]
                ibge_row = ibge.loc[ibge["municipality_id"] == municipality_id].iloc[0]
                matched_name = ibge_row["municipality_name"]
                match_method = "direct_tse_code_year"
                confidence = "high"
                reviewer_notes = "Matched via direct TSE municipality code using the year-specific crosswalk."
        if municipality_id is None and override_key in MANUAL_OVERRIDES:
            municipality_id = MANUAL_OVERRIDES[override_key]
            ibge_row = ibge.loc[ibge["municipality_id"] == municipality_id].iloc[0]
            matched_name = ibge_row["municipality_name"]
            match_method = "manual_override"
            confidence = "high"
            reviewer_notes = "Matched via explicit manual override after project-side review confirmed the within-state spelling variant."
        elif municipality_id is None and len(exact) == 1:
            ibge_row = exact.iloc[0]
            municipality_id = ibge_row["municipality_id"]
            matched_name = ibge_row["municipality_name"]
            match_method = "exact_state_normalized_name"
            confidence = "high"
            reviewer_notes = "Exact match on normalized municipality name within state."
        elif municipality_id is None:
            choices = state_matches["municipality_name"].tolist()
            candidate = process.extractOne(row["normalized_name_tse"], choices, scorer=fuzz.ratio)
            if candidate:
                candidate_name, score, _ = candidate
                ibge_row = state_matches.loc[state_matches["municipality_name"] == candidate_name].iloc[0]
                municipality_id = ibge_row["municipality_id"]
                matched_name = ibge_row["municipality_name"]
                match_method = "fuzzy_candidate"
                confidence = "needs_review"
                reviewer_notes = f"Best fuzzy candidate score: {score}."
            else:
                match_method = "unmatched"
                confidence = "unresolved"
                reviewer_notes = "No candidate returned by rapidfuzz within the state."

        review_rows.append(
            {
                "raw_name_tse": row["raw_name_tse"],
                "normalized_name_tse": row["normalized_name_tse"],
                "state": row["state"],
                "year_first_treat": row["year_first_treat"],
                "tse_municipality_id": row["tse_municipality_id"],
                "zone": row["zone"],
                "zone_key": row["zone_key"],
                "matched_name_ibge": matched_name,
                "municipality_id": municipality_id,
                "match_method": match_method,
                "confidence": confidence,
                "reviewer_notes": reviewer_notes,
            }
        )

    review = pd.DataFrame(review_rows)
    review.to_csv(INTERIM_DIR / "name_matching_review.csv", index=False)
    return review


def main() -> None:
    match_rows()


if __name__ == "__main__":
    main()
