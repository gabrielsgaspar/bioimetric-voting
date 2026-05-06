from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from plot_style import apply_matplotlib_paper_style, save_pdf_png


ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data" / "clean" / "lapop"
OUTPUT_DIR = ROOT / "resources" / "lapop" / "pca"
DOCS_DIR = ROOT / "docs"
LOG_DIR = ROOT / "resources" / "logs"

OUTPUT_PARQUET = DATA_DIR / "lapop_brazil_with_pca_indices.parquet"
OUTPUT_CSV = DATA_DIR / "lapop_brazil_with_pca_indices.csv"
NOTES_PATH = DOCS_DIR / "LAPOP_PCA_INDICES_NOTES.md"
LOG_PATH = LOG_DIR / "lapop_pca_indices_log.md"

INPUT_CANDIDATES = [
    DATA_DIR / "lapop_brazil_core_2008_2019.parquet",
    DATA_DIR / "lapop_brazil_core_2008_2019.csv",
]

REQUESTED_MAIN_SAMPLE_YEARS = [2006, 2008, 2010, 2012, 2014, 2016, 2018]
REQUESTED_EXTENDED_SAMPLE_YEARS = [2006, 2008, 2010, 2012, 2014, 2016, 2018, 2021, 2023]

TRUST_VARIABLES = OrderedDict(
    [
        ("trust_inst_respect", "Respect Brazil's political institutions"),
        ("trust_rights_protected", "Believe citizens' rights are protected by the political system"),
        ("trust_proud_system", "Feel proud to live under Brazil's political system"),
        ("trust_support_system", "Think the political system should be supported"),
        ("trust_parties", "Have confidence in political parties"),
        ("trust_municipal_gov", "Have confidence in the municipal government"),
        ("trust_president", "Have confidence in the president"),
        ("trust_elections", "Have confidence in elections in this country"),
    ]
)

DEMOCRACY_VARIABLES = OrderedDict(
    [
        ("democracy_best_form", "Democracy is better than any other form of government."),
        ("democracy_satisfaction", "I am satisfied with democracy."),
        ("democracy_voice_matters", "Those who govern care about what people like me think."),
    ]
)

TRUST_PLOT_COLOR = "darkslategrey"
DEMOCRACY_PLOT_COLOR = "saddlebrown"
EXPLAINED_VARIANCE_Y_STEP = 0.10
MIN_EXPLAINED_VARIANCE_Y_MAX = 0.50


@dataclass
class PCAArtifacts:
    name: str
    row_labels: list[str]
    variables: list[str]
    loadings: pd.DataFrame
    summary: pd.DataFrame
    scores_raw: pd.Series
    scores_std: pd.Series
    legacy_raw: pd.Series | None
    legacy_std: pd.Series | None
    explained_variance_ratio: np.ndarray
    imputed_counts: pd.Series
    medians: pd.Series
    complete_case_n: int
    n_obs: int
    orientation_note: str
    legacy_note: str | None


def ensure_directories() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def choose_input_file() -> Path:
    required_columns = {"survey_year", *TRUST_VARIABLES.keys(), *DEMOCRACY_VARIABLES.keys()}
    best_path: Path | None = None
    best_score = -1
    for path in INPUT_CANDIDATES:
        if not path.exists():
            continue
        if path.suffix == ".parquet":
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)
        score = len(required_columns & set(df.columns))
        if score > best_score:
            best_score = score
            best_path = path
    if best_path is None:
        checked = ", ".join(str(path) for path in INPUT_CANDIDATES)
        raise FileNotFoundError(f"Could not find a clean LAPOP Brazil input file. Checked: {checked}")
    return best_path


