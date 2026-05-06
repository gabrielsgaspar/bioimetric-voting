from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "data" / "clean" / "decomposition" / "decomposition_data.parquet"
OUTPUT_PATH = ROOT / "data" / "clean" / "decomposition" / "decomposition_data_v2.parquet"
AUDIT_PATH = ROOT / "data" / "clean" / "decomposition" / "decomposition_pct_bvr_backfill_audit.parquet"

YEARS = [2008, 2010, 2012, 2014, 2016, 2018]
BACKFILL_YEARS = {2008, 2010, 2012}
OBSERVED_YEARS = {2014, 2016, 2018}
KEY_COLUMNS = ["ibge_municipality_id", "age_cohort", "education"]
REQUIRED_COLUMNS = [
    "year",
    "ibge_municipality_id",
    "state",
    "bvr_status",
    "year_first_any_bvr",
    "year_first_strict_bvr",
    "year_first_hybrid_bvr",
    "age_cohort",
    "education",
    "low_ed",
    "high_ed",
    "num_voters",
    "num_voters_bvr",
    "pct_bvr",
]


def percent(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{100 * float(value):.2f}%"


def normalize_inputs(df: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise RuntimeError(f"{INPUT_PATH} is missing required columns: {missing}")

    output = df.copy()
    output["ibge_municipality_id"] = output["ibge_municipality_id"].astype(str).str.zfill(7)
    output["state"] = output["state"].astype(str).str.upper().str.strip()
    output["year"] = pd.to_numeric(output["year"], errors="raise").astype(int)
    for column in ["year_first_any_bvr", "year_first_strict_bvr", "year_first_hybrid_bvr"]:
        output[column] = pd.to_numeric(output[column], errors="raise").astype(int)
    for column in ["low_ed", "high_ed", "num_voters", "num_voters_bvr"]:
        output[column] = pd.to_numeric(output[column], errors="raise").astype("int64")
    output["pct_bvr"] = pd.to_numeric(output["pct_bvr"], errors="coerce").fillna(0.0)
    return output


def pct_bvr_descriptives(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    rows = []
    positive = df[df["num_voters"].gt(0)].copy()
    for year in YEARS:
        subset = positive[positive["year"].eq(year)]
        rows.append(
            {
                "period": prefix,
                "year": year,
                "n_cells_total": len(subset),
                "n_cells_pct_bvr_positive": int(subset["pct_bvr"].gt(0).sum()),
                "share_cells_pct_bvr_positive": subset["pct_bvr"].gt(0).mean() if len(subset) else np.nan,
                "mean_pct_bvr": subset["pct_bvr"].mean() if len(subset) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def build_2014_lookup(df: pd.DataFrame) -> pd.DataFrame:
    lookup = df[df["year"].eq(2014)][KEY_COLUMNS + ["pct_bvr", "num_voters_bvr"]].copy()
    duplicates = int(lookup.duplicated(KEY_COLUMNS).sum())
    if duplicates:
        raise RuntimeError(f"2014 lookup has {duplicates:,} duplicate key rows")
    return lookup.rename(
        columns={
            "pct_bvr": "pct_bvr_2014_source",
            "num_voters_bvr": "num_voters_bvr_2014_source",
        }
    )


def apply_backfill(df: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    output = df.merge(lookup, how="left", on=KEY_COLUMNS, validate="many_to_one")
    output["pct_bvr_before"] = output["pct_bvr"]
    output["num_voters_bvr_before"] = output["num_voters_bvr"]
    output["pct_bvr_imputed"] = False
    output["pct_bvr_source"] = "observed"

    backfill_rows = output["year"].isin(BACKFILL_YEARS)
    has_source = output["pct_bvr_2014_source"].notna()
    impute_rows = backfill_rows & has_source
    no_match_rows = backfill_rows & ~has_source

    output.loc[impute_rows, "pct_bvr"] = output.loc[impute_rows, "pct_bvr_2014_source"]
    output.loc[impute_rows, "num_voters_bvr"] = np.rint(
        output.loc[impute_rows, "pct_bvr"] * output.loc[impute_rows, "num_voters"]
    ).astype("int64")
    output.loc[impute_rows, "pct_bvr_imputed"] = True
    output.loc[impute_rows, "pct_bvr_source"] = "2014_backfill"

    output.loc[no_match_rows, "pct_bvr_source"] = "no_match_kept_zero"
    output.loc[output["year"].isin(OBSERVED_YEARS), "pct_bvr_source"] = "observed"

    output["num_voters_bvr"] = output["num_voters_bvr"].clip(lower=0, upper=output["num_voters"]).astype("int64")
    output["pct_bvr"] = output["pct_bvr"].clip(lower=0.0, upper=1.0)
    return output


def build_audit(backfilled: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in YEARS:
        subset = backfilled[backfilled["year"].eq(year)]
        rows.append(
            {
                "year": year,
                "n_cells_total": len(subset),
                "n_cells_observed": int(subset["pct_bvr_source"].eq("observed").sum()),
                "n_cells_imputed_from_2014": int(subset["pct_bvr_source"].eq("2014_backfill").sum()),
                "n_cells_no_match_kept_zero": int(subset["pct_bvr_source"].eq("no_match_kept_zero").sum()),
                "mean_pct_bvr_before": subset["pct_bvr_before"].mean(),
                "mean_pct_bvr_after": subset["pct_bvr"].mean(),
            }
        )
    return pd.DataFrame(rows)


def treated_cohort_spot_checks(before: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cohort_year in [2008, 2010, 2012]:
        before_subset = before[
            before["year"].eq(cohort_year) & before["year_first_any_bvr"].eq(cohort_year) & before["num_voters"].gt(0)
        ]
        after_subset = after[
            after["year"].eq(cohort_year) & after["year_first_any_bvr"].eq(cohort_year) & after["num_voters"].gt(0)
        ]
        rows.append(
            {
                "cohort_year": cohort_year,
                "municipalities": int(after_subset["ibge_municipality_id"].nunique()),
                "cells": len(after_subset),
                "mean_pct_bvr_before": before_subset["pct_bvr"].mean() if len(before_subset) else np.nan,
                "mean_pct_bvr_after": after_subset["pct_bvr"].mean() if len(after_subset) else np.nan,
                "share_positive_after": after_subset["pct_bvr"].gt(0).mean() if len(after_subset) else np.nan,
                "p10_after": after_subset["pct_bvr"].quantile(0.10) if len(after_subset) else np.nan,
                "p50_after": after_subset["pct_bvr"].quantile(0.50) if len(after_subset) else np.nan,
                "p90_after": after_subset["pct_bvr"].quantile(0.90) if len(after_subset) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def print_table(title: str, frame: pd.DataFrame, pct_columns: set[str] | None = None) -> None:
    pct_columns = pct_columns or set()
    display = frame.copy()
    for column in pct_columns:
        if column in display.columns:
            display[column] = display[column].map(percent)
    print(f"\n{title}")
    print("-" * len(title))
    print(display.to_string(index=False))


def main() -> None:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", None)

    if not INPUT_PATH.exists():
        raise FileNotFoundError(INPUT_PATH)
    source = normalize_inputs(pd.read_parquet(INPUT_PATH))
    pre = pct_bvr_descriptives(source, "pre")
    lookup = build_2014_lookup(source)
    backfilled = apply_backfill(source, lookup)
    post = pct_bvr_descriptives(backfilled, "post")
    audit = build_audit(backfilled)
    spots = treated_cohort_spot_checks(source, backfilled)

    output_columns = REQUIRED_COLUMNS + ["pct_bvr_imputed", "pct_bvr_source"]
    backfilled[output_columns].to_parquet(OUTPUT_PATH, index=False)
    audit.to_parquet(AUDIT_PATH, index=False)

    missing_lookup_rate = audit.loc[audit["year"].isin(BACKFILL_YEARS), "n_cells_no_match_kept_zero"].sum() / audit.loc[
        audit["year"].isin(BACKFILL_YEARS), "n_cells_total"
    ].sum()
    anomalies: list[str] = []
    if missing_lookup_rate > 0.05:
        anomalies.append(f"2014 lookup missing for {percent(missing_lookup_rate)} of pre-2014 cells")
    weak_spots = spots[spots["share_positive_after"].lt(0.50)]
    if len(weak_spots):
        years = ", ".join(str(int(year)) for year in weak_spots["cohort_year"])
        anomalies.append(f"spot-check cohorts still have fewer than half positive pct_bvr cells after backfill: {years}")

    print("=" * 64)
    print("pct_bvr Backfill — Summary")
    print("=" * 64)
    print(f"Source file: {INPUT_PATH.relative_to(ROOT)}")
    print(f"Output file: {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"2014 lookup cells: {len(lookup):,}")

    print_table(
        "Pre-backfill state",
        pre[["year", "n_cells_total", "n_cells_pct_bvr_positive", "share_cells_pct_bvr_positive", "mean_pct_bvr"]],
        {"share_cells_pct_bvr_positive", "mean_pct_bvr"},
    )
    print_table(
        "Post-backfill audit",
        audit,
        {"mean_pct_bvr_before", "mean_pct_bvr_after"},
    )
    print_table(
        "Spot checks for treated cohorts",
        spots,
        {
            "mean_pct_bvr_before",
            "mean_pct_bvr_after",
            "share_positive_after",
            "p10_after",
            "p50_after",
            "p90_after",
        },
    )

    print("\nAnomalies flagged:", len(anomalies))
    for anomaly in anomalies:
        print(f"  - {anomaly}")
    print("\nFiles saved:")
    print(f"  {OUTPUT_PATH.relative_to(ROOT)}")
    print(f"  {AUDIT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
