# Party Ideology L/C/R Crosswalk

- Source: Base dos Dados BigQuery dataset `basedosdados.br_tse_eleicoes`, years 2000-2024.
- Tables used: `resultados_candidato_municipio`, `resultados_partido_municipio`, and `partidos` for names.
- Inclusion rule: party-year rows with strictly positive observed candidate votes or party-list votes.
- Vote columns are source-specific; `max_votes_observed` avoids double counting nominal votes that appear in both TSE result tables.
- Ideology coding: direct application of the L/C/R/IDK party-sigla mapping supplied by Gabriel on 2026-04-27.
- Party-year output: `data/interim/party_ideology/bdd_voted_party_years_2000_2024.parquet` and `.csv`.
- Clean crosswalk: `data/clean/party_ideology/party_lcr_crosswalk_2000_2024.parquet` and `.csv`.
- BigQuery dry-run log: `data/interim/party_ideology/bigquery_query_log.csv`.

## Ideology Counts

```text
ideology_lcr
C      17
IDK    43
L       7
R      29
```

## Parties Per Year

```text
 year  n_parties_voted
 2000               30
 2002               30
 2004               27
 2006               29
 2008               27
 2010               27
 2012               30
 2014               33
 2016               35
 2018               52
 2020               34
 2022               57
 2024               29
```

## IDK Parties

P17, P24, P25, P26, P31, P37, P38, P41, P42, P47, P54, P56, P59, P60, P62, P66, P67, P69, P74, P75, P78, P81, P85, P87, P89, PCA1, PCA10, PCA11, PCA12, PCA13, PCA14, PCA15, PCA16, PCA17, PCA2, PCA3, PCA4, PCA5, PCA6, PCA7, PCA8, PCA9, PRD