def load_dataframe(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def validate_columns(df: pd.DataFrame) -> None:
    required = {"survey_year", *TRUST_VARIABLES.keys(), *DEMOCRACY_VARIABLES.keys()}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Input LAPOP file is missing required columns: {missing}")


def get_actual_years(df: pd.DataFrame) -> list[int]:
    years = sorted(int(year) for year in df["survey_year"].dropna().unique())
    if not years:
        raise ValueError("No non-missing survey_year values found in the LAPOP input.")
    return years


def build_main_sample(df: pd.DataFrame) -> tuple[pd.DataFrame, list[int], str]:
    actual_years = get_actual_years(df)
    if actual_years == REQUESTED_MAIN_SAMPLE_YEARS:
        note = "The clean LAPOP file exactly matches the requested 2006-2018 paper sample."
    else:
        note = (
            "The requested main sample was 2006, 2008, 2010, 2012, 2014, 2016, 2018, "
            f"but the best clean comparable LAPOP file in the repository contains actual survey years {actual_years}. "
            "The script therefore uses the full comparable clean file as the default main sample and does not relabel years."
        )
    main = df[df["survey_year"].isin(actual_years)].copy()
    return main, actual_years, note


def build_sample_size_table(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("survey_year", as_index=False)
        .size()
        .rename(columns={"size": "n_respondents"})
        .sort_values("survey_year")
        .reset_index(drop=True)
    )


def reverse_democracy_satisfaction(series: pd.Series) -> tuple[pd.Series, str]:
    observed = sorted(series.dropna().unique().tolist())
    allowed = {1.0, 2.0, 3.0, 4.0}
    if not set(observed).issubset(allowed):
        raise ValueError(
            "democracy_satisfaction has unexpected values. "
            f"Expected a subset of {sorted(allowed)}, found {observed[:20]}."
        )
    reversed_series = np.where(series.notna(), 5 - series, np.nan)
    note = (
        "The harmonized `democracy_satisfaction` variable uses the raw LAPOP 1-4 scale "
        "(1 = very satisfied, 4 = very dissatisfied). "
        "Following the notebook, the PCA input reverses it as `5 - democracy_satisfaction`, "
        "so larger values reflect more democratic satisfaction."
    )
    return pd.Series(reversed_series, index=series.index, name=series.name), note


def zscore_series(series: pd.Series) -> pd.Series:
    std = float(series.std(ddof=0))
    if not np.isfinite(std) or std == 0:
        raise ValueError(f"Cannot standardize series `{series.name}` because its standard deviation is {std}.")
    return (series - float(series.mean())) / std


def orient_pca_for_positive_pc1(scores: np.ndarray, loadings: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if float(np.nanmean(loadings[:, 0])) < 0:
        scores[:, 0] *= -1
        loadings[:, 0] *= -1
    return scores, loadings


def build_pca(
    df: pd.DataFrame,
    variable_map: OrderedDict[str, str],
    *,
    name: str,
    reverse_dem_satisfaction: bool = False,
    legacy_combo: bool = False,
) -> PCAArtifacts:
    working = df.copy()
    variables = list(variable_map.keys())
    row_labels = [variable_map[column] for column in variables]

    orientation_note = "All input items already use higher values for more trust or democracy."
    if reverse_dem_satisfaction:
        working["democracy_satisfaction"], orientation_note = reverse_democracy_satisfaction(
            working["democracy_satisfaction"]
        )

    inputs = working[variables].copy()
    imputed_counts = inputs.isna().sum().astype(int)
    complete_case_n = int(inputs.notna().all(axis=1).sum())

    imputer = SimpleImputer(strategy="median")
    matrix_imputed = imputer.fit_transform(inputs)
    medians = pd.Series(imputer.statistics_, index=variables, name="median_imputation_value")

    scaler = StandardScaler()
    matrix_scaled = scaler.fit_transform(matrix_imputed)

    pca = PCA(n_components=len(variables), svd_solver="full")
    scores = pca.fit_transform(matrix_scaled)
    loadings = pca.components_.T * np.sqrt(pca.explained_variance_)
    scores, loadings = orient_pca_for_positive_pc1(scores=scores, loadings=loadings)

    explained_sum = float(np.sum(pca.explained_variance_ratio_))
    if not np.isclose(explained_sum, 1.0, atol=1e-8):
        raise ValueError(f"Explained variance ratios for {name} sum to {explained_sum}, not 1.")

    raw_scores = pd.Series(scores[:, 0], index=df.index, name=f"{name}_index_pca1_raw")
    std_scores = zscore_series(raw_scores.rename(f"{name}_index_std"))
    std_scores.name = f"{name}_index_std"

    loadings_df = pd.DataFrame(
        {
            "variable": variables,
            "label": row_labels,
            "pc1_loading": loadings[:, 0],
            "pc2_loading": loadings[:, 1] if loadings.shape[1] > 1 else np.nan,
            "imputed_n": imputed_counts.reindex(variables).to_numpy(),
            "median_imputation_value": medians.reindex(variables).to_numpy(),
        }
    )

    summary_df = pd.DataFrame(
        {
            "component": np.arange(1, len(variables) + 1),
            "eigenvalue": pca.explained_variance_,
            "explained_variance_ratio": pca.explained_variance_ratio_,
            "cumulative_explained_variance_ratio": np.cumsum(pca.explained_variance_ratio_),
            "n_obs": len(df),
            "n_complete_case": complete_case_n,
        }
    )

    legacy_raw = None
    legacy_std = None
    legacy_note = None
    if legacy_combo:
        weights = pca.explained_variance_ratio_[:2]
        legacy_values = (scores[:, 0] * weights[0]) + (scores[:, 1] * weights[1])
        legacy_raw = pd.Series(legacy_values, index=df.index, name=f"{name}_index_legacy_combo_raw")
        if float(np.corrcoef(legacy_raw, raw_scores)[0, 1]) < 0:
            legacy_raw *= -1
        legacy_std = zscore_series(legacy_raw.rename(f"{name}_index_legacy_combo_std"))
        legacy_std.name = f"{name}_index_legacy_combo_std"
        legacy_note = (
            "Secondary notebook-style comparison only: a weighted combination of PC1 and PC2 "
            "using the first two explained-variance shares. This is not the paper-consistent main democracy index."
        )

    return PCAArtifacts(
        name=name,
        row_labels=row_labels,
        variables=variables,
        loadings=loadings_df,
        summary=summary_df,
        scores_raw=raw_scores,
        scores_std=std_scores,
        legacy_raw=legacy_raw,
        legacy_std=legacy_std,
        explained_variance_ratio=pca.explained_variance_ratio_,
        imputed_counts=imputed_counts.reindex(variables),
        medians=medians.reindex(variables),
        complete_case_n=complete_case_n,
        n_obs=len(df),
        orientation_note=orientation_note,
        legacy_note=legacy_note,
    )


def write_csv_and_tex(artifacts: PCAArtifacts) -> None:
    loadings_path = OUTPUT_DIR / f"{artifacts.name}_pca_loadings_main.csv"
    summary_path = OUTPUT_DIR / f"{artifacts.name}_pca_summary_main.csv"
    tex_path = OUTPUT_DIR / f"{artifacts.name}_pca_table_main.tex"

    artifacts.loadings.to_csv(loadings_path, index=False)
    artifacts.summary.to_csv(summary_path, index=False)

    top_summary = artifacts.summary.head(2).copy()
    lines = [
        r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lcc}",
        r"\doubletoprule",
        r" & PC1 & PC2 \\",
        r"\midrule",
    ]
    for row in artifacts.loadings.itertuples(index=False):
        lines.append(f"{latex_escape(row.label)} & {row.pc1_loading:.3f} & {row.pc2_loading:.3f} \\\\")
    lines.extend(
        [
            r"\midrule",
            f"Eigenvalue: & {top_summary.loc[top_summary['component'] == 1, 'eigenvalue'].iloc[0]:.3f} & "
            f"{top_summary.loc[top_summary['component'] == 2, 'eigenvalue'].iloc[0]:.3f} \\\\",
            f"Share of explained variance: & "
            f"{top_summary.loc[top_summary['component'] == 1, 'explained_variance_ratio'].iloc[0]:.3f} & "
            f"{top_summary.loc[top_summary['component'] == 2, 'explained_variance_ratio'].iloc[0]:.3f} \\\\",
            r"\doublebottomrule",
            r"\end{tabular*}",
            "",
            r"\begin{minipage}{\textwidth}",
            r"\footnotesize",
            rf"\textbf{{Note:}} Entries are PCA loadings after median imputation and standardization of the input variables. The table reports the first two principal components for the main comparable LAPOP Brazil sample. $N = {artifacts.n_obs:,}$. Complete-case $N = {artifacts.complete_case_n:,}.$",
            r"\end{minipage}",
        ]
    )
    tex_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def latex_escape(text: str) -> str:
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
    }
    escaped = text
    for old, new in replacements.items():
        escaped = escaped.replace(old, new)
    return escaped


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    columns = [str(column) for column in df.columns]
    rows = df.astype(object).where(pd.notna(df), "").values.tolist()
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join([header, separator, *body])


