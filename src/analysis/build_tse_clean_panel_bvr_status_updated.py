from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PANEL_CSV = ROOT / "data/clean/tse/tse_clean_panel_2000_2018.csv"
PANEL_PARQUET = ROOT / "data/clean/tse/tse_clean_panel_2000_2018.parquet"
STATUS_CSV = ROOT / "data/interim/tse_bvr/quantitativo_municipios_municipio_2012_2018_matched.csv"
BIOMETRIC_SHARES_CSV = ROOT / "data/clean/tse_eleitorado/eleitorado_biometric_shares_2000_2018.csv"
BIOMETRIC_SHARES_PARQUET = ROOT / "data/clean/tse_eleitorado/eleitorado_biometric_shares_2000_2018.parquet"
OUTPUT_DIR = ROOT / "data/clean/tse"
DIAGNOSTICS_DIR = ROOT / "data/interim/tse"
DOCS_DIR = ROOT / "docs"

OUTPUT_CSV = OUTPUT_DIR / "tse_clean_panel_2000_2018_bvr_status_updated.csv"
OUTPUT_PARQUET = OUTPUT_DIR / "tse_clean_panel_2000_2018_bvr_status_updated.parquet"
DIAGNOSTICS_CSV = DIAGNOSTICS_DIR / "tse_clean_panel_2000_2018_bvr_status_updated_diagnostics.csv"
NOTES_PATH = DOCS_DIR / "TSE_CLEAN_PANEL_BVR_STATUS_UPDATED_NOTES.md"

NEVER_TREATED_YEAR = 9999
STATUS_YEARS = [2012, 2014, 2016, 2018]
BIOMETRIC_SHARE_COLUMNS = ["pct_with_bvr", "pct_low_ed_with_bvr", "pct_high_ed_with_bvr"]


