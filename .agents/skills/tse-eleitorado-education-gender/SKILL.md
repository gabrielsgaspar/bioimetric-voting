---
name: tse-eleitorado-education-gender
description: Download, harmonize, and validate official TSE eleitorado data by municipality, education, and gender using the repo crosswalk from TSE municipality codes to IBGE municipality codes. Use when building or refreshing the 2000-2018 municipality x education x gender electorate panel.
---

# TSE Eleitorado Education-Gender

## Purpose

Use this skill to build a reproducible municipality-level electorate panel from official TSE `perfil_eleitorado` files, harmonized to IBGE municipality identifiers with stable education and gender categories.

The target analytical unit is:

- `year`
- `municipality_id`
- `municipality_name`
- `state`
- `education`
- `gender`

with `num_voters` equal to the total number of registered voters in that cell.

## Inputs

- Official TSE open-data historical electorate packages from `https://dadosabertos.tse.jus.br`
- Repo crosswalk at `data/raw/ibge/bd-tse_mun_ids.csv`
- Official IBGE municipality naming reference if available locally for validation

## Outputs

- `data/interim/tse_eleitorado/source_index.csv`
- `data/interim/tse_eleitorado/schema_by_year.csv`
- `data/interim/tse_eleitorado/municipality_crosswalk_review.csv`
- `data/clean/tse_eleitorado/eleitorado_education_gender_2000_2018.csv`
- `data/clean/tse_eleitorado/eleitorado_education_gender_2000_2018.parquet`
- `resources/logs/tse_eleitorado_build_log.md`

## Workflow

1. Run `src/data/download_tse_eleitorado.py`.
   - Query the TSE CKAN API for `eleitorado-{year}` packages.
   - Record the official resource URL, dataset page, filename, and format.
   - Preserve the original zip files under `data/raw/tse_eleitorado/{year}/`.
   - For years not exposed in the official historical catalog, record that explicitly in `source_index.csv`.

2. Run `src/cleaning/parse_tse_eleitorado.py`.
   - Inspect each raw zip and select the `perfil_eleitorado_{year}.csv` member.
   - Record the year-specific schema in `schema_by_year.csv`.
   - Parse only the fields needed for year, state, municipality, education, gender, and electorate totals.
   - Aggregate away extra dimensions such as zone, age, marital status, race, or biometric-status fields.
   - Save year-specific parsed parquet files in `data/interim/tse_eleitorado/`.

3. Run `src/cleaning/harmonize_tse_municipalities.py`.
   - Join TSE municipality codes to IBGE municipality codes with the repo crosswalk.
   - Match on `year + state + tse_municipality_id` first.
   - Use state-constrained name fallback only if the direct code join fails.
   - Save a municipality review table with match method, confidence, and notes.

4. Run `src/analysis/build_eleitorado_education_gender_panel.py`.
   - Append harmonized years.
   - Standardize the final columns and sort the panel.
   - Write the final CSV, parquet, and build log.

## Download Rules

- Prefer the TSE open-data CKAN API over ad hoc scraping.
- For each even historical package year, select the resource whose name matches the dataset title, e.g. `Eleitorado - 2018`.
- Preserve raw files exactly as downloaded.
- Use temporary download files and verify `content-length` before finalizing a raw file.

## Schema Inspection Rules

- Do not assume the schema is identical across all years.
- Capture the raw municipality code, municipality name, state, electorate count, education, and gender columns in `schema_by_year.csv`.
- Document extra columns but aggregate over them unless the final target dataset requires them.

## Harmonization Rules

### Municipality

- Normalize municipality names to lower-case ASCII with accents removed and whitespace compressed.
- Uppercase the UF code and validate it against the 27 official UFs.
- Prefer the year-specific code-based crosswalk from `bd-tse_mun_ids.csv`.
- Use name-based matching only as fallback, and only within state.
- Never assign an IBGE municipality code from fuzzy similarity alone without state confirmation and a written note.

### Education

Map TSE labels to these stable categories:

- `illiterate`
- `reads_and_writes`
- `incomplete_primary`
- `complete_primary`
- `incomplete_secondary`
- `complete_secondary`
- `incomplete_higher`
- `complete_higher`
- `unknown`

Preserve the original TSE label in `education_raw` during parsing.

### Gender

Map TSE labels to:

- `male`
- `female`
- `unknown`

Preserve the original TSE label in `gender_raw` during parsing.

## Validation Checklist

- Confirm which years are available as official historical TSE packages and which are not.
- Verify no duplicated final rows at `year + municipality_id + education + gender`.
- Verify `municipality_id` values come from the repo crosswalk or a documented fallback.
- Verify `state` is a valid UF.
- Verify `num_voters` is numeric and non-negative.
- Compare yearly national totals from the final panel to the raw file totals.
- Review unmatched municipalities and any fallback matches manually.

## Failure Modes

- The TSE catalog may not expose odd years as separate historical packages.
  - Record those years explicitly in `source_index.csv`; do not fabricate them.
- A raw zip may contain multiple members.
  - Use the `perfil_eleitorado_{year}.csv` member, not the `leiame.pdf`.
- Municipality code joins may fail for edge cases.
  - Escalate by checking the repo crosswalk for the same TSE code in adjacent years and by validating the municipality name within state.
- Category labels may change subtly over time.
  - Normalize labels and document the mapping logic in `docs/TSE_ELEITORADO_EDU_GENDER_NOTES.md`.