def shared_explained_variance_axis(*artifacts: PCAArtifacts) -> tuple[np.ndarray, tuple[float, float]]:
    max_ratio = max(float(np.max(item.explained_variance_ratio)) for item in artifacts)
    upper = max(
        MIN_EXPLAINED_VARIANCE_Y_MAX,
        np.ceil(max_ratio / EXPLAINED_VARIANCE_Y_STEP) * EXPLAINED_VARIANCE_Y_STEP,
    )
    ticks = np.arange(0, upper + EXPLAINED_VARIANCE_Y_STEP / 2, EXPLAINED_VARIANCE_Y_STEP)
    return ticks, (0.0, float(upper))


def plot_explained_variance(artifacts: PCAArtifacts, output_base: Path, color: str, y_ticks: np.ndarray, y_limits: tuple[float, float]) -> None:
    apply_matplotlib_paper_style()
    fig, ax = plt.subplots(figsize=(5.8, 3.4))
    x = np.arange(1, len(artifacts.explained_variance_ratio) + 1)
    ax.bar(x, artifacts.explained_variance_ratio, color=color, edgecolor=color, linewidth=0.6)
    ax.set_xticks(x)
    ax.set_xlabel("")
    ax.set_ylabel("Share of explained variance")
    ax.set_yticks(y_ticks)
    ax.set_ylim(y_limits)
    ax.yaxis.set_major_formatter(FormatStrFormatter("%.1f"))
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="0.85", linewidth=0.8)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.8)
        spine.set_color("0.2")
    save_pdf_png(fig, output_base)
    plt.close(fig)


