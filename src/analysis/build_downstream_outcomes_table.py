from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = ROOT / "resources" / "tables" / "downstream_outcomes_table.tex"
ESTIMATOR_DIR = ROOT / "resources" / "did" / "downstream_outcomes" / "unweighted"
PANEL_PATH = ROOT / "data" / "clean" / "downstream" / "downstream_outcomes_panel.parquet"
EVENT_TIMES = [-8, -6, -4, 0, 2, 4, 6, 8]
OUTCOME_ORDER = [
    "turnout",
    "blank_null_rate",
    "PT_vote_share_president",
    "PSDB_vote_share_president",
    "effective_number_of_candidates_mayor",
    "margin_of_victory_mayor",
    "incumbent_mayor_reelection",
    "health_spending_per_capita",
    "education_spending_per_capita",
    "social_assistance_spending_per_capita",
    "total_discretionary_spending_per_capita",
    "IPTU_collection_per_capita",
    "FPM_transfers_per_capita",
    "infant_mortality_rate",
    "pre_natal_7plus_visits_share",
    "bolsa_familia_coverage",
]
OUTCOME_LABELS = {
    "turnout": "Turnout",
    "blank_null_rate": "Blank/null rate",
    "PT_vote_share_president": "PT vote share",
    "PSDB_vote_share_president": "PSDB vote share",
    "effective_number_of_candidates_mayor": "ENP mayor",
    "margin_of_victory_mayor": "Mayor margin",
    "incumbent_mayor_reelection": "Mayor reelected",
    "health_spending_per_capita": "Health spend pc",
    "education_spending_per_capita": "Education spend pc",
    "social_assistance_spending_per_capita": "Social assist. pc",
    "total_discretionary_spending_per_capita": "Discretionary spend pc",
    "IPTU_collection_per_capita": "IPTU pc",
    "FPM_transfers_per_capita": "FPM pc",
    "infant_mortality_rate": "Infant mortality",
    "pre_natal_7plus_visits_share": "Prenatal 7+ share",
    "bolsa_familia_coverage": "Bolsa Familia cover.",
}


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


def fmt_est(value: float | None, p_value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{value:.3f}{stars(p_value)}"


def fmt_se(value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"({value:.3f})"


def load_available_outcomes() -> list[str]:
    df = pd.read_parquet(PANEL_PATH)
    available = {
        path.parent.parent.name
        for path in sorted(ESTIMATOR_DIR.glob("*/twfe_dynamic/event_study_estimates.csv"))
        if path.exists()
    }
    return [outcome for outcome in OUTCOME_ORDER if outcome in available and outcome in df.columns and df[outcome].notna().any()]


def load_event_study(outcome: str) -> pd.DataFrame:
    path = ESTIMATOR_DIR / outcome / "twfe_dynamic" / "event_study_estimates.csv"
    df = pd.read_csv(path)
    df["event_time"] = pd.to_numeric(df["event_time"], errors="coerce")
    return df.set_index("event_time")


def build_table() -> str:
    outcomes = load_available_outcomes()
    if not outcomes:
        return "% Downstream outcomes table not available yet.\n"

    studies = {outcome: load_event_study(outcome) for outcome in outcomes}
    lines = [
        r"\begin{table}[htbp]",
        r"    \caption{Dynamic TWFE Estimates for Downstream Outcomes}",
        r"    \label{tab:downstream-outcomes-main}",
        r"    \centering",
        r"    \scriptsize",
        r"    \renewcommand{\arraystretch}{1.05}",
        r"    \resizebox{\textwidth}{!}{%",
        "    \\begin{tabular}{l" + "c" * len(outcomes) + "}",
        r"        \doubletoprule",
        "        Years relative to BVR adoption & " + " & ".join(OUTCOME_LABELS.get(outcome, outcome) for outcome in outcomes) + r" \\",
        r"        \midrule",
    ]

    for event_time in EVENT_TIMES:
        est_cells = []
        se_cells = []
        for outcome in outcomes:
            row = studies[outcome].loc[event_time]
            est_cells.append(fmt_est(row["estimate"], row.get("p.value")))
            se_cells.append(fmt_se(row["std.error"]))
        lines.append("        " + f"${event_time}$ & " + " & ".join(est_cells) + r" \\")
        lines.append("        " + " & " + " & ".join(se_cells) + r" \\")

    lines.extend(
        [
            r"        \doublebottomrule",
            r"    \end{tabular}",
            r"    }",
            r"    \vspace{0.8em}",
            r"    \begin{minipage}{\textwidth}",
            r"        {\footnotesize \textbf{Note:} Event time is measured in years relative to first biometric adoption, with event time $-2$ omitted as the reference period. Standard errors are clustered by municipality and election year. Only outcomes with non-missing supporting data in the current build are shown here. $^{*} p<0.10$, $^{**} p<0.05$, $^{***} p<0.01$. \par}",
            r"    \end{minipage}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_table(), encoding="utf-8")


if __name__ == "__main__":
    main()
