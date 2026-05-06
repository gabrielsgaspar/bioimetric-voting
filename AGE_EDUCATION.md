# TSE Voter Age and Education Data

This note describes the age and education variables used from the official TSE
`perfil_eleitorado` files under `data/raw/tse_eleitorado/{year}/`.

## Raw Source

The source files are the official TSE `perfil_eleitorado_<year>.zip` packages.
The core raw fields used by this project are:

- `ANO_ELEICAO`: election year.
- `SG_UF`: state abbreviation.
- `CD_MUNICIPIO`: TSE municipality code.
- `NM_MUNICIPIO`: municipality name.
- `QT_ELEITORES_PERFIL`: number of voters in the profile cell.
- `DS_GRAU_ESCOLARIDADE`: raw education label.
- `DS_GENERO`: raw gender label.
- `CD_FAIXA_ETARIA`: raw age-bin code, used for the age-by-education panel.
- `DS_FAIXA_ETARIA`: raw age-bin label, used for the age-by-education panel.

Some years include extra fields such as biometric status, race/color, gender
identity, and voting-obligation type. The project aggregates over those extra
dimensions when building municipality-level age and education outcomes.

## Education

The raw education variable is `DS_GRAU_ESCOLARIDADE`. It is harmonized into:

- `illiterate`: labels equivalent to `ANALFABETO`.
- `reads_and_writes`: labels equivalent to `LE E ESCREVE`.
- `incomplete_primary`: labels equivalent to incomplete fundamental/first grade.
- `complete_primary`: labels equivalent to complete fundamental/first grade.
- `incomplete_secondary`: labels equivalent to incomplete secondary/high school.
- `complete_secondary`: labels equivalent to complete secondary/high school.
- `incomplete_higher`: labels equivalent to incomplete higher education.
- `complete_higher`: labels equivalent to complete higher education.
- `unknown`: missing, `#NE`, `NAO INFORMADO`, or non-informative labels.

For the main low/high education split:

- `low_ed`: `illiterate`, `reads_and_writes`, `incomplete_primary`, `complete_primary`.
- `high_ed`: `incomplete_secondary`, `complete_secondary`, `incomplete_higher`, `complete_higher`.
- `unknown_ed`: education not mapped to low or high education.

The education-by-gender panel is available for the official even-year TSE files
from 2000 through 2018.

## Age

The raw age variables are `CD_FAIXA_ETARIA` and `DS_FAIXA_ETARIA`. TSE reports
pre-binned age ranges, not exact ages. The raw age categories used here are:

- `1600`: 16 anos
- `1700`: 17 anos
- `1800`: 18 anos
- `1900`: 19 anos
- `2000`: 20 anos
- `2124`: 21 a 24 anos
- `2529`: 25 a 29 anos
- `3034`: 30 a 34 anos
- `3539`: 35 a 39 anos
- `4044`: 40 a 44 anos
- `4549`: 45 a 49 anos
- `5054`: 50 a 54 anos
- `5559`: 55 a 59 anos
- `6064`: 60 a 64 anos
- `6569`: 65 a 69 anos
- `7074`: 70 a 74 anos
- `7579`: 75 a 79 anos
- `8084`: 80 a 84 anos
- `8589`: 85 a 89 anos
- `9094`: 90 a 94 anos
- `9599`: 95 a 99 anos
- `9999`: 100 anos ou mais

The analysis groups whole raw TSE age bins by midpoint into four non-overlapping
age bands:

- `age_16_30`: 16, 17, 18, 19, 20, 21-24, 25-29.
- `age_31_45`: 30-34, 35-39, 40-44.
- `age_46_60`: 45-49, 50-54, 55-59.
- `age_60_plus`: 60-64, 65-69, 70-74, 75-79, 80-84, 85-89, 90-94, 95-99, 100+.

Usable age-bin data starts in 2008. In the 2000, 2002, 2004, and 2006 files,
the age field is only `#NE`, so those years are excluded from age-band outcomes.

## Clean Outputs and Coverage

The main clean age-by-education output is:

- `data/clean/tse_eleitorado/eleitorado_age_education_bands_2008_2018.parquet`
- `data/clean/tse_eleitorado/eleitorado_age_education_bands_2008_2018.csv`

It contains:

- years: 2008, 2010, 2012, 2014, 2016, 2018.
- municipalities: 5,570 unique Brazilian municipalities.
- municipality-year observations: 33,384.
- age bands: `age_16_30`, `age_31_45`, `age_46_60`, `age_60_plus`.
- education groups: `low_ed`, `high_ed`, `unknown_ed`.

Municipality IDs are harmonized to seven-digit IBGE municipality codes using
the repository TSE-to-IBGE crosswalk. Overseas `ZZ` rows in the raw TSE files are
not Brazilian municipalities and are excluded from the final municipality panel.
