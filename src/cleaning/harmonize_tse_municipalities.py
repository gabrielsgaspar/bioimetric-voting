from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.tse_eleitorado_common import CLEAN_DIR, IBGE_CROSSWALK_PATH, INTERIM_DIR, OFFICIAL_PACKAGE_YEARS, VALID_UFS, ensure_directories, normalize_name


IBGE_NAME_PATH = Path("data/clean/tse_bvr/ibge_municipalities.csv")


def load_crosswalk() -> pd.DataFrame:
    crosswalk = pd.read_csv(IBGE_CROSSWALK_PATH, dtype=str)
    crosswalk["year"] = pd.to_numeric(crosswalk["year"], errors="coerce").astype("Int64")
    crosswalk["state"] = crosswalk["state"].astype(str).str.upper().str.strip()
    crosswalk["municipality_id"] = crosswalk["municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    crosswalk["tse_municipality_id"] = crosswalk["tse_municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    return crosswalk


def load_ibge_names() -> pd.DataFrame:
    if not IBGE_NAME_PATH.exists():
        return pd.DataFrame(columns=["municipality_id", "matched_name_crosswalk", "state"])
    ibge = pd.read_csv(IBGE_NAME_PATH, dtype=str)
    return ibge.rename(columns={"municipality_name": "matched_name_crosswalk"})[
        ["municipality_id", "matched_name_crosswalk", "state"]
    ]


def attach_ids(year: int, crosswalk: pd.DataFrame, ibge_names: pd.DataFrame) -> pd.DataFrame:
    parsed_path = INTERIM_DIR / f"parsed_{year}.parquet"
    df = pd.read_parquet(parsed_path)

    merged = df.merge(
        crosswalk,
        how="left",
        on=["year", "state", "tse_municipality_id"],
        validate="many_to_one",
    )
    merged["matched_via_direct_code"] = merged["municipality_id"].notna()

    unmatched_mask = merged["municipality_id"].isna()
    if unmatched_mask.any() and not ibge_names.empty:
        fallback = (
            df.loc[unmatched_mask, ["year", "state", "tse_municipality_id", "municipality_name_raw", "municipality_name"]]
            .drop_duplicates()
            .merge(
                ibge_names.assign(_norm_name=ibge_names["matched_name_crosswalk"].map(normalize_name)),
                how="left",
                left_on=["state", "municipality_name"],
                right_on=["state", "_norm_name"],
            )
        )
        fallback = fallback[["year", "state", "tse_municipality_id", "municipality_id", "matched_name_crosswalk"]]
        merged = merged.merge(
            fallback,
            how="left",
            on=["year", "state", "tse_municipality_id"],
            suffixes=("", "_fallback"),
        )
        merged["municipality_id"] = merged["municipality_id"].fillna(merged["municipality_id_fallback"])
        merged = merged.drop(columns=[col for col in merged.columns if col.endswith("_fallback")], errors="ignore")

    merged = merged.merge(ibge_names, how="left", on=["municipality_id", "state"])
    if "matched_name_crosswalk_x" in merged.columns or "matched_name_crosswalk_y" in merged.columns:
        left = (
            merged["matched_name_crosswalk_x"]
            if "matched_name_crosswalk_x" in merged.columns
            else pd.Series(index=merged.index, dtype="object")
        )
        right = (
            merged["matched_name_crosswalk_y"]
            if "matched_name_crosswalk_y" in merged.columns
            else pd.Series(index=merged.index, dtype="object")
        )
        merged["matched_name_crosswalk"] = left.fillna(right)
        merged = merged.drop(columns=["matched_name_crosswalk_x", "matched_name_crosswalk_y"], errors="ignore")
    merged["match_method"] = "unmatched"
    merged.loc[merged["matched_via_direct_code"], "match_method"] = "direct_code_year_state"
    merged.loc[merged["municipality_id"].notna() & ~merged["matched_via_direct_code"], "match_method"] = "exact_state_name_fallback"
    merged["confidence"] = merged["match_method"].map(lambda value: "high" if value == "direct_code_year_state" else "review")
    merged["notes"] = merged["match_method"].map(
        lambda value: "Matched on year + state + TSE municipality code using the repo crosswalk."
        if value == "direct_code_year_state"
        else (
            "Matched on normalized municipality name within state after the direct year-specific crosswalk join failed."
            if value == "exact_state_name_fallback"
            else "No direct year-specific crosswalk match found."
        )
    )
    return merged


def main() -> None:
    ensure_directories()
    crosswalk = load_crosswalk()
    ibge_names = load_ibge_names()

    harmonized_frames: list[pd.DataFrame] = []
    review_rows: list[pd.DataFrame] = []
    for year in OFFICIAL_PACKAGE_YEARS:
        merged = attach_ids(year, crosswalk, ibge_names)
        merged.to_parquet(INTERIM_DIR / f"harmonized_{year}.parquet", index=False)
        harmonized_frames.append(merged)
        review_rows.append(
            merged[
                [
                    "year",
                    "tse_municipality_id",
                    "municipality_name_raw",
                    "municipality_name",
                    "state",
                    "municipality_id",
                    "matched_name_crosswalk",
                    "match_method",
                    "confidence",
                    "notes",
                ]
            ]
            .drop_duplicates()
            .rename(columns={"municipality_id": "matched_municipality_id"})
        )

    review_df = pd.concat(review_rows, ignore_index=True).sort_values(
        ["year", "state", "municipality_name", "tse_municipality_id"]
    )
    review_df.to_csv(INTERIM_DIR / "municipality_crosswalk_review.csv", index=False)

    unmatched = review_df["matched_municipality_id"].isna().sum()
    invalid_states = sorted(set(review_df["state"].dropna()) - VALID_UFS)
    print(
        f"Wrote harmonized parquet files and municipality review table. Unmatched rows: {unmatched}. Invalid states observed: {invalid_states}"
    )


if __name__ == "__main__":
    main()
