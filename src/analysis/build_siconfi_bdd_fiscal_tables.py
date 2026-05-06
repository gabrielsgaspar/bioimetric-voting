from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = ROOT / "resources" / "did" / "siconfi_bdd"
MAIN_TABLE_PATH = ROOT / "resources" / "tables" / "siconfi_bdd_fiscal_outcomes_main_table.tex"
ROBUSTNESS_TABLE_PATH = ROOT / "resources" / "tables" / "siconfi_bdd_fiscal_outcomes_robustness.tex"
EVENT_TIMES = [-4, -2, 0, 2, 4, 6]

OUTCOME_LABELS = {
    "health_spending_pc": "Health spending",
    "education_spending_pc": "Education spending",
    "social_assistance_pc": "Social assistance",
    "total_spending_pc": "Total spending",
    "agriculture_pc": "Agriculture",
    "investment_spending_pc": "Investment spending",
    "IPTU_pc": "IPTU",
    "ISS_pc": "ISS",
    "total_tax_revenue_pc": "Total tax revenue",
    "FPM_transfers_pc": "FPM transfers",
    "SUS_transfers_pc": "SUS transfers",
    "personnel_spending_pc": "Personnel spending",
    "debt_service_pc": "Debt service",
}

OUTCOME_ORDER = [
    "health_spending_pc",
    "education_spending_pc",
    "social_assistance_pc",
    "total_spending_pc",
    "agriculture_pc",
    "investment_spending_pc",
    "IPTU_pc",
    "ISS_pc",
    "total_tax_revenue_pc",
    "FPM_transfers_pc",
    "SUS_transfers_pc",
    "personnel_spending_pc",
    "debt_service_pc",
]

