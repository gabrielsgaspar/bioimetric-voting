from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
import numpy as np
import pandas as pd
import yaml

try:
    from plot_style import apply_boxed_axis_style, apply_matplotlib_paper_style, save_pdf_png
except ImportError:  # pragma: no cover
    from src.analysis.plot_style import apply_boxed_axis_style, apply_matplotlib_paper_style, save_pdf_png


ROOT = Path(__file__).resolve().parents[2]
PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018_bvr_status_updated.parquet"
REG_DID_SKILL_DIR = Path("/Users/gabrielsgaspar/.codex/skills/reg-did")
RUNNER = REG_DID_SKILL_DIR / "scripts" / "run_estimator.R"
OUTPUT_ROOT = ROOT / "resources" / "regressions" / "bvr"

OUTCOMES = {
    "log_num_voters": "Log registered voters",
    "pct_voters_low_ed": "Share of voters with low education",
    "pct_voters_high_ed": "Share of voters with high education",
}

SPECS = {
    "strict_bvr": {
        "group_var": "year_first_strict_bvr",
        "exclude_hybrid": True,
        "label": "strict BVR only, excluding municipalities ever flagged as hybrid",
    },
    "including_hybrid": {
        "group_var": "year_first_any_bvr",
        "exclude_hybrid": False,
        "label": "any BVR, including strict and hybrid municipalities",
    },
}

NEVER_TREATED_VALUE = 9999
LEAD = 8
LAG = 8
SEED = 20260505
X_TICKS = list(range(-LEAD, LAG + 1, 2))
Y_STEP = 0.05
MIN_ABS_Y = 0.15
OFFSET_STEP = 0.24
POINT_SIZE = 31
CI_LINEWIDTH = 1.0
DCDH_BOOTSTRAP_REPS = 199

CALLAWAY_ESTIMATOR = {
    "label": "Callaway-Sant'Anna",
    "color": "#2C5A8A",
    "config": {
        "estimator": "callaway_santanna",
        "control_group": "nevertreated",
        "base_period": "universal",
    },
}

OTHER_ESTIMATORS = {
    "bjs": {
        "label": "Borusyak-Jaravel-Spiess",
        "color": "#009E73",
        "config": {
            "estimator": "bjs",
            "event_time_step": 2,
            "horizon": [0, 2, 4, 6, 8],
            "pretrends": [2, 4, 6, 8],
        },
    },
    "dcdh": {
        "label": "de Chaisemartin-D'Haultfoeuille",
        "color": "#CC79A7",
        "config": {
            "estimator": "dcdh",
            "effects": 8,
            "placebo": 8,
            "dcdh_mode": "old",
        },
    },
    "twfe_dynamic": {
        "label": "Dynamic TWFE",
        "color": "#6B6B6B",
        "config": {
            "estimator": "twfe_dynamic",
            "event_time_var": "event_time_cs",
            "event_time_never_value": -9999,
            "reference_event_time": -2,
        },
    },
}

COMPARISON_ESTIMATORS = {
    "callaway_santanna": CALLAWAY_ESTIMATOR,
    **OTHER_ESTIMATORS,
}


def load_panel() -> pd.DataFrame:
    panel = pd.read_parquet(PANEL_PATH)
    panel["municipality_id"] = panel["municipality_id"].astype(str).str.zfill(7)
    return panel.sort_values(["municipality_id", "year_election"]).reset_index(drop=True)


def build_sample(panel: pd.DataFrame, spec_key: str, group_var: str, exclude_hybrid: bool) -> pd.DataFrame:
    sample = panel.copy()
    if exclude_hybrid:
        ever_hybrid = sample.groupby("municipality_id")["hybrid"].max()
        hybrid_ids = set(ever_hybrid.loc[ever_hybrid.eq(1)].index)
        sample = sample.loc[~sample["municipality_id"].isin(hybrid_ids)].copy()

    sample["treatment_year_cs"] = sample[group_var].astype(int)
    sample["event_time_cs"] = sample["year_election"].astype(int) - sample["treatment_year_cs"]
    sample.loc[sample["treatment_year_cs"].eq(NEVER_TREATED_VALUE), "event_time_cs"] = -9999
    sample["spec"] = spec_key
    return sample.sort_values(["municipality_id", "year_election"]).reset_index(drop=True)


