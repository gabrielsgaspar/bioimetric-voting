from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from src.decomposition.aging_operator import (  # noqa: E402
    AGE_COHORTS,
    AGING_MATRIX,
    INFLOW_COHORTS,
    SURVIVAL_COHORTS,
    validate_aging_matrix,
)


OUTPUT_DIR = ROOT / "data" / "clean" / "decomposition"

PANEL_MAIN_PATH = OUTPUT_DIR / "decomposition_panel_main_v2.parquet"
PANEL_FULL_PATH = OUTPUT_DIR / "decomposition_panel_full_v2.parquet"
DATA_V2_PATH = OUTPUT_DIR / "decomposition_data_v2.parquet"
SURVIVAL_MUNICIPALITY_PATH = OUTPUT_DIR / "decomposition_survival_municipality.parquet"
SURVIVAL_STATE_PATH = OUTPUT_DIR / "decomposition_survival_state.parquet"
SURVIVAL_NATIONAL_PATH = OUTPUT_DIR / "decomposition_survival_national.parquet"
INFLOW_PATH = OUTPUT_DIR / "decomposition_inflows.parquet"
PROGRESSION_PATH = OUTPUT_DIR / "decomposition_progression_rates_v2.parquet"
FINAL_MUNICIPALITY_V2_PATH = OUTPUT_DIR / "decomposition_final_municipality_v2.parquet"

DYNAMIC_MUNICIPALITY_PATH = OUTPUT_DIR / "decomposition_dynamic_municipality.parquet"
DYNAMIC_COHORT_PATH = OUTPUT_DIR / "decomposition_dynamic_cohort.parquet"
DYNAMIC_AGGREGATE_PATH = OUTPUT_DIR / "decomposition_dynamic_aggregate.parquet"
DYNAMIC_PLACEBO_PATH = OUTPUT_DIR / "decomposition_dynamic_placebo_diagnostic.parquet"

YEARS = [2008, 2010, 2012, 2014, 2016, 2018]
TREATED_REGIMES = {"strict", "hybrid"}
PLACEBO_THRESHOLD = 0.02

EVENT_TIME_TARGETS = {
    0: -0.1268,
    2: -0.0822,
    4: -0.0601,
    6: -0.0307,
    8: 0.0004,
}


