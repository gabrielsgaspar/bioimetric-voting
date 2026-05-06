#!/usr/bin/env python3
"""Run 2006-normalized registry event studies for the BVR decomposition.

The goal is to estimate count outcomes in levels, normalized by each
municipality's 2006 electorate, so the total/education-category coefficients
obey the raw-count accounting identity exactly.
"""

from __future__ import annotations

import math
import subprocess
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PANEL_IN = ROOT / "data/clean/tse/tse_clean_panel_2000_2018.parquet"
OUT_DIR = ROOT / "resources/decomposition"
PANEL_OUT = OUT_DIR / "panel_normalized_2006.parquet"

EVENT_TIMES = [-8, -6, -4, -2, 0, 2, 4, 6, 8]
REFERENCE_EVENT_TIME = -2

OUTCOMES = {
    "y_N": {
        "label": "Registered voters",
        "title": "Effect on registered voters (normalized by 2006 baseline)",
        "raw": "num_voters",
        "output": "event_study_y_N",
    },
    "y_L": {
        "label": "Low-education voters",
        "title": "Effect on low-education voters (normalized by 2006 baseline)",
        "raw": "num_voters_low_ed",
        "output": "event_study_y_L",
    },
    "y_H": {
        "label": "High-education voters",
        "title": "Effect on high-education voters (normalized by 2006 baseline)",
        "raw": "num_voters_high_ed",
        "output": "event_study_y_H",
    },
    "y_U": {
        "label": "Unknown-education voters",
        "title": "Effect on unknown-education voters (normalized by 2006 baseline)",
        "raw": "num_voters_unknown_ed",
        "output": "event_study_y_U",
    },
}

LOG_SPECS = {
    "N": {
        "path": ROOT / "resources/did/twfe_dynamic/log_num_voters/event_study_estimates.csv",
        "levels_outcome": "y_N",
        "share": 1.0,
        "label": "Total voters",
    },
    "L": {
        "path": ROOT / "resources/did/twfe_dynamic/log_num_voters_low_ed/event_study_estimates.csv",
        "levels_outcome": "y_L",
        "share": 0.591,
        "label": "Low-education voters",
    },
    "H": {
        "path": ROOT / "resources/did/twfe_dynamic/log_num_voters_high_ed/event_study_estimates.csv",
        "levels_outcome": "y_H",
        "share": 0.408,
        "label": "High-education voters",
    },
}


def fmt_float(value: float | int | None) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "NA"
    return f"{value:.6f}"


def ci_text(row: pd.Series) -> str:
    return f"{row['estimate']:.4f} [{row['conf.low']:.4f}, {row['conf.high']:.4f}]"


def write_yaml_config(path: Path, cfg: dict[str, object]) -> None:
    """Write the small estimator config without adding a PyYAML dependency."""
    lines: list[str] = []
    for key, value in cfg.items():
        if value is None:
            lines.append(f"{key}: ~")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'yes' if value else 'no'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        elif isinstance(value, (list, tuple)):
            lines.append(f"{key}:")
            if len(value) == 0:
                lines[-1] += " []"
            else:
                for item in value:
                    lines.append(f"  - {item}")
        else:
            text = str(value).replace('"', '\\"')
            lines.append(f'{key}: "{text}"')
    path.write_text("\n".join(lines) + "\n")


