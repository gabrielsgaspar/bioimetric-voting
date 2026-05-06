from __future__ import annotations

import sys

import pandas as pd

from build_regression_table import build_regression_summary, build_tex_table
from extract_results import extract_interaction_effects, extract_tidy_results
from fit_model_pyfixest import fit_model
from load_data import load_data
from parse_config import dump_config, load_config
from plot_interaction_bars import plot_interaction_bars
from save_outputs import save_dataframe, write_text
from utils import ensure_directory, title_from_variable
from validate_inputs import apply_sample_filter, validate_columns, validate_config


def _model_required_columns(config: dict, interaction_var: str | None) -> list[str]:
    columns = [config["outcome"], config["main_var"]]
    if interaction_var:
        columns.append(interaction_var)
    columns.extend(config.get("controls", []) or [])
    columns.extend(config.get("fixed_effects", []) or [])
    columns.extend(config.get("cluster", []) or [])
    weight_var = config.get("weight_var")
    if weight_var:
        columns.append(weight_var)
    return list(dict.fromkeys(columns))


def _prepare_model_data(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    prepared = df[columns].copy()
    prepared = prepared.dropna().reset_index(drop=True)
    if prepared.empty:
        raise ValueError("Regression sample is empty after dropping missing required variables.")
    return prepared


def _build_model_summary_text(model, tidy: pd.DataFrame, category_label: str) -> str:
    lines = [
        f"Category: {category_label}",
        f"Backend: {model.backend}",
        f"Formula: {model.formula}",
        f"Observations: {model.sample_n}",
        f"R-squared: {model.r_squared:.4f}" if model.r_squared is not None else "R-squared: NA",
        f"Clusters: {model.cluster_counts}" if model.cluster_counts else "Clusters: none",
    ]
    if model.notes:
        lines.append("Notes:")
        lines.extend([f"- {note}" for note in model.notes])
    lines.append("")
    lines.append(
        tidy[["term", "estimate", "std_error", "p_value", "ci95_low", "ci95_high"]].to_string(index=False)
    )
    return "\n".join(lines)


def run_interaction_series(config: dict) -> None:
    output_dir = ensure_directory(config["output_dir"])
    data = load_data(config["data_path"], config.get("file_format"))
    filtered = apply_sample_filter(data, config.get("sample_filter"))

    category_labels = config.get("category_labels", {}) or {}
    outcome_label = config.get("outcome_label", title_from_variable(config["outcome"]))

    tidy_frames: list[pd.DataFrame] = []
    interaction_frames: list[pd.DataFrame] = []
    model_summaries: list[str] = []

    for interaction_var in config["interaction_vars"]:
        required_columns = _model_required_columns(config, interaction_var)
        validate_columns(filtered, required_columns, f"interaction model `{interaction_var}`")
        model_data = _prepare_model_data(filtered, required_columns)
        model = fit_model(
            data=model_data,
            outcome=config["outcome"],
            main_var=config["main_var"],
            interaction_var=interaction_var,
            controls=config.get("controls", []) or [],
            fixed_effects=config.get("fixed_effects", []) or [],
            cluster_vars=config.get("cluster", []) or [],
            weight_var=config.get("weight_var"),
            sample_filter=config.get("sample_filter"),
        )
        category_label = category_labels.get(interaction_var, title_from_variable(interaction_var))
        tidy = extract_tidy_results(model, category=category_label)
        effects = extract_interaction_effects(
            model=model,
            interaction_var=interaction_var,
            category_label=category_label,
            outcome_label=outcome_label,
        )
        tidy_frames.append(tidy)
        interaction_frames.append(effects)
        model_summaries.append(_build_model_summary_text(model, tidy, category_label))

    tidy_results = pd.concat(tidy_frames, ignore_index=True)
    interaction_effects = pd.concat(interaction_frames, ignore_index=True)
    summary_table = build_regression_summary(interaction_effects)

    expected_rows = 2 * len(config["interaction_vars"])
    if len(interaction_effects) != expected_rows:
        raise ValueError(
            f"Interaction plotting dataset should have {expected_rows} rows but has {len(interaction_effects)}."
        )

    config_used = {key: value for key, value in config.items() if key != "config_path"}
    dump_config(config_used, output_dir / "config_used.yml")
    save_dataframe(tidy_results, output_dir / "tidy_results.csv")
    save_dataframe(interaction_effects, output_dir / "interaction_effects.csv")
    save_dataframe(summary_table, output_dir / "regression_table.csv")
    write_text("\n\n".join(model_summaries) + "\n", output_dir / "model_summaries.txt")

    note = (
        "Each row summarizes one interaction regression with municipality and survey-year fixed effects. "
        "The base-group effect is the coefficient on the treatment indicator. The interacted-group effect "
        "adds the interaction term using the fitted covariance matrix. Standard errors are cluster-robust "
        "using the clustering requested in the config. Stars refer to the interaction-difference p-value."
    )
    tex = build_tex_table(summary_table, note=note)
    write_text(tex, output_dir / "regression_table.tex")

    figure_output_base = config.get("figure_output_base")
    if figure_output_base:
        plot_interaction_bars(
            interaction_effects,
            output_base=figure_output_base,
            colors=config.get("plot_colors", {"No": "#b0b0b0", "Yes": "#707070"}),
        )


def run_single_model(config: dict) -> None:
    output_dir = ensure_directory(config["output_dir"])
    data = load_data(config["data_path"], config.get("file_format"))
    filtered = apply_sample_filter(data, config.get("sample_filter"))
    required_columns = _model_required_columns(config, None)
    validate_columns(filtered, required_columns, "single_model")
    model_data = _prepare_model_data(filtered, required_columns)

    model = fit_model(
        data=model_data,
        outcome=config["outcome"],
        main_var=config["main_var"],
        interaction_var=None,
        controls=config.get("controls", []) or [],
        fixed_effects=config.get("fixed_effects", []) or [],
        cluster_vars=config.get("cluster", []) or [],
        weight_var=config.get("weight_var"),
        sample_filter=config.get("sample_filter"),
    )
    tidy = extract_tidy_results(model, category=config.get("model_label", "Main model"))

    config_used = {key: value for key, value in config.items() if key != "config_path"}
    dump_config(config_used, output_dir / "config_used.yml")
    save_dataframe(tidy, output_dir / "tidy_results.csv")
    write_text(_build_model_summary_text(model, tidy, config.get("model_label", "Main model")) + "\n", output_dir / "model_summaries.txt")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python run_regression.py path/to/config.yml")

    config = load_config(sys.argv[1])
    validate_config(config)
    run_type = config["run_type"]
    if run_type == "interaction_series":
        run_interaction_series(config)
        return
    if run_type == "single_model":
        run_single_model(config)
        return
    raise SystemExit(f"Unsupported run_type: {run_type}")


if __name__ == "__main__":
    main()
