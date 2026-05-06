from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))


OUTPUT_DIR = ROOT / "data" / "clean" / "decomposition"
PANEL_PATH = OUTPUT_DIR / "decomposition_panel_main.parquet"
EXIT_MUNICIPALITY_PATH = OUTPUT_DIR / "decomposition_exit_municipality.parquet"
RELABEL_MUNICIPALITY_PATH = OUTPUT_DIR / "decomposition_relabel_municipality.parquet"
RELABEL_COHORT_PATH = OUTPUT_DIR / "decomposition_relabel_cohort.parquet"
TSE_PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018_bvr_status_updated.parquet"

FINAL_MUNICIPALITY_PATH = OUTPUT_DIR / "decomposition_final_municipality.parquet"
FINAL_AGGREGATE_PATH = OUTPUT_DIR / "decomposition_final_aggregate.parquet"
FINAL_BY_COHORT_PATH = OUTPUT_DIR / "decomposition_final_by_cohort.parquet"
CONSISTENCY_PATH = OUTPUT_DIR / "decomposition_consistency_check.parquet"
MAP_RATES_PATH = OUTPUT_DIR / "decomposition_map_rates.parquet"
MAP_COUNTS_PATH = OUTPUT_DIR / "decomposition_map_counts.parquet"

CROSS_SECTION_VALUES = {
    "exit_scenario_B": 0.1260,
    "R_B_lower_bound": 0.0522,
    "R_C_scenario_C": 0.1040,
}


def percent(value: float) -> str:
    return "NA" if pd.isna(value) else f"{100 * float(value):.2f}%"


def fmt_count(value: float) -> str:
    if pd.isna(value):
        return "NA"
    return f"{float(value):,.0f}"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    for path in [PANEL_PATH, EXIT_MUNICIPALITY_PATH, RELABEL_MUNICIPALITY_PATH, RELABEL_COHORT_PATH]:
        if not path.exists():
            raise FileNotFoundError(path)
    panel = pd.read_parquet(PANEL_PATH)
    exit_muni = pd.read_parquet(EXIT_MUNICIPALITY_PATH)
    relabel_muni = pd.read_parquet(RELABEL_MUNICIPALITY_PATH)
    relabel_cohort = pd.read_parquet(RELABEL_COHORT_PATH)

    for frame in [panel, exit_muni, relabel_muni, relabel_cohort]:
        frame["ibge_municipality_id"] = frame["ibge_municipality_id"].astype(str).str.zfill(7)
        if "state" in frame.columns:
            frame["state"] = frame["state"].astype(str).str.upper().str.strip()

    panel["year"] = pd.to_numeric(panel["year"], errors="raise").astype(int)
    panel["num_voters"] = pd.to_numeric(panel["num_voters"], errors="raise")
    for frame in [exit_muni, relabel_muni, relabel_cohort]:
        if "t_post" in frame.columns:
            frame["t_post"] = pd.to_numeric(frame["t_post"], errors="raise").astype(int)
        if "year_first_any_bvr" in frame.columns:
            frame["year_first_any_bvr"] = pd.to_numeric(frame["year_first_any_bvr"], errors="raise").astype(int)

    return panel, exit_muni, relabel_muni, relabel_cohort


def build_2008_baseline(panel: pd.DataFrame) -> pd.DataFrame:
    baseline_2008 = (
        panel[panel["year"].eq(2008)]
        .groupby("ibge_municipality_id", as_index=False)
        .agg(N_2008_total=("num_voters", "sum"))
    )
    earliest = (
        panel.sort_values(["ibge_municipality_id", "year"])
        .groupby(["ibge_municipality_id", "year"], as_index=False)
        .agg(N_earliest_total=("num_voters", "sum"))
        .sort_values(["ibge_municipality_id", "year"])
        .drop_duplicates("ibge_municipality_id", keep="first")
        .rename(columns={"year": "baseline_year_used"})
    )
    baseline = earliest.merge(baseline_2008, how="left", on="ibge_municipality_id", validate="one_to_one")
    baseline["N_2008_total"] = baseline["N_2008_total"].fillna(baseline["N_earliest_total"])
    baseline["baseline_year_used"] = np.where(
        baseline["baseline_year_used"].eq(2008) | baseline["N_2008_total"].eq(baseline["N_earliest_total"]),
        baseline["baseline_year_used"],
        2008,
    )
    baseline["baseline_is_exact_2008"] = baseline["baseline_year_used"].eq(2008)
    baseline = baseline.drop(columns="N_earliest_total")
    return baseline