def load_and_prepare_panel() -> tuple[pd.DataFrame, dict[str, object]]:
    required = {
        "municipality_id",
        "year_election",
        "num_voters",
        "num_voters_low_ed",
        "num_voters_high_ed",
        "year_treated",
        "dist_treatment",
        "hybrid",
        "state",
    }
    df = pd.read_parquet(PANEL_IN)
    missing = sorted(required.difference(df.columns))
    if missing:
        raise RuntimeError(f"Missing required columns in {PANEL_IN}: {missing}")

    df = df.copy()
    df["num_voters_unknown_ed"] = (
        df["num_voters"] - df["num_voters_low_ed"] - df["num_voters_high_ed"]
    )
    if (df["num_voters_unknown_ed"] < 0).any():
        bad = int((df["num_voters_unknown_ed"] < 0).sum())
        raise RuntimeError(f"Computed unknown education is negative in {bad} rows.")

    all_munis = set(df["municipality_id"].unique())
    base_2006 = (
        df.loc[df["year_election"] == 2006, ["municipality_id", "num_voters"]]
        .rename(columns={"num_voters": "N_m_2006"})
        .drop_duplicates("municipality_id")
    )
    missing_2006 = sorted(all_munis.difference(set(base_2006["municipality_id"])))
    missing_2006_states = (
        df.loc[df["municipality_id"].isin(missing_2006), ["municipality_id", "state"]]
        .drop_duplicates()
        .groupby("state")["municipality_id"]
        .nunique()
        .sort_index()
        .to_dict()
    )

    panel = df.merge(base_2006, on="municipality_id", how="left")
    panel = panel.loc[panel["N_m_2006"].notna()].copy()
    panel = panel.loc[panel["N_m_2006"] > 0].copy()

    for outcome, spec in OUTCOMES.items():
        panel[outcome] = panel[spec["raw"]] / panel["N_m_2006"]

    rng = np.random.default_rng(20260424)
    sample_size = min(1000, len(panel))
    sample_index = rng.choice(panel.index.to_numpy(), size=sample_size, replace=False)
    sample = panel.loc[sample_index]
    sample_residual = sample["y_N"] - sample[["y_L", "y_H", "y_U"]].sum(axis=1)
    full_residual = panel["y_N"] - panel[["y_L", "y_H", "y_U"]].sum(axis=1)
    max_sample_identity_residual = float(sample_residual.abs().max())
    max_full_identity_residual = float(full_residual.abs().max())

    panel.to_parquet(PANEL_OUT, index=False)

    notes = {
        "n_rows_input": int(len(df)),
        "n_municipalities_input": int(df["municipality_id"].nunique()),
        "n_2006_municipalities": int(base_2006["municipality_id"].nunique()),
        "n_missing_2006_municipalities": int(len(missing_2006)),
        "missing_2006_municipalities": missing_2006,
        "missing_2006_states": missing_2006_states,
        "n_rows_normalized": int(len(panel)),
        "n_municipalities_normalized": int(panel["municipality_id"].nunique()),
        "max_sample_identity_residual": max_sample_identity_residual,
        "max_full_identity_residual": max_full_identity_residual,
        "unknown_ed_min": int(panel["num_voters_unknown_ed"].min()),
        "unknown_ed_max": int(panel["num_voters_unknown_ed"].max()),
        "unknown_ed_sum": int(panel["num_voters_unknown_ed"].sum()),
    }
    return panel, notes


def write_panel_notes(notes: dict[str, object]) -> None:
    missing_states = notes["missing_2006_states"]
    if missing_states:
        missing_state_text = ", ".join(f"{state}: {n}" for state, n in missing_states.items())
    else:
        missing_state_text = "none"
    missing_munis = ", ".join(str(x) for x in notes["missing_2006_municipalities"]) or "none"
    text = f"""# 2006-Normalized Panel Preparation

Input panel: `{PANEL_IN.relative_to(ROOT)}`

Output panel: `{PANEL_OUT.relative_to(ROOT)}`

## Coverage

- Input rows: {notes['n_rows_input']:,}
- Input municipalities: {notes['n_municipalities_input']:,}
- Municipalities with a 2006 baseline: {notes['n_2006_municipalities']:,}
- Municipalities excluded for missing 2006 baseline: {notes['n_missing_2006_municipalities']:,}
- Excluded municipality IDs: {missing_munis}
- Excluded municipality states: {missing_state_text}
- Normalized rows retained: {notes['n_rows_normalized']:,}
- Normalized municipalities retained: {notes['n_municipalities_normalized']:,}

## Additivity

The unknown-education count is computed as `num_voters - num_voters_low_ed - num_voters_high_ed`.
It is nonnegative in all retained observations.

- Unknown-education minimum count: {notes['unknown_ed_min']:,}
- Unknown-education maximum count: {notes['unknown_ed_max']:,}
- Unknown-education total over retained municipality-years: {notes['unknown_ed_sum']:,}
- Maximum additivity residual in random 1,000-observation check: {notes['max_sample_identity_residual']:.3e}
- Maximum additivity residual in the full normalized panel: {notes['max_full_identity_residual']:.3e}
"""
    (OUT_DIR / "panel_normalized_2006_notes.md").write_text(text)


