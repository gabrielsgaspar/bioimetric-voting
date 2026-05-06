from __future__ import annotations

import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

try:
    from plot_style import apply_matplotlib_paper_style, save_pdf_png
except ImportError:  # pragma: no cover
    from src.analysis.plot_style import apply_matplotlib_paper_style, save_pdf_png


ROOT = Path(__file__).resolve().parents[2]
BVR_PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018_bvr_status_updated.parquet"
MAYOR_IDEOLOGY_PATH = ROOT / "data" / "clean" / "tse" / "tse_mayor_ideology_votes.parquet"
RUNNER = ROOT / "scripts" / "run_did_estimator.sh"

OUTPUT_DIR = ROOT / "resources" / "did" / "mayor_ideology" / "pct_mayor_L_any_bvr_2yr_anchor_m2"
CONFIG_DIR = OUTPUT_DIR / "configs"
SAMPLE_PATH = ROOT / "data" / "interim" / "tse" / "mayor_left_bvr_event_time_did_2yr_anchor_m2_panel.csv"
STATUS_PATH = OUTPUT_DIR / "run_status.csv"
IMAGE_DIR = ROOT / "resources" / "images" / "regressions" / "tse_mayor_ideology_bvr_event_time_did"
CS_FIGURE_BASE = IMAGE_DIR / "mayor_left_bvr_event_time_2yr_anchor_m2_callaway_santanna"
SA_FIGURE_BASE = IMAGE_DIR / "mayor_left_bvr_event_time_2yr_anchor_m2_sun_abraham"
TWFE_FIGURE_BASE = IMAGE_DIR / "mayor_left_bvr_event_time_2yr_anchor_m2_twfe"

OUTCOME = "pct_mayor_L"
MAYOR_ELECTION_YEARS = [2000, 2004, 2008, 2012, 2016, 2020]
NEVER_TREATED_VALUE = 9999
REFERENCE_EVENT_TIME = -2
LEAD = 18
LAG = 12
SEED = 20260427


def first_mayor_election_at_or_after(year: int) -> int | None:
    for election_year in MAYOR_ELECTION_YEARS:
        if election_year >= year:
            return election_year
    return None


def build_status() -> pd.DataFrame:
    bvr = pd.read_parquet(BVR_PANEL_PATH)
    bvr_latest = bvr.loc[bvr["year_election"].eq(bvr["year_election"].max())].copy()
    bvr_latest["municipality_id"] = bvr_latest["municipality_id"].astype(str).str.zfill(7)

    status = bvr_latest[["municipality_id", "year_first_any_bvr"]].drop_duplicates("municipality_id").copy()
    status["year_first_any_bvr"] = status["year_first_any_bvr"].astype(int)
    status["ever_bvr"] = status["year_first_any_bvr"].ne(NEVER_TREATED_VALUE).astype(int)
    status["year_first_bvr_mayor_election"] = [
        first_mayor_election_at_or_after(year) if year != NEVER_TREATED_VALUE else NEVER_TREATED_VALUE
        for year in status["year_first_any_bvr"]
    ]
    status = status.dropna(subset=["year_first_bvr_mayor_election"]).copy()
    status["year_first_bvr_mayor_election"] = status["year_first_bvr_mayor_election"].astype(int)
    return status


def build_sample() -> pd.DataFrame:
    mayor = pd.read_parquet(MAYOR_IDEOLOGY_PATH)
    mayor = mayor.loc[mayor["year"].isin(MAYOR_ELECTION_YEARS)].copy()
    mayor["municipality_id"] = mayor["municipality_id"].astype(str).str.zfill(7)

    sample = mayor.merge(build_status(), on="municipality_id", how="inner")
    sample = sample.dropna(subset=[OUTCOME, "year", "municipality_id", "year_first_any_bvr"]).copy()
    sample["year"] = sample["year"].astype(int)
    sample["state"] = sample["state"].astype(str)
    sample["municipality_id"] = sample["municipality_id"].astype(str)

    treated = sample["year_first_any_bvr"].ne(NEVER_TREATED_VALUE)
    sample["dist_to_bvr_year"] = NEVER_TREATED_VALUE
    sample.loc[treated, "dist_to_bvr_year"] = sample.loc[treated, "year"] - sample.loc[treated, "year_first_any_bvr"]
    sample["dist_to_first_bvr_mayor_election"] = NEVER_TREATED_VALUE
    sample.loc[treated, "dist_to_first_bvr_mayor_election"] = (
        sample.loc[treated, "year"] - sample.loc[treated, "year_first_bvr_mayor_election"]
    )
    sample["treated"] = (
        sample["year"].ge(sample["year_first_any_bvr"])
        & sample["year_first_any_bvr"].ne(NEVER_TREATED_VALUE)
    ).astype(int)
    sample["group"] = sample["ever_bvr"].map({1: "Ever BVR", 0: "Never BVR"})

    cols = [
        "year",
        "state",
        "municipality_id",
        OUTCOME,
        "pct_mayor_R",
        "pct_mayor_C",
        "pct_mayor_IDK",
        "ever_bvr",
        "treated",
        "year_first_any_bvr",
        "year_first_bvr_mayor_election",
        "dist_to_bvr_year",
        "dist_to_first_bvr_mayor_election",
        "group",
    ]
    return sample[cols].sort_values(["municipality_id", "year"]).reset_index(drop=True)


