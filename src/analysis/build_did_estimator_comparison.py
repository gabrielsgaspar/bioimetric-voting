from __future__ import annotations

import math
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
import pandas as pd
import yaml

try:
    from plot_style import apply_matplotlib_paper_style, save_pdf_png
except ImportError:  # pragma: no cover
    from src.analysis.plot_style import apply_matplotlib_paper_style, save_pdf_png


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / ".agents" / "skills" / "did-estimators" / "scripts" / "run_estimator.R"
BASE_OUTPUT_DIR = ROOT / "resources" / "did" / "estimator_comparison"
PLOT_OUTPUT_DIR = ROOT / "resources" / "images" / "regressions" / "estimator_comparison"
CONFIG_DIR = BASE_OUTPUT_DIR / "configs"
X_TICKS = list(range(-8, 9, 2))
Y_STEP = 0.05
MIN_ABS_Y = 0.15
OFFSET_STEP = 0.16
GRID_COLOR = "#D9D9D9"
FIG_WIDTH = 8
FIG_HEIGHT = 5
ERRORBAR_LINEWIDTH = 1.1
POINT_MARKERSIZE = 6.8

OUTCOMES = [
    "log_num_voters",
    "pct_voters_low_ed",
    "pct_voters_high_ed",
]

ESTIMATORS = [
    {
        "key": "twfe_dynamic",
        "label": "Dynamic TWFE",
        "color": "#2C5A8A",
        "config": {
            "estimator": "twfe_dynamic",
            "event_time_var": "dist_treatment",
            "event_time_never_value": -9999,
            "reference_event_time": -2,
        },
    },
    {
        "key": "callaway_santanna",
        "label": "Callaway-Sant'Anna",
        "color": "#2F7D32",
        "config": {
            "estimator": "callaway_santanna",
            "control_group": "nevertreated",
        },
    },
    {
        "key": "bjs",
        "label": "BJS",
        "color": "#8B3FB0",
        "config": {
            "estimator": "bjs",
            "event_time_step": 2,
            "pretrends": [2, 4, 6, 8],
        },
    },
    {
        "key": "sun_abraham",
        "label": "Sun-Abraham",
        "color": "#B23A48",
        "config": {
            "estimator": "sun_abraham",
            "reference_event_time": -2,
        },
    },
]


def _base_config(outcome: str, output_dir: Path) -> dict:
    return {
        "data_path": "data/clean/tse/tse_clean_panel_2000_2018.csv",
        "file_format": "csv",
        "outcome": outcome,
        "unit_id": "municipality_id",
        "time_id": "year_election",
        "group_id": "year_treated",
        "treatment_var": None,
        "controls": [],
        "cluster_var": "municipality_id",
        "weights_var": None,
        "lead": 8,
        "lag": 8,
        "anticipation": 0,
        "balanced_panel_required": False,
        "never_treated_value": 9999,
        "output_dir": str(output_dir),
        "notes": (
            "Municipality-clustered DID estimator comparison run for Brazil BVR "
            f"outcome `{outcome}`."
        ),
    }


def _write_config(config: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config, fh, sort_keys=False)