def build_final_municipality(
    exit_muni: pd.DataFrame,
    relabel_muni: pd.DataFrame,
    baseline_2008: pd.DataFrame,
) -> pd.DataFrame:
    merge_keys = ["ibge_municipality_id", "state", "t_post", "year_first_any_bvr", "first_regime"]
    final = exit_muni.merge(
        relabel_muni,
        how="inner",
        on=merge_keys,
        validate="one_to_one",
        suffixes=("", "_relabel"),
    )
    if len(final) != len(exit_muni):
        raise RuntimeError(
            f"Exit/relabel municipality merge lost rows: exit={len(exit_muni):,}, merged={len(final):,}"
        )

    final = final.merge(baseline_2008, how="left", on="ibge_municipality_id", validate="many_to_one")
    missing_baseline = final["N_2008_total"].isna().sum()
    if missing_baseline:
        raise RuntimeError(f"Missing 2008 baseline for {int(missing_baseline):,} treated municipalities")

    final["exit_count"] = final["exit_count_total"]
    final["R_B_count"] = final["R_B_total"]
    final["R_C_count"] = final["R_C_total"]
    final["exit_rate_t_post"] = final["exit_count"] / final["total_observed"].replace(0, np.nan)
    final["R_B_rate_t_post"] = final["R_B_count"] / final["total_observed"].replace(0, np.nan)
    final["R_C_rate_t_post"] = final["R_C_count"] / final["total_observed"].replace(0, np.nan)
    final["exit_rate_2008"] = final["exit_count"] / final["N_2008_total"].replace(0, np.nan)
    final["R_B_rate_2008"] = final["R_B_count"] / final["N_2008_total"].replace(0, np.nan)
    final["R_C_rate_2008"] = final["R_C_count"] / final["N_2008_total"].replace(0, np.nan)

    return final[
        [
            "ibge_municipality_id",
            "state",
            "t_post",
            "year_first_any_bvr",
            "first_regime",
            "N_2008_total",
            "baseline_year_used",
            "baseline_is_exact_2008",
            "total_predicted",
            "total_observed",
            "exit_count",
            "R_B_count",
            "R_C_count",
            "exit_rate_t_post",
            "R_B_rate_t_post",
            "R_C_rate_t_post",
            "exit_rate_2008",
            "R_B_rate_2008",
            "R_C_rate_2008",
            "n_cohorts_with_exit",
            "n_cohorts_bound_binds_B",
            "n_cohorts_bound_binds_C",
        ]
    ].sort_values(["t_post", "state", "ibge_municipality_id"]).reset_index(drop=True)


def aggregate_rows(frame: pd.DataFrame, group_label: str, group_value: str | None = None) -> dict[str, float | int | str]:
    working = frame if group_value is None else frame[frame["first_regime"].eq(group_value)]
    national_2008 = working["N_2008_total"].sum()
    national_t_post = working["total_observed"].sum()
    exit_count = working["exit_count"].sum()
    R_B_count = working["R_B_count"].sum()
    R_C_count = working["R_C_count"].sum()
    return {
        "aggregation_level": group_label,
        "n_municipalities": int(working["ibge_municipality_id"].nunique()),
        "national_2008_baseline": float(national_2008),
        "national_t_post_observed": float(national_t_post),
        "national_exit_count": float(exit_count),
        "national_R_B_count": float(R_B_count),
        "national_R_C_count": float(R_C_count),
        "national_exit_rate_2008": float(exit_count / national_2008) if national_2008 else np.nan,
        "national_R_B_rate_2008": float(R_B_count / national_2008) if national_2008 else np.nan,
        "national_R_C_rate_2008": float(R_C_count / national_2008) if national_2008 else np.nan,
        "national_exit_rate_t_post": float(exit_count / national_t_post) if national_t_post else np.nan,
        "national_R_B_rate_t_post": float(R_B_count / national_t_post) if national_t_post else np.nan,
        "national_R_C_rate_t_post": float(R_C_count / national_t_post) if national_t_post else np.nan,
    }


def build_aggregate(final: pd.DataFrame) -> pd.DataFrame:
    rows = [
        aggregate_rows(final, "strict", "strict"),
        aggregate_rows(final, "hybrid", "hybrid"),
        aggregate_rows(final, "all_treated", None),
    ]
    return pd.DataFrame(rows)


