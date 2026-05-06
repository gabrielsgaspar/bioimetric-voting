from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = Path(__file__).resolve().parent
FIGURE_DIR = ROOT / "resources" / "decomposition" / "figures"
TABLE_DIR = ROOT / "paper" / "tables" / "decomposition"
FIGURE_DATA_DIR = ROOT / "data" / "clean" / "decomposition" / "figure_data"

FIGURES = [
    {
        "number": 1,
        "filename": "figure_01_stacked_decomposition_by_regime",
        "title": "Registry impacts decompose into exit and re-labeling",
        "description": "Stacked exit and Scenario B re-labeling rates for strict- and hybrid-first municipalities.",
        "command": [sys.executable, str(SCRIPT_DIR / "figure_01_stacked_decomposition_by_regime.py")],
        "data": "figure_01_data.parquet",
    },
    {
        "number": 2,
        "filename": "figure_02_binned_scatter_exit_lowed",
        "title": "Municipal exit rises with baseline low-education share",
        "description": "Weighted decile binned scatter of municipality exit rates against 2008 low-education shares by regime.",
        "command": [sys.executable, str(SCRIPT_DIR / "figure_02_binned_scatter_exit_lowed.py")],
        "data": "figure_02_data.parquet",
    },
    {
        "number": 3,
        "filename": "figure_03_state_scatter_exit_lowed",
        "title": "State exit rates track baseline low-education shares",
        "description": "State-level scatter linking treated-municipality exit rates to baseline low-education shares.",
        "command": [sys.executable, str(SCRIPT_DIR / "figure_03_state_scatter_exit_lowed.py")],
        "data": "figure_03_data.parquet",
    },
    {
        "number": 4,
        "filename": "figure_04_interaction_coefficients",
        "title": "Strict x low-ed coefficients",
        "description": "Coefficient plot for strict x low-education-share interactions across three weighted specifications.",
        "command": ["Rscript", str(SCRIPT_DIR / "figure_04_interaction_coefficients.R")],
        "data": "figure_04_data.parquet",
    },
    {
        "number": 5,
        "filename": "figure_05_share_by_age_band",
        "title": "Exit and re-labeling concentrate in different age bands",
        "description": "Age-band shares of total exit and Scenario B re-labeling with 2008 population-share references.",
        "command": [sys.executable, str(SCRIPT_DIR / "figure_05_share_by_age_band.py")],
        "data": "figure_05_data.parquet",
    },
    {
        "number": 6,
        "filename": "figure_06_municipality_scatter_exit_lowed",
        "title": "Municipal exit rates track baseline low-education shares",
        "description": "Municipality-level bubble scatter linking exit rates to baseline low-education shares, colored by region.",
        "command": [sys.executable, str(SCRIPT_DIR / "figure_06_municipality_scatter_exit_lowed.py")],
        "data": "figure_06_data.parquet",
    },
]


def write_metadata() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    metadata = pd.DataFrame(
        [
            {
                "figure": item["number"],
                "filename": item["filename"],
                "title": item["title"],
                "description": item["description"],
            }
            for item in FIGURES
        ]
    )
    metadata.to_csv(FIGURE_DIR / "figures_metadata.csv", index=False)


def validate_outputs() -> None:
    missing: list[Path] = []
    for item in FIGURES:
        base = item["filename"]
        for suffix in ["", "_notitle"]:
            for extension in [".pdf", ".png"]:
                path = FIGURE_DIR / f"{base}{suffix}{extension}"
                if not path.exists():
                    missing.append(path)
        data_path = FIGURE_DATA_DIR / item["data"]
        if not data_path.exists():
            missing.append(data_path)
    table_path = TABLE_DIR / "table_compositional_regressions.tex"
    if not table_path.exists():
        missing.append(table_path)
    if missing:
        missing_list = "\n".join(str(path.relative_to(ROOT)) for path in missing)
        raise RuntimeError(f"Missing expected outputs:\n{missing_list}")


def print_summary() -> None:
    print("\nCompleted decomposition Section 5.5 outputs.")
    print("\nFigures produced:")
    for item in FIGURES:
        print(f"- {item['filename']} (.pdf/.png and _notitle variants)")

    print("\nFigure data saved:")
    for item in FIGURES:
        print(f"- data/clean/decomposition/figure_data/{item['data']}")
    print("- data/clean/decomposition/figure_data/table_compositional_regressions_coefficients.parquet")

    print("\nRegression table saved:")
    print("- paper/tables/decomposition/table_compositional_regressions.tex")

    figure_04 = pd.read_parquet(FIGURE_DATA_DIR / "figure_04_data.parquet")
    print("\nFigure 4 headline coefficients:")
    for _, row in figure_04.iterrows():
        print(
            f"- {row['spec']}: {row['coefficient']:.4f} "
            f"(SE {row['se']:.4f}), n = {int(row['n_obs']):,}"
        )


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DATA_DIR.mkdir(parents=True, exist_ok=True)

    for item in FIGURES:
        print(f"\nRunning Figure {item['number']}: {item['filename']}")
        subprocess.run(item["command"], cwd=ROOT, check=True)

    write_metadata()
    validate_outputs()
    print_summary()


if __name__ == "__main__":
    main()
