from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "clean" / "downstream" / "downstream_outcomes_panel_v2.parquet"
PREPARED_DATA_PATH = ROOT / "data" / "interim" / "siconfi_bdd" / "downstream_outcomes_panel_v2_prepared.parquet"
NONHYBRID_DATA_PATH = ROOT / "data" / "interim" / "siconfi_bdd" / "downstream_outcomes_panel_v2_nonhybrid.parquet"
HYBRID_SOURCE_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018.parquet"
COVERAGE_PATH = ROOT / "data" / "interim" / "siconfi_bdd" / "outcome_coverage_summary.csv"
RUNNER = ROOT / "scripts" / "run_did_estimator.sh"
BASE_OUTPUT_DIR = ROOT / "resources" / "did" / "siconfi_bdd"
CONFIG_DIR = BASE_OUTPUT_DIR / "configs"
STATUS_PATH = BASE_OUTPUT_DIR / "run_status.csv"

OUTCOME_SPECS = [
    ("health_spending_pc", "log_health_spending_pc", "tier1"),
    ("education_spending_pc", "log_education_spending_pc", "tier1"),
    ("social_assistance_pc", "log_social_assistance_pc", "tier1"),
    ("total_spending_pc", "log_total_spending_pc", "tier1"),
    ("urbanism_pc", "log_urbanism_pc", "tier2"),
    ("housing_pc", "log_housing_pc", "tier2"),
    ("sanitation_pc", "log_sanitation_pc", "tier2"),
    ("culture_pc", "log_culture_pc", "tier2"),
    ("sport_leisure_pc", "log_sport_leisure_pc", "tier2"),
    ("agriculture_pc", "log_agriculture_pc", "tier2"),
    ("investment_spending_pc", "log_investment_spending_pc", "tier2"),
    ("IPTU_pc", "log_IPTU_pc", "tier3"),
    ("ISS_pc", "log_ISS_pc", "tier3"),
    ("total_tax_revenue_pc", "log_total_tax_revenue_pc", "tier3"),
    ("FPM_transfers_pc", "log_FPM_transfers_pc", "tier4"),
    ("SUS_transfers_pc", "log_SUS_transfers_pc", "tier4"),
    ("personnel_spending_pc", "log_personnel_spending_pc", "tier4"),
    ("debt_service_pc", "log_debt_service_pc", "tier4"),
]

BASELINE_ESTIMATORS = {
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


def load_supported_outcomes() -> list[tuple[str, str, str]]:
    coverage = pd.read_csv(COVERAGE_PATH)
    min_coverage = coverage.groupby("outcome", as_index=False)["n_muni_nonmissing"].min()
    supported = set(min_coverage.loc[min_coverage["n_muni_nonmissing"] >= 4500, "outcome"].tolist())
    return [spec for spec in OUTCOME_SPECS if spec[0] in supported]


def prepare_data() -> None:
    df = pd.read_parquet(DATA_PATH)
    df["municipality_id"] = df["municipality_id"].astype(str)
    df["state_year_fe"] = df["state"].astype(str) + "_" + df["year_election"].astype(str)
    PREPARED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PREPARED_DATA_PATH, index=False)

    hybrid_source = pd.read_parquet(HYBRID_SOURCE_PATH)
    hybrid_ids = set(hybrid_source.loc[hybrid_source["hybrid"] == 1, "municipality_id"].astype(str).tolist())
    nonhybrid = df.loc[~df["municipality_id"].astype(str).isin(hybrid_ids)].copy()
    nonhybrid.to_parquet(NONHYBRID_DATA_PATH, index=False)

    sample_summary = pd.DataFrame(
        [
            {"metric": "rows_full_sample", "value": int(len(df))},
            {"metric": "rows_nonhybrid_sample", "value": int(len(nonhybrid))},
            {"metric": "municipalities_full_sample", "value": int(df["municipality_id"].nunique())},
            {"metric": "municipalities_nonhybrid_sample", "value": int(nonhybrid["municipality_id"].nunique())},
            {"metric": "hybrid_municipalities_excluded", "value": int(len(hybrid_ids))},
        ]
    )
    sample_summary.to_csv(BASE_OUTPUT_DIR / "sample_summary.csv", index=False)


def base_config(outcome_var: str, output_dir: Path, data_path: Path, weights_var: str | None = None) -> dict:
    return {
        "data_path": str(data_path),
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
        "notes": f"SICONFI Base dos Dados downstream-fiscal run for `{outcome_var}`.",
        "plot_title": None,
        "omit_plot_title": True,
    }


def write_config(config: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)


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


def output_exists(output_dir: Path) -> bool:
    return (output_dir / "event_study_estimates.csv").exists()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-outcomes", default=None, help="Comma-separated list of outcome names to run.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip runs whose output files already exist.")
    args = parser.parse_args()

    BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    prepare_data()
    outcomes = load_supported_outcomes()
    if args.only_outcomes:
        requested = {item.strip() for item in args.only_outcomes.split(",") if item.strip()}
        outcomes = [spec for spec in outcomes if spec[0] in requested]

    records: list[dict[str, object]] = []

    for outcome_name, outcome_var, tier in outcomes:
        for estimator_key, estimator_cfg in BASELINE_ESTIMATORS.items():
            output_dir = BASE_OUTPUT_DIR / "baseline" / outcome_name / estimator_key
            config_path = CONFIG_DIR / f"{outcome_name}_baseline_{estimator_key}.yml"
            cfg = base_config(outcome_var, output_dir, PREPARED_DATA_PATH)
            cfg.update(estimator_cfg)
            write_config(cfg, config_path)
            if args.skip_existing and output_exists(output_dir):
                success, log = True, "skipped_existing_output"
            else:
                success, log = run_one(config_path)
            records.append(
                {
                    "outcome_name": outcome_name,
                    "outcome_var": outcome_var,
                    "tier": tier,
                    "spec": "baseline",
                    "estimator": estimator_key,
                    "success": success,
                    "config_path": str(config_path),
                    "output_dir": str(output_dir),
                    "log": log.strip(),
                }
            )

        for spec_name, weights_var, data_path, extra_fixed_effects in [
            ("population_weighted", "population_estimate", PREPARED_DATA_PATH, None),
            ("state_year_fe", None, PREPARED_DATA_PATH, ["state_year_fe"]),
            ("nonhybrid", None, NONHYBRID_DATA_PATH, None),
        ]:
            output_dir = BASE_OUTPUT_DIR / spec_name / outcome_name / "twfe_dynamic"
            config_path = CONFIG_DIR / f"{outcome_name}_{spec_name}_twfe_dynamic.yml"
            cfg = base_config(outcome_var, output_dir, data_path, weights_var=weights_var)
            cfg.update(BASELINE_ESTIMATORS["twfe_dynamic"])
            if extra_fixed_effects is not None:
                cfg["extra_fixed_effects"] = extra_fixed_effects
            write_config(cfg, config_path)
            if args.skip_existing and output_exists(output_dir):
                success, log = True, "skipped_existing_output"
            else:
                success, log = run_one(config_path)
            records.append(
                {
                    "outcome_name": outcome_name,
                    "outcome_var": outcome_var,
                    "tier": tier,
                    "spec": spec_name,
                    "estimator": "twfe_dynamic",
                    "success": success,
                    "config_path": str(config_path),
                    "output_dir": str(output_dir),
                    "log": log.strip(),
                }
            )

    pd.DataFrame(records).to_csv(STATUS_PATH, index=False)


if __name__ == "__main__":
    main()
