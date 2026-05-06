# Data Sources

## Geospatial boundaries for mapping

- Brazilian municipalities: official IBGE Malha Municipal 2010 shapefiles from `https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2010/`.
- Access pattern: `src/data/download_geodata_shapefiles.R` downloads the 27 state-level `*_municipios.zip` files, because the 2010 IBGE release is organized by UF rather than as a single Brazil archive. The raw ZIP archives are cached under `data/raw/ibge/shapefiles/municipio_2010/`.
- Clean outputs: UF-level shapefile directories under `data/clean/geodata/ibge_municipalities_2010/by_uf/` and a merged Brazil-wide municipal shapefile at `data/clean/geodata/ibge_municipalities_2010/br_municipios_2010.shp`.
- Merge note: the official RS archive includes two water-body features, `4300001 LAGOA MIRIM` and `4300002 LAGOA DOS PATOS`, which are not municipalities and do not appear in the repo's IBGE municipality crosswalk. The UF-level official extract is kept intact, but these two features are excluded from the merged Brazil-wide municipality shapefile. The excluded rows are recorded at `data/interim/geodata/ibge_municipalities_2010_excluded_nonmunicipality_features.csv`.
- Documentation: the IBGE readme PDF is cached as `data/raw/ibge/shapefiles/municipio_2010/Malha_Municipal_2010.pdf`.
- Americas plotting layer: Natural Earth Admin 0 Countries 1:10m, version 5.1.1, from `https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries/` using the direct archive `https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip`.
- Clean outputs: full Natural Earth country shapefile under `data/clean/geodata/natural_earth_admin0_countries_10m/` and an Americas-only filtered shapefile under `data/clean/geodata/natural_earth_americas_10m/`.
- Validation: `data/interim/geodata/shapefile_download_diagnostics.csv` records source URLs, shapefile paths, and feature counts.

## TSE BVR municipality status counts

- Source files: `data/raw/tse_bvr_legal/quantitativo_municipios-municipio_2012.csv`, `quantitativo_municipios-municipio_2014.csv`, `quantitativo_municipios-municipio_2016.csv`, and `quantitativo_municipios-municipio_2018.csv`.
- Content: municipality-year BVR status counts by state and TSE municipality name. The status fields are `qt_municipio_sem_biometria`, `qt_municipio_biometria`, and `qt_municipio_hibrido`.
- ID harmonization: `src/cleaning/match_tse_bvr_quantitativo_municipios.py` matches each year/state/TSE municipality name to the corresponding year-specific harmonized TSE electorate file under `data/interim/tse_eleitorado/`, then carries the existing IBGE `municipality_id`.
- Matched outputs: `data/interim/tse_bvr/quantitativo_municipios_municipio_2012_2018_matched.csv` and `.parquet`.
- Review output: `data/interim/tse_bvr/quantitativo_municipios_municipio_2012_2018_match_review.csv` lists non-current-name variants and any rows requiring manual review.
- Derived clean panel: `data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.csv` and `.parquet` add year-specific `bvr_status`, `strict_bvr`, `hybrid`, and first-exposure timing fields while preserving the legacy `year_treated` design variable.
- Validation: all rows match to an IBGE municipality ID, no duplicate `year x municipality_id` rows are produced, and every row has exactly one BVR status flag equal to one.

## TSE biometric electorate shares by education

- Source files: official TSE `perfil_eleitorado_{year}.zip` packages under `data/raw/tse_eleitorado/{year}/`, using `QT_ELEITORES_PERFIL`, `QT_ELEITORES_BIOMETRIA`, `DS_GRAU_ESCOLARIDADE`, `SG_UF`, `CD_MUNICIPIO`, and `NM_MUNICIPIO`.
- Construction script: `src/analysis/build_tse_biometric_education_shares.py`.
- ID harmonization: year-specific TSE municipality codes are matched to IBGE municipality IDs using `data/raw/ibge/bd-tse_mun_ids.csv`, with the same state-constrained name fallback used by the main TSE electorate panel.
- Clean output: `data/clean/tse_eleitorado/eleitorado_biometric_shares_2000_2018.csv` and `.parquet`.
- Added clean-panel variables: `pct_with_bvr`, `pct_low_ed_with_bvr`, and `pct_high_ed_with_bvr` are merged into `data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.csv` and `.parquet`.
- Availability rule: the raw biometric count is zero nationally in 2000-2012 even though official rollout sources identify early BVR municipalities. The derived share variables are therefore set to missing for years where the raw biometric count is zero nationally and populated for 2014, 2016, and 2018 in this build.
- Diagnostics: `data/interim/tse_eleitorado/biometric_education_shares_2000_2018_diagnostics.csv` records year-level coverage, national biometric counts, missingness, and mean shares.

