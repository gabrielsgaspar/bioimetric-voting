from __future__ import annotations

import pandas as pd

import build_downstream_outcomes_panel as downstream


def main() -> None:
    panel = pd.read_parquet(downstream.OUTPUT_PATH)
    population = downstream.get_population_panel().rename(columns={"year": "year_election"})

    panel = panel.drop(columns=["population_estimate"], errors="ignore").merge(
        population,
        on=["municipality_id", "year_election"],
        how="left",
    )
    panel.loc[panel["population_estimate"] <= 1000, ["infant_mortality_rate", "neonatal_mortality_rate"]] = pd.NA
    panel.to_parquet(downstream.OUTPUT_PATH, index=False)
    print(f"Wrote {downstream.OUTPUT_PATH}")


if __name__ == "__main__":
    main()
