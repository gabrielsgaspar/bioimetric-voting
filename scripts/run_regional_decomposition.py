#!/usr/bin/env python3
"""Run regional BVR event studies and exit/re-labeling decompositions.

This script builds the region-augmented TSE registry panel, runs the existing
TWFE DID estimator wrapper for regional subsamples, and then computes the
accounting bounds requested for the BVR decomposition exercise.
"""

from __future__ import annotations

import argparse
import math
import shutil
import subprocess
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

PANEL_IN = ROOT / "data/clean/tse/tse_clean_panel_2000_2018.parquet"
PANEL_REGION_PARQUET = ROOT / "data/clean/tse/tse_clean_panel_2000_2018_with_region.parquet"
PANEL_REGION_CSV = ROOT / "data/clean/tse/tse_clean_panel_2000_2018_with_region.csv"
REGION_MAP_CSV = ROOT / "data/clean/region_mapping/state_to_region.csv"
INTERIM_DIR = ROOT / "data/interim/tse/regional_decomposition"
DID_DIR = ROOT / "resources/did/regional_decomposition"
IMAGE_DIR = ROOT / "resources/images/regressions/regional_decomposition"
DECOMP_DIR = ROOT / "resources/decomposition"
DECOMP_IMAGE_DIR = ROOT / "resources/images/decomposition"
TABLE_DIR = ROOT / "resources/tables"
PAPER_FIGURE_DIR = ROOT / "paper/figures"

OUTCOMES = [
    "log_num_voters",
    "pct_voters_low_ed",
    "pct_voters_high_ed",
    "log_num_voters_low_ed",
    "log_num_voters_high_ed",
]

DECOMP_OUTCOMES = {
    "N": "log_num_voters",
    "L": "log_num_voters_low_ed",
    "H": "log_num_voters_high_ed",
}

EVENT_TIMES = [-8, -6, -4, -2, 0, 2, 4, 6, 8]
POST_EVENT_TIMES = [0, 2, 4, 6, 8]

STATE_TO_REGION = {
    "AC": "Norte",
    "AM": "Norte",
    "AP": "Norte",
    "PA": "Norte",
    "RO": "Norte",
    "RR": "Norte",
    "TO": "Norte",
    "AL": "Nordeste",
    "BA": "Nordeste",
    "CE": "Nordeste",
    "MA": "Nordeste",
    "PB": "Nordeste",
    "PE": "Nordeste",
    "PI": "Nordeste",
    "RN": "Nordeste",
    "SE": "Nordeste",
    "DF": "Centro-Oeste",
    "GO": "Centro-Oeste",
    "MT": "Centro-Oeste",
    "MS": "Centro-Oeste",
    "ES": "Sudeste",
    "MG": "Sudeste",
    "RJ": "Sudeste",
    "SP": "Sudeste",
    "PR": "Sul",
    "RS": "Sul",
    "SC": "Sul",
}

REGION_ORDER = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]
ALL_GROUPS = REGION_ORDER + ["National"]
REGION_SLUGS = {
    "Norte": "norte",
    "Nordeste": "nordeste",
    "Centro-Oeste": "centro_oeste",
    "Sudeste": "sudeste",
    "Sul": "sul",
    "National": "national",
}

EXPECTED_REGION_COUNTS = {
    "Norte": 450,
    "Nordeste": 1794,
    "Centro-Oeste": 467,
    "Sudeste": 1668,
    "Sul": 1191,
}

OUTCOME_LABELS = {
    "log_num_voters": "Log voters",
    "pct_voters_low_ed": "Low-ed share",
    "pct_voters_high_ed": "High-ed share",
    "log_num_voters_low_ed": "Log low-ed voters",
    "log_num_voters_high_ed": "Log high-ed voters",
}

REGION_COLORS = {
    "Norte": "#1b9e77",
    "Nordeste": "#d95f02",
    "Centro-Oeste": "#7570b3",
    "Sudeste": "#e7298a",
    "Sul": "#66a61e",
    "National": "#333333",
}


