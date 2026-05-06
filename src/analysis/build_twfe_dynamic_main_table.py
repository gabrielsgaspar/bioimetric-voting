from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "clean" / "tse" / "tse_clean_panel_2000_2018.csv"
TWFE_DIR = ROOT / "resources" / "did" / "twfe_dynamic"
OUTPUT_PATH = ROOT / "resources" / "tables" / "twfe_dynamic_main_table.tex"

OUTCOMES = [
    ("log_num_voters", "Log voters"),
    ("pct_voters_low_ed", "Low education"),
    ("pct_voters_high_ed", "High education"),
]
EVENT_TIMES = [-8, -6, -4, 0, 2, 4, 6, 8]


def _stars(p_value: float | None) -> str:
    if p_value is None or pd.isna(p_value):
        return ""
    if p_value < 0.01:
        return "***"
    if p_value < 0.05:
        return "**"
    if p_value < 0.10:
        return "*"
    return ""


def _format_estimate(value: float | None, p_value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{value:.3f}{_stars(p_value)}"


def _format_se(value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"({value:.3f})"


def _load_event_study(outcome: str) -> pd.DataFrame:
    path = TWFE_DIR / outcome / "event_study_estimates.csv"
    df = pd.read_csv(path)
    df["event_time"] = pd.to_numeric(df["event_time"], errors="coerce")
    return df.set_index("event_time")


def _sample_moments() -> dict[str, dict[str, float | int]]:
    df = pd.read_csv(DATA_PATH)
    moments: dict[str, dict[str, float | int]] = {}
    for outcome, _ in OUTCOMES:
        series = pd.to_numeric(df[outcome], errors="coerce")
        moments[outcome] = {
            "mean": float(series.mean()),
            "sd": float(series.std()),
            "n": int(series.notna().sum()),
        }
    return moments


def _build_table() -> str:
    studies = {outcome: _load_event_study(outcome) for outcome, _ in OUTCOMES}
    moments = _sample_moments()

    lines = [
        r"\begin{table}[htbp]",
        r"    \caption{Dynamic TWFE Event-Study Estimates}",
        r"    \label{tab:twfe-dynamic-main}",
        r"    \centering",
        r"    \small",
        r"    \renewcommand{\arraystretch}{1.08}",
        r"    \begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}lccc}",
        r"        \doubletoprule",
        r"        Years relative to BVR adoption & Log voters & Low education & High education \\",
        r"        \midrule",
    ]

    for event_time in EVENT_TIMES:
        estimate_cells = []
        se_cells = []
        for outcome, _ in OUTCOMES:
            row = studies[outcome].loc[event_time]
            estimate_cells.append(_format_estimate(row["estimate"], row["p.value"]))
            se_cells.append(_format_se(row["std.error"]))

        lines.append(
            "        "
            + f"${event_time}$ & "
            + " & ".join(estimate_cells)
            + r" \\"
        )
        lines.append(
            r"        "
            + " "
            + " & ".join([""] + se_cells)
            + r" \\"
        )

    obs_row = []
    mean_row = []
    sd_row = []
    for outcome, _ in OUTCOMES:
        obs_row.append(f"{moments[outcome]['n']:,}")
        mean_row.append(f"{moments[outcome]['mean']:.3f}")
        sd_row.append(f"{moments[outcome]['sd']:.3f}")

    lines.extend(
        [
            r"        \midrule",
            r"        Municipality FE & \checkmark & \checkmark & \checkmark \\",
            r"        Election-year FE & \checkmark & \checkmark & \checkmark \\",
            "        Observations & " + " & ".join(obs_row) + r" \\",
            "        Mean dep. var. & " + " & ".join(mean_row) + r" \\",
            "        SD dep. var. & " + " & ".join(sd_row) + r" \\",
            r"        \doublebottomrule",
            r"    \end{tabular*}",
            r"    \vspace{1.1em}",
            r"    \begin{minipage}{\textwidth}",
            r"        {\footnotesize \textbf{Note:} Each column reports the dynamic TWFE event-study coefficients shown in the main-text figures. Event time is measured in years relative to the first biometric election, with event time $-2$ omitted as the reference period. Standard errors clustered by municipality and election year are reported in parentheses beneath the estimates. The dependent-variable means and standard deviations are computed from the municipality-election analysis sample. $^{*} p<0.10$, $^{**} p<0.05$, $^{***} p<0.01$. \par}",
            r"    \end{minipage}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(_build_table(), encoding="utf-8")


if __name__ == "__main__":
    main()
