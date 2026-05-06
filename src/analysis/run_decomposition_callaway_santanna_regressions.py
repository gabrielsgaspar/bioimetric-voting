from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
PANEL_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018_bvr_status_updated.parquet"
REG_DID_SKILL_DIR = Path("/Users/gabrielsgaspar/.codex/skills/reg-did")
RUNNER = REG_DID_SKILL_DIR / "scripts" / "run_estimator.R"
OUTPUT_ROOT = ROOT / "resources" / "regressions" / "decomposition"

NEVER_TREATED_VALUE = 9999
BASELINE_YEAR = 2006
LEAD = 8
LAG = 8
SEED = 20260505

OUTCOMES = {
    "num_voters_over_2006": {
        "column": "num_voters_over_2006",
        "label": "Total registered voters divided by 2006 registered voters",
    },
    "high_ed_over_2006": {
        "column": "high_ed_over_2006",
        "label": "High-education registered voters divided by 2006 registered voters",
    },
    "low_ed_over_2006": {
        "column": "low_ed_over_2006",
        "label": "Low-education registered voters divided by 2006 registered voters",
    },
    "unknown_ed_over_2006": {
        "column": "unknown_ed_over_2006",
        "label": "Unknown-education registered voters divided by 2006 registered voters",
    },
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

CALLAWAY_ESTIMATOR = {
    "label": "Callaway-Sant'Anna",
    "color": "#2C5A8A",
    "config": {
        "estimator": "callaway_santanna",
        "control_group": "nevertreated",
        "base_period": "universal",
    },
}


def load_panel() -> pd.DataFrame:
    panel = pd.read_parquet(PANEL_PATH)
    panel["municipality_id"] = panel["municipality_id"].astype(str).str.zfill(7)
    panel = panel.sort_values(["municipality_id", "year_election"]).reset_index(drop=True)
    return panel


def add_decomposition_outcomes(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = (
        panel.loc[panel["year_election"].eq(BASELINE_YEAR), ["municipality_id", "num_voters"]]
        .rename(columns={"num_voters": "num_voters_2006"})
        .drop_duplicates("municipality_id")
    )
    panel = panel.merge(base, on="municipality_id", how="left", validate="many_to_one")
    panel = panel.loc[panel["num_voters_2006"].notna() & panel["num_voters_2006"].gt(0)].copy()

    panel["num_voters_unknown_ed"] = (
        panel["num_voters"] - panel["num_voters_low_ed"] - panel["num_voters_high_ed"]
    )
    panel["num_voters_over_2006"] = panel["num_voters"] / panel["num_voters_2006"]
    panel["high_ed_over_2006"] = panel["num_voters_high_ed"] / panel["num_voters_2006"]
    panel["low_ed_over_2006"] = panel["num_voters_low_ed"] / panel["num_voters_2006"]
    panel["unknown_ed_over_2006"] = panel["num_voters_unknown_ed"] / panel["num_voters_2006"]
    panel["ratio_component_sum"] = (
        panel["high_ed_over_2006"] + panel["low_ed_over_2006"] + panel["unknown_ed_over_2006"]
    )
    panel["ratio_sum_gap"] = panel["num_voters_over_2006"] - panel["ratio_component_sum"]

    baseline_rows = panel.loc[panel["year_election"].eq(BASELINE_YEAR)]
    validation = pd.DataFrame(
        [
            {
                "check": "municipalities_with_2006_denominator",
                "value": panel["municipality_id"].nunique(),
                "passes": True,
            },
            {
                "check": "num_voters_over_2006_equals_one_in_2006",
                "value": float((baseline_rows["num_voters_over_2006"] - 1).abs().max()),
                "passes": bool((baseline_rows["num_voters_over_2006"] - 1).abs().max() < 1e-12),
            },
            {
                "check": "total_ratio_equals_component_sum_all_rows",
                "value": float(panel["ratio_sum_gap"].abs().max()),
                "passes": bool(panel["ratio_sum_gap"].abs().max() < 1e-12),
            },
            {
                "check": "negative_unknown_education_counts",
                "value": int(panel["num_voters_unknown_ed"].lt(0).sum()),
                "passes": bool(panel["num_voters_unknown_ed"].ge(0).all()),
            },
        ]
    )
    return panel, validation


def build_validation_by_year(panel: pd.DataFrame) -> pd.DataFrame:
    out = (
        panel.groupby("year_election", as_index=False)
        .agg(
            n_rows=("municipality_id", "size"),
            n_municipalities=("municipality_id", "nunique"),
            max_abs_total_minus_components=("ratio_sum_gap", lambda x: float(x.abs().max())),
            total_ratio=("num_voters_over_2006", "sum"),
            high_ed_ratio=("high_ed_over_2006", "sum"),
            low_ed_ratio=("low_ed_over_2006", "sum"),
            unknown_ed_ratio=("unknown_ed_over_2006", "sum"),
        )
        .sort_values("year_election")
    )
    out["component_ratio_sum"] = out["high_ed_ratio"] + out["low_ed_ratio"] + out["unknown_ed_ratio"]
    out["aggregate_sum_gap"] = out["total_ratio"] - out["component_ratio_sum"]
    out["passes"] = out["max_abs_total_minus_components"].lt(1e-12) & out["aggregate_sum_gap"].abs().lt(1e-9)
    return out


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
            {"metric": "rows_full_panel_with_2006_denominator", "value": len(full_panel)},
            {"metric": "rows_analysis_sample", "value": len(sample)},
            {
                "metric": "municipalities_full_panel_with_2006_denominator",
                "value": full_panel["municipality_id"].nunique(),
            },
            {"metric": "municipalities_analysis_sample", "value": sample["municipality_id"].nunique()},
            {"metric": "treated_municipalities", "value": sample.loc[treated, "municipality_id"].nunique()},
            {"metric": "never_treated_municipalities", "value": sample.loc[~treated, "municipality_id"].nunique()},
            {
                "metric": "hybrid_municipalities_in_sample",
                "value": sample.groupby("municipality_id")["hybrid"].max().sum(),
            },
        ]
    )


