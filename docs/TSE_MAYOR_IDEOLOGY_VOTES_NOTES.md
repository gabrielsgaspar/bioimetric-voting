# TSE Mayor Ideology Vote Shares

- Source: Base dos Dados BigQuery table `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`.
- Years: 2000, 2004, 2008, 2012, 2016, 2020.
- Filters: first round only (`turno = 1`) and mayoral race only (`cargo = 'Prefeito'`).
- Ideology source: `data/clean/party_ideology/party_lcr_crosswalk_2000_2024.parquet`.
- Unit: municipality-election year.
- Denominator: total positive candidate mayor votes in the municipality-year, excluding blank/null votes.
- Output: `data/clean/tse/tse_mayor_ideology_votes.parquet` and `.csv`.
- Interim party-vote cache: `data/interim/tse/tse_mayor_party_votes_bdd_2000_2020.parquet` and `.csv`.

## Output Columns

year, state, municipality_id, pct_mayor_R, pct_mayor_C, pct_mayor_L, pct_mayor_IDK

## Diagnostics

```text
 year  rows  states  municipalities  min_share_sum  max_share_sum  idk_parties
 2000  5555      26            5555            1.0            1.0            0
 2004  5561      26            5561            1.0            1.0            0
 2008  5562      26            5562            1.0            1.0            0
 2012  5568      26            5568            1.0            1.0            0
 2016  5564      26            5564            1.0            1.0            0
 2020  5567      26            5567            1.0            1.0            0
```