def build_by_cohort(final: pd.DataFrame, relabel_cohort: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        final.groupby(["year_first_any_bvr", "first_regime"], as_index=False)
        .agg(
            n_municipalities=("ibge_municipality_id", "nunique"),
            N_2008_total=("N_2008_total", "sum"),
            exit_count=("exit_count", "sum"),
            R_B_count=("R_B_count", "sum"),
            R_C_count=("R_C_count", "sum"),
        )
    )
    grouped["exit_rate_2008"] = grouped["exit_count"] / grouped["N_2008_total"].replace(0, np.nan)
    grouped["R_B_rate_2008"] = grouped["R_B_count"] / grouped["N_2008_total"].replace(0, np.nan)
    grouped["R_C_rate_2008"] = grouped["R_C_count"] / grouped["N_2008_total"].replace(0, np.nan)

    b_uptake = (
        relabel_cohort.groupby(["year_first_any_bvr", "first_regime"], as_index=False)
        .agg(average_b_uptake=("b_uptake", "mean"))
    )
    grouped = grouped.merge(b_uptake, how="left", on=["year_first_any_bvr", "first_regime"], validate="one_to_one")
    return grouped[
        [
            "year_first_any_bvr",
            "first_regime",
            "n_municipalities",
            "exit_count",
            "R_B_count",
            "R_C_count",
            "exit_rate_2008",
            "R_B_rate_2008",
            "R_C_rate_2008",
            "average_b_uptake",
        ]
    ].sort_values(["year_first_any_bvr", "first_regime"]).reset_index(drop=True)


def estimate_2008_to_2006_ratio(final: pd.DataFrame) -> tuple[float, str]:
    if not TSE_PANEL_PATH.exists():
        return np.nan, f"2006 comparison panel not found at {TSE_PANEL_PATH.relative_to(ROOT)}"

    tse = pd.read_parquet(TSE_PANEL_PATH, columns=["year_election", "municipality_id", "num_voters"])
    tse["municipality_id"] = tse["municipality_id"].astype(str).str.zfill(7)
    tse["year_election"] = pd.to_numeric(tse["year_election"], errors="raise").astype(int)
    treated_ids = set(final["ibge_municipality_id"])
    tse = tse[tse["municipality_id"].isin(treated_ids) & tse["year_election"].isin([2006, 2008])].copy()
    totals = tse.groupby("year_election")["num_voters"].sum()
    if 2006 not in totals.index or 2008 not in totals.index or totals.loc[2006] <= 0:
        return np.nan, "2006 totals unavailable for processed municipalities in TSE clean panel"
    ratio = float(totals.loc[2008] / totals.loc[2006])
    note = (
        f"Rescaling uses clean TSE panel totals for processed municipalities: "
        f"2008/2006 electorate ratio = {ratio:.4f}."
    )
    return ratio, note


def agreement(cross_section: float, muni_value: float) -> tuple[str, str]:
    if pd.isna(muni_value):
        return "not_computed", "not_computed"
    if np.sign(cross_section) != np.sign(muni_value):
        return "different_order_of_magnitude", "different_sign"
    denominator = max(min(abs(cross_section), abs(muni_value)), 1e-12)
    factor = max(abs(cross_section), abs(muni_value)) / denominator
    if factor <= 2:
        qualitative = "within_factor_2"
    elif factor <= 3:
        qualitative = "within_factor_3"
    else:
        qualitative = "different_order_of_magnitude"
    return qualitative, "same_sign"


def build_consistency(aggregate: pd.DataFrame, ratio_2008_to_2006: float) -> pd.DataFrame:
    all_row = aggregate[aggregate["aggregation_level"].eq("all_treated")].iloc[0]
    metric_map = {
        "exit_scenario_B": (
            all_row["national_exit_rate_t_post"],
            all_row["national_exit_rate_2008"],
        ),
        "R_B_lower_bound": (
            all_row["national_R_B_rate_t_post"],
            all_row["national_R_B_rate_2008"],
        ),
        "R_C_scenario_C": (
            all_row["national_R_C_rate_t_post"],
            all_row["national_R_C_rate_2008"],
        ),
    }
    rows = []
    for metric, cross_value in CROSS_SECTION_VALUES.items():
        t_post_value, value_2008 = metric_map[metric]
        rescaled = value_2008 * ratio_2008_to_2006 if not pd.isna(ratio_2008_to_2006) else np.nan
        value_for_agreement = rescaled if not pd.isna(rescaled) else value_2008
        qualitative, directional = agreement(cross_value, value_for_agreement)
        rows.append(
            {
                "metric": metric,
                "cross_section_value": cross_value,
                "muni_level_value_t_post_baseline": t_post_value,
                "muni_level_value_2008_baseline": value_2008,
                "muni_level_value_rescaled_to_2006": rescaled,
                "agreement_qualitative": qualitative,
                "agreement_directional": directional,
            }
        )
    return pd.DataFrame(rows)


