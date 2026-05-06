from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
INTERIM_DIR = ROOT / "data" / "interim" / "tse_bvr"
LOG_DIR = ROOT / "resources" / "logs"
YEARS = [2008, 2010, 2012, 2014, 2016, 2018]
OFFICIAL_NEW = {2008: 3, 2010: 57}
OFFICIAL_CUMULATIVE = {2008: 3, 2010: 60, 2014: 764}


def _normalize_code(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text.zfill(7) if text else ""


def load_treatment(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    df = df.copy()
    df["municipality_id"] = df["municipality_id"].map(_normalize_code)
    df["year_first_treat"] = pd.to_numeric(df["year_first_treat"], errors="coerce").astype("Int64")
    if "zone" not in df.columns:
        df["zone"] = pd.NA
    return df


def summarize_counts(df: pd.DataFrame) -> pd.DataFrame:
    municipal_first = (
        df.groupby("municipality_id", as_index=False)
        .agg(
            year_first_treat=("year_first_treat", "min"),
            n_rows=("year_first_treat", "size"),
            n_years=("year_first_treat", "nunique"),
            n_zones=("zone", "nunique"),
        )
    )

    rows = []
    for year in YEARS:
        new_rows = int((df["year_first_treat"] == year).sum())
        new_municipalities = int((municipal_first["year_first_treat"] == year).sum())
        cumulative_municipalities = int((municipal_first["year_first_treat"] <= year).sum())
        rows.append(
            {
                "year": year,
                "new_rows_input_grain": new_rows,
                "new_municipalities": new_municipalities,
                "cumulative_municipalities": cumulative_municipalities,
                "official_new": OFFICIAL_NEW.get(year),
                "official_cumulative": OFFICIAL_CUMULATIVE.get(year),
                "diff_new_vs_official": None if year not in OFFICIAL_NEW else new_municipalities - OFFICIAL_NEW[year],
                "diff_cumulative_vs_official": None if year not in OFFICIAL_CUMULATIVE else cumulative_municipalities - OFFICIAL_CUMULATIVE[year],
            }
        )

    return pd.DataFrame(rows)


def duplicate_report(df: pd.DataFrame) -> pd.DataFrame:
    report = (
        df.groupby("municipality_id", as_index=False)
        .agg(
            municipality_name=("municipality_name", "first"),
            state=("state", "first"),
            n_rows=("year_first_treat", "size"),
            n_years=("year_first_treat", "nunique"),
            years=("year_first_treat", lambda s: ",".join(str(int(v)) for v in sorted(set(s.dropna())))),
            n_zones=("zone", "nunique"),
        )
        .sort_values(["n_years", "n_rows", "municipality_id"], ascending=[False, False, True])
        .reset_index(drop=True)
    )
    return report


def write_audit_log(df: pd.DataFrame, summary: pd.DataFrame, duplicates: pd.DataFrame, log_path: Path) -> None:
    municipality_pairs = int(df[["municipality_id", "zone"]].drop_duplicates().shape[0])
    municipality_count = int(df["municipality_id"].nunique())
    multi_year = int((duplicates["n_years"] > 1).sum())
    summary_text = summary.to_string(index=False)
    text = (
        "# TSE BVR Treatment Audit\n\n"
        "## Existing Dataset Grain\n\n"
        f"- Raw rows: {len(df)}\n"
        f"- Unique municipalities: {municipality_count}\n"
        f"- Unique municipality-zone pairs: {municipality_pairs}\n"
        f"- Municipalities with more than one treatment year in the file: {multi_year}\n\n"
        "## Municipality-Level Counts\n\n"
        f"```\n{summary_text}\n```\n\n"
        "## Diagnosis\n\n"
        "- The existing file is not a pure municipality-level first-treatment file.\n"
        "- Many municipalities reappear in later election-use years, so downstream code must collapse to the earliest municipality treatment year.\n"
        "- Large benchmark gaps should therefore be interpreted after municipality-level collapse, not from raw row counts.\n"
    )
    log_path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--counts-output", required=True)
    parser.add_argument("--duplicates-output", required=True)
    parser.add_argument("--log-output", required=True)
    args = parser.parse_args()

    df = load_treatment(Path(args.input))
    summary = summarize_counts(df)
    duplicates = duplicate_report(df)

    Path(args.counts_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.log_output).parent.mkdir(parents=True, exist_ok=True)

    summary.to_csv(args.counts_output, index=False)
    duplicates.to_csv(args.duplicates_output, index=False)
    write_audit_log(df, summary, duplicates, Path(args.log_output))


if __name__ == "__main__":
    main()
