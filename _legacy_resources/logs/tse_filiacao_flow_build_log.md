# TSE Filiacao Flow Build Log

- Final panel: `data/clean/tse_filiacao/new_affiliations_election_year_panel.parquet`
- Rows: `55,710`
- Municipalities: `5,571`
- BigQuery bytes processed in uncached queries during this run: `0.00 GB`
- Dry-run bytes represented by the cached/query outputs: `27.08 GB`
- Every analytical query was dry-run before execution or cache reuse, and every single dry run was below the 15 GB guardrail.

## Query log

| label                                        |   bytes_processed | destination                                                                     | cached   |
|:---------------------------------------------|------------------:|:--------------------------------------------------------------------------------|:---------|
| filiacao_tables                              |                 0 | data/interim/tse_filiacao/schema_tables.parquet                                 | True     |
| microdados_columns                           |          10485760 | data/interim/tse_filiacao/schema_columns_microdados.parquet                     | True     |
| microdados_antigos_columns                   |          10485760 | data/interim/tse_filiacao/schema_columns_microdados_antigos.parquet             | True     |
| microdados_sample_1000                       |        2384283701 | data/interim/tse_filiacao/sample_microdados_1000.parquet                        | True     |
| microdados_antigos_sample_1000               |        2870206399 | data/interim/tse_filiacao/sample_microdados_antigos_1000.parquet                | True     |
| filiacao_union_dedup_totals                  |        3039850279 | data/interim/tse_filiacao/union_dedup_totals.parquet                            | True     |
| filiacao_union_dedup_yearly_coverage         |        3039850279 | data/interim/tse_filiacao/union_dedup_yearly_coverage.parquet                   | True     |
| filiacao_id_length_check                     |        3039850279 | data/interim/tse_filiacao/union_dedup_id_lengths.parquet                        | True     |
| filiacao_known_municipality_check            |        3039850279 | data/interim/tse_filiacao/known_municipality_counts.parquet                     | True     |
| filiacao_status_distribution                 |         398734279 | data/interim/tse_filiacao/status_distribution.parquet                           | True     |
| filiacao_monthly_disaffiliations             |        3074326943 | data/interim/tse_filiacao/monthly_disaffiliations.parquet                       | True     |
| flow_counts_election_years_duration_filtered |        3126449783 | data/interim/tse_filiacao/flow_counts_election_years.parquet                    | True     |
| flow_counts_no_duration_filter               |        3039850279 | data/interim/tse_filiacao/flow_counts_no_duration_filter_election_years.parquet | True     |
| ibge_population_2000_2018                    |           4773194 | data/interim/tse_filiacao/ibge_population_2000_2018.parquet                     | True     |

## Election-year summary

|   election_year |   total_new_affiliations |   total_new_affiliations_no_duration_filter |   municipalities_with_positive_flow |   population_missing |   adult_population_missing |
|----------------:|-------------------------:|--------------------------------------------:|------------------------------------:|---------------------:|---------------------------:|
|            2000 |                  2219070 |                                     2220853 |                                5570 |                   64 |                         64 |
|            2002 |                   757760 |                                      758546 |                                5527 |                   11 |                         64 |
|            2004 |                  3166136 |                                     3179943 |                                5570 |                    7 |                         64 |
|            2006 |                   733045 |                                      743345 |                                5506 |                    7 |                         64 |
|            2008 |                  3230933 |                                     3301213 |                                5570 |                    6 |                         64 |
|            2010 |                   642531 |                                      660068 |                                5463 |                    6 |                          6 |
|            2012 |                  2682473 |                                     2853322 |                                5570 |                    1 |                          6 |
|            2014 |                   586698 |                                      605764 |                                5479 |                    1 |                          6 |
|            2016 |                  2873297 |                                     2917516 |                                5570 |                    1 |                          6 |
|            2018 |                   680465 |                                      685675 |                                5436 |                    1 |                          6 |