def ensure_dirs() -> None:
    for path in [
        REGION_MAP_CSV.parent,
        PANEL_REGION_PARQUET.parent,
        INTERIM_DIR,
        DID_DIR,
        IMAGE_DIR,
        DECOMP_DIR,
        DECOMP_IMAGE_DIR,
        TABLE_DIR,
        PAPER_FIGURE_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def region_slug(region: str) -> str:
    return REGION_SLUGS[region]


def pct(x: float) -> str:
    if pd.isna(x):
        return ""
    return f"{100 * x:.1f}"


def fmt3(x: float) -> str:
    if pd.isna(x):
        return ""
    return f"{x:.3f}"


def fmt_ci(est: float, low: float, high: float) -> str:
    if pd.isna(est):
        return ""
    return f"{est:.3f} [{low:.3f}, {high:.3f}]"


def fit_latex_table(latex: str) -> str:
    """Wrap generated tabulars so wide regression tables fit the text width."""
    latex = latex.replace(
        r"\begin{tabular}",
        "\\centering\n\\begin{adjustbox}{width=\\textwidth}\n\\begin{tabular}",
        1,
    )
    latex = latex.replace(
        r"\end{tabular}",
        "\\end{tabular}\n\\end{adjustbox}",
        1,
    )
    return latex


def build_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    required = {
        "log_num_voters",
        "log_num_voters_low_ed",
        "log_num_voters_high_ed",
        "pct_voters_low_ed",
        "pct_voters_high_ed",
        "num_voters",
        "num_voters_low_ed",
        "num_voters_high_ed",
        "state",
        "municipality_id",
        "year_election",
        "year_treated",
        "dist_treatment",
        "hybrid",
    }
    df = pd.read_parquet(PANEL_IN)
    missing = sorted(required.difference(df.columns))
    if missing:
        raise RuntimeError(f"Missing required panel columns: {missing}")

    mapping = (
        pd.DataFrame(
            [{"state": state, "region": region} for state, region in sorted(STATE_TO_REGION.items())]
        )
        .sort_values(["region", "state"])
        .reset_index(drop=True)
    )
    mapping.to_csv(REGION_MAP_CSV, index=False)

    df = df.copy()
    df["region"] = df["state"].map(STATE_TO_REGION)
    if df["region"].isna().any():
        missing_states = sorted(df.loc[df["region"].isna(), "state"].dropna().unique())
        raise RuntimeError(f"Unmapped states in panel: {missing_states}")

    muni_counts = (
        df[["municipality_id", "state", "region"]]
        .drop_duplicates()
        .groupby("region")["municipality_id"]
        .nunique()
        .reindex(REGION_ORDER)
    )
    for region, expected in EXPECTED_REGION_COUNTS.items():
        observed = int(muni_counts.loc[region])
        if abs(observed - expected) > 2:
            raise RuntimeError(
                f"Region municipality count for {region} is {observed}, expected near {expected}."
            )

    df.to_parquet(PANEL_REGION_PARQUET, index=False)
    df.to_csv(PANEL_REGION_CSV, index=False)

    for region in REGION_ORDER:
        subset = df[df["region"] == region].copy()
        subset.to_csv(INTERIM_DIR / f"{region_slug(region)}_panel.csv", index=False)
    df.to_csv(INTERIM_DIR / "national_panel.csv", index=False)

    summary = (
        df[["municipality_id", "region"]]
        .drop_duplicates()
        .groupby("region")
        .size()
        .reindex(REGION_ORDER)
        .rename("n_municipalities")
        .reset_index()
    )
    summary.to_csv(DECOMP_DIR / "region_municipality_counts.csv", index=False)
    return df, summary


def write_config(region: str, outcome: str) -> Path:
    slug = region_slug(region)
    data_path = INTERIM_DIR / f"{slug}_panel.csv"
    output_dir = DID_DIR / slug / outcome
    config_dir = DID_DIR / "configs"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{slug}_{outcome}.yml"
    note_region = "full national sample" if region == "National" else f"{region} region only"
    config = f"""estimator: "twfe_dynamic"
data_path: "{data_path.relative_to(ROOT)}"
file_format: "csv"
outcome: "{outcome}"
unit_id: "municipality_id"
time_id: "year_election"
group_id: "year_treated"
treatment_var: null
controls: []
cluster_var:
  - "municipality_id"
  - "year_election"
weights_var: null
event_time_var: "dist_treatment"
event_time_never_value: -9999
never_treated_value: 9999
lead: 8
lag: 8
reference_event_time: -2
anticipation: 0
control_group: "nevertreated"
balanced_panel_required: false
omit_plot_title: true
output_dir: "{output_dir.relative_to(ROOT)}"
notes: "Regional decomposition TWFE event study for {outcome}; sample: {note_region}; clustered by municipality and election year."
"""
    config_path.write_text(config)
    return config_path


def run_estimator(config_path: Path) -> None:
    subprocess.run(
        ["bash", "scripts/run_did_estimator.sh", str(config_path.relative_to(ROOT))],
        cwd=ROOT,
        check=True,
    )


def copy_plot_outputs(region: str, outcome: str) -> None:
    slug = region_slug(region)
    out_dir = DID_DIR / slug / outcome
    target_dir = IMAGE_DIR / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    for ext in ["pdf", "png"]:
        src = out_dir / f"event_study_plot.{ext}"
        if src.exists():
            shutil.copyfile(src, target_dir / f"{outcome}_event_study.{ext}")
    summary = out_dir / "model_summary.txt"
    if summary.exists():
        shutil.copyfile(summary, out_dir / "fit_summary.txt")


def run_event_studies(skip_existing: bool = False) -> None:
    for region in ALL_GROUPS:
        for outcome in OUTCOMES:
            config = write_config(region, outcome)
            out_dir = DID_DIR / region_slug(region) / outcome
            expected = out_dir / "event_study_estimates.csv"
            if skip_existing and expected.exists():
                copy_plot_outputs(region, outcome)
                continue
            run_estimator(config)
            copy_plot_outputs(region, outcome)


def read_event_study(region: str, outcome: str) -> pd.DataFrame:
    path = DID_DIR / region_slug(region) / outcome / "event_study_estimates.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    df["region"] = region
    df["region_slug"] = region_slug(region)
    df["outcome"] = outcome
    return df


def collect_event_studies() -> pd.DataFrame:
    rows = []
    for region in ALL_GROUPS:
        for outcome in OUTCOMES:
            rows.append(read_event_study(region, outcome))
    out = pd.concat(rows, ignore_index=True)
    out.to_csv(DECOMP_DIR / "regional_event_study_estimates_all.csv", index=False)
    return out


def sanity_check_national(event_df: pd.DataFrame) -> None:
    checks = {
        "log_num_voters_low_ed": -0.259,
        "log_num_voters_high_ed": 0.155,
    }
    for outcome, expected in checks.items():
        row = event_df[
            (event_df["region"] == "National")
            & (event_df["outcome"] == outcome)
            & (event_df["event_time"] == 0)
        ]
        if row.empty:
            raise RuntimeError(f"Missing national sanity estimate for {outcome}.")
        observed = float(row.iloc[0]["estimate"])
        if abs(observed - expected) > 0.01:
            raise RuntimeError(
                f"National sanity check failed for {outcome}: observed {observed:.3f}, expected {expected:.3f}."
            )


def compute_baseline_shares(df: pd.DataFrame) -> pd.DataFrame:
    baseline = df[(df["year_treated"] != 9999) & (df["dist_treatment"] == -2)].copy()
    rows = []
    for region in ALL_GROUPS:
        sub = baseline if region == "National" else baseline[baseline["region"] == region]
        if sub.empty:
            raise RuntimeError(f"No baseline event-time -2 rows for {region}.")
        weights = sub["num_voters"].astype(float).to_numpy()
        s_l = np.average(sub["pct_voters_low_ed"], weights=weights)
        s_h = np.average(sub["pct_voters_high_ed"], weights=weights)
        s_unknown = np.average(
            1 - sub["pct_voters_low_ed"] - sub["pct_voters_high_ed"], weights=weights
        )
        rows.append(
            {
                "region": region,
                "region_slug": region_slug(region),
                "s_L": s_l,
                "s_H": s_h,
                "s_unknown": s_unknown,
                "n_municipalities": sub["municipality_id"].nunique(),
                "n_voters_baseline": int(sub["num_voters"].sum()),
            }
        )
    out = pd.DataFrame(rows)
    out.to_csv(DECOMP_DIR / "baseline_shares_by_region.csv", index=False)
    return out


def get_estimate(event_df: pd.DataFrame, region: str, outcome: str, event_time: int) -> dict[str, float]:
    row = event_df[
        (event_df["region"] == region)
        & (event_df["outcome"] == outcome)
        & (event_df["event_time"] == event_time)
    ]
    if row.empty:
        raise RuntimeError(f"Missing estimate for {region}, {outcome}, event time {event_time}.")
    rec = row.iloc[0].to_dict()
    return {
        "beta": float(rec["estimate"]),
        "se": float(rec["std.error"]) if not pd.isna(rec["std.error"]) else math.nan,
        "lower": float(rec["conf.low"]) if not pd.isna(rec["conf.low"]) else math.nan,
        "upper": float(rec["conf.high"]) if not pd.isna(rec["conf.high"]) else math.nan,
    }


def transformed_change(est: dict[str, float], share: float | None = None) -> dict[str, float]:
    mult = 1.0 if share is None else share
    return {
        "point": mult * (math.exp(est["beta"]) - 1),
        "lower": mult * (math.exp(est["lower"]) - 1) if not math.isnan(est["lower"]) else math.nan,
        "upper": mult * (math.exp(est["upper"]) - 1) if not math.isnan(est["upper"]) else math.nan,
    }


def decompose_one(
    region: str,
    event_time: int,
    shares: pd.Series,
    event_df: pd.DataFrame,
) -> dict[str, float | str | bool | int]:
    est_n = get_estimate(event_df, region, DECOMP_OUTCOMES["N"], event_time)
    est_l = get_estimate(event_df, region, DECOMP_OUTCOMES["L"], event_time)
    est_h = get_estimate(event_df, region, DECOMP_OUTCOMES["H"], event_time)
    s_l = float(shares["s_L"])
    s_h = float(shares["s_H"])
    s_unknown = float(shares["s_unknown"])

    dn = transformed_change(est_n)
    dl = transformed_change(est_l, s_l)
    dh = transformed_change(est_h, s_h)

    d_n = dn["point"]
    d_l = dl["point"]
    d_h = dh["point"]
    residual = d_n - d_l - d_h

    r_min = max(0.0, d_h)
    if est_h["beta"] > 0:
        r_min_se = s_h * math.exp(est_h["beta"]) * est_h["se"]
        r_min_lower = max(0.0, r_min - 1.96 * r_min_se)
        r_min_upper = r_min + 1.96 * r_min_se
    else:
        r_min_se = 0.0
        r_min_lower = 0.0
        r_min_upper = 0.0

    r_max = -d_l
    r_max_se = s_l * math.exp(est_l["beta"]) * est_l["se"]
    r_max_lower = r_max - 1.96 * r_max_se
    r_max_upper = r_max + 1.96 * r_max_se
    bounds_feasible = r_min <= r_max + 1e-12

    scenario_a_feasible = d_h <= 0
    scenario_a_r = 0.0
    scenario_a_e_l = -d_l
    scenario_a_e_h = -d_h

    scenario_b_r = d_h
    scenario_b_e_l = -d_n
    scenario_b_e_h = 0.0

    scenario_c_e_l = -d_n * s_l
    scenario_c_e_h = -d_n * s_h
    scenario_c_r = d_h + scenario_c_e_h
    scenario_c_feasible = (d_n <= 0) and (scenario_c_r >= 0)

    return {
        "region": region,
        "region_slug": region_slug(region),
        "event_time": event_time,
        "s_L": s_l,
        "s_H": s_h,
        "s_unknown": s_unknown,
        "n_municipalities": int(shares["n_municipalities"]),
        "n_voters_baseline": int(shares["n_voters_baseline"]),
        "beta_N": est_n["beta"],
        "beta_N_se": est_n["se"],
        "beta_N_lower": est_n["lower"],
        "beta_N_upper": est_n["upper"],
        "beta_L": est_l["beta"],
        "beta_L_se": est_l["se"],
        "beta_L_lower": est_l["lower"],
        "beta_L_upper": est_l["upper"],
        "beta_H": est_h["beta"],
        "beta_H_se": est_h["se"],
        "beta_H_lower": est_h["lower"],
        "beta_H_upper": est_h["upper"],
        "D_N": d_n,
        "D_N_lower": dn["lower"],
        "D_N_upper": dn["upper"],
        "D_L": d_l,
        "D_L_lower": dl["lower"],
        "D_L_upper": dl["upper"],
        "D_H": d_h,
        "D_H_lower": dh["lower"],
        "D_H_upper": dh["upper"],
        "D_residual": residual,
        "R_min": r_min,
        "R_min_se": r_min_se,
        "R_min_lower": r_min_lower,
        "R_min_upper": r_min_upper,
        "R_max": r_max,
        "R_max_se": r_max_se,
        "R_max_lower": r_max_lower,
        "R_max_upper": r_max_upper,
        "bounds_feasible": bounds_feasible,
        "scenario_A_feasible": scenario_a_feasible,
        "scenario_A_R": scenario_a_r,
        "scenario_A_E_L": scenario_a_e_l,
        "scenario_A_E_H": scenario_a_e_h,
        "scenario_B_R": scenario_b_r,
        "scenario_B_E_L": scenario_b_e_l,
        "scenario_B_E_H": scenario_b_e_h,
        "scenario_C_feasible": scenario_c_feasible,
        "scenario_C_R": scenario_c_r,
        "scenario_C_E_L": scenario_c_e_l,
        "scenario_C_E_H": scenario_c_e_h,
    }


def compute_decompositions(shares: pd.DataFrame, event_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    share_map = {row["region"]: row for _, row in shares.iterrows()}
    bounds_rows = [decompose_one(region, 0, share_map[region], event_df) for region in ALL_GROUPS]
    bounds = pd.DataFrame(bounds_rows)
    bounds.to_csv(DECOMP_DIR / "bounds_by_region.csv", index=False)

    dynamic_rows = []
    for region in ALL_GROUPS:
        for event_time in POST_EVENT_TIMES:
            dynamic_rows.append(decompose_one(region, event_time, share_map[region], event_df))
    dynamic = pd.DataFrame(dynamic_rows)
    dynamic.to_csv(DECOMP_DIR / "bounds_by_region_and_event_time.csv", index=False)
    return bounds, dynamic


def make_event_time0_table(event_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for region in ALL_GROUPS:
        for outcome in OUTCOMES:
            row = event_df[
                (event_df["region"] == region)
                & (event_df["outcome"] == outcome)
                & (event_df["event_time"] == 0)
            ].iloc[0]
            rows.append(
                {
                    "region": region,
                    "outcome": outcome,
                    "outcome_label": OUTCOME_LABELS[outcome],
                    "estimate": row["estimate"],
                    "std_error": row["std.error"],
                    "conf_low": row["conf.low"],
                    "conf_high": row["conf.high"],
                    "formatted": fmt_ci(row["estimate"], row["conf.low"], row["conf.high"]),
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(DECOMP_DIR / "regional_event_time0_coefficients.csv", index=False)

    wide = out.pivot(index="region", columns="outcome_label", values="formatted").reindex(ALL_GROUPS)
    wide = wide[
        [
            "Log voters",
            "Low-ed share",
            "High-ed share",
            "Log low-ed voters",
            "Log high-ed voters",
        ]
    ]
    latex = wide.reset_index().rename(columns={"region": "Region"}).to_latex(
        index=False,
        escape=False,
        column_format="lccccc",
        caption="Regional event-time-zero TWFE estimates.",
        label="tab:regional-event-time0",
    )
    (TABLE_DIR / "regional_event_time0_coefficients.tex").write_text(fit_latex_table(latex))
    return out


def make_decomposition_tables(bounds: pd.DataFrame) -> None:
    tab = bounds.copy()
    tab["Baseline voters (m)"] = tab["n_voters_baseline"] / 1_000_000
    tab["Exit, direct total (%)"] = -100 * tab["D_N"]
    tab["Exit voters (m)"] = (-tab["D_N"]) * tab["n_voters_baseline"] / 1_000_000
    tab["R min (%)"] = 100 * tab["R_min"]
    tab["R max (%)"] = 100 * tab["R_max"]
    tab["Relabel min voters (m)"] = tab["R_min"] * tab["n_voters_baseline"] / 1_000_000
    tab["Relabel max voters (m)"] = tab["R_max"] * tab["n_voters_baseline"] / 1_000_000
    tab["Scenario C R (%)"] = 100 * tab["scenario_C_R"]
    tab["ADPF 541 comparator"] = tab["region"].map(
        {
            "National": "3.3m cancelled titles, 2016-2018",
            "Nordeste": r"Claimed about 4\% affected",
            "Sudeste": r"Claimed about 1\% affected",
        }
    ).fillna("")
    display = tab[
        [
            "region",
            "Baseline voters (m)",
            "Exit, direct total (%)",
            "Exit voters (m)",
            "R min (%)",
            "R max (%)",
            "Relabel min voters (m)",
            "Relabel max voters (m)",
            "Scenario C R (%)",
            "ADPF 541 comparator",
        ]
    ].rename(columns={"region": "Region"})
    display = display.rename(
        columns={
            "Exit, direct total (%)": "Exit, direct total (\\%)",
            "R min (%)": "R min (\\%)",
            "R max (%)": "R max (\\%)",
            "Scenario C R (%)": "Scenario C R (\\%)",
        }
    )
    display.to_csv(DECOMP_DIR / "decomposition_vs_adpf541.csv", index=False)
    latex = display.to_latex(
        index=False,
        escape=False,
        float_format=lambda x: f"{x:.2f}",
        column_format="lrrrrrrrrl",
        caption="BVR exit and re-labeling decomposition compared with ADPF 541 benchmarks.",
        label="tab:decomposition-adpf541",
    )
    (TABLE_DIR / "decomposition_vs_adpf541.tex").write_text(fit_latex_table(latex))

    compact = bounds[
        [
            "region",
            "R_min",
            "R_min_lower",
            "R_min_upper",
            "R_max",
            "R_max_lower",
            "R_max_upper",
            "scenario_B_R",
            "scenario_B_E_L",
            "scenario_C_R",
            "scenario_C_E_L",
            "scenario_C_E_H",
            "D_residual",
        ]
    ].copy()
    compact.to_csv(DECOMP_DIR / "decomposition_bounds_compact.csv", index=False)
    pretty = compact.copy()
    for col in pretty.columns:
        if col != "region":
            pretty[col] = pretty[col].map(lambda x: f"{100*x:.1f}")
    pretty = pretty.rename(
        columns={
            "region": "Region",
            "R_min": "$R_{min}$",
            "R_min_lower": "$R_{min}$ 95\\% low",
            "R_min_upper": "$R_{min}$ 95\\% high",
            "R_max": "$R_{max}$",
            "R_max_lower": "$R_{max}$ 95\\% low",
            "R_max_upper": "$R_{max}$ 95\\% high",
            "scenario_B_R": "Scenario B $R$",
            "scenario_B_E_L": "Scenario B $E_L$",
            "scenario_C_R": "Scenario C $R$",
            "scenario_C_E_L": "Scenario C $E_L$",
            "scenario_C_E_H": "Scenario C $E_H$",
            "D_residual": "Residual",
        }
    )
    latex_bounds = pretty.to_latex(
        index=False,
        escape=False,
        column_format="lrrrrrrrrrrrr",
        caption="Regional decomposition bounds as percentages of baseline electorate.",
        label="tab:regional-decomposition-bounds",
    )
    (TABLE_DIR / "decomposition_bounds_by_region.tex").write_text(fit_latex_table(latex_bounds))


def apply_plot_style(ax) -> None:
    ax.grid(True, axis="x", color="#D9D9D9", linewidth=0.7)
    ax.grid(False, axis="y")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("black")
        spine.set_linewidth(0.6)
    ax.tick_params(axis="both", labelsize=9)


def figure_event_time0(event0: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 6), sharey=True)
    specs = [
        ("log_num_voters", "Log registered voters"),
        ("log_num_voters_low_ed", "Log low-education voters"),
        ("log_num_voters_high_ed", "Log high-education voters"),
    ]
    plot_regions = REGION_ORDER + ["National"]
    y_pos = np.arange(len(plot_regions))
    for ax, (outcome, title) in zip(axes, specs):
        sub = event0[event0["outcome"] == outcome].set_index("region").loc[plot_regions]
        colors = [REGION_COLORS[r] for r in plot_regions]
        x = sub["estimate"].to_numpy()
        low = sub["conf_low"].to_numpy()
        high = sub["conf_high"].to_numpy()
        ax.axvline(0, color="#595959", linewidth=0.9)
        ax.errorbar(
            x,
            y_pos,
            xerr=[x - low, high - x],
            fmt="o",
            color="#333333",
            ecolor="#333333",
            elinewidth=1.1,
            capsize=3,
        )
        ax.scatter(x, y_pos, c=colors, s=35, zorder=3)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Event time 0 coefficient", fontsize=9)
        apply_plot_style(ax)
    axes[0].set_yticks(y_pos)
    axes[0].set_yticklabels(plot_regions)
    axes[0].invert_yaxis()
    fig.tight_layout()
    fig.savefig(DECOMP_IMAGE_DIR / "regional_event_time0_coefficients.pdf", bbox_inches="tight")
    fig.savefig(DECOMP_IMAGE_DIR / "regional_event_time0_coefficients.png", dpi=320, bbox_inches="tight")
    plt.close(fig)


def figure_bounds(bounds: pd.DataFrame) -> None:
    plot_regions = REGION_ORDER + ["National"]
    sub = bounds.set_index("region").loc[plot_regions].reset_index()
    y_pos = np.arange(len(sub))
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    for i, row in sub.iterrows():
        color = REGION_COLORS[row["region"]]
        ax.plot([100 * row["R_min"], 100 * row["R_max"]], [i, i], color=color, linewidth=5, alpha=0.65)
        ax.errorbar(
            100 * row["R_min"],
            i,
            xerr=[[100 * (row["R_min"] - row["R_min_lower"])], [100 * (row["R_min_upper"] - row["R_min"])]],
            fmt="o",
            color=color,
            ecolor=color,
            capsize=3,
        )
        ax.errorbar(
            100 * row["R_max"],
            i,
            xerr=[[100 * (row["R_max"] - row["R_max_lower"])], [100 * (row["R_max_upper"] - row["R_max"])]],
            fmt="o",
            color=color,
            ecolor=color,
            capsize=3,
        )
        if row["scenario_C_feasible"]:
            ax.scatter(100 * row["scenario_C_R"], i, marker="D", color="black", s=35, zorder=4)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(sub["region"])
    ax.invert_yaxis()
    ax.set_xlabel("Re-labeling as percent of baseline electorate")
    ax.set_title("")
    apply_plot_style(ax)
    fig.tight_layout()
    fig.savefig(DECOMP_IMAGE_DIR / "regional_decomposition_bounds.pdf", bbox_inches="tight")
    fig.savefig(DECOMP_IMAGE_DIR / "regional_decomposition_bounds.png", dpi=320, bbox_inches="tight")
    plt.close(fig)


def figure_dynamic_bounds(dynamic: pd.DataFrame) -> None:
    plot_regions = REGION_ORDER
    fig, axes = plt.subplots(2, 3, figsize=(11.5, 6.8), sharex=True, sharey=True)
    axes = axes.ravel()
    for ax, region in zip(axes, plot_regions):
        sub = dynamic[dynamic["region"] == region].sort_values("event_time")
        x = sub["event_time"].to_numpy(dtype=float)
        r_min = 100 * sub["R_min"].to_numpy(dtype=float)
        r_max = 100 * sub["R_max"].to_numpy(dtype=float)
        contraction = 100 * np.abs(sub["D_N"].to_numpy(dtype=float))
        color = REGION_COLORS[region]
        feasible = r_min <= r_max
        ax.fill_between(x, r_min, r_max, where=feasible, color=color, alpha=0.18)
        ax.plot(x, r_min, color=color, linewidth=1.8, label="$R_{min}$")
        ax.plot(x, r_max, color=color, linestyle="--", linewidth=1.8, label="$R_{max}$")
        ax.plot(x, contraction, color="black", linestyle=":", linewidth=1.5, label="Registry contraction")
        ax.axhline(0, color="#595959", linewidth=0.8)
        ax.set_title(region, fontsize=11)
        apply_plot_style(ax)
    axes[-1].axis("off")
    axes[0].legend(frameon=False, fontsize=8, loc="upper right")
    for ax in axes[:5]:
        ax.set_xlabel("Event time")
        ax.set_ylabel("Percent of baseline electorate")
    fig.tight_layout()
    fig.savefig(DECOMP_IMAGE_DIR / "dynamic_bounds_by_region.pdf", bbox_inches="tight")
    fig.savefig(DECOMP_IMAGE_DIR / "dynamic_bounds_by_region.png", dpi=320, bbox_inches="tight")
    plt.close(fig)


def tikz_escape_region(region: str) -> str:
    return region.replace("_", "\\_")


def make_tikz_body(row: pd.Series, region: str) -> str:
    s_l = 100 * row["s_L"]
    s_h = 100 * row["s_H"]
    post_total = max(0.0, 100 * (1 + row["D_N"]))
    post_low = max(0.0, 100 * (row["s_L"] + row["D_L"]))
    post_high = max(0.0, 100 * (row["s_H"] + row["D_H"]))
    exit_pct = max(0.0, 100 * (-row["D_N"]))
    relabel_pct = max(0.0, 100 * row["scenario_B_R"])
    scale = 10.0 / 100.0
    pre_l = s_l * scale
    pre_h = (s_l + s_h) * scale
    post_l = post_low * scale
    post_h = (post_low + post_high) * scale
    post_t = post_total * scale
    caption_region = "national" if region == "National" else region
    return rf"""\begin{{figure}}[!ht]
\centering
\begin{{tikzpicture}}[scale=1.2, >=stealth]

\definecolor{{loweducolor}}{{RGB}}{{200, 80, 80}}
\definecolor{{higheducolor}}{{RGB}}{{60, 120, 180}}
\definecolor{{relabelcolor}}{{RGB}}{{140, 100, 60}}
\definecolor{{exitcolor}}{{RGB}}{{150, 150, 150}}

\draw[thick] (0, 0) rectangle (2.5, {pre_h:.2f});
\fill[loweducolor, opacity=0.6] (0, 0) rectangle (2.5, {pre_l:.2f});
\node[white, font=\small\bfseries] at (1.25, {pre_l/2:.2f}) {{Low-ed}};
\node[white, font=\footnotesize] at (1.25, {max(0.25, pre_l/2 - 0.4):.2f}) {{{s_l:.1f}\%}};

\draw[thick] (0, {pre_l:.2f}) rectangle (2.5, {pre_h:.2f});
\fill[higheducolor, opacity=0.6] (0, {pre_l:.2f}) rectangle (2.5, {pre_h:.2f});
\node[white, font=\small\bfseries] at (1.25, {(pre_l+pre_h)/2:.2f}) {{High-ed}};
\node[white, font=\footnotesize] at (1.25, {max(pre_l+0.25, (pre_l+pre_h)/2 - 0.4):.2f}) {{{s_h:.1f}\%}};

\node[font=\small\bfseries] at (1.25, 10.5) {{Pre-BVR registry}};
\node[font=\footnotesize] at (1.25, -0.4) {{100\% of baseline}};

\draw[thick] (7.5, 0) rectangle (10.0, {post_t:.2f});
\fill[loweducolor, opacity=0.6] (7.5, 0) rectangle (10.0, {post_l:.2f});
\node[white, font=\small\bfseries] at (8.75, {max(0.4, post_l/2):.2f}) {{Low-ed}};
\node[white, font=\footnotesize] at (8.75, {max(0.25, post_l/2 - 0.4):.2f}) {{{post_low:.1f}\%}};

\draw[thick] (7.5, {post_l:.2f}) rectangle (10.0, {post_h:.2f});
\fill[higheducolor, opacity=0.6] (7.5, {post_l:.2f}) rectangle (10.0, {post_h:.2f});
\node[white, font=\small\bfseries] at (8.75, {(post_l+post_h)/2:.2f}) {{High-ed}};
\node[white, font=\footnotesize] at (8.75, {max(post_l+0.25, (post_l+post_h)/2 - 0.4):.2f}) {{{post_high:.1f}\%}};

\node[font=\small\bfseries] at (8.75, 10.5) {{Post-BVR registry}};
\node[font=\footnotesize] at (8.75, -0.4) {{{post_total:.1f}\% of baseline}};

\draw[dashed, thin, gray] (2.6, 10.0) -- (7.5, 10.0);
\draw[dashed, thin, gray] (2.6, {post_t:.2f}) -- (7.5, {post_t:.2f});

\draw[->, very thick, exitcolor] (2.6, 3.0) .. controls (4.5, 3.0) and (5.5, -1.0) .. (7.0, -1.5);
\node[exitcolor, font=\footnotesize\bfseries] at (4.5, -0.8) {{Exit: {exit_pct:.2f}\%}};
\node[exitcolor, font=\scriptsize] at (4.5, -1.2) {{(removed from rolls)}};

\draw[->, very thick, relabelcolor] (2.6, {max(1.0, pre_l - 0.7):.2f}) .. controls (4.5, 5.8) and (5.5, 5.8) .. (7.4, {max(1.0, post_l + 0.3):.2f});
\node[relabelcolor, font=\footnotesize\bfseries] at (5.0, 6.3) {{Re-label: {relabel_pct:.2f}\%}};
\node[relabelcolor, font=\scriptsize] at (5.0, 5.9) {{(stale record corrected)}};

\draw[->, thick, higheducolor, opacity=0.4] (2.6, {(pre_l+pre_h)/2:.2f}) -- (7.4, {(post_l+post_h)/2:.2f});
\node[higheducolor, font=\scriptsize] at (5.0, 8.0) {{High-ed retained}};

\end{{tikzpicture}}

\caption{{\textbf{{Decomposition of BVR's registry effect at event time 0 ({tikz_escape_region(region)}).}} Under Scenario B, high-education voters experience zero exit, so the positive high-education count effect is interpreted as re-labeling. For this sample, the direct registry contraction is {exit_pct:.2f}\% of the baseline electorate and the lower-bound re-labeling channel is {relabel_pct:.2f}\%. Full bounds: $R \in [{100*row['R_min']:.2f}\%, {100*row['R_max']:.2f}\%]$ of baseline electorate.}}
\label{{fig:decomposition_{region_slug(region)}}}
\end{{figure}}
"""


def write_tikz_figures(bounds: pd.DataFrame) -> None:
    rows = {row["region"]: row for _, row in bounds.iterrows()}
    national = make_tikz_body(rows["National"], "National")
    (PAPER_FIGURE_DIR / "decomposition_schematic.tex").write_text(national)
    pdflatex = shutil.which("pdflatex")
    for region in ALL_GROUPS:
        body = make_tikz_body(rows[region], region)
        slug = region_slug(region)
        (PAPER_FIGURE_DIR / f"decomposition_schematic_{slug}.tex").write_text(body)
        tikz_start = body.index(r"\begin{tikzpicture}")
        tikz_end = body.index(r"\end{tikzpicture}") + len(r"\end{tikzpicture}")
        standalone = "\n".join(
            [
                r"\documentclass[border=5pt]{standalone}",
                r"\usepackage{tikz}",
                r"\usetikzlibrary{arrows.meta}",
                r"\begin{document}",
                body[tikz_start:tikz_end],
                r"\end{document}",
                "",
            ]
        )
        standalone_path = DECOMP_IMAGE_DIR / f"decomposition_schematic_{slug}.tex"
        standalone_path.write_text(standalone)
        if pdflatex is not None:
            subprocess.run(
                [
                    pdflatex,
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-output-directory",
                    str(DECOMP_IMAGE_DIR),
                    str(standalone_path),
                ],
                cwd=ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for ext in ["aux", "log"]:
                aux_path = DECOMP_IMAGE_DIR / f"decomposition_schematic_{slug}.{ext}"
                if aux_path.exists():
                    aux_path.unlink()


def make_figures(event0: pd.DataFrame, bounds: pd.DataFrame, dynamic: pd.DataFrame) -> None:
    figure_event_time0(event0)
    figure_bounds(bounds)
    figure_dynamic_bounds(dynamic)
    write_tikz_figures(bounds)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-estimators",
        action="store_true",
        help="Skip R estimator runs and reuse existing event-study outputs.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="When running estimators, skip outputs that already exist.",
    )
    args = parser.parse_args()

    ensure_dirs()
    df, region_summary = build_panel()
    print("Region municipality counts:")
    print(region_summary.to_string(index=False))

    if not args.skip_estimators:
        run_event_studies(skip_existing=args.skip_existing)

    event_df = collect_event_studies()
    sanity_check_national(event_df)
    shares = compute_baseline_shares(df)
    bounds, dynamic = compute_decompositions(shares, event_df)
    event0 = make_event_time0_table(event_df)
    make_decomposition_tables(bounds)
    make_figures(event0, bounds, dynamic)

    national = bounds[bounds["region"] == "National"].iloc[0]
    print("\nNational decomposition sanity:")
    print(
        f"R_min={100*national['R_min']:.2f}%, R_max={100*national['R_max']:.2f}%, "
        f"D_N={100*national['D_N']:.2f}%, residual={100*national['D_residual']:.2f}%"
    )
    print(f"Outputs written under {DECOMP_DIR.relative_to(ROOT)} and {DID_DIR.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
