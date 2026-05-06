from __future__ import annotations

import textwrap
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.cleaning.match_tse_to_ibge import match_rows
from src.cleaning.parse_tse_bvr_legal_docs import parse_tse_rows
from src.data.download_ibge_municipalities import download_ibge
from src.data.download_tse_bvr_legal_docs import download_tse_sources
from src.tse_bvr_common import CLEAN_DIR, DOCS_DIR, INTERIM_DIR, LOG_DIR, VALID_UFS, ensure_directories, normalize_name


def _normalize_code(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    if text.endswith(".0"):
        text = text[:-2]
    return text


NOTES_TEMPLATE = """# TSE BVR Dataset Notes

## Scope

This note documents the construction of the municipality-level dataset of first verified biometric voter registration election use in Brazil.

The current build combines direct legal and attachment evidence for 2008-2012 with official TSE election-year administrative or open-data evidence for 2014, 2016, and 2018. The evidence base used in the clean municipality-level dataset is:

- the 2008 pilot resolution,
- the official TSE ZIP attachment listing the municipalities where biometric voting occurred in 2010,
- the official TSE ZIP attachment listing municipalities apt for biometric identification in 2012,
- the official TSE 2014 electorate file, calibrated to the official municipality benchmark of 764 municipalities by 2014,
- the official TSE 2016 electorate open-data file, calibrated to the official TSE article reporting 1,540 municipalities voting totalmente com biometria in 2016,
- and the official TSE 2018 electorate open-data file, which explicitly labels municipalities as `Biométrico`, `Híbrido`, or `Sem biometria` in the election-year snapshot.

The dataset therefore now covers the first verified election-use years 2008, 2010, 2012, 2014, 2016, and 2018 for municipality-level full-biometric treatment. The 2015-2016 and 2017-2018 legal annexes were identified and indexed, but their municipality lists remain blocked behind SinTSE access controls in this environment. Municipality-level hybrid treatment for 2016 and municipality-level hybrid first-use timing for 2018 remain partially unresolved and are documented below.

## Source Inventory

- `data/interim/tse_bvr/tse_legal_sources_index.csv` records every TSE source downloaded or indexed for this build.
- `data/raw/tse_bvr_legal/` preserves the raw HTML, ZIP, and PDF downloads used in the build.
- `data/raw/ibge/` preserves the raw IBGE municipality API response used for the official municipality crosswalk.

## Interpretation Rules

### Year-first-treat rule

- `year_first_treat` is the first election year in which biometric identification was verified as being used.
- For 2008, the pilot resolution explicitly states that the listed municipalities would use biometric identification on election day.
- For 2010, the official TSE ZIP attachment listing the municipalities where biometric voting occurred in the 2010 election is treated as the election-use source. The legal provimentos remain indexed as supporting context but are not used as the municipal universe because they cover only a subset.
- For 2012, the official TSE ZIP attachment from the `Revisao eleitoral` page is treated as the verification source for municipalities apt for biometric identification in the 2012 elections.
- For 2014, the official TSE article gives the benchmark count and the official TSE 2014 electorate file is used to recover the election-use municipality set. A municipality is retained when its municipal biometric-elector share is at least 0.45, which reproduces the official cumulative benchmark of 764 municipalities by 2014.
- For 2016, the official TSE article states that 1,540 municipalities would vote totalmente com biometria and 840 would use sistema híbrido. The municipality-level TSE open-data electorate file is then used to identify which municipalities belong to the full-biometric 2016 group. A municipality is retained in the clean municipality-level dataset when its municipal biometric-elector share is at least 0.95, which reproduces the official full-biometric municipality count.
- For 2018, the official TSE article states that 2,793 municipalities would vote exclusively with biometrics and 1,533 would use hybrid identification. The official TSE 2018 electorate open-data file explicitly labels each municipality as `Biométrico`, `Híbrido`, or `Sem biometria`, allowing direct identification of municipality-level full-biometric treatment in 2018.

### Evidence versus inference

- 2008 and 2010 rows rely on direct legal-act text or inline annex text.
- 2010 rows rely on the official TSE election-use attachment rather than the narrower provimento annexes.
- 2012 rows rely on an official TSE summary attachment that is explicit about the election cycle, but it is not a one-to-one legal-act annex extract. This is a documented limitation.
- 2014 rows rely on the official TSE benchmark article plus the official TSE 2014 election-year electorate file because the archived PDF attachment under-extracts the full municipal universe in this environment.
- 2016 municipality-level full-biometric rows rely on an official TSE election-year open-data file plus a documented calibration rule anchored to the official TSE municipality count.
- 2018 municipality-level full-biometric rows rely on an explicit municipal status label in the official TSE election-year open-data file.
- 2018 hybrid municipalities are preserved in an interim review file but excluded from the clean municipality-level first-treatment dataset because municipality-wide first use may predate 2018 and zone-specific coverage is not explicit.

## Name-Standardization Rules

- Municipality names are lower-cased.
- Accents are removed with Unicode normalization.
- Asterisks from TSE tables are stripped.
- Punctuation is removed and whitespace is collapsed.
- Matching is always constrained within state before any fuzzy candidate generation is attempted.

## Matching Notes

- `data/clean/tse_bvr/ibge_municipalities.csv` is built from the official IBGE `localidades/municipios` API endpoint.
- `data/interim/tse_bvr/name_matching_review.csv` records every municipality-name match.
- Four within-state spelling variants have now been manually confirmed and are carried as `manual_override` matches in the review file: `santo antonio do leverger` in `MT`, `iguaraci` in `PE`, `machadinho do oeste` in `RO`, and `amparo de sao francisco` in `SE`.
- Fuzzy matching is used only to generate candidates. Any non-exact rows should be reviewed before treating the dataset as final for publication-grade analysis.

## Ambiguous and Unresolved Cases

- Exact municipality-level annex extraction remains unresolved for the 2013-2014 complementary provimentos and for the 2015-2016 and 2017-2018 program cycles.
- Zone-specific versus municipality-wide treatment cannot be fully resolved for 2012 from the accessible official attachment, because it reports municipality-level coverage without zone identifiers.
- The 2014 election-use set is calibrated from the official administrative file. The benchmark is matched, but the file does not include an explicit municipal status label, so the 0.45 cutoff should be treated as a documented administrative calibration rather than a direct legal annex extract.
- Hybrid identification in 2016 is documented as an important edge case by the official TSE article, but municipality-level hybrid coding is not directly recoverable from the blocked annexes or from an explicit status field in the 2016 electorate file.
- The 2018 electorate file does explicitly flag hybrid municipalities. These rows are preserved in `data/interim/tse_bvr/hybrid_2018_review.csv`, but they are excluded from the clean municipality-level first-treatment dataset because partial municipality coverage may have begun before 2018 and municipality-zone identifiers are not available in the open-data file.

## Legal and Timing Caveats

- `url_tse` is the exact official TSE URL used as evidence in the build. For 2012 and 2014 rows, this may be an official TSE attachment rather than an individual provimento page.
- For 2014, 2016, and 2018 full-biometric rows, `url_tse` points to the official TSE election-year administrative or open-data source used for municipality identification.
- The current clean dataset should be treated as a verified lower bound on municipality-level first use, with especially conservative handling of hybrid treatment.
"""


def _write_notes() -> None:
    path = DOCS_DIR / "TSE_BVR_DATASET_NOTES.md"
    path.write_text(NOTES_TEMPLATE, encoding="utf-8")


def _validate_dataset(df: pd.DataFrame, ibge: pd.DataFrame, review: pd.DataFrame) -> dict:
    duplicate_count = int(df.duplicated(subset=["municipality_id", "state", "zone", "year_first_treat", "url_tse"]).sum())
    invalid_states = sorted(set(df.loc[~df["state"].isin(VALID_UFS), "state"]))
    bad_ids = sorted(set(df.loc[df["municipality_id"].str.len() != 7, "municipality_id"]))
    bad_names = int((df["municipality_name"] != df["municipality_name"].map(normalize_name)).sum())
    missing_in_ibge = int((~df["municipality_id"].isin(ibge["municipality_id"])).sum())
    non_exact_matches = review.loc[~review["match_method"].isin(["exact_state_normalized_name", "direct_tse_code_year"])].copy()

    return {
        "duplicate_count": duplicate_count,
        "invalid_states": invalid_states,
        "bad_ids": bad_ids,
        "bad_names": bad_names,
        "missing_in_ibge": missing_in_ibge,
        "non_exact_match_count": int(len(non_exact_matches)),
    }


def _build_log(
    source_index: pd.DataFrame,
    final_df: pd.DataFrame,
    review: pd.DataFrame,
    validation: dict,
) -> str:
    exact_matches = int((review["match_method"] == "exact_state_normalized_name").sum())
    direct_code_matches = int((review["match_method"] == "direct_tse_code_year").sum())
    manual_override_matches = int((review["match_method"] == "manual_override").sum())
    fuzzy_matches = int((review["match_method"] == "fuzzy_candidate").sum())
    unresolved_matches = int((review["match_method"] == "unmatched").sum())

    unresolved_summary = textwrap.dedent(
        """
        ## Unresolved Items

        1. The 2015-2016 and 2017-2018 municipality annexes were identified but remained blocked behind SinTSE access-rejected pages when fetched via `requests` and via a headless browser.
        2. The 2012 rows are verified from an official TSE attachment, but not mapped one-by-one to individual provimentos.
        3. The 2014 rows are benchmarked with the official TSE article and recovered from the official election-year administrative file rather than a fully recoverable annex list.
        4. Municipality-level hybrid treatment for 2016 remains unresolved because the official TSE 2016 electorate file does not carry an explicit municipal hybrid status field.
        5. Municipality-level 2018 hybrid rows are preserved in `data/interim/tse_bvr/hybrid_2018_review.csv` but excluded from the clean municipality-level first-treatment dataset.
        """
    ).strip()

    hybrid_cases = 0
    log = f"""# TSE BVR Build Log

## Summary

- Number of source rows indexed: {len(source_index)}
- Number of treated municipality-zone rows in clean output: {len(final_df)}
- Number of direct TSE-code matches to IBGE: {direct_code_matches}
- Number of exact matches to IBGE: {exact_matches}
- Number of manually confirmed spelling-variant matches: {manual_override_matches}
- Number of fuzzy candidate matches: {fuzzy_matches}
- Number of unresolved matches: {unresolved_matches}
- Hybrid or partial-treatment cases explicitly coded in final data: {hybrid_cases}

## Validation

- Duplicate rows on `municipality_id + zone + year_first_treat + url_tse`: {validation['duplicate_count']}
- Invalid UF values: {validation['invalid_states'] or 'none'}
- Malformed municipality IDs: {validation['bad_ids'] or 'none'}
- Non-normalized municipality names in final output: {validation['bad_names']}
- Municipality IDs missing from IBGE table: {validation['missing_in_ibge']}

{unresolved_summary}
"""
    return log


def build_dataset() -> pd.DataFrame:
    ensure_directories()

    source_index_path = INTERIM_DIR / "tse_legal_sources_index.csv"
    if source_index_path.exists():
        source_index = pd.read_csv(source_index_path)
    else:
        source_index = download_tse_sources()
    if "https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2014.zip" not in set(source_index["source_url"]):
        source_index = pd.concat(
            [
                source_index,
                pd.DataFrame(
                    [
                        {
                            "source_url": "https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_2014.zip",
                            "source_type": "official_open_data",
                            "title": "Perfil do eleitorado 2014",
                            "issue_date": "",
                            "treatment_reference_year": 2014,
                            "annex_url": "",
                            "notes": "Official TSE election-year electorate file used as an administrative backstop for the 2014 biometric municipality benchmark.",
                            "municipality_scope": "",
                            "election_use_year": "",
                            "rollout_year": "",
                            "hybrid_flag": "",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        source_index.to_csv(source_index_path, index=False)
    ibge_clean_path = CLEAN_DIR / "ibge_municipalities.csv"
    if ibge_clean_path.exists():
        ibge_df = pd.read_csv(ibge_clean_path, dtype={"municipality_id": str})
    else:
        ibge_df, _ = download_ibge()
    parsed_rows = parse_tse_rows()
    review = match_rows()
    parsed_rows["zone_key"] = parsed_rows["zone"].fillna("").astype(str)
    parsed_rows["tse_municipality_id"] = parsed_rows.get("tse_municipality_id", "").map(_normalize_code)
    review["zone_key"] = review["zone_key"].fillna("").astype(str)
    review["tse_municipality_id"] = review.get("tse_municipality_id", "").map(_normalize_code)

    merged = parsed_rows.merge(
        review[
            [
                "raw_name_tse",
                "normalized_name_tse",
                "state",
                "zone_key",
                "year_first_treat",
                "tse_municipality_id",
                "municipality_id",
                "matched_name_ibge",
                "match_method",
                "confidence",
                "reviewer_notes",
            ]
        ],
        on=["raw_name_tse", "normalized_name_tse", "state", "zone_key", "year_first_treat", "tse_municipality_id"],
        how="left",
    )
    merged = merged.merge(
        ibge_df[["municipality_id", "municipality_name"]],
        on="municipality_id",
        how="left",
    )

    detailed_df = merged.copy()
    detailed_df["municipality_name"] = detailed_df["municipality_name"].fillna(detailed_df["normalized_name_tse"])
    detailed_df["zone"] = detailed_df["zone"].astype("Int64")
    detailed_df["hybrid_flag"] = False
    detailed_df["source_notes"] = detailed_df["notes"]
    detailed_df["match_method"] = detailed_df["match_method"].fillna("unmatched")

    detailed_df = detailed_df[
        [
            "municipality_id",
            "municipality_name",
            "state",
            "year_first_treat",
            "zone",
            "treatment_scope",
            "hybrid_flag",
            "url_tse",
            "source_title",
            "source_date",
            "source_notes",
            "source_kind",
            "raw_name_tse",
            "match_method",
            "confidence",
            "reviewer_notes",
            "notes",
        ]
    ].copy()

    detailed_df = (
        detailed_df.sort_values(["year_first_treat", "source_date", "state", "municipality_name", "zone"], na_position="last")
        .drop_duplicates(subset=["municipality_id", "state", "zone", "year_first_treat"], keep="first")
        .reset_index(drop=True)
    )

    first_rows = (
        detailed_df.sort_values(["year_first_treat", "source_date", "state", "municipality_name"], na_position="last")
        .drop_duplicates(subset=["municipality_id"], keep="first")
        .reset_index(drop=True)
    )
    first_rows["zone"] = pd.NA
    final_df = first_rows[["municipality_id", "municipality_name", "state", "zone", "url_tse", "year_first_treat"]].copy()

    validation = _validate_dataset(final_df, ibge_df, review)
    log_text = _build_log(source_index, final_df, review, validation)

    clean_csv = CLEAN_DIR / "municipality_bvr_first_treat.csv"
    clean_parquet = CLEAN_DIR / "municipality_bvr_first_treat.parquet"
    detailed_csv = CLEAN_DIR / "municipality_bvr_first_treat_detailed.csv"
    final_df[["municipality_id", "municipality_name", "state", "zone", "url_tse", "year_first_treat"]].to_csv(clean_csv, index=False)
    final_df[["municipality_id", "municipality_name", "state", "zone", "url_tse", "year_first_treat"]].to_parquet(clean_parquet, index=False)
    detailed_df.to_csv(detailed_csv, index=False)

    (LOG_DIR / "tse_bvr_build_log.md").write_text(log_text, encoding="utf-8")
    _write_notes()
    return final_df


def main() -> None:
    build_dataset()


if __name__ == "__main__":
    main()
