# BJS ref-0 Base dos Dados downstream screen

Generated on 2026-05-19. This is an exploratory downstream screen, not a paper-ready causal claim.

## Estimation setup

- Estimator: Borusyak-Jaravel-Spiess imputation DID via the local `reg-did` skill (`didimputation::did_imputation`).
- Treatment: first strict BVR year; municipalities ever flagged as hybrid BVR are excluded.
- Clustering: `municipality_id`.
- Event window: -8 to +8. Annual outcomes use one-year steps; biennial assessment and two-year fiscal-cycle outcomes use two-year steps.
- Reference: event time 0. For biennial assessment outcomes, analysis period is assessment year minus 1, so the first post-BVR assessment maps to event time 0.
- Monetary variables: SICONFI values are converted to December 2008 reais using the annual-average IPCA flow deflator anchored to December 2008; log outcomes use `log1p(real_2008 per capita)`.

## Output files

- Tested-variable manifest: `resources/tables/downstream_bjs_ref0_nonhybrid/tested_variables_with_rationale.csv`
- Master ranking: `resources/tables/downstream_bjs_ref0_nonhybrid/master_bjs_ref0_nonhybrid_ranking.csv`
- Master event-study table: `resources/tables/downstream_bjs_ref0_nonhybrid/master_bjs_ref0_nonhybrid_event_study.csv`
- Category summary: `resources/tables/downstream_bjs_ref0_nonhybrid/category_summary.csv`
- Individual plots: every row in the manifest has `figure_path` and `plot_path_absolute`.
- All-outcome plot pages: `resources/figures/downstream_bjs_ref0_nonhybrid/*_all_bjs_ref0_nonhybrid_page_*.png`.
- Top-ranked category plots: `resources/figures/downstream_bjs_ref0_nonhybrid/*_combined_bjs_ref0_nonhybrid.png`.

## Categories tested and why

- `adult_eja` (23 variables): Adult education and EJA outcomes are direct mechanism screens for whether BVR-induced education-record updating or administrative outreach coincided with adult schooling demand, staffing, or EJA spending.
- `birth_health` (89 variables): Health and birth outcomes are plausible downstream service-delivery or selection margins: BVR could shift who remains administratively connected, local political attention, or municipal health-service capacity around the rollout.
- `education` (146 variables): Education outcomes are relevant because the core BVR evidence changes recorded education composition; school flow, learning, teacher inputs, and education spending are useful placebo/mechanism screens for municipal public-service changes.
- `school_access_transport` (14 variables): School access and transport outcomes test concrete access/burden margins in public services, especially rural residence, cross-municipality attendance, and school transport arrangements.
- `siconfi_log_pc` (10 variables): Fiscal log per-capita outcomes test whether municipalities shifted real spending levels around BVR; all monetary values are in December 2008 reais before log(1+x).
- `siconfi_spending_shares` (16 variables): Fiscal share outcomes test composition changes in municipal budgets and reduce sensitivity to scale; numerator and denominator monetary values use the same December 2008 deflator.

## Category counts

| Category | Variables | Pass pretrend | Near | Fail |
|---|---:|---:|---:|---:|
| Adult education / EJA outcomes | 23 | 2 | 0 | 21 |
| Birth and health outcomes | 89 | 13 | 6 | 70 |
| Education outcomes | 146 | 25 | 6 | 115 |
| School access / transport | 14 | 0 | 1 | 13 |
| Log expenditure per capita | 10 | 2 | 1 | 7 |
| Spending shares | 16 | 0 | 6 | 10 |

## Top-ranked screens

Sorted by pretrend label first, then absolute post-event mean over event times 1..8 after normalizing event time 0 to zero.

