# Election Data Summary

Source table: `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`. The 2018 file was pulled with the same municipality-candidate query used in the earlier rho-estimation presidential pulls.

## Files

- 2018 raw runoff: `data/raw/tse_2018_president/resultados_candidato_2018_segundo_turno.csv`.
- 2018 raw first round: `data/raw/tse_2018_president/resultados_candidato_2018_primeiro_turno.csv`.
- 2018 clean: `data/clean/tse/president_2018_municipality.csv`.
- Integrated wide panel: `data/clean/tse/president_pt_runoff_panel_2006_2018.csv`.

## Sanity Checks

|   year |   clean_rows |   weighted_runoff_share |   unweighted_runoff_mean |   expected_national_runoff_share |
|-------:|-------------:|------------------------:|-------------------------:|---------------------------------:|
|   2006 |         5565 |                0.608324 |                 0.618997 |                           0.6083 |
|   2010 |         5567 |                0.560671 |                 0.594822 |                           0.5605 |
|   2014 |         5570 |                0.516759 |                 0.577317 |                           0.5164 |
|   2018 |         5570 |                0.448979 |                 0.534611 |                           0.4487 |

## Coverage

- Wide panel rows: 5,570.
- Missing runoff shares by year: `{'missing_2006_runoff': 5, 'missing_2010_runoff': 3, 'missing_2014_runoff': 0, 'missing_2018_runoff': 0}`.
