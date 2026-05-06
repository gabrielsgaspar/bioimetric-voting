from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter
import pandas as pd

try:
    from plot_style import apply_matplotlib_paper_style, save_pdf_png
except ImportError:  # pragma: no cover
    from src.analysis.plot_style import apply_matplotlib_paper_style, save_pdf_png


ROOT = Path(__file__).resolve().parents[2]
PANEL_PATH = ROOT / "data" / "clean" / "tse_filiacao" / "new_affiliations_election_year_panel.csv"
TABLE_MAIN_PATH = ROOT / "resources" / "tables" / "filiacao_flow_main_table.tex"
TABLE_ROBUSTNESS_PATH = ROOT / "resources" / "tables" / "filiacao_flow_robustness_table.tex"
COMPARISON_DIR = ROOT / "resources" / "images" / "regressions" / "estimator_comparison" / "filiacao_flow"

EVENT_TIMES = [-6, -4, -2, 0, 2, 4, 6]
PLOT_EVENT_TIMES = [-8, -6, -4, -2, 0, 2, 4, 6, 8]

OUTCOMES = [
    (
        "log_new_affiliations",
        "Panel A: Log new affiliations",
        "Log count",
        ROOT / "resources" / "did" / "twfe_dynamic" / "log_new_affiliations",
        ROOT / "resources" / "did" / "callaway_santanna" / "log_new_affiliations",
    ),
    (
        "new_affiliations_per_pop",
        "Panel B: New affiliations per 1,000 residents",
        "Per population",
        ROOT / "resources" / "did" / "twfe_dynamic" / "new_affiliations_per_pop",
        ROOT / "resources" / "did" / "callaway_santanna" / "new_affiliations_per_pop",
    ),
    (
        "new_affiliations_per_adult_pop",
        "Panel C: New affiliations per 1,000 adults",
        "Per adult population",
        ROOT / "resources" / "did" / "twfe_dynamic" / "new_affiliations_per_adult_pop",
        ROOT / "resources" / "did" / "callaway_santanna" / "new_affiliations_per_adult_pop",
    ),
]

ROBUSTNESS = [
    (
        "state_year_fe",
        "State $\\times$ year FE",
        ROOT / "resources" / "did" / "twfe_dynamic" / "log_new_affiliations_robustness" / "state_year_fe",
    ),
    (
        "population_weighted",
        "Population weighted",
        ROOT / "resources" / "did" / "twfe_dynamic" / "log_new_affiliations_robustness" / "population_weighted",
    ),
    (
        "exclude_hybrid",
        "No hybrid",
        ROOT / "resources" / "did" / "twfe_dynamic" / "log_new_affiliations_robustness" / "exclude_hybrid",
    ),
    (
        "exclude_cleanup_windows",
        "No cleanup windows",
        ROOT / "resources" / "did" / "twfe_dynamic" / "log_new_affiliations_robustness" / "exclude_cleanup_windows",
    ),
    (
        "drop_2000_2002",
        "Drop 2000/2002",
        ROOT / "resources" / "did" / "twfe_dynamic" / "log_new_affiliations_robustness" / "drop_2000_2002",
    ),
]


def stars(p_value: float | None) -> str:
    if p_value is None or pd.isna(p_value):
        return ""
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.10:
        return "*"
    return ""


def estimate_cell(row: pd.Series | None, *, include_stars: bool = True) -> str:
    if row is None:
        return ""
    estimate = row.get("estimate")
    if estimate is None or pd.isna(estimate):
        return ""
    p_value = row.get("p.value")
    suffix = stars(p_value) if include_stars else ""
    return f"{estimate:.3f}{suffix}"


def se_cell(row: pd.Series | None) -> str:
    if row is None:
        return ""
    se = row.get("std.error")
    if se is None or pd.isna(se):
        return ""
    return f"({se:.3f})"