| Variable | Category | Frequency | Post mean | Pretrend | Plot |
|---|---|---|---:|---|---|
| Child/basic share of education spending | adult_eja | annual | 17.8 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/adult_eja/annual/child_spending_share_bjs_ref0_nonhybrid.png` |
| Education Pc 2008 | education | annual | 14.8 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/siconfi_education_pc_2008_bjs_ref0_nonhybrid.png` |
| Municipal Dsu Em | education | annual | 11.9 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_dsu_em_bjs_ref0_nonhybrid.png` |
| Municipal Afd Em Grupo 5 | education | annual | -8.9 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_afd_em_grupo_5_bjs_ref0_nonhybrid.png` |
| Municipal Ef Final Taxa Aprovacao | education | biennial | 4 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/biennial/ideb_municipal_ef_final_taxa_aprovacao_bjs_ref0_nonhybrid.png` |
| Municipal Ied Em Nivel 5 | education | annual | 3.03 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_ied_em_nivel_5_bjs_ref0_nonhybrid.png` |
| Publica Ef Final Taxa Aprovacao | education | biennial | 2.71 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/biennial/ideb_publica_ef_final_taxa_aprovacao_bjs_ref0_nonhybrid.png` |
| Municipal Tdi Em | education | annual | -2.71 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_tdi_em_bjs_ref0_nonhybrid.png` |
| IEPS CSAP mortality | birth_health | annual | -2.67 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/birth_health/annual/ieps_mortality_csap_per_100k_bjs_ref0_nonhybrid.png` |
| IEPS avoidable mortality | birth_health | annual | 2.23 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/birth_health/annual/ieps_mortality_avoidable_per_100k_bjs_ref0_nonhybrid.png` |
| Municipal Grade5 Math Media | education | biennial | 2.1 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/biennial/saeb_municipal_grade5_math_media_bjs_ref0_nonhybrid.png` |
| Public Estadual Municipal Grade5 Portuguese Low Levels 0 2 | education | biennial | -1.99 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/biennial/saeb_public_estadual_municipal_grade5_portuguese_saeb_low_levels_0_2_bjs_ref0_nonhybrid.png` |
| IEPS SUS beds | birth_health | annual | -1.94 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/birth_health/annual/ieps_sus_beds_per_100k_bjs_ref0_nonhybrid.png` |
| Municipal Taxa Aprovacao Ef Anos Finais | education | annual | 1.91 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_taxa_aprovacao_ef_anos_finais_bjs_ref0_nonhybrid.png` |
| Municipal Taxa Abandono Ef Anos Finais | education | annual | -1.04 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_taxa_abandono_ef_anos_finais_bjs_ref0_nonhybrid.png` |
| Municipal Ied Em Nivel 6 | education | annual | -1.01 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_ied_em_nivel_6_bjs_ref0_nonhybrid.png` |
| Municipal Taxa Reprovacao Ef Anos Finais | education | annual | -0.868 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_taxa_reprovacao_ef_anos_finais_bjs_ref0_nonhybrid.png` |
| Municipal Taxa Reprovacao Ef | education | annual | -0.736 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_taxa_reprovacao_ef_bjs_ref0_nonhybrid.png` |
| Municipal Atu Ef Anos Finais | education | annual | -0.698 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_atu_ef_anos_finais_bjs_ref0_nonhybrid.png` |
| Municipal Taxa Reprovacao Em | education | annual | -0.625 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_taxa_reprovacao_em_bjs_ref0_nonhybrid.png` |
| Publica Ird Baixa Regularidade | education | annual | 0.603 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_publica_ird_baixa_regularidade_bjs_ref0_nonhybrid.png` |
| Municipal Ird Baixa Regularidade | education | annual | 0.536 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/annual/inep_ind_municipal_ird_baixa_regularidade_bjs_ref0_nonhybrid.png` |
| Municipal Grade5 Portuguese Media | education | biennial | 0.479 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/education/biennial/saeb_municipal_grade5_portuguese_media_bjs_ref0_nonhybrid.png` |
| Adequate prenatal visits share: Low education proxy | birth_health | annual | 0.356 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/birth_health/annual/sinasc_lowedu_prenatal_adequate_share_known_pp_bjs_ref0_nonhybrid.png` |
| IEPS SUS ICU beds | birth_health | annual | 0.291 | pass | `resources/figures/downstream_bjs_ref0_nonhybrid/birth_health/annual/ieps_sus_icu_beds_per_100k_bjs_ref0_nonhybrid.png` |

## Source notes

- Base dos Dados platform/source discovery pages used for this screen: SICONFI, SINASC, SIM, INEP Indicadores Educacionais, IDEB, SAEB, Sinopses Estatisticas da Educacao Basica, and IPCA.
- The local analysis uses the cleaned/cached panels in `data/clean/downstream/`; raw Base dos Dados queries and caches live under `data/interim/` subfolders.