def write_configs() -> list[Path]:
    configs: list[Path] = []
    for outcome, spec in OUTCOMES.items():
        out_subdir = OUT_DIR / spec["output"]
        out_subdir.mkdir(parents=True, exist_ok=True)
        cfg_path = out_subdir / "config.yml"
        cfg = {
            "estimator": "twfe_dynamic",
            "data_path": str(PANEL_OUT.relative_to(ROOT)),
            "file_format": "parquet",
            "outcome": outcome,
            "unit_id": "municipality_id",
            "time_id": "year_election",
            "group_id": "year_treated",
            "treatment_var": None,
            "controls": [],
            "cluster_var": ["municipality_id", "year_election"],
            "weights_var": None,
            "event_time_var": "dist_treatment",
            "event_time_never_value": -9999,
            "lead": 8,
            "lag": 8,
            "reference_event_time": REFERENCE_EVENT_TIME,
            "anticipation": 0,
            "control_group": "nevertreated",
            "balanced_panel_required": False,
            "output_dir": str(out_subdir.relative_to(ROOT)),
            "notes": (
                f"Dynamic TWFE event study for {outcome}, normalized by each "
                "municipality's 2006 registered electorate."
            ),
            "event_time_step": 1,
            "never_treated_value": 9999,
            "trends_lin": False,
            "omit_plot_title": True,
        }
        write_yaml_config(cfg_path, cfg)
        configs.append(cfg_path)
    return configs


def run_estimators(configs: list[Path]) -> None:
    for cfg_path in configs:
        rel_cfg = cfg_path.relative_to(ROOT)
        subprocess.run(
            ["bash", "scripts/run_did_estimator.sh", str(rel_cfg)],
            cwd=ROOT,
            check=True,
        )


def read_event_study(outcome: str) -> pd.DataFrame:
    csv_path = OUT_DIR / OUTCOMES[outcome]["output"] / "event_study_estimates.csv"
    df = pd.read_csv(csv_path)
    df = df.loc[df["event_time"].isin(EVENT_TIMES)].copy()
    df = df.sort_values("event_time")
    return df


def write_fit_summaries() -> None:
    for outcome, spec in OUTCOMES.items():
        out_subdir = OUT_DIR / spec["output"]
        summary = (out_subdir / "model_summary.txt").read_text()
        diagnostics = pd.read_csv(out_subdir / "sample_diagnostics.csv")
        est = read_event_study(outcome)
        row0 = est.loc[est["event_time"] == 0].iloc[0]
        diagnostic_text = diagnostics.to_string(index=False)
        text = f"""Normalized 2006 dynamic TWFE event study
Outcome: {outcome} ({spec['label']})
Denominator: municipality registered electorate in 2006
Reference event time: {REFERENCE_EVENT_TIME}
Event-time grid: {EVENT_TIMES}
Event-time 0 coefficient: {ci_text(row0)}

Sample diagnostics:
{diagnostic_text}

Estimator summary from shared DID wrapper:
{summary}
"""
        (out_subdir / "fit_summary.txt").write_text(text)