def build_legacy_comparison_table(democracy: PCAArtifacts) -> pd.DataFrame:
    if democracy.legacy_raw is None or democracy.legacy_std is None:
        raise ValueError("Legacy democracy comparison requested but no legacy scores were created.")
    comparison = pd.DataFrame(
        {
            "metric": [
                "n_obs",
                "pc1_explained_variance_ratio",
                "pc2_explained_variance_ratio",
                "correlation_main_vs_legacy_std",
                "mean_absolute_difference_std",
                "root_mean_squared_difference_std",
            ],
            "value": [
                democracy.n_obs,
                float(democracy.summary.loc[democracy.summary["component"] == 1, "explained_variance_ratio"].iloc[0]),
                float(democracy.summary.loc[democracy.summary["component"] == 2, "explained_variance_ratio"].iloc[0]),
                float(np.corrcoef(democracy.scores_std, democracy.legacy_std)[0, 1]),
                float(np.mean(np.abs(democracy.scores_std - democracy.legacy_std))),
                float(np.sqrt(np.mean((democracy.scores_std - democracy.legacy_std) ** 2))),
            ],
        }
    )
    comparison.to_csv(OUTPUT_DIR / "democracy_pca_legacy_notebook_comparison.csv", index=False)
    return comparison


def write_notes(
    *,
    input_path: Path,
    actual_years: list[int],
    year_counts: pd.DataFrame,
    main_note: str,
    trust: PCAArtifacts,
    democracy: PCAArtifacts,
    legacy_comparison: pd.DataFrame,
) -> None:
    notes = f"""# LAPOP PCA Indices Notes

## Input File Used

- Main input file: `{input_path.relative_to(ROOT)}`

## Actual Survey Years Included

- Clean file survey years: {actual_years}
- Requested main sample years from the draft/notebook instructions: {REQUESTED_MAIN_SAMPLE_YEARS}
- Requested extended notebook-availability years from the draft/notebook instructions: {REQUESTED_EXTENDED_SAMPLE_YEARS}

## Why The Main Sample Uses {actual_years}

- {main_note}
- The repository does not contain a clean comparable 2006 wave.
- The clean comparable core uses actual LAPOP field years `2008, 2010, 2012, 2014, 2017, 2019`; it does not relabel 2017 as 2016 or 2019 as 2018.
- A partial 2021 selected-question file exists, but it does not contain the full 8-item trust block or the 3-item democracy block, so it is not used for the default PCA outputs.
- No clean comparable 2023 Brazil LAPOP file is present in the repository.

## Variables Used

### Trust PCA

- `trust_inst_respect`
- `trust_rights_protected`
- `trust_proud_system`
- `trust_support_system`
- `trust_parties`
- `trust_municipal_gov`
- `trust_president`
- `trust_elections`

### Democracy PCA

- `democracy_best_form`
- `democracy_satisfaction`
- `democracy_voice_matters`

`democracy_understands_politics` is retained in the clean core but excluded from the main democracy index by design.

## Preprocessing Steps

1. Restrict to the main comparable clean sample described above.
2. Check that trust inputs already use larger values for more trust.
3. Reverse `democracy_satisfaction` as `5 - democracy_satisfaction` after verifying that the harmonized variable is on the raw 1-4 LAPOP scale.
4. Impute missing PCA inputs using the sample median for each variable.
5. Standardize each PCA input variable.
6. Run PCA on the standardized matrix.
7. Use the first principal component as the default paper-consistent index.
8. Standardize the respondent-level PCA1 score to mean zero and unit variance over the main sample.

## Direction Handling

- Trust items: larger values already correspond to more trust.
- Democracy items:
  - `democracy_best_form`: larger values correspond to stronger agreement that democracy is best.
  - `democracy_voice_matters`: larger values correspond to stronger belief that government cares about citizens' views.
  - `democracy_satisfaction`: reversed before PCA so larger values correspond to more satisfaction with democracy.

## Notebook Versus Paper Discrepancy

- The paper-consistent default implemented here uses the first principal component for both the trust index and the democracy index.
- The notebook-style trust construction is consistent with that choice.
- The notebook's democracy section appears to use a legacy combination of PC1 and PC2 rather than pure PCA1.
- This script does **not** use that legacy combination as the main democracy index.
- Instead, it saves:
  - `democracy_index_pca1_raw`
  - `democracy_index_std`
  - `democracy_index_legacy_combo_raw`
  - `democracy_index_legacy_combo_std`
- The legacy comparison summary is saved to `resources/lapop/pca/democracy_pca_legacy_notebook_comparison.csv`.

## Sample Sizes By Year

{dataframe_to_markdown(year_counts)}

## Imputation Counts

### Trust

{dataframe_to_markdown(trust.loadings[["variable", "imputed_n", "median_imputation_value"]])}

### Democracy

{dataframe_to_markdown(democracy.loadings[["variable", "imputed_n", "median_imputation_value"]])}

## Main PCA Results

- Trust PC1 explained variance: {trust.summary.loc[trust.summary["component"] == 1, "explained_variance_ratio"].iloc[0]:.4f}
- Trust PC2 explained variance: {trust.summary.loc[trust.summary["component"] == 2, "explained_variance_ratio"].iloc[0]:.4f}
- Democracy PC1 explained variance: {democracy.summary.loc[democracy.summary["component"] == 1, "explained_variance_ratio"].iloc[0]:.4f}
- Democracy PC2 explained variance: {democracy.summary.loc[democracy.summary["component"] == 2, "explained_variance_ratio"].iloc[0]:.4f}

## Legacy Democracy Comparison

{dataframe_to_markdown(legacy_comparison)}

## Outputs

- `data/clean/lapop/lapop_brazil_with_pca_indices.parquet`
- `data/clean/lapop/lapop_brazil_with_pca_indices.csv`
- `resources/lapop/pca/trust_pca_loadings_main.csv`
- `resources/lapop/pca/trust_pca_summary_main.csv`
- `resources/lapop/pca/democracy_pca_loadings_main.csv`
- `resources/lapop/pca/democracy_pca_summary_main.csv`
- `resources/lapop/pca/democracy_pca_legacy_notebook_comparison.csv`
- `resources/lapop/pca/trust_pca_table_main.tex`
- `resources/lapop/pca/democracy_pca_table_main.tex`
- `resources/lapop/pca/trust_explained_variance_main.pdf`
- `resources/lapop/pca/trust_explained_variance_main.png`
- `resources/lapop/pca/democracy_explained_variance_main.pdf`
- `resources/lapop/pca/democracy_explained_variance_main.png`
- `resources/logs/lapop_pca_indices_log.md`
"""
    NOTES_PATH.write_text(notes + "\n", encoding="utf-8")