def overall_assessment(consistency: pd.DataFrame) -> str:
    if (consistency["agreement_directional"] != "same_sign").any():
        return "FAIL"
    qualitative = set(consistency["agreement_qualitative"])
    if qualitative <= {"within_factor_2"}:
        return "PASS"
    if qualitative <= {"within_factor_2", "within_factor_3"}:
        return "QUALIFIED"
    return "FAIL"


def build_map_files(final: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rates = final[
        [
            "ibge_municipality_id",
            "state",
            "first_regime",
            "year_first_any_bvr",
            "exit_rate_2008",
            "R_B_rate_2008",
            "R_C_rate_2008",
        ]
    ].copy()
    rates["total_decomposition_rate_B"] = rates["exit_rate_2008"] + rates["R_B_rate_2008"]
    rates["total_decomposition_rate_C"] = rates["exit_rate_2008"] + rates["R_C_rate_2008"]

    counts = final[
        [
            "ibge_municipality_id",
            "state",
            "first_regime",
            "year_first_any_bvr",
            "exit_count",
            "R_B_count",
            "R_C_count",
        ]
    ].copy()
    counts["total_decomposition_count_B"] = counts["exit_count"] + counts["R_B_count"]
    counts["total_decomposition_count_C"] = counts["exit_count"] + counts["R_C_count"]
    return rates, counts


def format_rate_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    output = frame.copy()
    for column in columns:
        if column in output.columns:
            output[column] = output[column].map(percent)
    return output


def print_table(title: str, frame: pd.DataFrame) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if frame.empty:
        print("(none)")
        return
    print(frame.to_string(index=False))


def main() -> None:
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", None)

    panel, exit_muni, relabel_muni, relabel_cohort = load_inputs()
    baseline_2008 = build_2008_baseline(panel)
    final = build_final_municipality(exit_muni, relabel_muni, baseline_2008)
    aggregate = build_aggregate(final)
    by_cohort = build_by_cohort(final, relabel_cohort)
    ratio_2008_to_2006, ratio_note = estimate_2008_to_2006_ratio(final)
    consistency = build_consistency(aggregate, ratio_2008_to_2006)
    assessment = overall_assessment(consistency)
    map_rates, map_counts = build_map_files(final)

    final.to_parquet(FINAL_MUNICIPALITY_PATH, index=False)
    aggregate.to_parquet(FINAL_AGGREGATE_PATH, index=False)
    by_cohort.to_parquet(FINAL_BY_COHORT_PATH, index=False)
    consistency.to_parquet(CONSISTENCY_PATH, index=False)
    map_rates.to_parquet(MAP_RATES_PATH, index=False)
    map_counts.to_parquet(MAP_COUNTS_PATH, index=False)

    all_row = aggregate[aggregate["aggregation_level"].eq("all_treated")].iloc[0]
    strict_row = aggregate[aggregate["aggregation_level"].eq("strict")].iloc[0]
    hybrid_row = aggregate[aggregate["aggregation_level"].eq("hybrid")].iloc[0]

    by_year = (
        final.groupby("year_first_any_bvr", as_index=False)
        .agg(
            n=("ibge_municipality_id", "nunique"),
            N_2008_total=("N_2008_total", "sum"),
            exit_count=("exit_count", "sum"),
            R_B_count=("R_B_count", "sum"),
            R_C_count=("R_C_count", "sum"),
        )
    )
    by_year["exit_rate_2008"] = by_year["exit_count"] / by_year["N_2008_total"]
    by_year["R_B_rate_2008"] = by_year["R_B_count"] / by_year["N_2008_total"]
    by_year["R_C_rate_2008"] = by_year["R_C_count"] / by_year["N_2008_total"]

    consistency_display = consistency.copy()
    consistency_display = format_rate_columns(
        consistency_display,
        [
            "cross_section_value",
            "muni_level_value_t_post_baseline",
            "muni_level_value_2008_baseline",
            "muni_level_value_rescaled_to_2006",
        ],
    )

    print("=" * 64)
    print("MUNICIPALITY-LEVEL DECOMPOSITION FINAL RESULTS")
    print("=" * 64)
    print(f"Treated municipalities processed: {int(all_row['n_municipalities']):,} total")
    print(f"  Strict-first: {int(strict_row['n_municipalities']):,}")
    print(f"  Hybrid-first: {int(hybrid_row['n_municipalities']):,}")
    fallback_baselines = final[~final["baseline_is_exact_2008"]]
    if len(fallback_baselines):
        years = ", ".join(str(int(y)) for y in sorted(fallback_baselines["baseline_year_used"].unique()))
        print(
            f"  2008 baseline fallback: {len(fallback_baselines):,} municipalities use earliest available "
            f"age-by-education year ({years}) because 2008 is unavailable."
        )

    print("\nAggregate decomposition (all treated, Scenario B):")
    print(f"  National 2008 baseline: {fmt_count(all_row['national_2008_baseline'])} voters")
    print(
        f"  National exit: {fmt_count(all_row['national_exit_count'])} voters "
        f"({percent(all_row['national_exit_rate_2008'])} of 2008 baseline)"
    )
    print(
        f"  National re-labeling: {fmt_count(all_row['national_R_B_count'])} voters "
        f"({percent(all_row['national_R_B_rate_2008'])} of 2008 baseline)"
    )

    print("\nAggregate decomposition (all treated, Scenario C):")
    print(
        f"  National exit: {fmt_count(all_row['national_exit_count'])} voters "
        f"({percent(all_row['national_exit_rate_2008'])} of 2008 baseline)"
    )
    print(
        f"  National re-labeling: {fmt_count(all_row['national_R_C_count'])} voters "
        f"({percent(all_row['national_R_C_rate_2008'])} of 2008 baseline)"
    )

    print("\nBy first_regime:")
    print("  Strict-first municipalities:")
    print(f"    Exit rate: {percent(strict_row['national_exit_rate_2008'])} of 2008 baseline")
    print(f"    Re-labeling rate (Scenario B): {percent(strict_row['national_R_B_rate_2008'])}")
    print(f"    Re-labeling rate (Scenario C): {percent(strict_row['national_R_C_rate_2008'])}")
    print("  Hybrid-first municipalities:")
    print(f"    Exit rate: {percent(hybrid_row['national_exit_rate_2008'])}")
    print(f"    Re-labeling rate (Scenario B): {percent(hybrid_row['national_R_B_rate_2008'])}")
    print(f"    Re-labeling rate (Scenario C): {percent(hybrid_row['national_R_C_rate_2008'])}")

    print("\nBy adoption cohort year:")
    for _, row in by_year.sort_values("year_first_any_bvr").iterrows():
        print(
            f"  {int(row['year_first_any_bvr'])}: exit={percent(row['exit_rate_2008'])}, "
            f"R_B={percent(row['R_B_rate_2008'])}, R_C={percent(row['R_C_rate_2008'])}, n={int(row['n']):,}"
        )

    print("\nCONSISTENCY CHECK BETWEEN FRAMEWORKS")
    print("=====================================")
    print(f"  {ratio_note}")
    print_table("Consistency metrics", consistency_display)

    consistency_lookup = consistency.set_index("metric")
    print("\nCross-section consistency check:")
    exit_row = consistency_lookup.loc["exit_scenario_B"]
    rb_row = consistency_lookup.loc["R_B_lower_bound"]
    rc_row = consistency_lookup.loc["R_C_scenario_C"]
    print("  Cross-section exit (Scenario B): 12.60% of 2006 baseline")
    print(f"  Muni-level exit (Scenario B): {percent(exit_row['muni_level_value_2008_baseline'])} of 2008 baseline")
    print(f"  Rescaled to 2006: {percent(exit_row['muni_level_value_rescaled_to_2006'])}")
    print(f"  Verdict: {exit_row['agreement_qualitative']}")
    print("")
    print("  Cross-section R_B (lower bound): 5.22%")
    print(f"  Muni-level R_B: {percent(rb_row['muni_level_value_2008_baseline'])} of 2008 baseline")
    print(f"  Rescaled: {percent(rb_row['muni_level_value_rescaled_to_2006'])}")
    print(f"  Verdict: {rb_row['agreement_qualitative']}")
    print("")
    print("  Cross-section R_C (Scenario C): 10.40%")
    print(f"  Muni-level R_C: {percent(rc_row['muni_level_value_2008_baseline'])} of 2008 baseline")
    print(f"  Rescaled: {percent(rc_row['muni_level_value_rescaled_to_2006'])}")
    print(f"  Verdict: {rc_row['agreement_qualitative']}")

    print("\nOVERALL ASSESSMENT:")
    print(f"  Framework consistency: {assessment}")

    print("\nFiles saved:")
    for path in [
        FINAL_MUNICIPALITY_PATH,
        FINAL_AGGREGATE_PATH,
        FINAL_BY_COHORT_PATH,
        CONSISTENCY_PATH,
        MAP_RATES_PATH,
        MAP_COUNTS_PATH,
    ]:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
