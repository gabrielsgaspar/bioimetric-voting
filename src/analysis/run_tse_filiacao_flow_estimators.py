from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts" / "run_did_estimator.sh"
PANEL_PATH = ROOT / "data" / "clean" / "tse_filiacao" / "new_affiliations_election_year_panel.csv"
SAMPLE_DIR = ROOT / "data" / "interim" / "tse_filiacao" / "estimation_samples"
CONFIG_DIR = ROOT / "resources" / "did" / "tse_filiacao_flow" / "configs"
STATUS_PATH = ROOT / "resources" / "did" / "tse_filiacao_flow" / "run_status.csv"


OUTCOMES = {
    "log_new_affiliations": {
        "label": "Log new affiliations",
        "twfe_dir": ROOT / "resources" / "did" / "twfe_dynamic" / "log_new_affiliations",
        "cs_dir": ROOT / "resources" / "did" / "callaway_santanna" / "log_new_affiliations",
    },
    "new_affiliations_per_pop": {
        "label": "New affiliations per 1,000 population",
        "twfe_dir": ROOT / "resources" / "did" / "twfe_dynamic" / "new_affiliations_per_pop",
        "cs_dir": ROOT / "resources" / "did" / "callaway_santanna" / "new_affiliations_per_pop",
    },
    "new_affiliations_per_adult_pop": {
        "label": "New affiliations per 1,000 adult population",
        "twfe_dir": ROOT / "resources" / "did" / "twfe_dynamic" / "new_affiliations_per_adult_pop",
        "cs_dir": ROOT / "resources" / "did" / "callaway_santanna" / "new_affiliations_per_adult_pop",
    },
}


ROBUSTNESS_SPECS = {
    "state_year_fe": {
        "label": "State x year FE",
        "filter": None,
        "extra_fixed_effects": ["state_year_fe"],
        "weights_var": None,
    },
    "population_weighted": {
        "label": "Population-weighted TWFE",
        "filter": "population.notna()",
        "extra_fixed_effects": [],
        "weights_var": "population",
    },
    "exclude_hybrid": {
        "label": "Exclude hybrid municipalities",
        "filter": "hybrid_flag == 0",
        "extra_fixed_effects": [],
        "weights_var": None,
    },
    "exclude_cleanup_windows": {
        "label": "Exclude flagged cleanup windows",
        "filter": "cleanup_window_flag == 0",
        "extra_fixed_effects": [],
        "weights_var": None,
    },
    "drop_2000_2002": {
        "label": "Drop 2000 and 2002",
        "filter": "election_year > 2002",
        "extra_fixed_effects": [],
        "weights_var": None,
    },
}


def ensure_dirs() -> None:
    for path in [SAMPLE_DIR, CONFIG_DIR, STATUS_PATH.parent]:
        path.mkdir(parents=True, exist_ok=True)


def write_estimation_samples() -> dict[str, Path]:
    df = pd.read_csv(PANEL_PATH, dtype={"id_municipio": str, "municipality_id": str})
    paths: dict[str, Path] = {"main": PANEL_PATH}

    for key, spec in ROBUSTNESS_SPECS.items():
        sample = df.copy()
        filter_expr = spec["filter"]
        if filter_expr:
            sample = sample.query(filter_expr).copy()
        path = SAMPLE_DIR / f"{key}.csv"
        sample.to_csv(path, index=False)
        paths[key] = path

    return paths


def base_config(outcome: str, data_path: Path, output_dir: Path) -> dict:
    return {
        "data_path": str(data_path.relative_to(ROOT)),
        "file_format": "csv",
        "outcome": outcome,
        "unit_id": "municipality_id",
        "time_id": "election_year",
        "group_id": "year_treated",
        "treatment_var": None,
        "controls": [],
        "cluster_var": ["municipality_id", "election_year"],
        "weights_var": None,
        "event_time_var": "dist_treatment",
        "event_time_never_value": -9999,
        "lead": 8,
        "lag": 8,
        "anticipation": 0,
        "balanced_panel_required": False,
        "never_treated_value": 9999,
        "reference_event_time": -2,
        "omit_plot_title": True,
        "output_dir": str(output_dir),
        "notes": f"Party affiliation flow event-study run for `{outcome}`.",
    }


def write_config(config: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(config, fh, sort_keys=False)


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


def main() -> None:
    ensure_dirs()
    sample_paths = write_estimation_samples()
    records: list[dict[str, object]] = []

    for outcome, info in OUTCOMES.items():
        twfe_config = base_config(outcome, sample_paths["main"], info["twfe_dir"])
        twfe_config["estimator"] = "twfe_dynamic"
        twfe_path = CONFIG_DIR / f"{outcome}_twfe_dynamic.yml"
        write_config(twfe_config, twfe_path)
        success, log = run_config(twfe_path)
        records.append(
            {
                "outcome": outcome,
                "specification": "main",
                "estimator": "twfe_dynamic",
                "success": success,
                "config": str(twfe_path.relative_to(ROOT)),
                "log": log.strip(),
            }
        )

        cs_config = base_config(outcome, sample_paths["main"], info["cs_dir"])
        cs_config["estimator"] = "callaway_santanna"
        cs_config["event_time_var"] = None
        cs_config["event_time_never_value"] = None
        cs_config["cluster_var"] = "municipality_id"
        cs_config["control_group"] = "nevertreated"
        cs_path = CONFIG_DIR / f"{outcome}_callaway_santanna.yml"
        write_config(cs_config, cs_path)
        success, log = run_config(cs_path)
        records.append(
            {
                "outcome": outcome,
                "specification": "main",
                "estimator": "callaway_santanna",
                "success": success,
                "config": str(cs_path.relative_to(ROOT)),
                "log": log.strip(),
            }
        )

    outcome = "log_new_affiliations"
    for spec_key, spec in ROBUSTNESS_SPECS.items():
        output_dir = ROOT / "resources" / "did" / "twfe_dynamic" / "log_new_affiliations_robustness" / spec_key
        config = base_config(outcome, sample_paths[spec_key], output_dir)
        config["estimator"] = "twfe_dynamic"
        config["extra_fixed_effects"] = spec["extra_fixed_effects"]
        config["weights_var"] = spec["weights_var"]
        config["notes"] = f"Party affiliation flow robustness: {spec['label']}."
        path = CONFIG_DIR / f"{outcome}_{spec_key}_twfe_dynamic.yml"
        write_config(config, path)
        success, log = run_config(path)
        records.append(
            {
                "outcome": outcome,
                "specification": spec_key,
                "estimator": "twfe_dynamic",
                "success": success,
                "config": str(path.relative_to(ROOT)),
                "log": log.strip(),
            }
        )

    status = pd.DataFrame(records)
    status.to_csv(STATUS_PATH, index=False)
    print(status[["outcome", "specification", "estimator", "success"]].to_string(index=False))


if __name__ == "__main__":
    main()
