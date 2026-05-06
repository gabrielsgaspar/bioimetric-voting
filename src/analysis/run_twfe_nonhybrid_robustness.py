from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / ".agents" / "skills" / "did-estimators" / "scripts" / "run_estimator.R"
INPUT_DATA = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018.csv"
FILTERED_DATA = ROOT / "data" / "interim" / "tse" / "tse_clean_panel_2000_2018_excl_hybrid_municipalities.csv"
OUTPUT_DIR = ROOT / "resources" / "did" / "twfe_dynamic_excl_hybrid"
CONFIG_DIR = OUTPUT_DIR / "configs"

OUTCOMES = [
    "log_num_voters",
    "pct_voters_low_ed",
    "pct_voters_high_ed",
]


def build_filtered_data() -> pd.DataFrame:
    df = pd.read_csv(INPUT_DATA)
    hybrid_ids = sorted(df.loc[df["hybrid"] == 1, "municipality_id"].astype(str).unique())
    filtered = df.loc[~df["municipality_id"].astype(str).isin(hybrid_ids)].copy()

    FILTERED_DATA.parent.mkdir(parents=True, exist_ok=True)
    filtered.to_csv(FILTERED_DATA, index=False)

    summary = pd.DataFrame(
        [
            {"metric": "rows_full_sample", "value": int(len(df))},
            {"metric": "rows_filtered_sample", "value": int(len(filtered))},
            {"metric": "municipalities_full_sample", "value": int(df["municipality_id"].nunique())},
            {"metric": "municipalities_filtered_sample", "value": int(filtered["municipality_id"].nunique())},
            {"metric": "hybrid_municipalities_excluded", "value": int(len(hybrid_ids))},
            {
                "metric": "treated_municipalities_filtered_sample",
                "value": int(filtered.loc[filtered["year_treated"] != 9999, "municipality_id"].nunique()),
            },
            {
                "metric": "never_treated_municipalities_filtered_sample",
                "value": int(filtered.loc[filtered["year_treated"] == 9999, "municipality_id"].nunique()),
            },
        ]
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUTPUT_DIR / "sample_summary.csv", index=False)
    return filtered


def write_config(outcome: str, outdir: Path) -> Path:
    config = {
        "data_path": str(FILTERED_DATA),
        "file_format": "csv",
        "estimator": "twfe_dynamic",
        "outcome": outcome,
        "unit_id": "municipality_id",
        "time_id": "year_election",
        "group_id": "year_treated",
        "cluster_var": ["municipality_id", "year_election"],
        "event_time_var": "dist_treatment",
        "event_time_never_value": -9999,
        "lead": 8,
        "lag": 8,
        "reference_event_time": -2,
        "anticipation": 0,
        "control_group": "nevertreated",
        "balanced_panel_required": False,
        "never_treated_value": 9999,
        "plot_title": None,
        "omit_plot_title": True,
        "output_dir": str(outdir),
        "notes": (
            "Dynamic TWFE robustness run excluding municipalities ever flagged as "
            "hybrid in the official 2018 status source; never-treated municipalities "
            "remain in the sample as controls."
        ),
    }

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = CONFIG_DIR / f"{outcome}.yml"
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config, fh, sort_keys=False)
    return path


def run_estimator(config_path: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["Rscript", str(RUNNER), str(config_path)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return True, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.CalledProcessError as exc:
        return False, (exc.stdout or "") + (exc.stderr or "")


def main() -> None:
    build_filtered_data()

    records = []
    for outcome in OUTCOMES:
        outdir = OUTPUT_DIR / outcome
        config_path = write_config(outcome, outdir)
        success, log = run_estimator(config_path)
        records.append(
            {
                "outcome": outcome,
                "success": success,
                "config_path": str(config_path),
                "output_dir": str(outdir),
                "log": log.strip(),
            }
        )

    pd.DataFrame(records).to_csv(OUTPUT_DIR / "run_status.csv", index=False)


if __name__ == "__main__":
    main()
