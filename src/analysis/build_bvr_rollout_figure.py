from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FIRST_TREAT_CSV = ROOT / "data/clean/tse_bvr/municipality_bvr_first_treat.csv"
PANEL_PATH = ROOT / "data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.parquet"
OUTPUT_DIR = ROOT / "resources/context"
SUMMARY_CSV = OUTPUT_DIR / "bvr_rollout_summary.csv"
TEX_PATH = OUTPUT_DIR / "bvr_rollout_timeline.tex"


def build_summary() -> pd.DataFrame:
    panel = pd.read_parquet(
        PANEL_PATH,
        columns=[
            "municipality_id",
            "year_election",
            "strict_bvr",
            "hybrid",
            "any_bvr",
            "year_first_any_bvr",
            "year_first_strict_bvr",
            "year_first_hybrid_bvr",
        ],
    ).rename(columns={"year_election": "year", "hybrid": "hybrid_bvr"})
    panel = panel[panel["year"].between(2008, 2018)].drop_duplicates(["municipality_id", "year"]).copy()

    summary = (
        panel.groupby("year", as_index=False)
        .agg(
            panel_municipalities=("municipality_id", "nunique"),
            strict_bvr_municipalities=("strict_bvr", "sum"),
            hybrid_bvr_municipalities=("hybrid_bvr", "sum"),
            any_bvr_municipalities=("any_bvr", "sum"),
        )
        .sort_values("year")
    )
    summary["no_bvr_municipalities"] = (
        summary["panel_municipalities"] - summary["any_bvr_municipalities"]
    )

    for regime, first_col in [
        ("any", "year_first_any_bvr"),
        ("strict", "year_first_strict_bvr"),
        ("hybrid", "year_first_hybrid_bvr"),
    ]:
        first_counts = (
            panel[["municipality_id", first_col]]
            .drop_duplicates("municipality_id")
            .query(f"{first_col} != 9999")
            .groupby(first_col)
            .size()
            .rename(f"new_{regime}_bvr_municipalities")
            .reset_index()
            .rename(columns={first_col: "year"})
        )
        summary = summary.merge(first_counts, how="left", on="year")

    count_cols = [
        "panel_municipalities",
        "strict_bvr_municipalities",
        "hybrid_bvr_municipalities",
        "any_bvr_municipalities",
        "no_bvr_municipalities",
        "new_strict_bvr_municipalities",
        "new_hybrid_bvr_municipalities",
        "new_any_bvr_municipalities",
    ]
    for col in count_cols:
        summary[col] = summary[col].fillna(0).astype(int)

    summary["strict_bvr_share_panel"] = (
        summary["strict_bvr_municipalities"] / summary["panel_municipalities"]
    )
    summary["hybrid_bvr_share_panel"] = (
        summary["hybrid_bvr_municipalities"] / summary["panel_municipalities"]
    )
    summary["any_bvr_share_panel"] = (
        summary["any_bvr_municipalities"] / summary["panel_municipalities"]
    )

    return summary[
        [
            "year",
            "panel_municipalities",
            "strict_bvr_municipalities",
            "hybrid_bvr_municipalities",
            "any_bvr_municipalities",
            "no_bvr_municipalities",
            "new_strict_bvr_municipalities",
            "new_hybrid_bvr_municipalities",
            "new_any_bvr_municipalities",
            "strict_bvr_share_panel",
            "hybrid_bvr_share_panel",
            "any_bvr_share_panel",
        ]
    ]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = build_summary()
    summary.to_csv(SUMMARY_CSV, index=False)

    treatment = pd.read_csv(FIRST_TREAT_CSV)
    timeline_summary = (
        treatment.groupby("year_first_treat")
        .size()
        .rename("new_treated")
        .sort_index()
        .reset_index()
    )

    x_positions = [0.8 + 2.55 * idx for idx in range(len(timeline_summary))]
    max_new = float(timeline_summary["new_treated"].max())
    min_height = 0.55
    max_height = 2.65

    nodes = []
    for x_pos, row in zip(x_positions, timeline_summary.itertuples(index=False)):
        height = min_height + (max_height - min_height) * ((row.new_treated / max_new) ** 0.5)
        label_y = height + 0.34
        count_label = f"{int(row.new_treated):,}"
        nodes.append(
            "\n".join(
                [
                    rf"\draw[line width=0.9pt] ({x_pos:.2f},0.12) -- ({x_pos:.2f},-0.12);",
                    rf"\filldraw[fill=BVRBlue, draw=BVRBlue] ({x_pos:.2f},0) circle (0.06);",
                    rf"\draw[BVRBlue, line width=1.2pt] ({x_pos:.2f},0.18) -- ({x_pos:.2f},{height:.2f});",
                    (
                        r"\node[anchor=south, draw=BVRBlue, fill=BVRBlue!10, rounded corners=2pt, "
                        r"minimum width=1.25cm, inner sep=3.5pt, text=BVRBlue, font=\bfseries\small] "
                        rf"at ({x_pos:.2f},{label_y:.2f}) {{{count_label}}};"
                    ),
                    rf"\node[anchor=north, font=\small] at ({x_pos:.2f},-0.33) {{{int(row.year_first_treat)}}};",
                ]
            )
        )

    tex = "\n".join(
        [
            r"\begin{tikzpicture}[x=1cm,y=1cm]",
            r"\definecolor{BVRBlue}{HTML}{2C5A8A}",
            r"\draw[line width=1.1pt, ->] (0,0) -- (13.9,0);",
            *nodes,
            r"\end{tikzpicture}",
            "",
        ]
    )
    TEX_PATH.write_text(tex)

    print(f"Wrote {SUMMARY_CSV}")
    print(f"Wrote {TEX_PATH}")


if __name__ == "__main__":
    main()