def write_config(estimator: str, output_dir: Path) -> Path:
    config = {
        "estimator": estimator,
        "data_path": str(SAMPLE_PATH.relative_to(ROOT)),
        "file_format": "csv",
        "outcome": OUTCOME,
        "unit_id": "municipality_id",
        "time_id": "year",
        "group_id": "year_first_any_bvr",
        "treatment_var": None,
        "controls": [],
        "cluster_var": ["municipality_id"],
        "weights_var": None,
        "lead": LEAD,
        "lag": LAG,
        "anticipation": 0,
        "balanced_panel_required": False,
        "never_treated_value": NEVER_TREATED_VALUE,
        "reference_event_time": REFERENCE_EVENT_TIME,
        "control_group": "nevertreated",
        "omit_plot_title": True,
        "seed": SEED,
        "output_dir": str(output_dir),
        "notes": (
            "Mayor-left vote share event-time DID. Treatment is first strict-or-hybrid BVR exposure. "
            "Event time is measured in calendar years from the first BVR year, producing a 2-year grid "
            "because BVR rollout years and municipal election years are both even years."
        ),
    }
    if estimator == "twfe_dynamic":
        config["event_time_var"] = "dist_to_bvr_year"
        config["event_time_never_value"] = NEVER_TREATED_VALUE

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config_path = CONFIG_DIR / f"{estimator}.yml"
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
    return config_path