ESTIMATOR_PANELS = [
    ("twfe_dynamic", "Dynamic TWFE"),
    ("callaway_santanna", "Callaway-Sant'Anna"),
    ("bjs", "BJS"),
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


def fmt_est(value: float | None, p_value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{value:.3f}{stars(p_value)}"


def fmt_se(value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"({value:.3f})"


def load_event_study(spec: str, outcome: str, estimator: str) -> pd.DataFrame | None:
    path = BASE_DIR / spec / outcome / estimator / "event_study_estimates.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if "event_time" not in df.columns:
        return None
    df["event_time"] = pd.to_numeric(df["event_time"], errors="coerce")
    return df.set_index("event_time")


def available_outcomes() -> list[str]:
    present = {
        path.parent.parent.name
        for path in (BASE_DIR / "baseline").glob("*/twfe_dynamic/event_study_estimates.csv")
    }
    return [outcome for outcome in OUTCOME_ORDER if outcome in present]


def build_main_table() -> str:
    outcomes = available_outcomes()
    if not outcomes:
        return "% SICONFI BDD fiscal outcomes table not available yet.\n"

    lines = [
        r"\begin{table}[htbp]",
        r"    \caption{Fiscal Downstream Outcomes from the Base dos Dados SICONFI Extension}",
        r"    \label{tab:siconfi-bdd-fiscal-main}",
        r"    \centering",
        r"    \scriptsize",
        r"    \renewcommand{\arraystretch}{1.05}",
    ]

    for estimator, panel_label in ESTIMATOR_PANELS:
        studies = {outcome: load_event_study("baseline", outcome, estimator) for outcome in outcomes}
        lines.extend(
            [
                r"    \vspace{0.6em}",
                f"    \\textit{{Panel: {panel_label}}}",
                r"    \resizebox{\textwidth}{!}{%",
                "    \\begin{tabular}{l" + "c" * len(EVENT_TIMES) + "}",
                r"        \doubletoprule",
                r"        Outcome & $-4$ & $-2$ & $0$ & $2$ & $4$ & $6$ \\",
                r"        \midrule",
            ]
        )
        for outcome in outcomes:
            est_cells = []
            se_cells = []
            study = studies[outcome]
            for event_time in EVENT_TIMES:
                if study is None or event_time not in study.index:
                    est_cells.append("")
                    se_cells.append("")
                    continue
                row = study.loc[event_time]
                est_cells.append(fmt_est(row.get("estimate"), row.get("p.value")))
                se_cells.append(fmt_se(row.get("std.error")))
            lines.append("        " + OUTCOME_LABELS.get(outcome, outcome) + " & " + " & ".join(est_cells) + r" \\")
            lines.append("        " + " " + " & " + " & ".join(se_cells) + r" \\")
        lines.extend(
            [
                r"        \doublebottomrule",
                r"    \end{tabular}",
                r"    }",
            ]
        )

    lines.extend(
        [
            r"    \vspace{0.8em}",
            r"    \begin{minipage}{\textwidth}",
            r"        {\footnotesize \textbf{Note:} The table reports baseline unweighted event-study coefficients at selected horizons from the Base dos Dados fiscal panel. Event time is measured relative to first biometric adoption. Dynamic TWFE omits event time $-2$ as the reference period; the corresponding Callaway-Sant'Anna and BJS rows are shown on the same event-time grid using their stored dynamic estimates. Fiscal outcomes are log transformed as $\log(1 + x)$ after winsorization at the 1st and 99th percentiles. $^{*} p<0.10$, $^{**} p<0.05$, $^{***} p<0.01$. \par}",
            r"    \end{minipage}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def build_robustness_table() -> str:
    outcomes = available_outcomes()
    if not outcomes:
        return "% SICONFI BDD fiscal robustness table not available yet.\n"

    significant = []
    for outcome in outcomes:
        study = load_event_study("baseline", outcome, "twfe_dynamic")
        if study is None or 0 not in study.index:
            continue
        row = study.loc[0]
        if pd.notna(row.get("p.value")) and row.get("p.value") < 0.10:
            significant.append(outcome)

    if not significant:
        significant = outcomes[:4]

    spec_labels = [
        ("baseline", "Baseline"),
        ("state_year_fe", "State x year FE"),
        ("population_weighted", "Population weighted"),
        ("nonhybrid", "Non-hybrid"),
    ]

    lines = [
        r"\begin{table}[htbp]",
        r"    \caption{TWFE Fiscal Robustness Checks at Event Time $0$}",
        r"    \label{tab:siconfi-bdd-fiscal-robustness}",
        r"    \centering",
        r"    \scriptsize",
        r"    \renewcommand{\arraystretch}{1.05}",
        "    \\begin{tabular}{l" + "c" * len(spec_labels) + "}",
        r"        \doubletoprule",
        "        Outcome & " + " & ".join(label for _, label in spec_labels) + r" \\",
        r"        \midrule",
    ]

    for outcome in significant:
        est_cells = []
        se_cells = []
        for spec, _ in spec_labels:
            study = load_event_study(spec, outcome, "twfe_dynamic")
            if study is None or 0 not in study.index:
                est_cells.append("")
                se_cells.append("")
                continue
            row = study.loc[0]
            est_cells.append(fmt_est(row.get("estimate"), row.get("p.value")))
            se_cells.append(fmt_se(row.get("std.error")))
        lines.append("        " + OUTCOME_LABELS.get(outcome, outcome) + " & " + " & ".join(est_cells) + r" \\")
        lines.append("        " + " " + " & " + " & ".join(se_cells) + r" \\")

    lines.extend(
        [
            r"        \doublebottomrule",
            r"    \end{tabular}",
            r"    \vspace{0.8em}",
            r"    \begin{minipage}{\textwidth}",
            r"        {\footnotesize \textbf{Note:} The robustness table compares the event-time-$0$ TWFE estimate across the baseline, state-by-year fixed-effects, population-weighted, and non-hybrid specifications. Outcomes enter in $\log(1 + x)$ form after winsorization. $^{*} p<0.10$, $^{**} p<0.05$, $^{***} p<0.01$. \par}",
            r"    \end{minipage}",
            r"\end{table}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    MAIN_TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MAIN_TABLE_PATH.write_text(build_main_table(), encoding="utf-8")
    ROBUSTNESS_TABLE_PATH.write_text(build_robustness_table(), encoding="utf-8")


if __name__ == "__main__":
    main()