def write_config(
    *,
    outcome: str,
    outcome_label: str,
    spec_label: str,
    sample_path: Path,
    output_dir: Path,
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
            "color": CALLAWAY_ESTIMATOR["color"],
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
            "show_line": True,
            "show_points": True,
        },
        "output_dir": str(output_dir),
        "notes": (
            f"Callaway-Sant'Anna dynamic DID for {outcome_label}. "
            f"Specification: {spec_label}. Denominator is municipality registered voters in 2006. "
            "Standard errors are clustered by municipality; control group is never-treated municipalities."
        ),
    }
    config.update(CALLAWAY_ESTIMATOR["config"])
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


def main() -> None:
    raw_panel = load_panel()
    panel, validation = add_decomposition_outcomes(raw_panel)
    validation_by_year = build_validation_by_year(panel)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    validation.to_csv(OUTPUT_ROOT / "outcome_validation.csv", index=False)
    validation_by_year.to_csv(OUTPUT_ROOT / "outcome_validation_by_year.csv", index=False)

    statuses = []
    for outcome_key, outcome_info in OUTCOMES.items():
        for spec_key, spec in SPECS.items():
            sample = build_sample(
                panel,
                spec_key=spec_key,
                group_var=spec["group_var"],
                exclude_hybrid=spec["exclude_hybrid"],
            )
            output_dir = OUTPUT_ROOT / outcome_key / spec_key / "callaway_santanna"
            if output_dir.exists():
                shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            sample_path = output_dir / "analysis_sample.parquet"
            sample.to_parquet(sample_path, index=False)
            build_sample_summary(sample, panel, spec_key).to_csv(output_dir / "sample_summary.csv", index=False)
            validation.to_csv(output_dir / "outcome_validation.csv", index=False)
            validation_by_year.to_csv(output_dir / "outcome_validation_by_year.csv", index=False)

            config_path = write_config(
                outcome=outcome_info["column"],
                outcome_label=outcome_info["label"],
                spec_label=spec["label"],
                sample_path=sample_path,
                output_dir=output_dir,
            )
            success, log = run_estimator(config_path)
            status = {
                "outcome": outcome_key,
                "spec": spec_key,
                "estimator": "callaway_santanna",
                "success": success,
                "output_dir": str(output_dir.relative_to(ROOT)),
                "config": str(config_path.relative_to(ROOT)),
                "log": log.strip(),
            }
            statuses.append(status)
            pd.DataFrame([status]).to_csv(output_dir / "run_status.csv", index=False)
            print(f"{outcome_key} / {spec_key} / callaway_santanna: {'OK' if success else 'FAILED'}")

    status_frame = pd.DataFrame(statuses)
    status_frame.to_csv(OUTPUT_ROOT / "run_status.csv", index=False)
    print(f"\nWrote {OUTPUT_ROOT.relative_to(ROOT) / 'run_status.csv'}")
    print("\nOutcome validation:")
    print(validation.to_string(index=False))
    print("\nOutcome validation by year:")
    print(validation_by_year[["year_election", "max_abs_total_minus_components", "aggregate_sum_gap", "passes"]].to_string(index=False))


if __name__ == "__main__":
    main()
