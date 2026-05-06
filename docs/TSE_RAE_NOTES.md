# TSE RAE Data Pipeline Notes

## Source

- Dataset: TSE Open Data Portal, `RAE - Requerimento de alistamento eleitoral`.
- Catalog page: `https://dadosabertos.tse.jus.br/dataset/rae-requerimento-de-alistamento-eleitoral`.
- Scope in this build: annual `perfil_rae_{year}.zip` files for 2009 through 2020.
- Raw cache location: `data/raw/tse/rae/{year}/perfil_rae_{year}.zip`.
- Municipality-code lookup: official TSE `Codigos oficiais de UF e municipios segundo o TSE e o IBGE`, cached as `data/raw/tse/municipio_tse_ibge/municipio_tse_ibge.zip`.

## Build Script

- Script: `src/data/build_tse_rae.py`.
- Final output: `data/clean/tse/rae.parquet`.
- Interim yearly aggregates: `data/interim/tse/rae/rae_{year}_municipality_month_profile.parquet`.
- Source index: `data/interim/tse/rae/source_index.csv`.
- Build diagnostics: `data/interim/tse/rae/build_diagnostics.csv`.
- Municipality-ID lookup provenance: `data/interim/tse/rae/municipality_id_lookup_source.csv`.

Run from the repository root:

```powershell
python src/data/build_tse_rae.py
```

The script uses `requests` and `BeautifulSoup` to discover yearly download links from the live TSE catalog page. It caches raw ZIP files without overwriting existing raw files. If a cached raw file has a different byte size from the live TSE `Content-Length`, the script stops and asks the user to remove or quarantine that raw file before rebuilding.

The script also downloads the official TSE municipality-code lookup linking TSE municipality codes to IBGE municipality codes. The clean output uses the repository-standard `municipality_id` name for the 7-digit IBGE municipality code.

## Parsing Rules

- CSV delimiter: semicolon (`;`).
- Quote character: double quote (`"`).
- Documented encoding: `latin1`, following the `leiame.pdf` included in the ZIP packages.
- Null conventions:
  - `#NULO` becomes null for text fields and `-1` for numeric fields.
  - `#NE` becomes null for text fields and `-3` for numeric fields.

The sampled TSE RAE CSV byte streams use UTF-8 accent bytes despite the included `leiame.pdf` documenting Latin 1. The build opens the files with the documented `latin1` encoding and repairs the resulting UTF-8 mojibake in text labels when detected. Disable this with `--no-repair-mojibake` if exact documented-decoder output is needed for audit.

## Transformation

The raw RAE files are reported by electoral zone. The clean file keeps only:

- `year`
- `month`
- `state`
- `tse_municipality_id`
- `municipality_id`
- `municipality_name`
- `rae_operation`
- `gender`
- `age_group`
- `education`
- `num_rae`

The script groups by all retained fields except `num_rae`, thereby summing over `NR_ZONA` and any other omitted raw dimensions. Raw `QT_RAE` is exported as `num_rae` and summed within each municipality-month-demographic-operation profile.

The raw RAE names are aligned to the main dataset where a direct equivalent exists: `NR_ANO_REGISTRO` becomes `year`, `NR_MES_REGISTRO` becomes `month`, `SG_UF` becomes `state`, `CD_MUNICIPIO` becomes `tse_municipality_id`, `NM_MUNICIPIO` becomes `municipality_name`, `DS_TIPO_OPERACAO` becomes `rae_operation`, `DS_GENERO` becomes `gender`, `DS_FAIXA_ETARIA` becomes `age_group`, `DS_GRAU_ESCOLARIDADE` becomes `education`, and `QT_RAE` becomes `num_rae`.

`tse_municipality_id` is preserved as a string-like categorical field to keep TSE leading-zero municipality codes intact. `municipality_id` is stored as a string field with the 7-digit IBGE code. `municipality_name` and label fields are exported as categorical columns before Parquet writing to reduce file size.

The municipality-ID merge is based on raw `SG_UF + CD_MUNICIPIO`, after normalizing the TSE code by removing leading zeros. Rows with raw `SG_UF == ZZ` are overseas consular locations, not Brazilian municipalities, and are excluded from the clean and yearly interim Parquet outputs before aggregation. All retained Brazilian UF rows match to an IBGE municipality ID.

## Validation

For each year, the build diagnostics record raw row counts, excluded `ZZ` rows, retained row counts, aggregated row counts, raw `QT_RAE`/clean `num_rae` totals, rows with negative numeric null sentinels in `QT_RAE`, and rows with missing group keys. The script stops if aggregation changes the retained annual `num_rae` total or if final municipality-month-profile keys are duplicated.

## Current Build

The 2009-2020 build run on 2026-05-06 excludes all `SG_UF == ZZ` records and produced `data/clean/tse/rae.parquet` with:

- 32,191,265 municipality-month-profile rows.
- Total retained `num_rae`: 179,672,132.
- Excluded `SG_UF == ZZ` raw `QT_RAE`: 663,800.
- Year coverage: every year from 2009 through 2020.
- Duplicate final keys: 0.
- Rows with missing grouping keys in the raw required fields: 0.
- Rows with negative raw `QT_RAE`/clean `num_rae` null sentinels: 0.
- Brazilian UF rows with missing `municipality_id`: 0.
- Final rows with `SG_UF == ZZ`: 0.
- Final rows with missing `municipality_id`: 0.
- Unique nonmissing `municipality_id` values: 5,570.

Annual retained totals match annual aggregated totals exactly in `data/interim/tse/rae/build_diagnostics.csv`.
