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
PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018_bvr_status_updated.parquet"
RUNNER = ROOT / ".agents" / "skills" / "did-estimators" / "scripts" / "run_estimator.R"

SAMPLE_PATH = ROOT / "data" / "interim" / "tse" / "electorate_size_cs_nonhybrid_sample.csv"
OUTPUT_DIR = ROOT / "resources" / "did" / "callaway_santanna_nonhybrid" / "log_num_voters"
CONFIG_PATH = OUTPUT_DIR / "config.yml"
SUMMARY_PATH = OUTPUT_DIR / "sample_summary.csv"
IMAGE_DIR = ROOT / "resources" / "images" / "regressions" / "callaway_santanna_nonhybrid" / "log_num_voters"
FIGURE_BASE = IMAGE_DIR / "event_study_plot"

OUTCOME = "log_num_voters"
NEVER_TREATED_VALUE = 9999
LEAD = 8
LAG = 8
SEED = 20260427


def build_sample() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_parquet(PANEL_PATH)
    df["municipality_id"] = df["municipality_id"].astype(str).str.zfill(7)

    ever_hybrid = df.groupby("municipality_id")["hybrid"].max()
    hybrid_ids = set(ever_hybrid.loc[ever_hybrid.eq(1)].index)
    sample = df.loc[~df["municipality_id"].isin(hybrid_ids)].copy()

    sample["year_treated_cs"] = sample["year_first_strict_bvr"].astype(int)
    sample["dist_treatment_cs"] = sample["dist_strict_bvr"].astype(int)

    summary = pd.DataFrame(
        [
            {"metric": "rows_full_sample", "value": int(len(df))},
            {"metric": "rows_nonhybrid_sample", "value": int(len(sample))},
            {"metric": "municipalities_full_sample", "value": int(df["municipality_id"].nunique())},
            {"metric": "municipalities_nonhybrid_sample", "value": int(sample["municipality_id"].nunique())},
            {"metric": "hybrid_municipalities_excluded", "value": int(len(hybrid_ids))},
            {
                "metric": "treated_municipalities_nonhybrid_sample",
                "value": int(sample.loc[sample["year_treated_cs"].ne(NEVER_TREATED_VALUE), "municipality_id"].nunique()),
            },
            {
                "metric": "never_treated_municipalities_nonhybrid_sample",
                "value": int(sample.loc[sample["year_treated_cs"].eq(NEVER_TREATED_VALUE), "municipality_id"].nunique()),
            },
        ]
    )
    return sample.sort_values(["municipality_id", "year_election"]).reset_index(drop=True), summary


def write_config() -> None:
    config = {
        "estimator": "callaway_santanna",
        "data_path": str(SAMPLE_PATH.relative_to(ROOT)),
        "file_format": "csv",
        "outcome": OUTCOME,
        "unit_id": "municipality_id",
        "time_id": "year_election",
        "group_id": "year_treated_cs",
        "treatment_var": None,
        "controls": [],
        "cluster_var": "municipality_id",
        "weights_var": None,
        "lead": LEAD,
        "lag": LAG,
        "anticipation": 0,
        "balanced_panel_required": False,
        "never_treated_value": NEVER_TREATED_VALUE,
        "control_group": "nevertreated",
        "seed": SEED,
        "omit_plot_title": True,
        "output_dir": str(OUTPUT_DIR),
        "notes": (
            "Figure 3 electorate-size rerun using Callaway-Sant'Anna with never-treated controls, "
            "municipality-clustered standard errors, and municipalities ever flagged as hybrid excluded. "
            "Outcome is log registered voters; treatment cohort is first strict BVR year."
        ),
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)


def run_estimator() -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["Rscript", str(RUNNER.relative_to(ROOT)), str(CONFIG_PATH.relative_to(ROOT))],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return True, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.CalledProcessError as exc:
        return False, (exc.stdout or "") + (exc.stderr or "")