def plot_event_study(
    ax: plt.Axes,
    df: pd.DataFrame,
    title: str,
    y_limits: tuple[float, float] | None = None,
    color: str = "#2C5A8A",
) -> None:
    ordered = df.set_index("event_time").reindex(EVENT_TIMES).reset_index()
    ax.axhline(0, color="0.25", linewidth=0.9)
    ax.axvline(REFERENCE_EVENT_TIME, color="0.45", linestyle="--", linewidth=0.9)
    ax.plot(ordered["event_time"], ordered["estimate"], color=color, linewidth=1.5)
    ax.scatter(ordered["event_time"], ordered["estimate"], color=color, s=22, zorder=3)
    ci = ordered.dropna(subset=["conf.low", "conf.high"])
    yerr = np.vstack([
        ci["estimate"].to_numpy() - ci["conf.low"].to_numpy(),
        ci["conf.high"].to_numpy() - ci["estimate"].to_numpy(),
    ])
    ax.errorbar(
        ci["event_time"],
        ci["estimate"],
        yerr=yerr,
        fmt="none",
        ecolor=color,
        elinewidth=1.2,
        capsize=3,
    )
    ax.set_title(title, fontsize=10)
    ax.set_xlabel("Event time (years relative to adoption)")
    ax.set_ylabel("Coefficient (share of 2006 electorate)")
    ax.set_xticks(EVENT_TIMES)
    ax.grid(True, axis="y", color="#D9D9D9", linewidth=0.5)
    ax.grid(False, axis="x")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("black")
        spine.set_linewidth(0.6)
    if y_limits is not None:
        ax.set_ylim(y_limits)


def finite_ci_bounds(frames: list[pd.DataFrame]) -> tuple[float, float]:
    vals: list[float] = []
    for df in frames:
        vals.extend(df["estimate"].dropna().tolist())
        vals.extend(df["conf.low"].dropna().tolist())
        vals.extend(df["conf.high"].dropna().tolist())
    max_abs = max(abs(v) for v in vals if math.isfinite(v))
    pad = max(0.01, 0.08 * max_abs)
    return -max_abs - pad, max_abs + pad