def _load_panel() -> pd.DataFrame:
    if PANEL_PARQUET.exists():
        df = pd.read_parquet(PANEL_PARQUET)
    elif PANEL_CSV.exists():
        df = pd.read_csv(PANEL_CSV)
    else:
        raise FileNotFoundError(f"Missing clean TSE panel: {PANEL_PARQUET} or {PANEL_CSV}")
    df = df.copy()
    df["municipality_id"] = df["municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["year_election"] = pd.to_numeric(df["year_election"], errors="raise").astype(int)
    df["year_treated"] = pd.to_numeric(df["year_treated"], errors="raise").astype(int)
    df["dist_treatment"] = pd.to_numeric(df["dist_treatment"], errors="raise").astype(int)
    df["hybrid"] = pd.to_numeric(df["hybrid"], errors="raise").fillna(0).astype(int)
    return df


def _load_status() -> pd.DataFrame:
    if not STATUS_CSV.exists():
        raise FileNotFoundError(f"Missing matched BVR status file: {STATUS_CSV}")
    status = pd.read_csv(STATUS_CSV, dtype={"municipality_id": str})
    required = {
        "year",
        "municipality_id",
        "bvr_status",
        "is_strict_bvr",
        "is_hybrid_bvr",
        "qt_municipio_sem_biometria",
        "qt_municipio_biometria",
        "qt_municipio_hibrido",
    }
    missing = sorted(required - set(status.columns))
    if missing:
        raise ValueError(f"Matched status file is missing required columns: {missing}")

    status = status.copy()
    status["year"] = pd.to_numeric(status["year"], errors="raise").astype(int)
    status["municipality_id"] = status["municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    status = status[status["year"].isin(STATUS_YEARS)].copy()
    duplicate = int(status.duplicated(["year", "municipality_id"]).sum())
    if duplicate:
        raise ValueError(f"Matched status file has {duplicate} duplicate year x municipality_id rows.")

    status_count_sum = (
        pd.to_numeric(status["qt_municipio_sem_biometria"], errors="raise")
        + pd.to_numeric(status["qt_municipio_biometria"], errors="raise")
        + pd.to_numeric(status["qt_municipio_hibrido"], errors="raise")
    )
    if not status_count_sum.eq(1).all():
        bad = status.loc[~status_count_sum.eq(1), ["year", "municipality_id", "bvr_status"]]
        raise ValueError(f"Status indicators do not sum to one for some rows:\n{bad.head(20).to_string(index=False)}")

    return status[
        [
            "year",
            "municipality_id",
            "bvr_status",
            "is_strict_bvr",
            "is_hybrid_bvr",
            "qt_municipio_sem_biometria",
            "qt_municipio_biometria",
            "qt_municipio_hibrido",
        ]
    ].rename(columns={"year": "year_election"})


def _load_biometric_shares(panel: pd.DataFrame) -> pd.DataFrame:
    if BIOMETRIC_SHARES_PARQUET.exists():
        shares = pd.read_parquet(BIOMETRIC_SHARES_PARQUET)
    elif BIOMETRIC_SHARES_CSV.exists():
        shares = pd.read_csv(BIOMETRIC_SHARES_CSV)
    else:
        keys = panel[["year_election", "municipality_id"]].copy()
        for column in BIOMETRIC_SHARE_COLUMNS:
            keys[column] = np.nan
        return keys

    required = {"year", "municipality_id", *BIOMETRIC_SHARE_COLUMNS}
    missing = sorted(required - set(shares.columns))
    if missing:
        raise ValueError(f"Biometric share file is missing required columns: {missing}")

    shares = shares.copy()
    shares["year_election"] = pd.to_numeric(shares["year"], errors="raise").astype(int)
    shares["municipality_id"] = shares["municipality_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(7)
    for column in BIOMETRIC_SHARE_COLUMNS:
        shares[column] = pd.to_numeric(shares[column], errors="coerce")
        nonmissing = shares[column].dropna()
        if ((nonmissing < -1e-12) | (nonmissing > 1 + 1e-12)).any():
            raise ValueError(f"{column} has values outside [0, 1].")

    duplicate = int(shares.duplicated(["year_election", "municipality_id"]).sum())
    if duplicate:
        raise ValueError(f"Biometric share file has {duplicate} duplicate year x municipality_id rows.")

    return shares[["year_election", "municipality_id", *BIOMETRIC_SHARE_COLUMNS]]


def _first_year_by_status(df: pd.DataFrame, flag: str, output: str) -> pd.Series:
    first = df.loc[df[flag].eq(1)].groupby("municipality_id")["year_election"].min()
    return df["municipality_id"].map(first).fillna(NEVER_TREATED_YEAR).astype(int).rename(output)


def build_updated_panel() -> pd.DataFrame:
    panel = _load_panel()
    status = _load_status()
    biometric_shares = _load_biometric_shares(panel)

    panel_keys = panel.loc[panel["year_election"].isin(STATUS_YEARS), ["year_election", "municipality_id"]]
    status_keys = status[["year_election", "municipality_id"]]
    missing_status = panel_keys.merge(status_keys, on=["year_election", "municipality_id"], how="left", indicator=True)
    missing_status = missing_status[missing_status["_merge"].eq("left_only")]
    extra_status = status_keys.merge(panel_keys, on=["year_election", "municipality_id"], how="left", indicator=True)
    extra_status = extra_status[extra_status["_merge"].eq("left_only")]
    if not missing_status.empty or not extra_status.empty:
        raise ValueError(
            "Matched status file does not align one-to-one with clean panel for 2012/2014/2016/2018. "
            f"Missing status rows: {len(missing_status)}; extra status rows: {len(extra_status)}."
        )

    out = panel.merge(status, on=["year_election", "municipality_id"], how="left", validate="one_to_one")
    out = out.rename(columns={"hybrid": "hybrid_legacy_2018_only"})

    legacy_strict = out["year_treated"].ne(NEVER_TREATED_YEAR) & out["year_treated"].le(out["year_election"])
    status_year_mask = out["year_election"].isin(STATUS_YEARS)

    out["bvr_status_source"] = np.where(
        status_year_mask,
        "quantitativo_municipios_matched",
        "legacy_first_treatment_timing",
    )
    out["bvr_status"] = out["bvr_status"].where(
        status_year_mask,
        np.where(legacy_strict, "strict_bvr", "no_bvr"),
    )
    out["strict_bvr"] = np.where(
        status_year_mask,
        out["is_strict_bvr"].eq(True),
        legacy_strict,
    ).astype(int)
    out["hybrid"] = np.where(
        status_year_mask,
        out["is_hybrid_bvr"].eq(True),
        False,
    ).astype(int)
    out["any_bvr"] = out["bvr_status"].isin(["strict_bvr", "hybrid_bvr"]).astype(int)
    out["no_bvr"] = out["bvr_status"].eq("no_bvr").astype(int)

    out["year_first_any_bvr"] = _first_year_by_status(out, "any_bvr", "year_first_any_bvr")
    out["year_first_strict_bvr"] = _first_year_by_status(out, "strict_bvr", "year_first_strict_bvr")
    out["year_first_hybrid_bvr"] = _first_year_by_status(out, "hybrid", "year_first_hybrid_bvr")

    for year_col, dist_col in [
        ("year_first_any_bvr", "dist_any_bvr"),
        ("year_first_strict_bvr", "dist_strict_bvr"),
        ("year_first_hybrid_bvr", "dist_hybrid_bvr"),
    ]:
        out[dist_col] = out["year_election"] - out[year_col]
        out.loc[out[year_col].eq(NEVER_TREATED_YEAR), dist_col] = -9999
        out[dist_col] = out[dist_col].astype(int)

    drop_cols = ["is_strict_bvr", "is_hybrid_bvr"]
    out = out.drop(columns=[c for c in drop_cols if c in out.columns])
    out = out.merge(
        biometric_shares,
        on=["year_election", "municipality_id"],
        how="left",
        validate="one_to_one",
    )

    ordered_tail = [
        "pct_with_bvr",
        "pct_low_ed_with_bvr",
        "pct_high_ed_with_bvr",
        "hybrid_legacy_2018_only",
        "bvr_status",
        "bvr_status_source",
        "strict_bvr",
        "hybrid",
        "any_bvr",
        "no_bvr",
        "year_first_any_bvr",
        "dist_any_bvr",
        "year_first_strict_bvr",
        "dist_strict_bvr",
        "year_first_hybrid_bvr",
        "dist_hybrid_bvr",
        "qt_municipio_sem_biometria",
        "qt_municipio_biometria",
        "qt_municipio_hibrido",
    ]
    base_cols = [c for c in out.columns if c not in ordered_tail]
    out = out[base_cols + ordered_tail]
    return out


def validate(updated: pd.DataFrame) -> pd.DataFrame:
    duplicate = int(updated.duplicated(["year_election", "municipality_id"]).sum())
    if duplicate:
        raise ValueError(f"Updated panel has {duplicate} duplicate year x municipality_id rows.")

    bad_status = sorted(set(updated["bvr_status"]) - {"strict_bvr", "hybrid_bvr", "no_bvr"})
    if bad_status:
        raise ValueError(f"Unexpected BVR status values: {bad_status}")

    bad_sum = int((updated[["strict_bvr", "hybrid", "no_bvr"]].sum(axis=1) != 1).sum())
    if bad_sum:
        raise ValueError(f"Found {bad_sum} rows where strict/hybrid/no-BVR indicators do not sum to one.")

    rows = []
    for year, group in updated.groupby("year_election"):
        rows.append(
            {
                "year": int(year),
                "rows": int(len(group)),
                "municipalities": int(group["municipality_id"].nunique()),
                "strict_bvr": int(group["strict_bvr"].sum()),
                "hybrid": int(group["hybrid"].sum()),
                "any_bvr": int(group["any_bvr"].sum()),
                "no_bvr": int(group["no_bvr"].sum()),
                "legacy_hybrid_2018_only": int(group["hybrid_legacy_2018_only"].sum()),
                "nonmissing_pct_with_bvr": int(group["pct_with_bvr"].notna().sum()),
                "nonmissing_pct_low_ed_with_bvr": int(group["pct_low_ed_with_bvr"].notna().sum()),
                "nonmissing_pct_high_ed_with_bvr": int(group["pct_high_ed_with_bvr"].notna().sum()),
            }
        )
    diagnostics = pd.DataFrame(rows).sort_values("year")
    return diagnostics


def write_notes(diagnostics: pd.DataFrame) -> None:
    status_lines = diagnostics.to_markdown(index=False)
    NOTES_PATH.write_text(
        f"""# TSE Clean Panel With Updated BVR Status

This file documents `data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.csv`
and `.parquet`.

## Construction

- Base panel: `data/clean/tse/tse_clean_panel_2000_2018`.
- Status source for 2012, 2014, 2016, and 2018:
  `data/interim/tse_bvr/quantitativo_municipios_municipio_2012_2018_matched.csv`.
- The legacy `year_treated` and `dist_treatment` columns are preserved unchanged.
- The old `hybrid` indicator is preserved as `hybrid_legacy_2018_only`.
- The updated `hybrid` indicator is year-specific and equals one when the matched
  quantitative municipality status source classifies that municipality-year as
  `hybrid_bvr`.

## Added Variables

- `bvr_status`: one of `strict_bvr`, `hybrid_bvr`, or `no_bvr`.
- `strict_bvr`, `hybrid`, `any_bvr`, `no_bvr`: mutually exclusive status flags,
  except `any_bvr`, which is the union of strict and hybrid.
- `year_first_any_bvr`, `dist_any_bvr`: first observed strict-or-hybrid BVR year
  and event time.
- `year_first_strict_bvr`, `dist_strict_bvr`: first observed strict/full BVR year
  and event time.
- `year_first_hybrid_bvr`, `dist_hybrid_bvr`: first observed hybrid BVR year
  and event time.
- `pct_with_bvr`: share of the municipality electorate with biometric registration
  in the official TSE `perfil_eleitorado` file.
- `pct_low_ed_with_bvr`: share of low-education voters with biometric registration.
- `pct_high_ed_with_bvr`: share of high-education voters with biometric registration.

## Diagnostics

{status_lines}

## Caveat

For election years before 2012, there is no row in the matched quantitative
status files, so `bvr_status` is derived from the legacy first-treatment timing.
For 2012 onward, status comes from the matched quantitative files.

The biometric-share variables come from
`data/clean/tse_eleitorado/eleitorado_biometric_shares_2000_2018`. They are set
to missing for years where the raw TSE biometric count is zero nationally,
because this source does not capture the known early BVR rollout before 2014.
""",
        encoding="utf-8",
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    updated = build_updated_panel()
    diagnostics = validate(updated)
    updated.to_csv(OUTPUT_CSV, index=False)
    updated.to_parquet(OUTPUT_PARQUET, index=False)
    diagnostics.to_csv(DIAGNOSTICS_CSV, index=False)
    write_notes(diagnostics)
    print(f"Wrote {len(updated)} rows to {OUTPUT_CSV}")
    print(f"Wrote diagnostics to {DIAGNOSTICS_CSV}")
    print(diagnostics.to_string(index=False))


if __name__ == "__main__":
    main()