def load_event_study(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path / "event_study_estimates.csv")
    df["event_time"] = pd.to_numeric(df["event_time"], errors="coerce")
    for col in ["estimate", "std.error", "p.value", "conf.low", "conf.high"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.set_index("event_time")


def row_at(df: pd.DataFrame, event_time: int) -> pd.Series | None:
    if event_time not in df.index:
        return None
    row = df.loc[event_time]
    if isinstance(row, pd.DataFrame):
        row = row.iloc[0]
    return row


def sample_moments(data_path: Path, outcome: str) -> dict[str, float | int]:
    df = pd.read_csv(
        data_path,
        dtype={"id_municipio": str, "municipality_id": str},
        low_memory=False,
    )
    series = pd.to_numeric(df[outcome], errors="coerce")
    return {
        "n": int(series.notna().sum()),
        "mean": float(series.mean()),
        "sd": float(series.std()),
    }


def diagnostics_n(output_dir: Path) -> int | None:
    path = output_dir / "sample_diagnostics.csv"
    if not path.exists():
        return None
    diag = pd.read_csv(path)
    row = diag.loc[diag["metric"] == "n_rows", "value"]
    if row.empty:
        return None
    return int(float(row.iloc[0]))


def build_main_table() -> str:
    panel = pd.read_csv(PANEL_PATH, dtype={"id_municipio": str, "municipality_id": str}, low_memory=False)
    lines = [
        r"\begin{table}[htbp]",
        r"    \caption{Biometric Registration and New Party Affiliations}",
        r"    \label{tab:filiacao-flow-main}",
        r"    \centering",
        r"    \small",
        r"    \renewcommand{\arraystretch}{1.08}",
        r"    \begin{tabular*}{0.82\textwidth}{@{\extracolsep{\fill}}lcc}",
        r"        \doubletoprule",
        r"        Years relative to BVR adoption & TWFE & Callaway-Sant'Anna \\",
        r"        \midrule",
    ]

    for outcome, panel_title, _, twfe_dir, cs_dir in OUTCOMES:
        twfe = load_event_study(twfe_dir)
        cs = load_event_study(cs_dir)
        lines.append(r"        \multicolumn{3}{l}{\textit{" + panel_title + r"}} \\")
        for event_time in EVENT_TIMES:
            twfe_row = row_at(twfe, event_time)
            cs_row = row_at(cs, event_time)
            lines.append(
                "        "
                + f"${event_time}$ & {estimate_cell(twfe_row)} & {estimate_cell(cs_row, include_stars=False)} "
                + r"\\"
            )
            lines.append(
                "        "
                + f" & {se_cell(twfe_row)} & {se_cell(cs_row)} "
                + r"\\"
            )

        moments = sample_moments(PANEL_PATH, outcome)
        lines.extend(
            [
                r"        \addlinespace[0.25em]",
                r"        Municipality FE & \checkmark & -- \\",
                r"        Election-year FE & \checkmark & -- \\",
                f"        Observations & {moments['n']:,} & {moments['n']:,} " + r"\\",
                f"        Mean dep. var. & {moments['mean']:.3f} & {moments['mean']:.3f} " + r"\\",
                f"        SD dep. var. & {moments['sd']:.3f} & {moments['sd']:.3f} " + r"\\",
            ]
        )
        if outcome != OUTCOMES[-1][0]:
            lines.append(r"        \midrule")

    lines.extend(
        [
            r"        \doublebottomrule",
            r"    \end{tabular*}",
            r"    \vspace{1.1em}",
            r"    \begin{minipage}{\textwidth}",
            r"        {\footnotesize \textbf{Note:} The table reports dynamic event-study estimates for new TSE party affiliation flows in the two-year window before each election. The TWFE specification includes municipality and election-year fixed effects and clusters standard errors by municipality and election year. Event time $-2$ is the omitted TWFE reference period. Callaway-Sant'Anna estimates use never-treated municipalities as the comparison group and municipality-clustered standard errors. All dependent variables are winsorized at the 1st and 99th municipality-election percentiles. $^{*} p<0.10$, $^{**} p<0.05$, $^{***} p<0.01$. \par}",
            r"    \end{minipage}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_robustness_table() -> str:
    panel = pd.read_csv(PANEL_PATH, dtype={"id_municipio": str, "municipality_id": str}, low_memory=False)
    studies = [(key, label, load_event_study(path), path) for key, label, path in ROBUSTNESS]

    lines = [
        r"\begin{table}[htbp]",
        r"    \caption{Robustness: Log New Party Affiliations}",
        r"    \label{tab:filiacao-flow-robustness}",
        r"    \centering",
        r"    \scriptsize",
        r"    \renewcommand{\arraystretch}{1.08}",
        r"    \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lccccc}",
        r"        \doubletoprule",
        "        Years relative to BVR adoption & "
        + " & ".join(label for _, label, _, _ in studies)
        + r" \\",
        r"        \midrule",
    ]

    for event_time in EVENT_TIMES:
        estimate_cells = []
        se_cells = []
        for _, _, study, _ in studies:
            row = row_at(study, event_time)
            estimate_cells.append(estimate_cell(row))
            se_cells.append(se_cell(row))
        lines.append("        " + f"${event_time}$ & " + " & ".join(estimate_cells) + r" \\")
        lines.append("        " + " & ".join([""] + se_cells) + r" \\")

    obs_cells = []
    mean_cells = []
    sd_cells = []
    for key, _, _, path in studies:
        data_path = ROOT / "data" / "interim" / "tse_filiacao" / "estimation_samples" / f"{key}.csv"
        if not data_path.exists():
            data_path = PANEL_PATH
        moments = sample_moments(data_path, "log_new_affiliations")
        obs_cells.append(f"{diagnostics_n(path) or moments['n']:,}")
        mean_cells.append(f"{moments['mean']:.3f}")
        sd_cells.append(f"{moments['sd']:.3f}")

    lines.extend(
        [
            r"        \midrule",
            r"        Municipality FE & \checkmark & \checkmark & \checkmark & \checkmark & \checkmark \\",
            r"        Election-year FE & \checkmark & \checkmark & \checkmark & \checkmark & \checkmark \\",
            r"        State $\times$ year FE & \checkmark & -- & -- & -- & -- \\",
            r"        Population weights & -- & \checkmark & -- & -- & -- \\",
            "        Observations & " + " & ".join(obs_cells) + r" \\",
            "        Mean dep. var. & " + " & ".join(mean_cells) + r" \\",
            "        SD dep. var. & " + " & ".join(sd_cells) + r" \\",
            r"        \doublebottomrule",
            r"    \end{tabular*}",
            r"    \vspace{1.1em}",
            r"    \begin{minipage}{\textwidth}",
            r"        {\footnotesize \textbf{Note:} The dependent variable is $\log(1+\text{new affiliations})$, winsorized at the 1st and 99th municipality-election percentiles. All specifications are dynamic TWFE event studies with municipality and election-year fixed effects unless noted. Standard errors are clustered by municipality and election year. The cleanup-window specification drops election windows containing disaffiliation months flagged as administrative events in the diagnostic file. $^{*} p<0.10$, $^{**} p<0.05$, $^{***} p<0.01$. \par}",
            r"    \end{minipage}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def load_plot_data(output_dir: Path, label: str, color: str) -> pd.DataFrame:
    df = pd.read_csv(output_dir / "event_study_estimates.csv")
    df["event_time"] = pd.to_numeric(df["event_time"], errors="coerce")
    for col in ["estimate", "conf.low", "conf.high"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df["event_time"].isin(PLOT_EVENT_TIMES)].dropna(subset=["estimate", "conf.low", "conf.high"])
    df["estimator"] = label
    df["color"] = color
    return df


def build_comparison_figure() -> None:
    apply_matplotlib_paper_style()
    COMPARISON_DIR.mkdir(parents=True, exist_ok=True)

    twfe = load_plot_data(
        ROOT / "resources" / "did" / "twfe_dynamic" / "log_new_affiliations",
        "Dynamic TWFE",
        "#2C5A8A",
    )
    cs = load_plot_data(
        ROOT / "resources" / "did" / "callaway_santanna" / "log_new_affiliations",
        "Callaway-Sant'Anna",
        "#2F7D32",
    )
    dfs = [twfe, cs]
    bounds = pd.concat(dfs, ignore_index=True)[["conf.low", "conf.high"]].to_numpy().ravel()
    max_abs = max(0.15, math.ceil(float(max(abs(bounds))) / 0.05) * 0.05)

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.5), sharey=True)
    for ax, df in zip(axes, dfs):
        color = df["color"].iloc[0]
        ax.axhline(0, color="0.35", linewidth=0.9)
        ax.axvline(0, color="0.55", linestyle="dotted", linewidth=0.9)
        ax.errorbar(
            df["event_time"],
            df["estimate"],
            yerr=[df["estimate"] - df["conf.low"], df["conf.high"] - df["estimate"]],
            fmt="o",
            linestyle="-",
            color=color,
            ecolor=color,
            elinewidth=1.1,
            linewidth=1.1,
            markersize=5.5,
            capsize=0,
        )
        ax.set_title(df["estimator"].iloc[0])
        ax.set_xlim(-8.5, 8.5)
        ax.set_xticks(PLOT_EVENT_TIMES)
        ax.set_ylim(-max_abs, max_abs)
        ax.set_yticks([round(-max_abs + i * 0.05, 2) for i in range(int(round((2 * max_abs) / 0.05)) + 1)])
        ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
        ax.set_xlabel("Distance to treatment")
        ax.grid(True, which="major", axis="both", color="#D9D9D9", linewidth=0.8)
        for side in ["top", "right", "bottom", "left"]:
            ax.spines[side].set_visible(True)
            ax.spines[side].set_linewidth(0.6)
            ax.spines[side].set_color("black")

    axes[0].set_ylabel("")
    fig.tight_layout()
    save_pdf_png(fig, COMPARISON_DIR / "comparison")
    plt.close(fig)


def main() -> None:
    TABLE_MAIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TABLE_MAIN_PATH.write_text(build_main_table(), encoding="utf-8")
    TABLE_ROBUSTNESS_PATH.write_text(build_robustness_table(), encoding="utf-8")
    build_comparison_figure()
    print(f"Wrote {TABLE_MAIN_PATH.relative_to(ROOT)}")
    print(f"Wrote {TABLE_ROBUSTNESS_PATH.relative_to(ROOT)}")
    print(f"Wrote {(COMPARISON_DIR / 'comparison.pdf').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
