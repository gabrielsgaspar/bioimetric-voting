from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


ROOT = Path("resources/regressions/reg_fe_compare/compliance_descriptives")
ROOT.mkdir(parents=True, exist_ok=True)

FULL_PANEL = Path("data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.parquet")
REG_PANEL = Path("resources/regressions/reg_fe_compare/analysis_panel.parquet")

COMPLIANCE_VARS = [
    "pct_with_bvr",
    "pct_low_ed_with_bvr",
    "pct_high_ed_with_bvr",
]


def classify_first_regime(row: pd.Series) -> str:
    strict = row["year_first_strict_bvr"]
    hybrid = row["year_first_hybrid_bvr"]
    strict_finite = pd.notna(strict) and strict != 9999
    hybrid_finite = pd.notna(hybrid) and hybrid != 9999

    if not strict_finite and not hybrid_finite:
        return "never_treated"
    if hybrid_finite and (not strict_finite or hybrid < strict):
        return "hybrid"
    return "strict"


def q(series: pd.Series, prob: float) -> float:
    x = series.dropna()
    if x.empty:
        return np.nan
    return float(x.quantile(prob))


def summarize_group(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    work = df.copy()
    work["compliance_gap"] = work["pct_high_ed_with_bvr"] - work["pct_low_ed_with_bvr"]

    rows: list[dict[str, object]] = []
    for keys, group in work.groupby(group_cols, dropna=False, observed=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {col: val for col, val in zip(group_cols, keys)}
        row["n_municipalities"] = group["municipality_id"].nunique()
        row["n_observations"] = len(group)
        for var in COMPLIANCE_VARS + ["compliance_gap"]:
            row[f"mean_{var}"] = group[var].mean(skipna=True)
            row[f"median_{var}"] = group[var].median(skipna=True)
        for prob, name in [(0.10, "p10"), (0.25, "p25"), (0.75, "p75"), (0.90, "p90")]:
            row[f"{name}_pct_with_bvr"] = q(group["pct_with_bvr"], prob)
        rows.append(row)

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(group_cols).reset_index(drop=True)
    return out


def pct_fmt(value: float, digits: int = 1) -> str:
    if pd.isna(value):
        return ""
    return f"{100 * value:.{digits}f}%"


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_None._"
    return df.to_markdown(index=False)


def make_distribution(df: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    bins = np.array([i / 10 for i in range(11)] + [1.000000001])
    rows = []
    for var in variables:
        valid = df[var].dropna()
        total = len(valid)
        cumulative = 0
        for i in range(10):
            lower = i / 10
            upper = (i + 1) / 10
            if i < 9:
                mask = (valid >= lower) & (valid < upper)
                label = f"[{lower:.1f}, {upper:.1f})"
            else:
                mask = (valid >= lower) & (valid <= upper)
                label = f"[{lower:.1f}, {upper:.1f}]"
            count = int(mask.sum())
            cumulative += count
            rows.append(
                {
                    "variable": var,
                    "bin_lower": lower,
                    "bin_upper": upper,
                    "bin_label": label,
                    "count": count,
                    "cumulative_count": cumulative,
                    "share": count / total if total else np.nan,
                    "cumulative_share": cumulative / total if total else np.nan,
                }
            )
    return pd.DataFrame(rows)


def gap_distribution(df: pd.DataFrame, group_col: str, group_values: list[str]) -> pd.DataFrame:
    rows = []
    work = df[df[group_col].isin(group_values)].copy()
    work["compliance_gap"] = work["pct_high_ed_with_bvr"] - work["pct_low_ed_with_bvr"]
    work = work[
        work["pct_low_ed_with_bvr"].notna()
        & work["pct_high_ed_with_bvr"].notna()
        & (work["pct_low_ed_with_bvr"] > 0)
        & (work["pct_high_ed_with_bvr"] > 0)
    ]
    for value, group in work.groupby(group_col, observed=False):
        gap = group["compliance_gap"]
        rows.append(
            {
                "classification": group_col,
                "regime": value,
                "n_observations": len(group),
                "n_municipalities": group["municipality_id"].nunique(),
                "mean_gap": gap.mean(),
                "median_gap": gap.median(),
                "p10_gap": q(gap, 0.10),
                "p25_gap": q(gap, 0.25),
                "p75_gap": q(gap, 0.75),
                "p90_gap": q(gap, 0.90),
                "share_gap_gt_0": float((gap > 0).mean()),
                "share_gap_lt_0": float((gap < 0).mean()),
            }
        )
    return pd.DataFrame(rows)


def save_plot(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    plt.close()


def main() -> None:
    full = pd.read_parquet(FULL_PANEL)
    reg_panel = pd.read_parquet(REG_PANEL)

    regime_lookup = (
        reg_panel[["municipality_id", "first_regime"]]
        .drop_duplicates()
        .rename(columns={"first_regime": "first_regime_from_regression_panel"})
    )
    if regime_lookup["municipality_id"].duplicated().any():
        raise ValueError("Regression panel has multiple first_regime labels per municipality.")

    full = full.merge(regime_lookup, on="municipality_id", how="left")
    computed = (
        full[
            [
                "municipality_id",
                "year_first_strict_bvr",
                "year_first_hybrid_bvr",
                "year_first_any_bvr",
            ]
        ]
        .drop_duplicates("municipality_id")
        .copy()
    )
    computed["first_regime_computed"] = computed.apply(classify_first_regime, axis=1)
    full = full.merge(
        computed[["municipality_id", "first_regime_computed"]],
        on="municipality_id",
        how="left",
    )
    full["first_regime"] = full["first_regime_from_regression_panel"].fillna(
        full["first_regime_computed"]
    )
    full["first_regime_source"] = np.where(
        full["first_regime_from_regression_panel"].notna(),
        "regression_panel",
        "recomputed_from_clean_panel",
    )

    panel = full[full["year_election"].isin([2014, 2016, 2018])].copy()
    panel["event_time"] = np.where(
        panel["year_first_any_bvr"].eq(9999),
        np.nan,
        panel["year_election"] - panel["year_first_any_bvr"],
    )
    panel["compliance_gap"] = panel["pct_high_ed_with_bvr"] - panel["pct_low_ed_with_bvr"]
    panel["cohort"] = panel["year_first_any_bvr"].where(
        panel["year_first_any_bvr"].ne(9999), np.nan
    )

    panel_cols = [
        "municipality_id",
        "municipality_name",
        "state",
        "year_election",
        "first_regime",
        "first_regime_source",
        "bvr_status",
        "year_first_any_bvr",
        "year_first_strict_bvr",
        "year_first_hybrid_bvr",
        "event_time",
        "pct_with_bvr",
        "pct_low_ed_with_bvr",
        "pct_high_ed_with_bvr",
        "compliance_gap",
    ]
    panel[panel_cols].to_parquet(ROOT / "panel.parquet", index=False)

    missing_rows = []
    for year, group in panel.groupby("year_election"):
        row = {"year_election": year, "n_observations": len(group), "n_municipalities": group["municipality_id"].nunique()}
        for var in COMPLIANCE_VARS:
            row[f"n_nonmissing_{var}"] = int(group[var].notna().sum())
            row[f"n_missing_{var}"] = int(group[var].isna().sum())
            row[f"mean_{var}"] = group[var].mean(skipna=True)
            row[f"all_zero_{var}"] = bool((group[var].fillna(0) == 0).all())
        missing_rows.append(row)
    missingness = pd.DataFrame(missing_rows).sort_values("year_election")
    missingness.to_csv(ROOT / "compliance_nonmissing_by_year.csv", index=False)

    anomaly_rows = []
    for var in COMPLIANCE_VARS:
        bad = panel[panel[var].notna() & ((panel[var] < 0) | (panel[var] > 1))]
        anomaly_rows.append(
            {
                "variable": var,
                "n_anomalous": len(bad),
                "min_value": panel[var].min(skipna=True),
                "max_value": panel[var].max(skipna=True),
            }
        )
    anomalies = pd.DataFrame(anomaly_rows)
    anomalies.to_csv(ROOT / "compliance_anomalies.csv", index=False)

    by_year_status = summarize_group(panel[panel["pct_with_bvr"].notna()], ["year_election", "bvr_status"])
    by_year_status.to_csv(ROOT / "compliance_by_year_status.csv", index=False)

    by_event = panel[
        panel["first_regime"].isin(["hybrid", "strict"])
        & panel["event_time"].isin([0, 2, 4])
        & panel["pct_with_bvr"].notna()
    ].copy()
    by_regime_event = summarize_group(by_event, ["first_regime", "event_time"])
    by_regime_event.to_csv(ROOT / "compliance_by_first_regime_event_time.csv", index=False)

    hybrid_obs = panel[
        (panel["first_regime"] == "hybrid")
        & (panel["bvr_status"] == "hybrid_bvr")
    ].copy()
    hybrid_dist = make_distribution(hybrid_obs, COMPLIANCE_VARS)
    hybrid_dist.to_csv(ROOT / "hybrid_voluntary_uptake_distribution.csv", index=False)

    gap_by_first_regime = gap_distribution(panel, "first_regime", ["hybrid", "strict"])
    gap_by_status = gap_distribution(panel, "bvr_status", ["hybrid_bvr", "strict_bvr"])
    gap_dist = pd.concat([gap_by_first_regime, gap_by_status], ignore_index=True)
    gap_dist.to_csv(ROOT / "compliance_gap_distribution.csv", index=False)

    hybrid_first = panel[panel["first_regime"] == "hybrid"].copy()
    intensity = hybrid_first[
        hybrid_first["year_election"].eq(hybrid_first["year_first_any_bvr"])
    ].copy()

    def intensity_bin(x: float) -> str:
        if pd.isna(x):
            return "missing"
        if x < 0.05:
            return "dormant"
        if x < 0.20:
            return "low"
        if x < 0.50:
            return "moderate"
        return "active"

    intensity["intensity_bin"] = intensity["pct_with_bvr"].map(intensity_bin)
    bin_order = ["dormant", "low", "moderate", "active", "missing"]
    intensity["intensity_bin"] = pd.Categorical(intensity["intensity_bin"], categories=bin_order, ordered=True)
    screening_rows = []
    total_hybrid_munis = intensity["municipality_id"].nunique()
    for bin_name, group in intensity.groupby("intensity_bin", observed=False):
        screening_rows.append(
            {
                "intensity_bin": bin_name,
                "n_municipalities": group["municipality_id"].nunique(),
                "share_municipalities": group["municipality_id"].nunique() / total_hybrid_munis if total_hybrid_munis else np.nan,
                "mean_pct_with_bvr": group["pct_with_bvr"].mean(skipna=True),
                "sd_pct_with_bvr": group["pct_with_bvr"].std(skipna=True),
                "mean_pct_low_ed_with_bvr": group["pct_low_ed_with_bvr"].mean(skipna=True),
                "sd_pct_low_ed_with_bvr": group["pct_low_ed_with_bvr"].std(skipna=True),
                "mean_pct_high_ed_with_bvr": group["pct_high_ed_with_bvr"].mean(skipna=True),
                "sd_pct_high_ed_with_bvr": group["pct_high_ed_with_bvr"].std(skipna=True),
            }
        )
    screening = pd.DataFrame(screening_rows)
    screening.to_csv(ROOT / "hybrid_intensity_screening.csv", index=False)

    # Plot 1: compliance evolution by first regime and event time.
    evo = (
        by_event.groupby(["first_regime", "event_time"], as_index=False)[COMPLIANCE_VARS]
        .mean()
        .sort_values(["first_regime", "event_time"])
    )
    long_evo = evo.melt(
        id_vars=["first_regime", "event_time"],
        value_vars=COMPLIANCE_VARS,
        var_name="measure",
        value_name="mean_compliance",
    )
    labels = {
        "pct_with_bvr": "Overall",
        "pct_low_ed_with_bvr": "Low ed",
        "pct_high_ed_with_bvr": "High ed",
    }
    palette = {
        "pct_with_bvr": "#222222",
        "pct_low_ed_with_bvr": "#D55E00",
        "pct_high_ed_with_bvr": "#0072B2",
    }
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2), sharey=True)
    for ax, regime in zip(axes, ["hybrid", "strict"]):
        sub = long_evo[long_evo["first_regime"] == regime]
        for measure, group in sub.groupby("measure"):
            ax.plot(group["event_time"], group["mean_compliance"], marker="o", linewidth=2, label=labels[measure], color=palette[measure])
        ax.set_title(regime.capitalize())
        ax.set_xlabel("Event time")
        ax.set_xticks(sorted(sub["event_time"].dropna().unique()))
        ax.set_ylim(0, 1.02)
        ax.grid(True, color="#dddddd", linewidth=0.8)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("black")
            spine.set_linewidth(0.8)
    axes[0].set_ylabel("Mean compliance rate")
    axes[1].legend(frameon=False, loc="lower right")
    save_plot(ROOT / "compliance_evolution_by_regime.pdf")

    # Plot 2: hybrid voluntary uptake histogram.
    hist_long = hybrid_obs[COMPLIANCE_VARS].melt(var_name="measure", value_name="compliance").dropna()
    plt.figure(figsize=(7.5, 4.6))
    for measure in COMPLIANCE_VARS:
        vals = hist_long.loc[hist_long["measure"] == measure, "compliance"]
        plt.hist(vals, bins=20, range=(0, 1), alpha=0.35, label=labels[measure], color=palette[measure])
    plt.xlabel("Compliance rate")
    plt.ylabel("Municipality-years")
    plt.xlim(0, 1)
    plt.grid(True, axis="y", color="#dddddd", linewidth=0.8)
    plt.legend(frameon=False)
    ax = plt.gca()
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("black")
        spine.set_linewidth(0.8)
    save_plot(ROOT / "hybrid_voluntary_uptake_histogram.pdf")

    # Plot 3: compliance gap by observation-level BVR status.
    gap_plot = panel[
        panel["bvr_status"].isin(["hybrid_bvr", "strict_bvr"])
        & panel["pct_low_ed_with_bvr"].notna()
        & panel["pct_high_ed_with_bvr"].notna()
        & (panel["pct_low_ed_with_bvr"] > 0)
        & (panel["pct_high_ed_with_bvr"] > 0)
    ].copy()
    gap_plot["status_label"] = gap_plot["bvr_status"].map({"hybrid_bvr": "Hybrid", "strict_bvr": "Strict"})
    plt.figure(figsize=(6.2, 4.6))
    sns.violinplot(data=gap_plot, x="status_label", y="compliance_gap", inner=None, color="#cfcfcf", cut=0)
    sns.boxplot(data=gap_plot, x="status_label", y="compliance_gap", width=0.22, color="white", fliersize=1.5)
    plt.axhline(0, color="black", linewidth=1.1)
    plt.xlabel("")
    plt.ylabel("High-ed minus low-ed compliance")
    plt.grid(True, axis="y", color="#dddddd", linewidth=0.8)
    ax = plt.gca()
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("black")
        spine.set_linewidth(0.8)
    save_plot(ROOT / "compliance_gap_by_regime.pdf")

    # Plot 4: cohort-specific compliance trajectories.
    cohort_plot = panel[
        panel["first_regime"].isin(["hybrid", "strict"])
        & panel["year_first_any_bvr"].isin([2014, 2016, 2018])
        & panel["pct_with_bvr"].notna()
    ].copy()
    cohort_mean = (
        cohort_plot.groupby(["first_regime", "year_first_any_bvr", "year_election"], as_index=False)["pct_with_bvr"]
        .mean()
        .sort_values(["first_regime", "year_first_any_bvr", "year_election"])
    )
    plt.figure(figsize=(8.2, 4.8))
    colors = {"hybrid": "#7B3294", "strict": "#008837"}
    linestyles = {2014: "-", 2016: "--", 2018: ":"}
    markers = {2014: "o", 2016: "s", 2018: "^"}
    for (regime, cohort), group in cohort_mean.groupby(["first_regime", "year_first_any_bvr"]):
        plt.plot(
            group["year_election"],
            group["pct_with_bvr"],
            label=f"{regime}, {int(cohort)}",
            color=colors[regime],
            linestyle=linestyles[int(cohort)],
            marker=markers[int(cohort)],
            linewidth=2,
        )
    plt.xlabel("Calendar year")
    plt.ylabel("Mean overall compliance")
    plt.ylim(0, 1.02)
    plt.xticks([2014, 2016, 2018])
    plt.grid(True, color="#dddddd", linewidth=0.8)
    plt.legend(frameon=False, ncol=2, fontsize=9)
    ax = plt.gca()
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("black")
        spine.set_linewidth(0.8)
    save_plot(ROOT / "cohort_compliance_trajectories.pdf")

    # Compact prose summary.
    hybrid_event0 = by_regime_event[
        (by_regime_event["first_regime"] == "hybrid") & (by_regime_event["event_time"] == 0)
    ]
    strict_event0 = by_regime_event[
        (by_regime_event["first_regime"] == "strict") & (by_regime_event["event_time"] == 0)
    ]
    hybrid_event2 = by_regime_event[
        (by_regime_event["first_regime"] == "hybrid") & (by_regime_event["event_time"] == 2)
    ]
    strict_event2 = by_regime_event[
        (by_regime_event["first_regime"] == "strict") & (by_regime_event["event_time"] == 2)
    ]
    strict_event4 = by_regime_event[
        (by_regime_event["first_regime"] == "strict") & (by_regime_event["event_time"] == 4)
    ]

    def first_value(df: pd.DataFrame, col: str) -> float:
        return float(df.iloc[0][col]) if not df.empty else np.nan

    h0_total = first_value(hybrid_event0, "mean_pct_with_bvr")
    h0_low = first_value(hybrid_event0, "mean_pct_low_ed_with_bvr")
    h0_high = first_value(hybrid_event0, "mean_pct_high_ed_with_bvr")
    h2_total = first_value(hybrid_event2, "mean_pct_with_bvr")
    s0_total = first_value(strict_event0, "mean_pct_with_bvr")
    s2_total = first_value(strict_event2, "mean_pct_with_bvr")
    s4_total = first_value(strict_event4, "mean_pct_with_bvr")

    gap_first = gap_dist[gap_dist["classification"] == "first_regime"].copy()
    gap_status = gap_dist[gap_dist["classification"] == "bvr_status"].copy()
    h_gap = gap_first.loc[gap_first["regime"] == "hybrid", "mean_gap"].iloc[0]
    s_gap = gap_first.loc[gap_first["regime"] == "strict", "mean_gap"].iloc[0]
    h_status_gap = gap_status.loc[gap_status["regime"] == "hybrid_bvr", "mean_gap"].iloc[0]
    s_status_gap = gap_status.loc[gap_status["regime"] == "strict_bvr", "mean_gap"].iloc[0]

    screening_nonmissing = screening[screening["intensity_bin"] != "missing"].copy()
    dormant_share = screening.loc[screening["intensity_bin"] == "dormant", "share_municipalities"].iloc[0]
    low_share = screening.loc[screening["intensity_bin"] == "low", "share_municipalities"].iloc[0]
    moderate_share = screening.loc[screening["intensity_bin"] == "moderate", "share_municipalities"].iloc[0]
    active_share = screening.loc[screening["intensity_bin"] == "active", "share_municipalities"].iloc[0]

    nonmissing_md = missingness.copy()
    for col in nonmissing_md.columns:
        if col.startswith("mean_"):
            nonmissing_md[col] = nonmissing_md[col].map(lambda x: pct_fmt(x, 2))

    anomaly_text = "No compliance variables had values below 0 or above 1."
    if int(anomalies["n_anomalous"].sum()) > 0:
        anomaly_text = "At least one compliance variable has values outside [0, 1]; see `compliance_anomalies.csv`."

    summary = f"""# Compliance Descriptives

The strict-vs-hybrid regression in `resources/regressions/reg_fe_compare/` found a very small hybrid-first registry-count effect at event time 0. This descriptive pass looks directly at biometric compliance rates to see whether that small coefficient reflects low voluntary uptake, regime transitions, or some other pattern in the observed compliance variables.

I use the full clean municipality-year panel, restrict to 2014, 2016, and 2018 because the compliance variables are intentionally missing before 2014, and merge in the previously constructed `first_regime` labels where available. Municipalities not present in the restricted regression panel are assigned the same first-regime rule from the clean-panel treatment-year variables. The output panel contains {len(panel):,} municipality-year observations across {panel['municipality_id'].nunique():,} municipalities.

This is descriptive only. The compliance rate measures the share of currently registered voters with biometric data on file; in strict municipalities, high compliance after cancellation is partly mechanical and should not be read as voluntary uptake.

## Data Coverage

{md_table(nonmissing_md)}

{anomaly_text}

## Voluntary Uptake in Hybrid Municipalities

At event time 0, hybrid-first municipalities have mean overall biometric uptake of {pct_fmt(h0_total)}, with {pct_fmt(h0_low)} among low-education voters and {pct_fmt(h0_high)} among high-education voters. By the thresholds in the prompt, this is low voluntary uptake, though not near-zero. The key nuance is heterogeneity: the event-time-0 mean hides many low-activity municipalities alongside a substantial set with active biometric capture.

## Compliance Evolution

Hybrid-first municipalities rise from {pct_fmt(h0_total)} at event time 0 to {pct_fmt(h2_total)} at event time 2. Strict-first municipalities start much higher at {pct_fmt(s0_total)} at event time 0 and reach {pct_fmt(s2_total)} by event time 2 and {pct_fmt(s4_total)} by event time 4. Within the observed 2014-2018 window, hybrid municipalities remain persistently below strict municipalities rather than catching up to the same compliance level.

## Compliance Gap

Using first-treatment regime, the mean high-minus-low education compliance gap is {pct_fmt(h_gap)} in hybrid-first municipality-years and {pct_fmt(s_gap)} in strict-first municipality-years. Using observation-year status, the corresponding gap is {pct_fmt(h_status_gap)} for hybrid-status municipality-years and {pct_fmt(s_status_gap)} for strict-status municipality-years. The gap is positive in both cases, meaning high-education voters are more likely to have biometric data on file, and it is much larger in hybrid-status observations than in strict-status observations in this descriptive window.

## Hybrid Intensity Screening

At event time 0, {pct_fmt(dormant_share)} of hybrid-first municipalities are dormant, {pct_fmt(low_share)} are low intensity, {pct_fmt(moderate_share)} are moderate intensity, and {pct_fmt(active_share)} are active. This means the binary hybrid indicator is not simply zero-treatment for most municipalities, but it does combine a nontrivial dormant/low-intensity group with a large moderate/active group. That mixture can attenuate binary hybrid comparisons even when many hybrid municipalities have meaningful voluntary uptake.

## Implications for the Next Phase

The descriptive evidence suggests that a binary hybrid indicator is too coarse for the next decomposition exercise. Useful next steps could include redefining hybrid exposure using a minimum intensity threshold, using compliance as a continuous treatment intensity, or using the within-municipality low-versus-high compliance gap to discipline a compliance-cost parameter. The present outputs do not choose among those options; they show that compliance intensity and education-specific uptake are empirically important margins to carry forward.
"""
    (ROOT / "SUMMARY.md").write_text(summary)

    # Small manifest for quick checking.
    manifest = pd.DataFrame(
        {
            "file": sorted(p.name for p in ROOT.iterdir() if p.is_file()),
        }
    )
    manifest.to_csv(ROOT / "manifest.csv", index=False)


if __name__ == "__main__":
    main()