def write_log(
    *,
    input_path: Path,
    actual_years: list[int],
    year_counts: pd.DataFrame,
    main_note: str,
    trust: PCAArtifacts,
    democracy: PCAArtifacts,
    legacy_comparison: pd.DataFrame,
) -> None:
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    log_text = f"""# LAPOP PCA Indices Log

- Timestamp: `{timestamp}`
- Input file: `{input_path.relative_to(ROOT)}`
- Actual survey years used: `{actual_years}`
- Requested main sample years: `{REQUESTED_MAIN_SAMPLE_YEARS}`
- Requested extended notebook years: `{REQUESTED_EXTENDED_SAMPLE_YEARS}`

## Sample Sizes

{dataframe_to_markdown(year_counts)}

## Main-Sample Note

- {main_note}

## Imputation Counts

### Trust

{dataframe_to_markdown(trust.loadings[["variable", "imputed_n", "median_imputation_value"]])}

### Democracy

{dataframe_to_markdown(democracy.loadings[["variable", "imputed_n", "median_imputation_value"]])}

## Explained Variance

- Trust PC1: {trust.summary.loc[trust.summary["component"] == 1, "explained_variance_ratio"].iloc[0]:.6f}
- Trust PC2: {trust.summary.loc[trust.summary["component"] == 2, "explained_variance_ratio"].iloc[0]:.6f}
- Democracy PC1: {democracy.summary.loc[democracy.summary["component"] == 1, "explained_variance_ratio"].iloc[0]:.6f}
- Democracy PC2: {democracy.summary.loc[democracy.summary["component"] == 2, "explained_variance_ratio"].iloc[0]:.6f}

## Validation

- Trust PCA uses {len(trust.variables)} variables.
- Democracy PCA uses {len(democracy.variables)} variables.
- Trust standardized index mean: {trust.scores_std.mean():.8f}
- Trust standardized index sd: {trust.scores_std.std(ddof=0):.8f}
- Democracy standardized index mean: {democracy.scores_std.mean():.8f}
- Democracy standardized index sd: {democracy.scores_std.std(ddof=0):.8f}

## Notebook Legacy Democracy Comparison

{dataframe_to_markdown(legacy_comparison)}

## Output Files

- `data/clean/lapop/lapop_brazil_with_pca_indices.parquet`
- `data/clean/lapop/lapop_brazil_with_pca_indices.csv`
- `resources/lapop/pca/trust_pca_loadings_main.csv`
- `resources/lapop/pca/trust_pca_summary_main.csv`
- `resources/lapop/pca/democracy_pca_loadings_main.csv`
- `resources/lapop/pca/democracy_pca_summary_main.csv`
- `resources/lapop/pca/democracy_pca_legacy_notebook_comparison.csv`
- `resources/lapop/pca/trust_pca_table_main.tex`
- `resources/lapop/pca/democracy_pca_table_main.tex`
- `resources/lapop/pca/trust_explained_variance_main.pdf`
- `resources/lapop/pca/trust_explained_variance_main.png`
- `resources/lapop/pca/democracy_explained_variance_main.pdf`
- `resources/lapop/pca/democracy_explained_variance_main.png`

## Warnings And Deviations

- The repository's clean comparable LAPOP input does not include 2006, 2016, 2018, or 2023 as actual survey years.
- The default main PCA outputs therefore use the actual clean comparable years in the core file: 2008, 2010, 2012, 2014, 2017, 2019.
- The 2021 selected-question clean file is incomplete for the full trust and democracy blocks, so it is not used for the default PCA outputs.
- The democracy legacy combo is provided only as a notebook-comparison artifact; the main democracy index remains PCA1 only.
"""
    LOG_PATH.write_text(log_text + "\n", encoding="utf-8")