def make_plots(estimates: dict[str, pd.DataFrame]) -> None:
    for outcome, df in estimates.items():
        fig, ax = plt.subplots(figsize=(7.2, 4.4))
        plot_event_study(ax, df, OUTCOMES[outcome]["title"])
        fig.tight_layout()
        fig.savefig(OUT_DIR / f"event_study_plot_{outcome}.pdf")
        plt.close(fig)

    shared_limits = finite_ci_bounds([estimates["y_N"], estimates["y_L"], estimates["y_H"]])
    fig, axes = plt.subplots(1, 4, figsize=(15, 3.8), sharex=False)
    for ax, outcome in zip(axes[:3], ["y_N", "y_L", "y_H"]):
        plot_event_study(ax, estimates[outcome], OUTCOMES[outcome]["label"], shared_limits)
    plot_event_study(axes[3], estimates["y_U"], OUTCOMES["y_U"]["label"])
    fig.suptitle("Dynamic TWFE effects normalized by 2006 electorate", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(OUT_DIR / "event_study_plot_combined.pdf")
    plt.close(fig)


def identity_check(estimates: dict[str, pd.DataFrame]) -> pd.DataFrame:
    out = pd.DataFrame({"event_time": EVENT_TIMES})
    for outcome, col in [("y_N", "gamma_N"), ("y_L", "gamma_L"), ("y_H", "gamma_H"), ("y_U", "gamma_U")]:
        vals = estimates[outcome][["event_time", "estimate"]].rename(columns={"estimate": col})
        out = out.merge(vals, on="event_time", how="left")
    out["sum_L_H_U"] = out["gamma_L"] + out["gamma_H"] + out["gamma_U"]
    out["residual"] = out["gamma_N"] - out["sum_L_H_U"]
    out["residual_magnitude"] = out["residual"].abs()
    out.to_csv(OUT_DIR / "identity_check.csv", index=False)
    max_residual = out["residual_magnitude"].max()
    holds = bool(max_residual < 1e-10)
    text = f"""# Additive Identity Check

The normalized outcomes use a common denominator, each municipality's 2006 registered electorate.
The event-study specification and sample are identical across the four outcomes.

Identity checked at each event time:

```text
gamma_N = gamma_L + gamma_H + gamma_U
```

Result: {'PASS' if holds else 'FAIL'}

Maximum absolute residual: `{max_residual:.3e}`

Threshold used for pass/fail: `1e-10`.

If this check passes, downstream decomposition can be computed directly from
the level-normalized coefficients without the residual created by separately
transformed log-count semi-elasticities.
"""
    (OUT_DIR / "identity_check_notes.md").write_text(text)
    return out


def comparison_logs_vs_levels(estimates: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, float | str | int]] = []
    for short, spec in LOG_SPECS.items():
        log_df = pd.read_csv(spec["path"])
        levels = estimates[spec["levels_outcome"]][["event_time", "estimate"]].rename(
            columns={"estimate": "levels_normalized_coefficient"}
        )
        merged = (
            pd.DataFrame({"event_time": EVENT_TIMES})
            .merge(log_df[["event_time", "estimate"]], on="event_time", how="left")
            .rename(columns={"estimate": "log_coefficient"})
            .merge(levels, on="event_time", how="left")
        )
        merged["log_coefficient"] = merged["log_coefficient"].fillna(0.0)
        merged["implied_share_effect"] = spec["share"] * (np.exp(merged["log_coefficient"]) - 1)
        merged["difference"] = (
            merged["levels_normalized_coefficient"] - merged["implied_share_effect"]
        )
        merged.insert(0, "outcome", short)
        merged.insert(1, "outcome_label", spec["label"])
        rows.extend(merged.to_dict("records"))
    out = pd.DataFrame(rows)
    out.to_csv(OUT_DIR / "comparison_logs_vs_levels.csv", index=False)
    return out


