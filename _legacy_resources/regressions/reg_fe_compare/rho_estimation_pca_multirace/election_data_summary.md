# Multi-Race Election Data Summary

Source table: `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`. The left coalition is coded as PT, PSB, PCdoB, PDT, PSOL, PV, and REDE. Deputy elections use candidate-result rows from the Base dos Dados candidate-municipality table.

## Files

- Federal deputy raw files: `data/raw/tse_dep_fed/resultados_candidato_dep_fed_2006.csv`, `..._2010.csv`, `..._2014.csv`.
- State deputy raw files: `data/raw/tse_dep_est/resultados_candidato_dep_est_2006.csv`, `..._2010.csv`, `..._2014.csv`.
- Federal deputy clean file: `data/clean/tse/dep_fed_left_coalition_municipality.csv`.
- State deputy clean file: `data/clean/tse/dep_est_left_coalition_municipality.csv`.
- Integrated preference panel: `data/clean/tse/preference_panel_3races_2006_2014.csv`.

## Deputy Vote-Share Sanity Checks

| office            |   year |   municipality_rows |   unweighted_mean_left_share |   weighted_left_share |   min_left_share |   max_left_share |
|:------------------|-------:|--------------------:|-----------------------------:|----------------------:|-----------------:|-----------------:|
| deputado federal  |   2006 |                5565 |                     0.245826 |              0.319851 |       0.00471527 |         0.976487 |
| deputado federal  |   2010 |                5567 |                     0.294591 |              0.356396 |       0.00962811 |         0.92249  |
| deputado federal  |   2014 |                5570 |                     0.273816 |              0.287999 |       0.00567537 |         0.964844 |
| deputado estadual |   2006 |                5564 |                     0.251853 |              0.300896 |       0.00280308 |         0.901486 |
| deputado estadual |   2010 |                5566 |                     0.308677 |              0.355385 |       0.00442955 |         0.975744 |
| deputado estadual |   2014 |                5569 |                     0.275364 |              0.299562 |       0.00343965 |         0.937689 |

Share anomalies outside [0, 1]: 0.

## Coverage

- Integrated panel rows: 5,570.
- Missing values by PCA variable: `{'pt_share_2006_runoff': 5, 'pt_share_2010_runoff': 3, 'pt_share_2014_runoff': 0, 'left_share_dep_fed_2006': 5, 'left_share_dep_fed_2010': 3, 'left_share_dep_fed_2014': 0, 'left_share_dep_est_2006': 6, 'left_share_dep_est_2010': 4, 'left_share_dep_est_2014': 1}`.
- Municipalities with complete 9-variable coverage: 5,564.
- Event-time-0 rho rows before multirace merge: 1,845.
- Event-time-0 rho rows matched to multirace PC1: 1,845.
- Event-time-0 rho rows unmatched to multirace PC1: 0.
- Unmatched event-time-0 rows by state: `{}`.

The Federal District lacks `deputado estadual` rows in this office definition; this is expected because it elects district deputies rather than state deputies.
