from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils import CLEAN_DIR, DOCS_DIR, INTERIM_DIR, LOG_DIR, save_dataframe


NOTES_TEMPLATE = """# LAPOP Brazil Harmonization Notes

## Official Source Inventory

- Official public data access page: `https://www.vanderbilt.edu/lapop/raw-data.php`
- Official Brazil public dataset pages and direct files are indexed in `data/interim/lapop/source_inventory.csv`.
- Official public Brazil waves confirmed for this harmonizer are: 2008, 2010, 2012, 2014, 2017, 2019, 2021.

## Wave Coverage

- The comparable core uses the actual public Brazil survey years 2008, 2010, 2012, 2014, 2017, 2019.
- There is no official public Brazil 2020 wave in the LAPOP catalog.
- `2019` is not relabeled as `2020`.
- `2021` is supported for requested-year extracts but is not part of the `2008-2019` comparable core.

## Notebook Relevance

The harmonized core is designed for the notebook workflow that:

- builds respondent-level trust and democracy measures,
- preserves state and municipality fields for later merges,
- and links respondents to municipality-level BVR exposure and covariates.

## Trust Variables

Preferred trust items:

- `b2` -> `trust_inst_respect`
- `b3` -> `trust_rights_protected`
- `b4` -> `trust_proud_system`
- `b6` -> `trust_support_system`
- `b21` -> `trust_parties`
- `b21a` -> `trust_president`
- `b32` -> `trust_municipal_gov`
- `b47` in 2008 and 2010, and `b47a` from 2012 onward -> `trust_elections`

### b47 versus b47a

- 2008 and 2010 use `b47`.
- 2012 onward uses `b47a`.
- The harmonizer maps both to `trust_elections` after verifying the actual official wave files.

## Democracy Variables

Preferred democracy items:

- `ing4` -> `democracy_best_form`
- `pn4` -> `democracy_satisfaction`
- `eff1` -> `democracy_voice_matters`

Optional retained item:

- `eff2` -> `democracy_understands_politics`

`eff2` is not part of the preferred 3-item democracy index unless explicitly requested.

## Education Harmonization

- For the 2008-2019 core, `ed` behaves as a years-of-schooling style variable and is preserved in `education_years_raw`.
- A conservative categorical mapping is created:
  - `less_than_secondary` for 0-10 years
  - `secondary` for 11-12 years
  - `tertiary` for 13+ years
- This mapping is project-facing and should be treated as a documented harmonization choice rather than as an official LAPOP category.
- The 2021 file uses `edr`, a broader education-category variable, so 2021 is not folded into the 2008-2019 comparable education-years core.

## Race Comparability Caveats

- `etid` is used to create `white_raw`.
- The binary `white` indicator is coded as 1 for category code 1 and 0 for other substantive race/self-identification categories.
- This is acceptable for a white versus non-white split, but the detailed non-white categories vary in naming across languages and waves.

## Location Caveats

- State and municipality identifiers are often numeric with LAPOP value labels rather than direct text.
- The harmonizer decodes those labels and also stores normalized lowercase ASCII versions.
- This skill does not assign municipality IDs; it only harmonizes survey-side state and municipality names.

## Variables Excluded From The Comparable Core

- `strata` is not available for the 2008-2019 core.
- `has_voter_title_raw` and `has_voter_title` were not promoted because the notebook alias could not be verified as a consistent voter-title item in the official files.
"""


def save_core_outputs(core: pd.DataFrame) -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    save_dataframe(core, CLEAN_DIR / "lapop_brazil_core_2008_2019.csv")
    save_dataframe(core, CLEAN_DIR / "lapop_brazil_core_2008_2019.parquet")


def save_notes() -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / "LAPOP_BRAZIL_HARMONIZATION_NOTES.md").write_text(NOTES_TEMPLATE, encoding="utf-8")


def save_build_log(summary: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    text = f"""# LAPOP Brazil Build Log

## Summary

- Core waves built: {summary['wave_coverage']}
- Core rows: {summary['n_rows']}
- Fully comparable variables: {len(summary['fully_comparable_variables'])}
- Partially comparable variables: {len(summary['partially_comparable_variables'])}
- Excluded variables: {len(summary['excluded_variables'])}
- Non-normalized state rows: {summary['bad_state_name_rows']}
- Non-normalized municipality rows: {summary['bad_municipality_name_rows']}

## Fully Comparable Variables

{", ".join(summary['fully_comparable_variables'])}

## Partially Comparable Variables

{", ".join(summary['partially_comparable_variables'])}

## Excluded Variables

{", ".join(summary['excluded_variables'])}
"""
    (LOG_DIR / "lapop_brazil_build_log.md").write_text(text, encoding="utf-8")