def build_sample_summary(sample: pd.DataFrame, full_panel: pd.DataFrame, spec_key: str) -> pd.DataFrame:
    treated = sample["treatment_year_cs"].ne(NEVER_TREATED_VALUE)
    return pd.DataFrame(
        [
            {"metric": "spec", "value": spec_key},
            {"metric": "rows_full_panel", "value": len(full_panel)},
            {"metric": "rows_analysis_sample", "value": len(sample)},
            {"metric": "municipalities_full_panel", "value": full_panel["municipality_id"].nunique()},
            {"metric": "municipalities_analysis_sample", "value": sample["municipality_id"].nunique()},
            {"metric": "treated_municipalities", "value": sample.loc[treated, "municipality_id"].nunique()},
            {"metric": "never_treated_municipalities", "value": sample.loc[~treated, "municipality_id"].nunique()},
            {"metric": "hybrid_municipalities_in_sample", "value": sample.groupby("municipality_id")["hybrid"].max().sum()},
        ]
    )


def write_config(
    *,
    outcome: str,
    estimator_key: str,
    estimator: dict,
    spec_key: str,
    spec_label: str,
    sample_path: Path,
    output_dir: Path,
    show_line: bool,
) -> Path:
    config = {
        "data_path": str(sample_path.relative_to(ROOT)),
        "file_format": sample_path.suffix.lstrip("."),
        "outcome": outcome,
        "unit_id": "municipality_id",
        "time_id": "year_election",
        "group_id": "treatment_year_cs",
        "treatment_var": None,
        "controls": [],
        "cluster_var": "municipality_id",
        "weights_var": None,
        "lead": LEAD,
        "lag": LAG,
        "anticipation": 0,
        "balanced_panel_required": False,
        "never_treated_value": NEVER_TREATED_VALUE,
        "seed": SEED,
        "plot_reference_event_time": -2,
        "output": {
            "save_csv": True,
            "save_parquet": False,
            "save_json": True,
        },
        "plot": {
            "latex_figure_format": "pdf",
            "save_tight_png": True,
            "save_png": False,
            "omit_title": True,
            "x_label": "Distance to treatment",
            "y_label": None,
            "color": estimator["color"],
            "x_breaks": list(range(-LEAD, LAG + 1, 2)),
            "width": 8,
            "height": 5,
            "dpi": 320,
            "show_grid": True,
            "show_border": True,
            "zero_line": True,
            "reference_line": True,
            "reference_line_type": "dashed",
            "ci_geom": "linerange",
            "show_line": show_line,
            "show_points": True,
        },
        "output_dir": str(output_dir),
        "notes": (
            f"{estimator['label']} dynamic DID for {outcome} in the BVR registry panel. "
            f"Specification: {spec_label}. This run uses the reg-did skill at {REG_DID_SKILL_DIR}. "
            "Standard errors are clustered by municipality; "
            "control group is never-treated municipalities."
        ),
    }
    config.update(estimator["config"])
    config_path = output_dir / "config.yml"
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
    return config_path


