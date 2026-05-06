# TSE Eleitorado Education-Gender Notes

## Scope

This note documents the construction of a municipality-by-education-by-gender electorate panel from official TSE historical `perfil_eleitorado` files. The target output is a harmonized panel with IBGE municipality identifiers and stable cross-year categories for education and gender.

## Source Inventory

- Official source family: TSE open-data catalog at `https://dadosabertos.tse.jus.br`
- Historical package naming pattern confirmed in the catalog: `eleitorado-{year}`
- Main resource naming pattern confirmed in the catalog: `Eleitorado - {year}`
- Main download URL pattern confirmed in the official resources: `https://cdn.tse.jus.br/estatistica/sead/odsele/perfil_eleitorado/perfil_eleitorado_{year}.zip`

The build writes the full year-by-year inventory to `data/interim/tse_eleitorado/source_index.csv`.

## Coverage Notes

The official historical TSE open-data catalog exposes separate `eleitorado` packages for even years from 2000 through 2018. During source discovery, no separate historical package was found in the official catalog for odd years in that range. Those years are recorded in `source_index.csv` as unavailable rather than imputed.

The resulting final panel therefore covers the official historical snapshot years:

- 2000
- 2002
- 2004
- 2006
- 2008
- 2010
- 2012
- 2014
- 2016
- 2018

## Schema Notes

The raw `perfil_eleitorado` files include more dimensions than the final dataset requires. Across the inspected files, the core variables needed for this project are:

- election year,
- UF,
- TSE municipality code,
- municipality name,
- education label,
- gender label,
- electorate count.

Additional columns vary by year and may include biometric-status fields, age brackets, marital status, race/color, identity-related fields, and voting-obligation fields. The parser aggregates over these extra dimensions when building the municipality-by-education-by-gender panel.

Observed pattern in this build:

- 2000-2006 files include biometric-status fields alongside the core variables.
- 2008-2016 files include race/color, identity-related fields, and voting-obligation fields in addition to the core variables.
- 2018 returns to the leaner schema with biometric-status fields and without the extra race/identity/voting-obligation columns seen in 2008-2016.

The year-by-year schema inventory is written to `data/interim/tse_eleitorado/schema_by_year.csv`.

## Education Recoding Logic

The parser preserves the original TSE label in `education_raw` and maps it to one of the following stable categories:

- `illiterate`
- `reads_and_writes`
- `incomplete_primary`
- `complete_primary`
- `incomplete_secondary`
- `complete_secondary`
- `incomplete_higher`
- `complete_higher`
- `unknown`

The recoding is based on normalized TSE labels. Labels equivalent to `ANALFABETO`, `LÊ E ESCREVE`, `ENSINO FUNDAMENTAL INCOMPLETO`, `ENSINO FUNDAMENTAL COMPLETO`, `ENSINO MÉDIO INCOMPLETO`, `ENSINO MÉDIO COMPLETO`, `SUPERIOR INCOMPLETO`, and `SUPERIOR COMPLETO` are mapped directly. Missing, `#NE`, and `NÃO INFORMADO` values are mapped to `unknown`.

## Gender Recoding Logic

The parser preserves the original TSE label in `gender_raw` and maps it to:

- `male`
- `female`
- `unknown`

`MASCULINO` maps to `male`, `FEMININO` maps to `female`, and missing or non-informative labels map to `unknown`.

## Municipality Matching Notes

The main municipality harmonization path is the year-specific code join:

- `year`
- `state`
- `tse_municipality_id`

using `data/raw/ibge/bd-tse_mun_ids.csv`.

This is preferred over name matching because the raw TSE electorate files already contain a municipality code. Name-based matching is treated as fallback only, constrained within state, and should be documented explicitly in `data/interim/tse_eleitorado/municipality_crosswalk_review.csv`.

Where available, an official IBGE municipality name table can be used to validate that the final `municipality_id` corresponds to the expected municipality name and UF.

Observed matching results in this build:

- Most municipality rows match directly on `year + state + tse_municipality_id`.
- A small number of rows required exact normalized name fallback within state because the year-specific crosswalk lacked the direct code mapping.
- The remaining unmatched rows are all `ZZ` locations corresponding to overseas voting places rather than Brazilian municipalities, so they are preserved in the review table but excluded from the final municipality panel.

## Caveats

- Odd years from 2001 through 2017 are not exposed as separate historical `eleitorado` packages in the official TSE open-data catalog that was queried for this build.
- The raw files are highly granular. The final output sums across dimensions not requested by the project, including zone and age.
- Cross-year comparability depends on stable interpretation of education labels. Any year-specific label changes should be checked against `schema_by_year.csv` and the raw distinct labels before analysis.
- The review table includes `ZZ` overseas units because they appear in the raw TSE extracts. They are not municipality observations and therefore do not appear in the final panel.

## Recommended Use

- Treat the final file as a panel over official historical snapshot years rather than as a complete annual calendar-year panel unless a separate official source for the missing odd years is added later.
- When using the panel for empirical work, document that municipality identifiers come from the year-specific TSE-to-IBGE crosswalk in the repository.
- Re-check yearly totals against the raw files before publishing tables or figures.

## Biometric Shares by Education

The raw `perfil_eleitorado` files also include `QT_ELEITORES_BIOMETRIA`, which can be aggregated with `QT_ELEITORES_PERFIL` to construct municipality-year biometric-registration shares. The project builds these with `src/analysis/build_tse_biometric_education_shares.py`.

Clean output:

- `data/clean/tse_eleitorado/eleitorado_biometric_shares_2000_2018.csv`
- `data/clean/tse_eleitorado/eleitorado_biometric_shares_2000_2018.parquet`

Variables:

- `pct_with_bvr`: biometric registered voters divided by all registered voters in the municipality-year.
- `pct_low_ed_with_bvr`: biometric registered low-education voters divided by all low-education voters in the municipality-year.
- `pct_high_ed_with_bvr`: biometric registered high-education voters divided by all high-education voters in the municipality-year.

The same low/high education definitions used in the main clean panel are used here. The raw biometric count is zero nationally in 2000-2012, even though official rollout sources identify early BVR municipalities in 2008, 2010, and 2012. To avoid falsely coding those early BVR municipalities as zero biometric-registration share, the derived share variables are set to missing for years where the raw biometric count is zero nationally. In this build, the biometric-share variables are populated for 2014, 2016, and 2018.