def _run_estimator(config_path: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["Rscript", str(RUNNER), str(config_path)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return True, proc.stdout + proc.stderr
    except subprocess.CalledProcessError as exc:
        return False, (exc.stdout or "") + (exc.stderr or "")


def _load_event_study(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "event_time" not in df.columns:
        raise ValueError(f"Missing `event_time` in {path}")
    df["event_time"] = pd.to_numeric(df["event_time"], errors="coerce")
    df["estimate"] = pd.to_numeric(df["estimate"], errors="coerce")
    df["conf.low"] = pd.to_numeric(df["conf.low"], errors="coerce")
    df["conf.high"] = pd.to_numeric(df["conf.high"], errors="coerce")
    df = df.dropna(subset=["event_time", "estimate", "conf.low", "conf.high"]).copy()
    df = df[df["event_time"].isin(X_TICKS)].sort_values("event_time")
    return df


def _y_axis_bounds(dfs: list[pd.DataFrame]) -> tuple[list[float], tuple[float, float]]:
    bounds = []
    for df in dfs:
        bounds.extend(df["conf.low"].tolist())
        bounds.extend(df["conf.high"].tolist())
    max_abs = max(abs(value) for value in bounds)
    max_abs = max(MIN_ABS_Y, math.ceil(max_abs / Y_STEP) * Y_STEP)
    y_ticks = [round(-max_abs + i * Y_STEP, 2) for i in range(int(round((2 * max_abs) / Y_STEP)) + 1)]
    return y_ticks, (-max_abs, max_abs)


def _plot_outcome(outcome: str, successful_runs: list[dict]) -> None:
    apply_matplotlib_paper_style()
    plot_dir = PLOT_OUTPUT_DIR / outcome
    plot_dir.mkdir(parents=True, exist_ok=True)

    data_frames = []
    n_runs = len(successful_runs)
    offsets = [
        (idx - (n_runs - 1) / 2) * OFFSET_STEP
        for idx in range(n_runs)
    ]
    for idx, run in enumerate(successful_runs):
        df = _load_event_study(run["output_dir"] / "event_study_estimates.csv")
        df["estimator"] = run["label"]
        df["color"] = run["color"]
        df["x_offset"] = offsets[idx]
        data_frames.append(df)

    y_ticks, y_limits = _y_axis_bounds(data_frames)

    fig, ax = plt.subplots(figsize=(FIG_WIDTH, FIG_HEIGHT))
    ax.set_axisbelow(True)
    ax.set_facecolor("white")
    ax.grid(True, which="major", axis="both", color=GRID_COLOR, linewidth=0.8)
    ax.axhline(0, color="0.35", linestyle="-", linewidth=0.9, zorder=3)

    for df, run in zip(data_frames, successful_runs):
        x_values = df["event_time"] + df["x_offset"]
        ax.errorbar(
            x_values,
            df["estimate"],
            yerr=[df["estimate"] - df["conf.low"], df["conf.high"] - df["estimate"]],
            fmt="o",
            linestyle="none",
            color=run["color"],
            ecolor=run["color"],
            elinewidth=ERRORBAR_LINEWIDTH,
            markersize=POINT_MARKERSIZE,
            markerfacecolor=run["color"],
            markeredgecolor=run["color"],
            markeredgewidth=0,
            capsize=0,
            label=run["label"],
            zorder=4,
        )

    ax.set_xlim(min(X_TICKS) - 0.45, max(X_TICKS) + 0.45)
    ax.set_xticks(X_TICKS)
    ax.set_ylim(y_limits)
    ax.set_yticks(y_ticks)
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax.set_xlabel("Distance to treatment")
    ax.set_ylabel("")
    ax.tick_params(axis="both", labelsize=11)
    ax.legend(frameon=False, ncol=min(3, n_runs), loc="upper left")

    for side in ["top", "right", "bottom", "left"]:
        ax.spines[side].set_visible(True)
        ax.spines[side].set_linewidth(0.6)
        ax.spines[side].set_color("black")

    fig.tight_layout()
    save_pdf_png(fig, plot_dir / "estimator_comparison")


def main() -> None:
    BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []

    for outcome in OUTCOMES:
        successful_runs = []
        for estimator in ESTIMATORS:
            output_dir = BASE_OUTPUT_DIR / outcome / estimator["key"]
            config_path = CONFIG_DIR / f"{outcome}_{estimator['key']}.yml"
            config = _base_config(outcome, output_dir)
            config.update(estimator["config"])
            _write_config(config, config_path)

            success, log = _run_estimator(config_path)
            records.append(
                {
                    "outcome": outcome,
                    "estimator": estimator["key"],
                    "success": success,
                    "log": log.strip(),
                }
            )

            event_path = output_dir / "event_study_estimates.csv"
            if success and event_path.exists():
                successful_runs.append(
                    {
                        "key": estimator["key"],
                        "label": estimator["label"],
                        "color": estimator["color"],
                        "output_dir": output_dir,
                    }
                )

        if successful_runs:
            _plot_outcome(outcome, successful_runs)

    pd.DataFrame(records).to_csv(BASE_OUTPUT_DIR / "run_status.csv", index=False)


if __name__ == "__main__":
    main()