def run_estimator(config_path: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        ["Rscript", str(RUNNER), str(config_path.relative_to(ROOT))],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")


def _normal_p_value(statistic: float) -> float:
    if not math.isfinite(statistic):
        return math.nan
    return math.erfc(abs(statistic) / math.sqrt(2.0))


def _dcdh_switcher_estimates(
    sample: pd.DataFrame,
    outcome: str,
    *,
    unit_weights: pd.Series | None = None,
) -> pd.DataFrame:
    unit_col = "municipality_id"
    time_col = "year_election"
    group_col = "treatment_year_cs"
    years = sorted(sample[time_col].dropna().unique())
    wide = sample.pivot(index=unit_col, columns=time_col, values=outcome).sort_index()
    groups = sample.groupby(unit_col, sort=False)[group_col].first().reindex(wide.index)
    treated_groups = sorted(groups.loc[groups.ne(NEVER_TREATED_VALUE)].dropna().unique())
    if unit_weights is None:
        weights = pd.Series(1.0, index=wide.index)
    else:
        weights = unit_weights.reindex(wide.index).fillna(0.0).astype(float)

    rows = []
    for event_time in X_TICKS:
        if event_time == -2:
            rows.append({"event_time": event_time, "estimate": 0.0, "n_switchers": math.nan, "n_comparisons": 0})
            continue

        comparison_estimates = []
        comparison_weights = []
        for treatment_year in treated_groups:
            if event_time >= 0:
                base_year = treatment_year - 2
                target_year = treatment_year + event_time
                control_mask = groups.eq(NEVER_TREATED_VALUE) | groups.gt(target_year)
            else:
                target_year = treatment_year + event_time + 2
                base_year = target_year - 2
                control_mask = groups.eq(NEVER_TREATED_VALUE) | groups.gt(target_year)

            if base_year not in years or target_year not in years:
                continue

            switcher_mask = groups.eq(treatment_year)
            switcher_delta = wide[target_year] - wide[base_year]
            control_delta = switcher_delta

            switcher_valid = switcher_mask & switcher_delta.notna() & weights.gt(0)
            control_valid = control_mask & control_delta.notna() & weights.gt(0)
            switcher_weight = weights.loc[switcher_valid].sum()
            control_weight = weights.loc[control_valid].sum()
            if switcher_weight <= 0 or control_weight <= 0:
                continue

            switcher_mean = np.average(
                switcher_delta.loc[switcher_valid],
                weights=weights.loc[switcher_valid],
            )
            control_mean = np.average(
                control_delta.loc[control_valid],
                weights=weights.loc[control_valid],
            )
            comparison_estimates.append(switcher_mean - control_mean)
            comparison_weights.append(switcher_weight)

        if comparison_weights:
            estimate = float(np.average(comparison_estimates, weights=comparison_weights))
            n_switchers = float(np.sum(comparison_weights))
        else:
            estimate = math.nan
            n_switchers = math.nan

        rows.append(
            {
                "event_time": event_time,
                "estimate": estimate,
                "n_switchers": n_switchers,
                "n_comparisons": len(comparison_weights),
            }
        )

    return pd.DataFrame(rows)


def run_dcdh_switcher_fallback(
    *,
    sample: pd.DataFrame,
    outcome: str,
    output_dir: Path,
    config_path: Path,
) -> tuple[bool, str]:
    estimates = _dcdh_switcher_estimates(sample, outcome)
    units = pd.Index(sorted(sample["municipality_id"].dropna().unique()))
    rng = np.random.default_rng(SEED)
    bootstrap_estimates = []
    for _ in range(DCDH_BOOTSTRAP_REPS):
        draw = rng.choice(units.to_numpy(), size=len(units), replace=True)
        counts = pd.Series(draw).value_counts().reindex(units).fillna(0.0)
        boot = _dcdh_switcher_estimates(sample, outcome, unit_weights=counts)
        bootstrap_estimates.append(boot.set_index("event_time")["estimate"])

    boot_frame = pd.concat(bootstrap_estimates, axis=1).T
    se = boot_frame.std(axis=0, ddof=1)
    estimates["std.error"] = estimates["event_time"].map(se)
    ref_mask = estimates["event_time"].eq(-2)
    estimates.loc[ref_mask, "std.error"] = np.nan
    estimates["conf.low"] = estimates["estimate"] - 1.96 * estimates["std.error"]
    estimates["conf.high"] = estimates["estimate"] + 1.96 * estimates["std.error"]
    estimates.loc[ref_mask, ["conf.low", "conf.high"]] = np.nan
    estimates["statistic"] = estimates["estimate"] / estimates["std.error"]
    estimates.loc[ref_mask, "statistic"] = np.nan
    estimates["p.value"] = estimates["statistic"].map(_normal_p_value)
    estimates["term"] = estimates["event_time"].map(lambda value: f"dcdh_event_{int(value)}")
    estimates = estimates[
        [
            "event_time",
            "term",
            "estimate",
            "std.error",
            "conf.low",
            "conf.high",
            "statistic",
            "p.value",
            "n_switchers",
            "n_comparisons",
        ]
    ]

    estimates.to_csv(output_dir / "event_study_estimates.csv", index=False)
    try:
        estimates.to_parquet(output_dir / "event_study_estimates.parquet", index=False)
    except Exception:
        pass

    shutil.copyfile(config_path, output_dir / "config_used.yml")
    summary = (
        "Estimator: de Chaisemartin-D'Haultfoeuille switcher DID fallback\n"
        f"Outcome: {outcome}\n"
        "Post-treatment point estimates use the same switcher-versus-stable-control logic as "
        "the archived DIDmultiplegt dynamic estimator for this staggered binary-treatment panel.\n"
        f"Standard errors are municipality-cluster bootstrap standard errors with {DCDH_BOOTSTRAP_REPS} replications.\n"
    )
    (output_dir / "model_summary.txt").write_text(summary, encoding="utf-8")
    metadata = {
        "estimator": "dcdh",
        "mode": "python_switcher_fallback",
        "outcome": outcome,
        "bootstrap_reps": DCDH_BOOTSTRAP_REPS,
        "nobs": int(len(sample)),
        "n_units": int(sample["municipality_id"].nunique()),
    }
    with (output_dir / "run_metadata.yml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(metadata, handle, sort_keys=False)
    with (output_dir / "results.json").open("w", encoding="utf-8") as handle:
        json.dump({"model_stats": metadata, "event_study": estimates.to_dict(orient="records")}, handle, indent=2)

    build_single_event_plot(
        estimates,
        output_dir=output_dir,
        color=OTHER_ESTIMATORS["dcdh"]["color"],
        show_line=False,
    )
    return True, summary.strip()


def build_single_event_plot(data: pd.DataFrame, *, output_dir: Path, color: str, show_line: bool) -> None:
    apply_matplotlib_paper_style()
    plt.rcParams["text.usetex"] = False
    fig, ax = plt.subplots(figsize=(8, 5))
    apply_boxed_axis_style(ax)
    ax.axhline(0, color="0.35", linewidth=1.1, zorder=3)
    ax.axvline(-2, color="0.50", linestyle="--", linewidth=0.7, zorder=3)
    ci_data = data[data[["conf.low", "conf.high"]].notna().all(axis=1)]
    if not ci_data.empty:
        ax.vlines(
            ci_data["event_time"],
            ci_data["conf.low"],
            ci_data["conf.high"],
            color=color,
            linewidth=CI_LINEWIDTH,
            zorder=4,
        )
    if show_line:
        ax.plot(data["event_time"], data["estimate"], color=color, linewidth=1.0, zorder=4)
    ax.scatter(data["event_time"], data["estimate"], s=POINT_SIZE, color=color, zorder=5)
    y_ticks, y_limits = y_axis_limits(data)
    ax.set_xlim(min(X_TICKS) - 0.55, max(X_TICKS) + 0.55)
    ax.set_ylim(y_limits)
    ax.set_xticks(X_TICKS)
    ax.set_yticks(y_ticks)
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax.set_xlabel("Distance to treatment")
    ax.set_ylabel("")
    fig.tight_layout()
    save_pdf_png(fig, output_dir / "event_study_plot")
    plt.close(fig)


def _ensure_reference_row(df: pd.DataFrame, estimator_key: str) -> pd.DataFrame:
    if "event_time" not in df.columns:
        return pd.DataFrame()
    out = df.copy()
    out["event_time"] = pd.to_numeric(out["event_time"], errors="coerce")
    for col in ["estimate", "std.error", "conf.low", "conf.high"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["event_time", "estimate"]).copy()

    if not out["event_time"].eq(-2).any():
        ref_idx = len(out)
        out.loc[ref_idx, :] = pd.NA
        out.loc[ref_idx, "event_time"] = -2
        out.loc[ref_idx, "estimate"] = 0.0
        if "estimator" in out.columns:
            out.loc[ref_idx, "estimator"] = estimator_key

    ref_mask = out["event_time"].eq(-2)
    out.loc[ref_mask, "estimate"] = 0.0
    for col in ["std.error", "conf.low", "conf.high"]:
        if col in out.columns:
            out.loc[ref_mask, col] = pd.NA

    out = out[out["event_time"].isin(X_TICKS)].sort_values("event_time")
    return out


def load_comparison_data(base_dir: Path) -> pd.DataFrame:
    frames = []
    for estimator_key, estimator in COMPARISON_ESTIMATORS.items():
        if estimator_key == "callaway_santanna":
            event_path = base_dir / "callaway_santanna" / "event_study_estimates.csv"
        else:
            event_path = base_dir / "other_estimators" / estimator_key / "event_study_estimates.csv"
        if not event_path.exists():
            continue
        event = _ensure_reference_row(pd.read_csv(event_path), estimator_key)
        if event.empty:
            continue
        event["estimator"] = estimator_key
        event["estimator_label"] = estimator["label"]
        event["color"] = estimator["color"]
        frames.append(event)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def y_axis_limits(data: pd.DataFrame) -> tuple[list[float], tuple[float, float]]:
    bounds = pd.concat([data["conf.low"], data["conf.high"], data["estimate"]], ignore_index=True)
    bounds = pd.to_numeric(bounds, errors="coerce").dropna()
    max_abs = max(MIN_ABS_Y, float(bounds.abs().max())) if len(bounds) else MIN_ABS_Y
    max_abs = math.ceil(max_abs / Y_STEP) * Y_STEP
    tick_count = int(round((2 * max_abs) / Y_STEP)) + 1
    ticks = [round(-max_abs + idx * Y_STEP, 2) for idx in range(tick_count)]
    return ticks, (-max_abs, max_abs)


def build_comparison_plot(base_dir: Path) -> None:
    data = load_comparison_data(base_dir)
    if data.empty:
        return

    output_dir = base_dir / "other_estimators"
    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / "estimator_comparison_data.csv"
    data.to_csv(data_path, index=False)

    plotter = ROOT / "src" / "analysis" / "plot_bvr_estimator_comparison.R"
    proc = subprocess.run(
        ["Rscript", str(plotter), str(data_path), str(output_dir)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Failed to render estimator comparison plot with the reg-did ggplot theme:\n"
            + (proc.stdout or "")
            + (proc.stderr or "")
        )
    return

    ordered_keys = [key for key in COMPARISON_ESTIMATORS if key in set(data["estimator"])]
    offsets = {
        key: (idx - (len(ordered_keys) - 1) / 2) * OFFSET_STEP
        for idx, key in enumerate(ordered_keys)
    }

    apply_matplotlib_paper_style()
    plt.rcParams["text.usetex"] = False
    fig, ax = plt.subplots(figsize=(8, 5))
    apply_boxed_axis_style(ax)
    ax.axhline(0, color="0.35", linewidth=1.1, zorder=3)
    ax.axvline(-2, color="0.50", linestyle="--", linewidth=0.7, zorder=3)

    for key in ordered_keys:
        estimator = COMPARISON_ESTIMATORS[key]
        frame = data[data["estimator"].eq(key)].copy()
        x = frame["event_time"] + offsets[key]
        has_ci = frame[["conf.low", "conf.high"]].notna().all(axis=1)
        ci_frame = frame[has_ci]
        if not ci_frame.empty:
            ci_x = ci_frame["event_time"] + offsets[key]
            ax.vlines(
                ci_x,
                ci_frame["conf.low"],
                ci_frame["conf.high"],
                color=estimator["color"],
                linewidth=CI_LINEWIDTH,
                zorder=4,
            )
        ax.scatter(
            x,
            frame["estimate"],
            s=POINT_SIZE,
            color=estimator["color"],
            label=estimator["label"],
            zorder=5,
        )

    y_ticks, y_limits = y_axis_limits(data)
    ax.set_xlim(min(X_TICKS) - 0.55, max(X_TICKS) + 0.55)
    ax.set_ylim(y_limits)
    ax.set_xticks(X_TICKS)
    ax.set_yticks(y_ticks)
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax.set_xlabel("Distance to treatment")
    ax.set_ylabel("")
    legend = ax.legend(
        frameon=True,
        ncol=2,
        loc="upper left",
        facecolor="white",
        edgecolor="0.75",
        framealpha=1.0,
        fancybox=False,
    )
    legend.set_zorder(20)
    fig.tight_layout()

    save_pdf_png(fig, output_dir / "estimator_comparison")
    plt.close(fig)


def main() -> None:
    panel = load_panel()
    statuses = []

    for outcome in OUTCOMES:
        for spec_key, spec in SPECS.items():
            sample = build_sample(
                panel,
                spec_key=spec_key,
                group_var=spec["group_var"],
                exclude_hybrid=spec["exclude_hybrid"],
            )
            base_dir = OUTPUT_ROOT / outcome / spec_key

            for stale_name in ["bjs", "dcdh", "sun_abraham", "twfe_dynamic"]:
                stale_dir = base_dir / stale_name
                if stale_dir.exists():
                    shutil.rmtree(stale_dir)
            for stale_file in [
                base_dir / "estimator_comparison.csv",
                base_dir / "estimator_comparison_data.csv",
                base_dir / "estimator_comparison.pdf",
                base_dir / "estimator_comparison.png",
            ]:
                if stale_file.exists():
                    stale_file.unlink()

            callaway_dir = base_dir / "callaway_santanna"
            if callaway_dir.exists():
                shutil.rmtree(callaway_dir)
            callaway_dir.mkdir(parents=True, exist_ok=True)
            sample_path = callaway_dir / "analysis_sample.parquet"
            sample.to_parquet(sample_path, index=False)
            sample_summary = build_sample_summary(sample, panel, spec_key)
            sample_summary.to_csv(callaway_dir / "sample_summary.csv", index=False)
            config_path = write_config(
                outcome=outcome,
                estimator_key="callaway_santanna",
                estimator=CALLAWAY_ESTIMATOR,
                spec_key=spec_key,
                spec_label=spec["label"],
                sample_path=sample_path,
                output_dir=callaway_dir,
                show_line=True,
            )
            success, log = run_estimator(config_path)
            status = {
                "outcome": outcome,
                "spec": spec_key,
                "estimator": "callaway_santanna",
                "success": success,
                "output_dir": str(callaway_dir.relative_to(ROOT)),
                "config": str(config_path.relative_to(ROOT)),
                "log": log.strip(),
            }
            statuses.append(status)
            pd.DataFrame([status]).to_csv(callaway_dir / "run_status.csv", index=False)
            print(f"{outcome} / {spec_key} / callaway_santanna: {'OK' if success else 'FAILED'}")

            other_dir = base_dir / "other_estimators"
            if other_dir.exists():
                shutil.rmtree(other_dir)
            other_dir.mkdir(parents=True, exist_ok=True)

            for estimator_key, estimator in OTHER_ESTIMATORS.items():
                output_dir = other_dir / estimator_key
                output_dir.mkdir(parents=True, exist_ok=True)
                sample_path = output_dir / "analysis_sample.parquet"
                sample.to_parquet(sample_path, index=False)

                sample_summary.to_csv(output_dir / "sample_summary.csv", index=False)

                config_path = write_config(
                    outcome=outcome,
                    estimator_key=estimator_key,
                    estimator=estimator,
                    spec_key=spec_key,
                    spec_label=spec["label"],
                    sample_path=sample_path,
                    output_dir=output_dir,
                    show_line=False,
                )
                if estimator_key == "dcdh":
                    success, log = run_dcdh_switcher_fallback(
                        sample=sample,
                        outcome=outcome,
                        output_dir=output_dir,
                        config_path=config_path,
                    )
                else:
                    success, log = run_estimator(config_path)

                status = {
                    "outcome": outcome,
                    "spec": spec_key,
                    "estimator": estimator_key,
                    "success": success,
                    "output_dir": str(output_dir.relative_to(ROOT)),
                    "config": str(config_path.relative_to(ROOT)),
                    "log": log.strip(),
                }
                statuses.append(status)
                pd.DataFrame([status]).to_csv(output_dir / "run_status.csv", index=False)
                print(f"{outcome} / {spec_key} / {estimator_key}: {'OK' if success else 'FAILED'}")

            build_comparison_plot(base_dir)

    status_frame = pd.DataFrame(statuses)
    status_frame.to_csv(OUTPUT_ROOT / "run_status.csv", index=False)
    print(f"\nWrote {OUTPUT_ROOT.relative_to(ROOT) / 'run_status.csv'}")


if __name__ == "__main__":
    main()
