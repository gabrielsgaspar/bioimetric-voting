from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from build_core_panel import build_core_panel
from build_requested_extract import build_requested_extract
from discover_lapop_sources import discover_sources
from download_lapop_brazil import download_waves
from save_outputs import save_build_log, save_core_outputs, save_notes
from utils import CORE_WAVES, OFFICIAL_WAVES, ensure_dirs, load_config
from validate_panel import validate_core_panel


def main(config_path: str) -> None:
    ensure_dirs()
    config = load_config(config_path)
    discover_sources()

    mode = config["mode"]
    if mode == "build_core":
        years = config.get("core_years", CORE_WAVES)
        download_waves(years)
        core, crosswalk, availability = build_core_panel()
        validation = validate_core_panel(core, crosswalk, availability)
        save_core_outputs(core)
        save_notes()
        save_build_log(
            {
                "wave_coverage": validation["wave_coverage"],
                "n_rows": len(core),
                "fully_comparable_variables": validation["fully_comparable_variables"],
                "partially_comparable_variables": validation["partially_comparable_variables"],
                "excluded_variables": validation["excluded_variables"],
                "bad_state_name_rows": validation["bad_state_name_rows"],
                "bad_municipality_name_rows": validation["bad_municipality_name_rows"],
            }
        )
        print(f"Built LAPOP Brazil core panel with {len(core)} rows.")
    elif mode == "extract_year":
        requested_year = int(config["requested_year"])
        requested_questions = list(config.get("requested_questions", []))
        output_path = config["output_path"]
        df = build_requested_extract(requested_year, requested_questions, output_path)
        print(f"Built requested LAPOP extract for {requested_year} with {len(df)} rows.")
    else:
        raise ValueError(f"Unsupported mode: {mode}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python run_lapop_harmonizer.py path/to/config.yml")
    main(sys.argv[1])