def run_config(config_path: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["bash", str(RUNNER.relative_to(ROOT)), str(config_path.relative_to(ROOT))],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return True, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.CalledProcessError as exc:
        return False, (exc.stdout or "") + (exc.stderr or "")


def build_custom_plot(estimator_dir: Path, figure_base: Path, title: str) -> None:
    estimates_path = estimator_dir / "event_study_estimates.csv"
    event_study = pd.read_csv(estimates_path)
    event_study = event_study.dropna(subset=["event_time", "estimate"]).copy()
    event_study["event_time"] = event_study["event_time"].astype(int)

    ref = pd.DataFrame(
        [
            {
                "event_time": REFERENCE_EVENT_TIME,
                "estimate": 0.0,
                "std.error": float("nan"),
                "conf.low": float("nan"),
                "conf.high": float("nan"),
            }
        ]
    )
    if REFERENCE_EVENT_TIME not in set(event_study["event_time"]):
        event_study = pd.concat([event_study, ref], ignore_index=True, sort=False)
    event_study = event_study.loc[
        event_study["event_time"].between(-LEAD, LAG)
    ].sort_values("event_time")

    ci_df = event_study.dropna(subset=["conf.low", "conf.high"]).copy()

    apply_matplotlib_paper_style()
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    color = "#2C5A8A"
    ax.axhline(0, color="0.35", linewidth=0.9)
    ax.axvline(REFERENCE_EVENT_TIME, color="0.55", linestyle=":", linewidth=1.1)
    ax.vlines(
        ci_df["event_time"],
        ci_df["conf.low"].astype(float),
        ci_df["conf.high"].astype(float),
        color=color,
        linewidth=1.1,
    )
    ax.plot(event_study["event_time"], event_study["estimate"], color=color, linewidth=1.8)
    ax.scatter(event_study["event_time"], event_study["estimate"], color=color, s=28, zorder=3)
    ax.scatter([REFERENCE_EVENT_TIME], [0], color="black", s=28, zorder=4)

    max_abs = max(
        abs(ci_df["conf.low"].astype(float)).max(),
        abs(ci_df["conf.high"].astype(float)).max(),
        abs(event_study["estimate"].astype(float)).max(),
    )
    max_abs = max(0.08, float(max_abs) * 1.15)
    ax.set_ylim(-max_abs, max_abs)
    ax.set_xticks(list(range(-LEAD, LAG + 1, 2)))
    ax.set_xlabel("Years from first BVR treatment")
    ax.set_ylabel("Effect on share of mayoral votes for left parties")
    ax.set_title(title)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()

    figure_base.parent.mkdir(parents=True, exist_ok=True)
    save_pdf_png(fig, figure_base, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    sample = build_sample()
    sample.to_csv(SAMPLE_PATH, index=False)

    runs = []
    estimator_specs = {
        "callaway_santanna": OUTPUT_DIR / "callaway_santanna",
        "sun_abraham": OUTPUT_DIR / "sun_abraham",
        "twfe_dynamic": OUTPUT_DIR / "twfe_dynamic",
    }
    for estimator, output_dir in estimator_specs.items():
        config_path = write_config(estimator, output_dir)
        success, log = run_config(config_path)
        runs.append(
            {
                "estimator": estimator,
                "success": success,
                "config": str(config_path.relative_to(ROOT)),
                "output_dir": str(output_dir.relative_to(ROOT)),
                "log": log.strip(),
            }
        )
        if not success:
            break

    run_status = pd.DataFrame(runs)
    run_status.to_csv(STATUS_PATH, index=False)

    if run_status.loc[run_status["estimator"].eq("callaway_santanna"), "success"].any():
        build_custom_plot(
            estimator_specs["callaway_santanna"],
            CS_FIGURE_BASE,
            "Callaway-Sant'Anna dynamic DiD",
        )
    if run_status.loc[run_status["estimator"].eq("sun_abraham"), "success"].any():
        build_custom_plot(
            estimator_specs["sun_abraham"],
            SA_FIGURE_BASE,
            "Sun-Abraham event study",
        )
    if run_status.loc[run_status["estimator"].eq("twfe_dynamic"), "success"].any():
        build_custom_plot(
            estimator_specs["twfe_dynamic"],
            TWFE_FIGURE_BASE,
            "Dynamic TWFE event study",
        )

    diagnostics = (
        sample[["municipality_id", "ever_bvr", "year_first_any_bvr", "year_first_bvr_mayor_election"]]
        .drop_duplicates("municipality_id")
        .groupby(["ever_bvr", "year_first_any_bvr", "year_first_bvr_mayor_election"], as_index=False)
        .agg(n_municipalities=("municipality_id", "nunique"))
        .sort_values(["ever_bvr", "year_first_any_bvr", "year_first_bvr_mayor_election"])
    )
    diagnostics_path = OUTPUT_DIR / "treatment_timing_diagnostics.csv"
    diagnostics.to_csv(diagnostics_path, index=False)
    event_support = (
        sample.loc[sample["ever_bvr"].eq(1)]
        .groupby("dist_to_bvr_year", as_index=False)
        .agg(n_treated_municipalities=("municipality_id", "nunique"))
        .sort_values("dist_to_bvr_year")
    )
    event_support_path = OUTPUT_DIR / "event_time_support.csv"
    event_support.to_csv(event_support_path, index=False)

    print(f"Wrote {SAMPLE_PATH.relative_to(ROOT)}")
    print(f"Wrote {STATUS_PATH.relative_to(ROOT)}")
    print(f"Wrote {diagnostics_path.relative_to(ROOT)}")
    print(f"Wrote {event_support_path.relative_to(ROOT)}")
    print(f"Wrote {CS_FIGURE_BASE.with_suffix('.png').relative_to(ROOT)}")
    print(f"Wrote {SA_FIGURE_BASE.with_suffix('.png').relative_to(ROOT)}")
    print(f"Wrote {TWFE_FIGURE_BASE.with_suffix('.png').relative_to(ROOT)}")
    print("\nRun status:")
    print(run_status[["estimator", "success", "output_dir"]].to_string(index=False))
    print("\nTreatment timing diagnostics:")
    print(diagnostics.to_string(index=False))
    print("\nEvent-time support:")
    print(event_support.to_string(index=False))

    cs_event = estimator_specs["callaway_santanna"] / "event_study_estimates.csv"
    if cs_event.exists():
        print("\nCallaway-Sant'Anna event study:")
        print(pd.read_csv(cs_event).to_string(index=False))


if __name__ == "__main__":
    main()
