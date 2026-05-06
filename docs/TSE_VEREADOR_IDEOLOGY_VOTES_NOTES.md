# TSE Vereador Ideology Vote Shares

- Source: Base dos Dados BigQuery table `basedosdados.br_tse_eleicoes.resultados_candidato_municipio`.
- Years: 2000, 2004, 2008, 2012, 2016, 2020.
- Filters: first round only (`turno = 1`) and city-council race only (`cargo = 'Vereador'`).
- Ideology source: `data/clean/party_ideology/party_lcr_crosswalk_2000_2024.parquet`.
- Unit: municipality-election year.
- Denominator: total positive candidate vereador votes in the municipality-year, excluding blank/null and party-list votes.
- Output: `data/clean/tse/tse_vereador_ideology_votes.parquet` and `.csv`.
- Interim party-vote cache: `data/interim/tse/tse_vereador_party_votes_bdd_2000_2020.parquet` and `.csv`.

## Output Columns

year, state, municipality_id, pct_vereador_R, pct_vereador_C, pct_vereador_L, pct_vereador_IDK

## Diagnostics

```text
 year  rows  states  municipalities  min_share_sum  max_share_sum  idk_parties
 2000  5555      26            5555            1.0            1.0            0
 2004  5560      26            5560            1.0            1.0            0
 2008  5563      26            5563            1.0            1.0            0
 2012  5567      26            5567            1.0            1.0            0
 2016  5563      26            5563            1.0            1.0            0
 2020  5565      26            5565            1.0            1.0            0
```
