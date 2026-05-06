from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.tse_eleitorado_common import CLEAN_DIR, INTERIM_DIR, LOG_DIR, OFFICIAL_PACKAGE_YEARS, TARGET_YEARS, VALID_UFS, ensure_directories


def load_harmonized_frames() -> pd.DataFrame:
    frames = []
    for year in OFFICIAL_PACKAGE_YEARS:
        path = INTERIM_DIR / f"harmonized_{year}.parquet"
        frames.append(pd.read_parquet(path))
    return pd.concat(frames, ignore_index=True)


def validate_panel(panel: pd.DataFrame) -> list[str]:
    messages: list[str] = []
    missing_years = sorted(set(OFFICIAL_PACKAGE_YEARS) - set(panel["year"].dropna().astype(int).unique()))
    messages.append(f"Official historical TSE packages parsed for years: {sorted(panel['year'].dropna().astype(int).unique().tolist())}.")
    if missing_years:
        messages.append(f"Missing even-year packages in final panel: {missing_years}.")

    missing_official_odd_years = [year for year in TARGET_YEARS if year not in OFFICIAL_PACKAGE_YEARS]
    messages.append(
        "No separate official historical eleitorado package was found in the TSE open-data catalog for odd years "
        f"{missing_official_odd_years}; those years are documented in source_index.csv as unavailable."
    )

    duplicate_count = int(panel.duplicated(["year", "municipality_id", "education", "gender"]).sum())
    messages.append(f"Duplicate final-key rows: {duplicate_count}.")

    invalid_states = sorted(set(panel["state"].dropna()) - VALID_UFS)
    messages.append(f"Invalid UF codes in final panel: {invalid_states}.")

    missing_ids = int(panel["municipality_id"].isna().sum())
    messages.append(f"Rows with missing municipality_id: {missing_ids}.")

    national_totals = panel.groupby("year", as_index=False)["num_voters"].sum()
    totals_preview = ", ".join(
        f"{int(row.year)}={int(row.num_voters)}" for row in national_totals.itertuples(index=False)
    )
    messages.append(f"National totals by year from the final panel: {totals_preview}.")
    return messages


def main() -> None:
    ensure_directories()
    df = load_harmonized_frames()
    df["municipality_id"] = (
        df["municipality_id"]
        .where(df["municipality_id"].notna(), None)
        .map(lambda value: None if value is None else str(value).replace(".0", "").zfill(7))
    )
    df["municipality_name"] = df["matched_name_crosswalk"].fillna(df["municipality_name"])

    panel = (
        df[df["municipality_id"].notna()]
        .groupby(
            ["year", "municipality_id", "municipality_name", "state", "education", "gender"],
            as_index=False,
            dropna=False,
        )["num_voters"]
        .sum()
        .sort_values(["year", "state", "municipality_name", "education", "gender"])
        .reset_index(drop=True)
    )

    csv_path = CLEAN_DIR / "eleitorado_education_gender_2000_2018.csv"
    parquet_path = CLEAN_DIR / "eleitorado_education_gender_2000_2018.parquet"
    panel.to_csv(csv_path, index=False)
    panel.to_parquet(parquet_path, index=False)

    source_index = pd.read_csv(INTERIM_DIR / "source_index.csv")
    review = pd.read_csv(INTERIM_DIR / "municipality_crosswalk_review.csv", dtype=str)
    downloaded_source_count = int((source_index["status"] == "downloaded").sum())
    odd_year_missing_count = int((source_index["status"] == "not_found_in_catalog").sum())
    direct_count = int((review["match_method"] == "direct_code_year_state").sum())
    fallback_count = int((review["match_method"] == "exact_state_name_fallback").sum())
    unmatched_count = int((review["match_method"] == "unmatched").sum())
    unmatched_states = sorted(review.loc[review["match_method"] == "unmatched", "state"].dropna().unique().tolist())

    log_lines = ["# TSE Eleitorado Build Log", ""]
    log_lines.append(f"- Official TSE historical electorate packages downloaded: {downloaded_source_count}.")
    log_lines.append(
        f"- Odd years recorded as unavailable in the official catalog: {odd_year_missing_count}."
    )
    log_lines.append(f"- Municipality crosswalk matches via direct code join: {direct_count}.")
    log_lines.append(f"- Municipality crosswalk matches via exact state-name fallback: {fallback_count}.")
    log_lines.append(
        f"- Municipality crosswalk rows left unmatched: {unmatched_count}. Unmatched states: {unmatched_states}."
    )
    for line in validate_panel(panel):
        log_lines.append(f"- {line}")
    (LOG_DIR / "tse_eleitorado_build_log.md").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(f"Wrote {csv_path}, {parquet_path}, and the build log.")


if __name__ == "__main__":
    main()
