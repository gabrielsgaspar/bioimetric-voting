from __future__ import annotations

import argparse

import pandas as pd

import build_downstream_outcomes_panel as downstream


def merge_outcomes(panel: pd.DataFrame, updates: pd.DataFrame) -> pd.DataFrame:
    if updates.empty:
        return panel
    key = ["year_election", "municipality_id"]
    outcome_cols = [col for col in updates.columns if col not in key]
    out = panel.drop(columns=[col for col in outcome_cols if col in panel.columns]).merge(updates, on=key, how="left")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--download-detail", action="store_true")
    parser.add_argument("--download-candidate", action="store_true")
    parser.add_argument("--party-only", action="store_true")
    parser.add_argument("--candidate-only", action="store_true")
    args = parser.parse_args()

    panel = pd.read_parquet(downstream.OUTPUT_PATH)
    crosswalk, _ = downstream.get_crosswalk()
    source_index = downstream.fetch_tse_results_resource_index()

    if args.download_detail:
        detail_df = downstream.build_tse_turnout_blanknull(source_index, crosswalk, download_missing=True)
        panel = merge_outcomes(panel, detail_df)

    if args.download_candidate or args.party_only:
        party_df = downstream.build_tse_party_presidential_outcomes(source_index, crosswalk, download_missing=True)
        panel = merge_outcomes(panel, party_df)

    if args.download_candidate or args.candidate_only:
        candidate_df = downstream.build_tse_candidate_outcomes(source_index, crosswalk, download_missing=True)
        panel = merge_outcomes(panel, candidate_df)

    panel.to_parquet(downstream.OUTPUT_PATH, index=False)
    print(f"Wrote {downstream.OUTPUT_PATH}")


if __name__ == "__main__":
    main()
