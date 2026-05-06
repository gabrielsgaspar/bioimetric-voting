from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "clean" / "downstream" / "downstream_outcomes_panel.parquet"
RUNNER = ROOT / "scripts" / "run_did_estimator.sh"
BASE_OUTPUT_DIR = ROOT / "resources" / "did" / "downstream_outcomes"
CONFIG_DIR = BASE_OUTPUT_DIR / "configs"

OUTCOME_SPECS = [
    ("turnout", "turnout"),
    ("blank_null_rate", "blank_null_rate"),
    ("PT_vote_share_president", "PT_vote_share_president"),
    ("PSDB_vote_share_president", "PSDB_vote_share_president"),
    ("effective_number_of_candidates_mayor", "effective_number_of_candidates_mayor"),
    ("margin_of_victory_mayor", "margin_of_victory_mayor"),
    ("incumbent_mayor_reelection", "incumbent_mayor_reelection"),
    ("health_spending_per_capita", "log_health_spending_per_capita"),
    ("education_spending_per_capita", "log_education_spending_per_capita"),
    ("social_assistance_spending_per_capita", "log_social_assistance_spending_per_capita"),
    ("total_discretionary_spending_per_capita", "log_total_discretionary_spending_per_capita"),
    ("IPTU_collection_per_capita", "log_IPTU_collection_per_capita"),
    ("FPM_transfers_per_capita", "log_FPM_transfers_per_capita"),
    ("infant_mortality_rate", "infant_mortality_rate"),
    ("pre_natal_7plus_visits_share", "pre_natal_7plus_visits_share"),
    ("bolsa_familia_coverage", "bolsa_familia_coverage"),
]

ESTIMATORS = {
    "twfe_dynamic": {
        "estimator": "twfe_dynamic",
        "event_time_var": "dist_treatment",
        "event_time_never_value": -9999,
        "reference_event_time": -2,
    },
    "callaway_santanna": {
        "estimator": "callaway_santanna",
        "control_group": "nevertreated",
        "cluster_var": ["municipality_id"],
    },
    "bjs": {
        "estimator": "bjs",
        "event_time_step": 2,
        "pretrends": [2, 4, 6, 8],
    },
}


def available_outcomes(selected: set[str] | None = None) -> list[tuple[str, str]]:
    df = pd.read_parquet(DATA_PATH)
    out = []
    for output_name, outcome_var in OUTCOME_SPECS:
        if selected is not None and output_name not in selected:
            continue
        if outcome_var in df.columns and df[outcome_var].notna().sum() > 0:
            out.append((output_name, outcome_var))
    return out


def base_config(outcome_var: str, output_dir: Path, weights_var: str | None) -> dict:
    return {
        "data_path": "data/clean/downstream/downstream_outcomes_panel.parquet",
        "file_format": "parquet",
        "outcome": outcome_var,
        "unit_id": "municipality_id",
        "time_id": "year_election",
        "group_id": "year_treated",
        "cluster_var": ["municipality_id", "year_election"],
        "weights_var": weights_var,
        "lead": 8,
        "lag": 8,
        "anticipation": 0,
        "balanced_panel_required": False,
        "never_treated_value": 9999,
        "output_dir": str(output_dir),
        "controls": [],
        "notes": f"Downstream-outcomes run for `{outcome_var}`.",
    }


def run_one(config_path: Path) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["bash", str(RUNNER), str(config_path)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return True, (proc.stdout or "") + (proc.stderr or "")
    except subprocess.CalledProcessError as exc:
        return False, (exc.stdout or "") + (exc.stderr or "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-outcomes", default=None, help="Comma-separated list of output outcome names to run.")
    parser.add_argument(
        "--only-estimators",
        default=None,
        help="Comma-separated list of estimator keys to run (twfe_dynamic, callaway_santanna, bjs).",
    )
    parser.add_argument(
        "--only-weights",
        default=None,
        help="Comma-separated list of weight modes to run (unweighted, population_weighted).",
    )
    args = parser.parse_args()

    selected = None
    if args.only_outcomes:
        selected = {item.strip() for item in args.only_outcomes.split(",") if item.strip()}
    selected_estimators = None
    if args.only_estimators:
        selected_estimators = {item.strip() for item in args.only_estimators.split(",") if item.strip()}
    selected_weights = None
    if args.only_weights:
        selected_weights = {item.strip() for item in args.only_weights.split(",") if item.strip()}

    BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    runs: list[dict] = []
    for outcome_name, outcome_var in available_outcomes(selected):
        for weights_var, weight_label in [(None, "unweighted"), ("population_estimate", "population_weighted")]:
            if selected_weights is not None and weight_label not in selected_weights:
                continue
            for estimator_key, estimator_cfg in ESTIMATORS.items():
                if selected_estimators is not None and estimator_key not in selected_estimators:
                    continue
                output_dir = BASE_OUTPUT_DIR / weight_label / outcome_name / estimator_key
                config_path = CONFIG_DIR / f"{outcome_name}_{weight_label}_{estimator_key}.yml"
                cfg = base_config(outcome_var, output_dir, weights_var)
                cfg.update(estimator_cfg)
                with config_path.open("w", encoding="utf-8") as handle:
                    yaml.safe_dump(cfg, handle, sort_keys=False)
                success, log = run_one(config_path)
                runs.append(
                    {
                        "outcome": outcome_name,
                        "outcome_var": outcome_var,
                        "weights": weight_label,
                        "estimator": estimator_key,
                        "success": success,
                        "log": log.strip(),
                    }
                )

    pd.DataFrame(runs).to_csv(BASE_OUTPUT_DIR / "run_status.csv", index=False)


if __name__ == "__main__":
    main()