def percent(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{100 * float(value):.2f}%"


def count(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{float(value):,.0f}"


def read_required_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def normalize_common_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ibge_municipality_id"] = out["ibge_municipality_id"].astype(str).str.zfill(7)
    if "state" in out.columns:
        out["state"] = out["state"].astype(str).str.upper().str.strip()
    for column in ["year", "year_first_any_bvr", "year_first_strict_bvr", "year_first_hybrid_bvr"]:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="raise").astype(int)
    return out


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    for path in [
        PANEL_MAIN_PATH,
        PANEL_FULL_PATH,
        DATA_V2_PATH,
        SURVIVAL_MUNICIPALITY_PATH,
        SURVIVAL_STATE_PATH,
        SURVIVAL_NATIONAL_PATH,
        INFLOW_PATH,
        PROGRESSION_PATH,
    ]:
        if not path.exists():
            raise FileNotFoundError(path)

    panel = normalize_common_columns(pd.read_parquet(PANEL_MAIN_PATH))
    data_v2 = normalize_common_columns(pd.read_parquet(DATA_V2_PATH))
    survival = normalize_common_columns(pd.read_parquet(SURVIVAL_MUNICIPALITY_PATH))
    inflows = normalize_common_columns(pd.read_parquet(INFLOW_PATH))
    progression = normalize_common_columns(pd.read_parquet(PROGRESSION_PATH))

    required_panel = {
        "ibge_municipality_id",
        "state",
        "year",
        "age_cohort",
        "low_ed",
        "high_ed",
        "num_voters",
        "num_voters_bvr",
        "pct_bvr",
        "year_first_any_bvr",
        "year_first_strict_bvr",
        "year_first_hybrid_bvr",
        "first_regime",
    }
    required_data_v2 = {"ibge_municipality_id", "year", "age_cohort", "num_voters", "pct_bvr"}
    required_survival = {"ibge_municipality_id", "state", "age_cohort", "sigma_used"}
    required_inflows = {"ibge_municipality_id", "state", "age_cohort", "inflow_rate_used"}
    required_progression = {"ibge_municipality_id", "state", "age_cohort", "delta_used"}

    for label, frame, required in [
        ("panel_main_v2", panel, required_panel),
        ("decomposition_data_v2", data_v2, required_data_v2),
        ("survival", survival, required_survival),
        ("inflows", inflows, required_inflows),
        ("progression", progression, required_progression),
    ]:
        missing = sorted(required - set(frame.columns))
        if missing:
            raise RuntimeError(f"{label} missing required columns: {missing}")

    for column in ["low_ed", "high_ed", "num_voters", "num_voters_bvr"]:
        panel[column] = pd.to_numeric(panel[column], errors="raise")
    data_v2["num_voters"] = pd.to_numeric(data_v2["num_voters"], errors="raise")
    data_v2["pct_bvr"] = pd.to_numeric(data_v2["pct_bvr"], errors="coerce").fillna(0.0)
    survival["sigma_used"] = pd.to_numeric(survival["sigma_used"], errors="coerce")
    inflows["inflow_rate_used"] = pd.to_numeric(inflows["inflow_rate_used"], errors="coerce")
    progression["delta_used"] = pd.to_numeric(progression["delta_used"], errors="coerce").fillna(0.0)

    unexpected_ages = sorted(set(panel["age_cohort"].unique()) - set(AGE_COHORTS))
    if unexpected_ages:
        raise RuntimeError(f"Unexpected age cohorts in panel_main_v2: {unexpected_ages}")

    return panel, data_v2, survival, inflows, progression


def build_municipality_metadata(panel: pd.DataFrame) -> pd.DataFrame:
    metadata = (
        panel[
            [
                "ibge_municipality_id",
                "state",
                "year_first_any_bvr",
                "year_first_strict_bvr",
                "year_first_hybrid_bvr",
                "first_regime",
            ]
        ]
        .drop_duplicates("ibge_municipality_id")
        .sort_values(["state", "ibge_municipality_id"])
        .reset_index(drop=True)
    )
    duplicated = metadata["ibge_municipality_id"].duplicated().sum()
    if duplicated:
        raise RuntimeError(f"Municipality metadata contains {int(duplicated):,} duplicated ids")
    return metadata


def build_observed_counts(panel: pd.DataFrame, data_v2: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
    working = panel.copy()
    working["observed_low_count"] = working["num_voters"] * working["low_ed"]
    working["observed_high_count"] = working["num_voters"] * working["high_ed"]

    grouped = (
        working.groupby(["ibge_municipality_id", "year", "age_cohort"], as_index=False)
        .agg(
            observed_count=("num_voters", "sum"),
            observed_low_count=("observed_low_count", "sum"),
            observed_high_count=("observed_high_count", "sum"),
        )
    )

    bvr_source = data_v2[data_v2["age_cohort"].isin(AGE_COHORTS) & data_v2["num_voters"].gt(0)].copy()
    bvr_source["weighted_pct_bvr"] = bvr_source["pct_bvr"].clip(lower=0.0, upper=1.0) * bvr_source["num_voters"]
    pct_bvr = (
        bvr_source.groupby(["ibge_municipality_id", "year", "age_cohort"], as_index=False)
        .agg(weighted_pct_bvr=("weighted_pct_bvr", "sum"), pct_bvr_weight=("num_voters", "sum"))
    )
    pct_bvr["pct_bvr_at_y"] = pct_bvr["weighted_pct_bvr"] / pct_bvr["pct_bvr_weight"].replace(0, np.nan)
    pct_bvr = pct_bvr[["ibge_municipality_id", "year", "age_cohort", "pct_bvr_at_y"]]

    complete = metadata.merge(pd.DataFrame({"year": YEARS}), how="cross").merge(
        pd.DataFrame({"age_cohort": AGE_COHORTS}), how="cross"
    )
    counts = complete.merge(grouped, how="left", on=["ibge_municipality_id", "year", "age_cohort"])
    counts = counts.merge(pct_bvr, how="left", on=["ibge_municipality_id", "year", "age_cohort"])
    for column in ["observed_count", "observed_low_count", "observed_high_count", "pct_bvr_at_y"]:
        counts[column] = pd.to_numeric(counts[column], errors="coerce").fillna(0.0)

    counts["age_order"] = counts["age_cohort"].map({cohort: i for i, cohort in enumerate(AGE_COHORTS)})
    counts = counts.sort_values(["ibge_municipality_id", "year", "age_order"]).reset_index(drop=True)
    return counts.drop(columns="age_order")


def pivot_count_matrix(counts: pd.DataFrame, value: str) -> pd.DataFrame:
    matrix = counts.pivot_table(
        index=["ibge_municipality_id", "year"],
        columns="age_cohort",
        values=value,
        aggfunc="sum",
        fill_value=0.0,
    )
    return matrix.reindex(columns=AGE_COHORTS, fill_value=0.0).sort_index()


def pivot_rate_matrix(frame: pd.DataFrame, value: str, fill_value: float = np.nan) -> pd.DataFrame:
    matrix = frame.pivot_table(
        index="ibge_municipality_id",
        columns="age_cohort",
        values=value,
        aggfunc="first",
    )
    return matrix.reindex(columns=AGE_COHORTS).fillna(fill_value).sort_index()


def safe_share(numerator: np.ndarray, denominator: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    output = np.array(fallback, dtype=float, copy=True)
    mask = denominator > 0
    output[mask] = numerator[mask] / denominator[mask]
    return np.clip(output, 0.0, 1.0)


def first_positive_year(observed_total: pd.DataFrame, municipality_id: str) -> int:
    totals = observed_total.loc[municipality_id]
    positive = totals.sum(axis=1)
    positive_years = [int(year) for year, value in positive.items() if value > 0]
    if 2008 in positive_years:
        return 2008
    if positive_years:
        return min(positive_years)
    return 2008


def build_dynamic_panels(
    metadata: pd.DataFrame,
    counts: pd.DataFrame,
    survival: pd.DataFrame,
    inflows: pd.DataFrame,
    progression: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    observed_total = pivot_count_matrix(counts, "observed_count")
    observed_low = pivot_count_matrix(counts, "observed_low_count")
    pct_bvr = pivot_count_matrix(counts, "pct_bvr_at_y")

    sigma = pivot_rate_matrix(survival, "sigma_used")
    inflow_rate = pivot_rate_matrix(inflows, "inflow_rate_used", fill_value=0.0)
    delta = pivot_rate_matrix(progression, "delta_used", fill_value=0.0)

    missing_sigma = sigma.loc[:, SURVIVAL_COHORTS].isna().sum().sum()
    if missing_sigma:
        raise RuntimeError(f"Missing sigma_used for {int(missing_sigma):,} municipality-survival-cohort cells")
    missing_inflow = inflow_rate.loc[:, INFLOW_COHORTS].isna().sum().sum()
    if missing_inflow:
        raise RuntimeError(f"Missing inflow_rate_used for {int(missing_inflow):,} municipality-inflow-cohort cells")

    aging_matrix = AGING_MATRIX.to_numpy(dtype=float)
    survival_mask = np.array([cohort in SURVIVAL_COHORTS for cohort in AGE_COHORTS])
    inflow_mask = np.array([cohort in INFLOW_COHORTS for cohort in AGE_COHORTS])

    municipality_rows: list[dict[str, object]] = []
    cohort_blocks: list[pd.DataFrame] = []

    for meta in metadata.itertuples(index=False):
        municipality_id = str(meta.ibge_municipality_id)
        baseline_year_used = first_positive_year(observed_total, municipality_id)
        baseline_total = observed_total.loc[(municipality_id, baseline_year_used)].to_numpy(dtype=float)
        baseline_low = observed_low.loc[(municipality_id, baseline_year_used)].to_numpy(dtype=float)
        baseline_2008 = float(observed_total.loc[(municipality_id, 2008)].sum())
        if baseline_2008 <= 0:
            baseline_2008 = float(baseline_total.sum())
        baseline_share = safe_share(baseline_low, baseline_total, np.zeros(len(AGE_COHORTS)))

        sigma_vec = sigma.loc[municipality_id].to_numpy(dtype=float)
        inflow_vec = inflow_rate.loc[municipality_id].to_numpy(dtype=float)
        delta_vec = delta.loc[municipality_id].to_numpy(dtype=float)

        current_total: np.ndarray | None = None
        current_low: np.ndarray | None = None

        for year in YEARS:
            observed_vec = observed_total.loc[(municipality_id, year)].to_numpy(dtype=float)
            observed_low_vec = observed_low.loc[(municipality_id, year)].to_numpy(dtype=float)
            pct_bvr_vec = pct_bvr.loc[(municipality_id, year)].to_numpy(dtype=float).clip(0.0, 1.0)

            if year < baseline_year_used:
                predicted_vec = observed_vec.copy()
                predicted_low_vec = observed_low_vec.copy()
            elif year == baseline_year_used:
                current_total = observed_vec.copy()
                current_low = observed_low_vec.copy()
                predicted_vec = current_total.copy()
                predicted_low_vec = current_low.copy()
            else:
                if current_total is None or current_low is None:
                    raise RuntimeError(f"Missing initialized baseline vector for {municipality_id} in {year}")
                previous_total_sum = float(current_total.sum())
                aged_total = current_total @ aging_matrix.T
                aged_low = current_low @ aging_matrix.T
                same_cohort_share = safe_share(current_low, current_total, baseline_share)
                aged_share = safe_share(aged_low, aged_total, same_cohort_share)

                predicted_vec = np.zeros(len(AGE_COHORTS), dtype=float)
                predicted_low_vec = np.zeros(len(AGE_COHORTS), dtype=float)

                predicted_vec[survival_mask] = sigma_vec[survival_mask] * aged_total[survival_mask]
                survival_pi = np.clip(aged_share[survival_mask] - delta_vec[survival_mask], 0.0, 1.0)
                predicted_low_vec[survival_mask] = predicted_vec[survival_mask] * survival_pi

                predicted_vec[inflow_mask] = inflow_vec[inflow_mask] * previous_total_sum
                inflow_pi = np.clip(same_cohort_share[inflow_mask] - delta_vec[inflow_mask], 0.0, 1.0)
                predicted_low_vec[inflow_mask] = predicted_vec[inflow_mask] * inflow_pi

                current_total = predicted_vec.copy()
                current_low = predicted_low_vec.copy()

            if year == 2008:
                exit_vec = np.zeros(len(AGE_COHORTS), dtype=float)
                relabel_B = np.zeros(len(AGE_COHORTS), dtype=float)
                relabel_C = np.zeros(len(AGE_COHORTS), dtype=float)
                bound_binds_B = np.zeros(len(AGE_COHORTS), dtype=bool)
                bound_binds_C = np.zeros(len(AGE_COHORTS), dtype=bool)
            else:
                exit_vec = np.maximum(0.0, predicted_vec - observed_vec)
                pi_predicted = safe_share(predicted_low_vec, predicted_vec, np.zeros(len(AGE_COHORTS)))
                relabel_B_raw = np.maximum(0.0, predicted_low_vec - observed_low_vec - exit_vec)
                relabel_C_raw = np.maximum(0.0, predicted_low_vec - observed_low_vec - exit_vec * pi_predicted)
                b_bound = pct_bvr_vec * observed_vec
                relabel_B = np.minimum(relabel_B_raw, b_bound)
                relabel_C = np.minimum(relabel_C_raw, b_bound)
                bound_binds_B = relabel_B_raw > b_bound + 1e-9
                bound_binds_C = relabel_C_raw > b_bound + 1e-9

            event_time = (
                np.nan
                if int(meta.year_first_any_bvr) == 9999
                else int(year) - int(meta.year_first_any_bvr)
            )
            is_pre_treatment = int(year < int(meta.year_first_any_bvr))
            is_treated_now = int(int(meta.year_first_any_bvr) != 9999 and year >= int(meta.year_first_any_bvr))

            exit_count = float(exit_vec.sum())
            relabel_B_count = float(relabel_B.sum())
            relabel_C_count = float(relabel_C.sum())
            observed_sum = float(observed_vec.sum())
            predicted_sum = float(predicted_vec.sum())
            municipality_rows.append(
                {
                    "ibge_municipality_id": municipality_id,
                    "state": meta.state,
                    "year": int(year),
                    "first_regime": meta.first_regime,
                    "year_first_any_bvr": int(meta.year_first_any_bvr),
                    "year_first_strict_bvr": int(meta.year_first_strict_bvr),
                    "year_first_hybrid_bvr": int(meta.year_first_hybrid_bvr),
                    "event_time": event_time,
                    "is_pre_treatment": is_pre_treatment,
                    "is_treated_now": is_treated_now,
                    "baseline_2008": baseline_2008,
                    "baseline_year_used": int(baseline_year_used),
                    "baseline_is_exact_2008": bool(baseline_year_used == 2008),
                    "observed_total_voters_y": observed_sum,
                    "predicted_total_voters_y_no_bvr": predicted_sum,
                    "exit_count_cumulative": exit_count,
                    "exit_rate_cumulative": exit_count / baseline_2008 if baseline_2008 > 0 else np.nan,
                    "relabel_count_B_cumulative": relabel_B_count,
                    "relabel_rate_B_cumulative": relabel_B_count / baseline_2008 if baseline_2008 > 0 else np.nan,
                    "relabel_count_C_cumulative": relabel_C_count,
                    "relabel_rate_C_cumulative": relabel_C_count / baseline_2008 if baseline_2008 > 0 else np.nan,
                    "bbound_binding_share_y": float(bound_binds_B.mean()),
                    "bbound_binding_share_C_y": float(bound_binds_C.mean()),
                }
            )

            cohort_blocks.append(
                pd.DataFrame(
                    {
                        "ibge_municipality_id": municipality_id,
                        "state": meta.state,
                        "year": int(year),
                        "age_cohort": AGE_COHORTS,
                        "first_regime": meta.first_regime,
                        "year_first_any_bvr": int(meta.year_first_any_bvr),
                        "event_time": event_time,
                        "is_pre_treatment": is_pre_treatment,
                        "observed_count": observed_vec,
                        "predicted_count_no_bvr": predicted_vec,
                        "exit_count_cumulative": exit_vec,
                        "relabel_count_B_cumulative": relabel_B,
                        "relabel_count_C_cumulative": relabel_C,
                        "pct_bvr_at_y": pct_bvr_vec,
                        "bbound_binding": bound_binds_B,
                        "bbound_binding_C": bound_binds_C,
                    }
                )
            )

    municipality = pd.DataFrame(municipality_rows)
    cohort = pd.concat(cohort_blocks, ignore_index=True)
    cohort["event_time"] = cohort["event_time"].astype("float64")
    municipality["event_time"] = municipality["event_time"].astype("float64")
    return municipality, cohort


def build_dynamic_aggregate(municipality: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year in YEARS:
        year_frame = municipality[municipality["year"].eq(year)]
        for label, subset in [
            ("strict", year_frame[year_frame["first_regime"].eq("strict")]),
            ("hybrid", year_frame[year_frame["first_regime"].eq("hybrid")]),
            ("all_treated", year_frame[year_frame["first_regime"].isin(TREATED_REGIMES)]),
            ("never_treated", year_frame[year_frame["first_regime"].eq("never_treated")]),
        ]:
            baseline = subset["baseline_2008"].sum()
            exit_count = subset["exit_count_cumulative"].sum()
            relabel_B = subset["relabel_count_B_cumulative"].sum()
            relabel_C = subset["relabel_count_C_cumulative"].sum()
            rows.append(
                {
                    "year": year,
                    "first_regime": label,
                    "total_municipalities": int(subset["ibge_municipality_id"].nunique()),
                    "total_baseline_2008": float(baseline),
                    "total_exit_count_cumulative": float(exit_count),
                    "total_relabel_B_count_cumulative": float(relabel_B),
                    "total_relabel_C_count_cumulative": float(relabel_C),
                    "exit_rate_aggregate": float(exit_count / baseline) if baseline > 0 else np.nan,
                    "relabel_rate_B_aggregate": float(relabel_B / baseline) if baseline > 0 else np.nan,
                    "relabel_rate_C_aggregate": float(relabel_C / baseline) if baseline > 0 else np.nan,
                }
            )
    return pd.DataFrame(rows)


def build_placebo_diagnostic(municipality: pd.DataFrame) -> pd.DataFrame:
    working = municipality.copy()
    working["treatment_status"] = np.where(working["is_treated_now"].eq(1), "post", "pre")
    grouped = (
        working.groupby(["year", "first_regime", "treatment_status"], as_index=False)
        .agg(
            n_observations=("ibge_municipality_id", "size"),
            mean_exit_rate=("exit_rate_cumulative", "mean"),
            p25_exit_rate=("exit_rate_cumulative", lambda s: s.quantile(0.25)),
            p75_exit_rate=("exit_rate_cumulative", lambda s: s.quantile(0.75)),
            share_exit_above_threshold=(
                "exit_rate_cumulative",
                lambda s: float(s.gt(PLACEBO_THRESHOLD).mean()),
            ),
            mean_relabel_B_rate=("relabel_rate_B_cumulative", "mean"),
            p25_relabel_B_rate=("relabel_rate_B_cumulative", lambda s: s.quantile(0.25)),
            p75_relabel_B_rate=("relabel_rate_B_cumulative", lambda s: s.quantile(0.75)),
            share_relabel_B_above_threshold=(
                "relabel_rate_B_cumulative",
                lambda s: float(s.gt(PLACEBO_THRESHOLD).mean()),
            ),
            mean_relabel_C_rate=("relabel_rate_C_cumulative", "mean"),
            p25_relabel_C_rate=("relabel_rate_C_cumulative", lambda s: s.quantile(0.25)),
            p75_relabel_C_rate=("relabel_rate_C_cumulative", lambda s: s.quantile(0.75)),
            share_relabel_C_above_threshold=(
                "relabel_rate_C_cumulative",
                lambda s: float(s.gt(PLACEBO_THRESHOLD).mean()),
            ),
        )
    )
    return grouped.sort_values(["year", "first_regime", "treatment_status"]).reset_index(drop=True)


def single_cycle_reconciliation(municipality: pd.DataFrame) -> pd.DataFrame:
    if not FINAL_MUNICIPALITY_V2_PATH.exists():
        return pd.DataFrame()

    single = normalize_common_columns(pd.read_parquet(FINAL_MUNICIPALITY_V2_PATH))
    single["t_post"] = pd.to_numeric(single["t_post"], errors="raise").astype(int)

    dynamic_at_tpost = municipality.rename(columns={"year": "t_post"})
    merged = single.merge(
        dynamic_at_tpost[
            [
                "ibge_municipality_id",
                "t_post",
                "exit_count_cumulative",
                "relabel_count_B_cumulative",
                "relabel_count_C_cumulative",
            ]
        ],
        how="left",
        on=["ibge_municipality_id", "t_post"],
        validate="one_to_one",
    )
    rows: list[dict[str, object]] = []
    for metric, dynamic_metric in [
        ("exit_count", "exit_count_cumulative"),
        ("R_B_count", "relabel_count_B_cumulative"),
        ("R_C_count", "relabel_count_C_cumulative"),
    ]:
        diff = merged[dynamic_metric] - merged[metric]
        rows.append(
            {
                "comparison": "current_single_cycle_t_post",
                "metric": metric,
                "n_rows": int(diff.notna().sum()),
                "mean_abs_difference": float(diff.abs().mean()),
                "median_abs_difference": float(diff.abs().median()),
                "max_abs_difference": float(diff.abs().max()),
                "n_rows_abs_gt_1": int(diff.abs().gt(1.0).sum()),
            }
        )

    plus_two = single.copy()
    plus_two["t_post"] = plus_two["year_first_any_bvr"] + 2
    merged_plus_two = plus_two.merge(
        dynamic_at_tpost[
            [
                "ibge_municipality_id",
                "t_post",
                "exit_count_cumulative",
                "relabel_count_B_cumulative",
                "relabel_count_C_cumulative",
            ]
        ],
        how="left",
        on=["ibge_municipality_id", "t_post"],
        validate="one_to_one",
    )
    for metric, dynamic_metric in [
        ("exit_count", "exit_count_cumulative"),
        ("R_B_count", "relabel_count_B_cumulative"),
        ("R_C_count", "relabel_count_C_cumulative"),
    ]:
        diff = merged_plus_two[dynamic_metric] - merged_plus_two[metric]
        rows.append(
            {
                "comparison": "prompt_plus_two_horizon",
                "metric": metric,
                "n_rows": int(diff.notna().sum()),
                "mean_abs_difference": float(diff.abs().mean()),
                "median_abs_difference": float(diff.abs().median()),
                "max_abs_difference": float(diff.abs().max()),
                "n_rows_abs_gt_1": int(diff.abs().gt(1.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def print_table(title: str, frame: pd.DataFrame, max_rows: int | None = None) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if frame.empty:
        print("(none)")
        return
    if max_rows is not None and len(frame) > max_rows:
        print(frame.head(max_rows).to_string(index=False))
        print(f"... ({len(frame) - max_rows:,} additional rows)")
    else:
        print(frame.to_string(index=False))


def print_validation(municipality: pd.DataFrame, cohort: pd.DataFrame, aggregate: pd.DataFrame, placebo: pd.DataFrame) -> None:
    print("=" * 72)
    print("DYNAMIC DECOMPOSITION EXTENSION SUMMARY")
    print("=" * 72)
    print(f"Municipality-year rows: {len(municipality):,}")
    print(f"Cohort-year rows: {len(cohort):,}")
    print(f"Municipalities: {municipality['ibge_municipality_id'].nunique():,}")
    print(f"Municipalities without exact positive 2008 baseline: {int((~municipality.groupby('ibge_municipality_id')['baseline_is_exact_2008'].first()).sum()):,}")

    trajectory_rows: list[dict[str, object]] = []
    for year in YEARS:
        subset = municipality[
            municipality["year"].eq(year)
            & municipality["first_regime"].isin(TREATED_REGIMES)
            & municipality["year_first_any_bvr"].le(year)
        ]
        baseline = subset["baseline_2008"].sum()
        trajectory_rows.append(
            {
                "year": year,
                "treated_municipalities_now": int(subset["ibge_municipality_id"].nunique()),
                "exit_count": subset["exit_count_cumulative"].sum(),
                "R_B_count": subset["relabel_count_B_cumulative"].sum(),
                "baseline_2008": baseline,
                "exit_rate": subset["exit_count_cumulative"].sum() / baseline if baseline > 0 else np.nan,
                "R_B_rate": subset["relabel_count_B_cumulative"].sum() / baseline if baseline > 0 else np.nan,
            }
        )
    trajectory = pd.DataFrame(trajectory_rows)
    display = trajectory.copy()
    for column in ["exit_count", "R_B_count", "baseline_2008"]:
        display[column] = display[column].map(count)
    for column in ["exit_rate", "R_B_rate"]:
        display[column] = display[column].map(percent)
    print_table("National aggregate trajectory among municipalities already treated by year", display)

    reconciliation = single_cycle_reconciliation(municipality)
    if not reconciliation.empty:
        display_recon = reconciliation.copy()
        for column in ["mean_abs_difference", "median_abs_difference", "max_abs_difference"]:
            display_recon[column] = display_recon[column].map(lambda x: f"{x:,.3f}" if pd.notna(x) else "NA")
        print_table("Single-cycle reconciliation diagnostics", display_recon)
        print(
            "\nNote: the current v2 single-cycle file has t_post equal to year_first_any_bvr for all rows. "
            "The dynamic extension starts from the 2008 cohort vector, so later adoption cohorts need not match exactly."
        )

    strict_pre = municipality[
        municipality["first_regime"].eq("strict")
        & municipality["year_first_any_bvr"].ne(9999)
        & municipality["year"].lt(municipality["year_first_any_bvr"])
    ]
    hybrid_pre_strict = municipality[
        municipality["first_regime"].eq("hybrid")
        & municipality["year"].lt(municipality["year_first_strict_bvr"])
    ]
    placebo_rows = []
    for label, frame in [("strict_pre_treatment", strict_pre), ("hybrid_pre_strict", hybrid_pre_strict)]:
        placebo_rows.append(
            {
                "sample": label,
                "n_rows": len(frame),
                "share_exit_gt_2pct": frame["exit_rate_cumulative"].gt(PLACEBO_THRESHOLD).mean(),
                "share_relabel_B_gt_2pct": frame["relabel_rate_B_cumulative"].gt(PLACEBO_THRESHOLD).mean(),
                "share_relabel_C_gt_2pct": frame["relabel_rate_C_cumulative"].gt(PLACEBO_THRESHOLD).mean(),
            }
        )
    placebo_display = pd.DataFrame(placebo_rows)
    for column in ["share_exit_gt_2pct", "share_relabel_B_gt_2pct", "share_relabel_C_gt_2pct"]:
        placebo_display[column] = placebo_display[column].map(percent)
    print_table("Placebo threshold checks", placebo_display)

    event = municipality[
        municipality["first_regime"].isin(TREATED_REGIMES)
        & municipality["event_time"].isin(list(EVENT_TIME_TARGETS))
    ].copy()
    event_summary = (
        event.groupby("event_time", as_index=False)
        .agg(
            municipalities=("ibge_municipality_id", "nunique"),
            baseline_2008=("baseline_2008", "sum"),
            exit_count=("exit_count_cumulative", "sum"),
            R_B_count=("relabel_count_B_cumulative", "sum"),
        )
        .sort_values("event_time")
    )
    event_summary["cohort_exit_rate"] = event_summary["exit_count"] / event_summary["baseline_2008"].replace(0, np.nan)
    event_summary["cross_section_gamma_N"] = event_summary["event_time"].map(EVENT_TIME_TARGETS)
    event_summary["cross_section_exit_magnitude"] = -event_summary["cross_section_gamma_N"]
    event_display = event_summary.copy()
    event_display["event_time"] = event_display["event_time"].astype(int)
    for column in ["baseline_2008", "exit_count", "R_B_count"]:
        event_display[column] = event_display[column].map(count)
    for column in ["cohort_exit_rate", "cross_section_gamma_N", "cross_section_exit_magnitude"]:
        event_display[column] = event_display[column].map(percent)
    print_table("Event-time trajectory compared with cross-section registry effect", event_display)

    bind = (
        cohort.groupby(["year", "first_regime"], as_index=False)
        .agg(B_bind_share=("bbound_binding", "mean"), C_bind_share=("bbound_binding_C", "mean"), cells=("age_cohort", "size"))
        .sort_values(["year", "first_regime"])
    )
    bind_display = bind.copy()
    for column in ["B_bind_share", "C_bind_share"]:
        bind_display[column] = bind_display[column].map(percent)
    print_table("b-bound binding share by year and first_regime", bind_display, max_rows=30)

    print_table("Aggregate-year panel preview", aggregate.head(12))
    print_table("Placebo diagnostic preview", placebo.head(12))

    print("\nFiles saved:")
    for path in [
        DYNAMIC_MUNICIPALITY_PATH,
        DYNAMIC_COHORT_PATH,
        DYNAMIC_AGGREGATE_PATH,
        DYNAMIC_PLACEBO_PATH,
    ]:
        print(f"  {path.relative_to(ROOT)}")


def main() -> None:
    pd.set_option("display.width", 240)
    pd.set_option("display.max_columns", None)
    validate_aging_matrix()

    panel, data_v2, survival, inflows, progression = load_inputs()
    metadata = build_municipality_metadata(panel)
    counts = build_observed_counts(panel, data_v2, metadata)
    municipality, cohort = build_dynamic_panels(metadata, counts, survival, inflows, progression)
    aggregate = build_dynamic_aggregate(municipality)
    placebo = build_placebo_diagnostic(municipality)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    municipality.to_parquet(DYNAMIC_MUNICIPALITY_PATH, index=False)
    cohort.to_parquet(DYNAMIC_COHORT_PATH, index=False)
    aggregate.to_parquet(DYNAMIC_AGGREGATE_PATH, index=False)
    placebo.to_parquet(DYNAMIC_PLACEBO_PATH, index=False)

    print_validation(municipality, cohort, aggregate, placebo)


if __name__ == "__main__":
    main()
