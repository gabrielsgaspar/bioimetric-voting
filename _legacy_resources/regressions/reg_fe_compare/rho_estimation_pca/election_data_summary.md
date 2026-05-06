# Election Data Summary

Source table: `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`. The 2010 file comes from the previously cleaned `data/clean/tse/president_2010_municipality.csv`; 2006 and 2014 were pulled with the same query structure.

## Raw And Clean Files

- 2006 raw runoff: `data/raw/tse_2006_president/resultados_candidato_2006_segundo_turno.csv`.
- 2006 raw first round: `data/raw/tse_2006_president/resultados_candidato_2006_primeiro_turno.csv`.
- 2006 clean: `data/clean/tse/president_2006_municipality.csv`.
- 2014 raw runoff: `data/raw/tse_2014_president/resultados_candidato_2014_segundo_turno.csv`.
- 2014 raw first round: `data/raw/tse_2014_president/resultados_candidato_2014_primeiro_turno.csv`.
- 2014 clean: `data/clean/tse/president_2014_municipality.csv`.
- Combined panel: `data/clean/tse/president_pt_runoff_panel_2006_2014.csv`.

## Sanity Checks

|   year |   clean_rows |   weighted_runoff_share |   unweighted_runoff_mean |   expected_national_runoff_share |
|-------:|-------------:|------------------------:|-------------------------:|---------------------------------:|
|   2006 |         5565 |                0.608324 |                 0.618997 |                           0.6083 |
|   2010 |         5567 |                0.560671 |                 0.594822 |                           0.5605 |
|   2014 |         5570 |                0.516759 |                 0.577317 |                           0.5164 |

## Coverage

- Wide panel rows: 5,570.
- Municipalities with complete 2006, 2010, and 2014 runoff coverage: 5,565.
- Missing by year: `{'missing_2006_runoff': 5, 'missing_2010_runoff': 3, 'missing_2014_runoff': 0}`.
- Event-time-0 rho rows before PCA merge: 1,845.
- Event-time-0 rho rows matched to full PCA coverage: 1,845.
- Event-time-0 rho rows unmatched to full PCA coverage: 0.
- Unmatched event-time-0 rows by state: `{}`.

The 2014 presidential vote is contemporaneous with the first hybrid year for municipalities treated in 2014; this is retained by design for the multi-year construct and flagged in the summary as a limitation.