def main() -> None:
    ensure_directories()

    input_path = choose_input_file()
    df = load_dataframe(input_path)
    validate_columns(df)

    main_df, actual_years, main_note = build_main_sample(df)
    year_counts = build_sample_size_table(main_df)

    trust = build_pca(main_df, TRUST_VARIABLES, name="trust")
    democracy = build_pca(
        main_df,
        DEMOCRACY_VARIABLES,
        name="democracy",
        reverse_dem_satisfaction=True,
        legacy_combo=True,
    )

    output_df = main_df.copy()
    output_df["used_in_pca_main_sample"] = True
    output_df["used_in_trust_pca"] = True
    output_df["used_in_democracy_pca"] = True
    output_df["trust_index_pca1_raw"] = trust.scores_raw
    output_df["trust_index_std"] = trust.scores_std
    output_df["democracy_index_pca1_raw"] = democracy.scores_raw
    output_df["democracy_index_std"] = democracy.scores_std
    output_df["democracy_index_legacy_combo_raw"] = democracy.legacy_raw
    output_df["democracy_index_legacy_combo_std"] = democracy.legacy_std

    output_df.to_parquet(OUTPUT_PARQUET, index=False)
    output_df.to_csv(OUTPUT_CSV, index=False)

    write_csv_and_tex(trust)
    write_csv_and_tex(democracy)
    y_ticks, y_limits = shared_explained_variance_axis(trust, democracy)
    plot_explained_variance(
        trust,
        OUTPUT_DIR / "trust_explained_variance_main",
        TRUST_PLOT_COLOR,
        y_ticks,
        y_limits,
    )
    plot_explained_variance(
        democracy,
        OUTPUT_DIR / "democracy_explained_variance_main",
        DEMOCRACY_PLOT_COLOR,
        y_ticks,
        y_limits,
    )
    legacy_comparison = build_legacy_comparison_table(democracy)

    write_notes(
        input_path=input_path,
        actual_years=actual_years,
        year_counts=year_counts,
        main_note=main_note,
        trust=trust,
        democracy=democracy,
        legacy_comparison=legacy_comparison,
    )
    write_log(
        input_path=input_path,
        actual_years=actual_years,
        year_counts=year_counts,
        main_note=main_note,
        trust=trust,
        democracy=democracy,
        legacy_comparison=legacy_comparison,
    )

    print(f"Input file: {input_path.relative_to(ROOT)}")
    print(f"Actual survey years used: {actual_years}")
    print(f"Respondents in main sample: {len(main_df):,}")
    print(
        "Trust PC1 explained variance:",
        f"{trust.summary.loc[trust.summary['component'] == 1, 'explained_variance_ratio'].iloc[0]:.4f}",
    )
    print(
        "Democracy PC1 explained variance:",
        f"{democracy.summary.loc[democracy.summary['component'] == 1, 'explained_variance_ratio'].iloc[0]:.4f}",
    )


if __name__ == "__main__":
    main()