## TSE party affiliation flow

- Source: Base dos Dados BigQuery dataset `basedosdados.br_tse_filiacao_partidaria`.
- Tables used: deduplicated union of `microdados` and `microdados_antigos`.
- Access pattern: Google BigQuery through the local service-account credentials in `credentials/gcp-key.json`, with dry runs before execution and cached parquet outputs under `data/interim/tse_filiacao/`.
- Key columns: `data_filiacao`, `data_desfiliacao`, `data_cancelamento`, `data_exclusao`, `situacao_registro`, `id_municipio`, `sigla_uf`, and `sigla_partido`.
- Clean output: `data/clean/tse_filiacao/new_affiliations_election_year_panel.parquet`.
- Notes: the analytical flow outcome counts new affiliation start events in non-overlapping two-year windows from December 1 of `t-2` through November 30 of election year `t`. The primary count excludes records invalidated within six months of `data_filiacao`.

## IBGE population denominators for affiliation flow

- Total municipal population: Base dos Dados BigQuery table `basedosdados.br_ibge_populacao.municipio`, years 2000-2018.
- Adult population robustness denominator: official IBGE SIDRA census tables. Table 200 supplies 2000 and 2010 age-group counts; table 9514 supplies 2022 age-by-sex counts. The script sums ages 15+ and linearly interpolates adult population to election years.
- Cached outputs: `data/interim/tse_filiacao/ibge_population_2000_2018.parquet` and `data/interim/tse_filiacao/adult_population_census_points.parquet`.

## Party ideology L/C/R crosswalk

- Source: Base dos Dados BigQuery dataset `basedosdados.br_tse_eleicoes`, covering election-result tables from 2000 through 2024.
- Tables used: `resultados_candidato_municipio` and `resultados_partido_municipio` to identify parties with positive observed votes; `partidos` to recover official party names where available.
- Access pattern: Google BigQuery through the local service-account credentials in `credentials/gcp-key.json`, with a dry run before execution and cached outputs under `data/interim/party_ideology/`.
- Interim output: `data/interim/party_ideology/bdd_voted_party_years_2000_2024.csv` and `.parquet`.
- Clean output: `data/clean/party_ideology/party_lcr_crosswalk_2000_2024.csv` and `.parquet`.
- Coding rule: each party sigla is assigned `L`, `C`, `R`, or `IDK` using the explicit mapping supplied by Gabriel on 2026-04-27; party keys are uppercased and accent-insensitive for matching.

## TSE mayor ideology vote shares

- Source: Base dos Dados BigQuery table `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`.
- Scope: first-round (`turno = 1`) mayoral (`cargo = 'Prefeito'`) candidate votes in municipal election years 2000, 2004, 2008, 2012, 2016, and 2020.
- Party ideology merge: `data/clean/party_ideology/party_lcr_crosswalk_2000_2024.csv`, using normalized party sigla and assigning unmatched parties to `IDK`.
- Interim output: `data/interim/tse/tse_mayor_party_votes_bdd_2000_2020.csv` and `.parquet`.
- Clean output: `data/clean/tse/tse_mayor_ideology_votes.csv` and `.parquet`.
- Columns: `year`, `state`, `municipality_id`, `pct_mayor_R`, `pct_mayor_C`, `pct_mayor_L`, and `pct_mayor_IDK`.

## TSE vereador ideology vote shares

- Source: Base dos Dados BigQuery table `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`.
- Scope: first-round (`turno = 1`) vereador (`cargo = 'Vereador'`) candidate votes in municipal election years 2000, 2004, 2008, 2012, 2016, and 2020.
- Party ideology merge: `data/clean/party_ideology/party_lcr_crosswalk_2000_2024.csv`, using normalized party sigla and assigning unmatched parties to `IDK`.
- Interim output: `data/interim/tse/tse_vereador_party_votes_bdd_2000_2020.csv` and `.parquet`.
- Clean output: `data/clean/tse/tse_vereador_ideology_votes.csv` and `.parquet`.
- Columns: `year`, `state`, `municipality_id`, `pct_vereador_R`, `pct_vereador_C`, `pct_vereador_L`, and `pct_vereador_IDK`.