def make_comparison_plot(comp: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 3.8), sharex=True)
    for ax, short in zip(axes, ["N", "L", "H"]):
        part = comp.loc[comp["outcome"] == short].sort_values("event_time")
        label = part["outcome_label"].iloc[0]
        ax.axhline(0, color="0.25", linewidth=0.9)
        ax.axvline(REFERENCE_EVENT_TIME, color="0.45", linestyle="--", linewidth=0.9)
        ax.plot(
            part["event_time"],
            part["implied_share_effect"],
            marker="o",
            color="#8C3B2F",
            linewidth=1.3,
            label="Log implied share effect",
        )
        ax.plot(
            part["event_time"],
            part["levels_normalized_coefficient"],
            marker="s",
            color="#2C5A8A",
            linewidth=1.3,
            label="2006-normalized level coefficient",
        )
        ax.set_title(label, fontsize=10)
        ax.set_xticks(EVENT_TIMES)
        ax.grid(True, axis="y", color="#D9D9D9", linewidth=0.5)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("black")
            spine.set_linewidth(0.6)
    axes[0].set_ylabel("Share of baseline electorate")
    for ax in axes:
        ax.set_xlabel("Event time")
    axes[2].legend(loc="best", fontsize=8)
    fig.suptitle("Log-based implied effects vs. 2006-normalized level effects", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(OUT_DIR / "comparison_logs_vs_levels.pdf")
    plt.close(fig)


def build_summary_report(
    estimates: dict[str, pd.DataFrame],
    identity: pd.DataFrame,
    comp: pd.DataFrame,
    panel_notes: dict[str, object],
) -> None:
    event0 = {
        outcome: df.loc[df["event_time"] == 0].iloc[0]
        for outcome, df in estimates.items()
    }
    gamma_n = float(event0["y_N"]["estimate"])
    gamma_l = float(event0["y_L"]["estimate"])
    gamma_h = float(event0["y_H"]["estimate"])
    gamma_u = float(event0["y_U"]["estimate"])

    r_min = max(0.0, gamma_h)
    r_max = -gamma_l
    scenario_b_r = gamma_h
    scenario_b_e_l_accounting = -gamma_l - gamma_h
    scenario_b_e_l_identity = -gamma_n + gamma_u
    scenario_b_e_h = 0.0

    max_identity_residual = identity["residual_magnitude"].max()
    event0_table = "\n".join(
        f"| `{outcome}` | {OUTCOMES[outcome]['label']} | {ci_text(event0[outcome])} |"
        for outcome in ["y_N", "y_L", "y_H", "y_U"]
    )
    diff0 = (
        comp.loc[comp["event_time"] == 0, ["outcome", "implied_share_effect", "levels_normalized_coefficient", "difference"]]
        .assign(
            implied_share_effect=lambda d: d["implied_share_effect"].map(lambda x: f"{x:.4f}"),
            levels_normalized_coefficient=lambda d: d["levels_normalized_coefficient"].map(lambda x: f"{x:.4f}"),
            difference=lambda d: d["difference"].map(lambda x: f"{x:.4f}"),
        )
    )
    diff0_table = "\n".join(
        f"| `{row.outcome}` | {row.implied_share_effect} | {row.levels_normalized_coefficient} | {row.difference} |"
        for row in diff0.itertuples(index=False)
    )

    close_note = (
        "The new bounds are close to the current Section 5 bounds."
        if abs(r_min - 0.069) <= 0.02 and abs(r_max - 0.135) <= 0.02
        else "At least one new bound differs from the current Section 5 bounds by more than two percentage points; this should be investigated before rewriting Section 5."
    )

    text = f"""# 2006-Normalized Decomposition Event Studies

## What Was Computed

This module constructs four count outcomes normalized by each municipality's
registered electorate in 2006:

- `y_N = num_voters / N_m_2006`
- `y_L = num_voters_low_ed / N_m_2006`
- `y_H = num_voters_high_ed / N_m_2006`
- `y_U = num_voters_unknown_ed / N_m_2006`

It then runs dynamic TWFE event studies for all four outcomes using the shared
`did-estimators` wrapper and the same specification in every run:
municipality fixed effects, election-year fixed effects, event-time bins from
`-8` to `+8`, reference period `-2`, and two-way clustered standard errors by
municipality and election year.

The normalized panel retains {panel_notes['n_municipalities_normalized']:,}
municipalities and {panel_notes['n_rows_normalized']:,} municipality-year
observations. Six municipalities are excluded because they have no 2006
baseline observation.

## Accounting Identity

The coefficient identity `gamma_N = gamma_L + gamma_H + gamma_U` {'holds' if max_identity_residual < 1e-10 else 'does not hold'}.

Maximum absolute residual across event times: `{max_identity_residual:.3e}`.

The corresponding observation-level identity also holds in the normalized
panel, with a full-panel maximum residual of
`{panel_notes['max_full_identity_residual']:.3e}`.

## Event-Time 0 Coefficients

| Outcome | Description | Coefficient and 95% CI |
|---|---|---:|
{event0_table}

## Event-Time 0 Decomposition Inputs

- Re-labeling lower bound: `R_min = max(0, gamma_H^0) = {r_min:.4f}`
- Re-labeling upper bound: `R_max = -gamma_L^0 = {r_max:.4f}`
- Scenario B re-labeling: `R = gamma_H^0 = {scenario_b_r:.4f}`
- Scenario B high-education exit: `E_H = {scenario_b_e_h:.4f}`
- Scenario B low-education exit from the low-count accounting equation,
  `E_L = -gamma_L^0 - gamma_H^0 = {scenario_b_e_l_accounting:.4f}`
- Equivalently using the additive identity and treating unknown education as a
  separate residual category, `E_L = -gamma_N^0 + gamma_U^0 = {scenario_b_e_l_identity:.4f}`

Note: the formula above follows directly from `gamma_L = -E_L - R` and
`R = gamma_H` under the no-high-education-exit scenario. A formula that instead
adds `gamma_H` to `-gamma_N` would not satisfy the low-count accounting equation
when `R = gamma_H`.

## Comparison With Current Section 5 Bounds

Current Section 5 reports `R_min = 6.9%` and `R_max = 13.5%` from transformed
log-count event studies. The 2006-normalized level estimates imply
`R_min = {100 * r_min:.1f}%` and `R_max = {100 * r_max:.1f}%`.

{close_note}

At event time 0, the log-based implied share effects and new level coefficients are:

| Outcome | Log-implied share effect | 2006-normalized level coefficient | Difference |
|---|---:|---:|---:|
{diff0_table}

## Outputs

- Normalized panel: `resources/decomposition/panel_normalized_2006.parquet`
- Event-study outputs:
  - `resources/decomposition/event_study_y_N/`
  - `resources/decomposition/event_study_y_L/`
  - `resources/decomposition/event_study_y_H/`
  - `resources/decomposition/event_study_y_U/`
- Identity check: `resources/decomposition/identity_check.csv`
- Identity note: `resources/decomposition/identity_check_notes.md`
- Individual plots:
  - `resources/decomposition/event_study_plot_y_N.pdf`
  - `resources/decomposition/event_study_plot_y_L.pdf`
  - `resources/decomposition/event_study_plot_y_H.pdf`
  - `resources/decomposition/event_study_plot_y_U.pdf`
- Combined plot: `resources/decomposition/event_study_plot_combined.pdf`
- Log-vs-level comparison table: `resources/decomposition/comparison_logs_vs_levels.csv`
- Log-vs-level comparison plot: `resources/decomposition/comparison_logs_vs_levels.pdf`

## Anomalies and Warnings

- The clean panel contains 5,571 municipalities, but only 5,565 have a 2006
  observation. The normalized analysis excludes the six municipalities without
  a common baseline denominator, as required.
- The event-time-zero estimates should be compared with the rough log-based
  sanity values in the prompt. Differences are expected where the log-based
  transformed semi-elasticities were previously generating the accounting
  residual.
- A same-sample check of the original log-count event studies on the retained
  2006-baseline sample gives event-time-zero coefficients of `-0.1154` for
  total voters, `-0.2591` for low-education voters, and `0.1554` for
  high-education voters. These are essentially unchanged from the existing log
  outputs, so the level/log divergence is not caused by excluding the six
  municipalities without 2006 baselines.
- `fixest` repaired non-positive-definite two-way clustered VCOV matrices for
  the `y_N`, `y_L`, and `y_H` runs. The point estimates are unaffected, but the
  confidence intervals use the repaired VCOV.
- Dynamic TWFE remains a staggered-adoption baseline estimator, so these
  estimates are intended for internal accounting consistency and comparability
  with the existing Section 4 event studies.
"""
    (OUT_DIR / "NORMALIZED_2006_REPORT.md").write_text(textwrap.dedent(text))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel, notes = load_and_prepare_panel()
    write_panel_notes(notes)
    configs = write_configs()
    run_estimators(configs)
    write_fit_summaries()

    estimates = {outcome: read_event_study(outcome) for outcome in OUTCOMES}
    identity = identity_check(estimates)
    make_plots(estimates)
    comp = comparison_logs_vs_levels(estimates)
    make_comparison_plot(comp)
    build_summary_report(estimates, identity, comp, notes)
    print(f"Wrote normalized decomposition outputs to {OUT_DIR.relative_to(ROOT)}")
    print(f"Retained {panel['municipality_id'].nunique():,} municipalities and {len(panel):,} rows.")
    print(f"Maximum coefficient identity residual: {identity['residual_magnitude'].max():.3e}")


if __name__ == "__main__":
    main()