def build_custom_plot() -> None:
    event_path = OUTPUT_DIR / "event_study_estimates.csv"
    event_study = pd.read_csv(event_path)
    event_study = event_study.dropna(subset=["event_time", "estimate", "conf.low", "conf.high"]).copy()
    event_study = event_study.loc[event_study["event_time"].between(-LEAD, LAG)].copy()
    event_study = event_study.sort_values("event_time")

    apply_matplotlib_paper_style()
    fig, ax = plt.subplots(figsize=(8, 5))
    color = "#2C5A8A"

    ax.set_axisbelow(True)
    ax.set_facecolor("white")
    ax.grid(True, which="major", axis="both", color="#D9D9D9", linewidth=0.8)
    ax.axhline(0, color="0.35", linewidth=0.9, zorder=3)
    ax.axvline(-2, color="0.5", linestyle=":", linewidth=1.1, zorder=3)
    ax.vlines(
        event_study["event_time"],
        event_study["conf.low"],
        event_study["conf.high"],
        color=color,
        linewidth=1.1,
        zorder=4,
    )
    ax.plot(event_study["event_time"], event_study["estimate"], color=color, linewidth=1.1, zorder=4)
    ax.scatter(event_study["event_time"], event_study["estimate"], color=color, s=30, zorder=5)

    max_abs = max(
        abs(event_study["conf.low"]).max(),
        abs(event_study["conf.high"]).max(),
        abs(event_study["estimate"]).max(),
    )
    max_abs = max(0.15, math.ceil(float(max_abs) / 0.05) * 0.05)
    y_ticks = [round(-max_abs + i * 0.05, 2) for i in range(int(round((2 * max_abs) / 0.05)) + 1)]
    ax.set_xlim(-LEAD - 0.4, LAG + 0.4)
    ax.set_ylim(-max_abs, max_abs)
    ax.set_xticks(list(range(-LEAD, LAG + 1, 2)))
    ax.set_yticks(y_ticks)
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
    ax.set_xlabel("Distance to treatment")
    ax.set_ylabel("")
    ax.set_title("")
    for side in ["top", "right", "bottom", "left"]:
        ax.spines[side].set_visible(True)
        ax.spines[side].set_linewidth(0.6)
        ax.spines[side].set_color("black")
    fig.tight_layout()

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    save_pdf_png(fig, FIGURE_BASE)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)

    sample, summary = build_sample()
    sample.to_csv(SAMPLE_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)
    write_config()
    success, log = run_estimator()

    status = pd.DataFrame(
        [
            {
                "estimator": "callaway_santanna",
                "success": success,
                "config": str(CONFIG_PATH.relative_to(ROOT)),
                "output_dir": str(OUTPUT_DIR.relative_to(ROOT)),
                "log": log.strip(),
            }
        ]
    )
    status.to_csv(OUTPUT_DIR / "run_status.csv", index=False)
    if not success:
        raise RuntimeError(log)

    build_custom_plot()

    event_study = pd.read_csv(OUTPUT_DIR / "event_study_estimates.csv")
    simple_att = pd.read_csv(OUTPUT_DIR / "aggregate_simple.csv")

    print(f"Wrote {SAMPLE_PATH.relative_to(ROOT)}")
    print(f"Wrote {SUMMARY_PATH.relative_to(ROOT)}")
    print(f"Wrote {CONFIG_PATH.relative_to(ROOT)}")
    print(f"Wrote {(OUTPUT_DIR / 'event_study_estimates.csv').relative_to(ROOT)}")
    print(f"Wrote {FIGURE_BASE.with_suffix('.png').relative_to(ROOT)}")
    print(f"Wrote {FIGURE_BASE.with_suffix('.pdf').relative_to(ROOT)}")
    print("\nSample summary:")
    print(summary.to_string(index=False))
    print("\nEvent study:")
    print(event_study.to_string(index=False))
    print("\nSimple ATT:")
    print(simple_att.to_string(index=False))


if __name__ == "__main__":
    main()
