# Rho Estimation Dataset Summary

## Base dos Dados Pull

Source table: `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`.

- Schema saved to `resources/regressions/reg_fe_compare/rho_estimation/bdd_resultados_candidato_municipio_schema.csv`.
- Raw runoff rows saved to `data/raw/tse_2010_president/resultados_candidato_2010_segundo_turno.csv`.
- Raw first-round rows saved to `data/raw/tse_2010_president/resultados_candidato_2010_primeiro_turno.csv`.
- Clean runoff municipality file saved to `data/clean/tse/president_2010_second_round_municipality.csv`.
- Clean combined municipality file saved to `data/clean/tse/president_2010_municipality.csv`.
- BigQuery query log saved to `resources/regressions/reg_fe_compare/rho_estimation/bdd_query_log.csv`.

## Presidential Vote Sanity Checks

- Clean municipality rows: 5,567.
- National weighted Dilma runoff share: 0.5607.
- Unweighted municipality mean Dilma runoff share: 0.5948.
- Unweighted municipality mean Dilma first-round share: 0.5530.
- Unweighted municipality mean left-coalition first-round share: 0.6616.

The weighted runoff share should be close to the official national Dilma second-round share of 56.05%.

## Hybrid Rho Datasets

Event time 0:

- Initial hybrid-status observations: 1,846.
- Initial hybrid-status municipalities: 1,846.
- Presidential matches: 1,845; nonmatches: 1.
- 2010 control matches: 1,845; nonmatches: 1.
- Complete analysis rows: 1,845.
- Complete analysis municipalities: 1,845.
- Unmatched presidential rows by state: `{'SC': 1}`.
- Unmatched control rows by state: `{'SC': 1}`.

Event time 2:

- Initial hybrid-status observations: 528.
- Initial hybrid-status municipalities: 528.
- Presidential matches: 528; nonmatches: 0.
- 2010 control matches: 528; nonmatches: 0.
- Complete analysis rows: 528.
- Complete analysis municipalities: 528.
- Unmatched presidential rows by state: `{}`.
- Unmatched control rows by state: `{}`.

## Controls

Controls use 2010 IBGE GDP/population from `data/clean/ibge/municipality_gdp_population_survey_years.parquet`, so no nearest-year fallback was required. Region comes from `data/clean/region_mapping/state_to_region.csv`.

## Notes

The broader first-round left-coalition measure is computed from candidate-party rows in the Base dos Dados table. Because the table records the candidate party rather than all coalition parties, coalition parties without a presidential candidate do not contribute separate votes.