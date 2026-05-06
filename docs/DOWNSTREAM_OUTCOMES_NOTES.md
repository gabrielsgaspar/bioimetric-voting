# Downstream Outcomes Notes

- Panel key: `(year_election, municipality_id)`.
- Treatment timing source: `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`.
- Election years covered in the skeleton: `2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022`.
- Fiscal-year alignment rule: prior odd fiscal year is carried to the following election year, so FY2001 maps to election year 2002.
- DATASUS mortality rates are blanked out when `population_estimate <= 1000`.
- Spending variables are stored as per-capita levels and also as winsorized `log(1 + x)` transforms under `log_<variable>`. The downstream DiD regressions use the logged versions for fiscal outcomes.
- Municipal population is now pulled from official IBGE SIDRA population series. Years 2000 and 2010 use census table `202`; non-census election years use SIDRA table `6579`, variable `9324`; 2022 is temporarily assigned the 2021 SIDRA estimate because the `6579` public endpoint did not return a 2022 municipal panel in this environment.

## Available Outcomes

- `turnout`
- `blank_null_rate`
- `PT_vote_share_president`
- `PSDB_vote_share_president`
- `health_spending_per_capita`
- `education_spending_per_capita`
- `social_assistance_spending_per_capita`
- `total_discretionary_spending_per_capita`
- `IPTU_collection_per_capita`
- `FPM_transfers_per_capita`
- `infant_mortality_rate`
- `pre_natal_7plus_visits_share`

## Currently Missing or Partial

- `effective_number_of_candidates_mayor`
- `incumbent_mayor_reelection`
- `margin_of_victory_mayor`
- `neonatal_mortality_rate` (withheld from paper-facing outputs because the current DATASUS extraction returned the same series as under-1 mortality and needs a cleaner age-band pull)
- `bolsa_familia_coverage`

## Source-Specific Caveats

- TSE turnout and blank/null rates come from `detalhe_votacao_munzona`, aggregated to the executive race in each election year (`Prefeito` in municipal years, `Presidente` in national years).
- Presidential PT and PSDB vote shares are built from the official TSE `votacao_partido_munzona` files, which are much smaller than the candidate archives and sufficient for party-level shares. The mayoral competition outcomes still require the larger municipal `votacao_candidato_munzona` files.
- Historical FINBRA 2000-2012 files are downloaded from the Tesouro publication archive. The post-2012 Siconfi bulk path is more brittle in this environment, so fiscal coverage may be concentrated in the historical span unless the public Siconfi extraction is completed later.
- The public FINBRA build currently stops at 2012, so fiscal outcomes are observed through election year 2012 under the paper's fiscal-year alignment rule. Later election years remain in the panel, but fiscal fields are blank.
- DATASUS outcomes are pulled through the open-source `datasus` R wrapper, which submits the official TabNet forms and writes municipality-year aggregates to `data/interim/downstream/datasus_outcomes.csv`.
- Bolsa Família coverage is intentionally left blank until the municipal bulk extract from the Cidadania explorer is stabilized and documented.

## SICONFI Base dos Dados Fiscal Extension

- Built with `src/analysis/build_siconfi_bdd_fiscal_panel.py` using Base dos Dados BigQuery tables in `basedosdados.br_me_siconfi`.
- Clean fiscal output: `data/clean/downstream/siconfi_bdd_fiscal_panel_2000_2022.parquet`.
- Merged panel output: `data/clean/downstream/downstream_outcomes_panel_v2.parquet`.
- Backup of the pre-extension panel: `data/clean/downstream/downstream_outcomes_panel_pre_bdd.parquet`.
- Query caches live under `data/interim/siconfi_bdd/`.
- Spending tables use `Despesas Liquidadas`; revenue tables use `Receitas Brutas Realizadas`.
- All monetary values are deflated to 2018 reais with annual-average national IPCA from IBGE SIDRA table 1737, then normalized by the project population panel from `build_downstream_outcomes_panel.py`.
- Within municipality-years that are present in the relevant SICONFI stage, missing category rows are treated as zeros; municipality-years absent from the stage remain missing and are flagged by `has_function_stage_data`, `has_economic_stage_data`, and `has_revenue_stage_data`.
- Unmatched municipality IDs relative to the IBGE-TSE crosswalk: `2`.

### Coverage summary

```text
                        outcome  min_n_muni_nonmissing
               FPM_transfers_pc                   5050
                        IPTU_pc                   5050
                         ISS_pc                   5050
               SUS_transfers_pc                   5050
              administration_pc                      0
       agrarian_organization_pc                      0
                 agriculture_pc                   5050
          citizenship_rights_pc                      0
           commerce_services_pc                      0
              communications_pc                   5050
                     culture_pc                      0
                debt_service_pc                   5050
          education_spending_pc                   5050
                      energy_pc                      0
    environmental_management_pc                      0
           essential_justice_pc                      0
        financial_inversions_pc                   5050
           foreign_relations_pc                      0
             health_spending_pc                   5050
                     housing_pc                      0
                    industry_pc                      0
         investment_spending_pc                   5050
                   judiciary_pc                   5050
                       labor_pc                      0
                 legislative_pc                   5050
            national_defense_pc                      0
      other_current_spending_pc                   5050
          personnel_spending_pc                   5050
             public_security_pc                   5050
                  sanitation_pc                      0
          science_technology_pc                      0
           social_assistance_pc                   5050
             social_security_pc                      0
             special_charges_pc                      0
               sport_leisure_pc                      0
total_discretionary_spending_pc                   5050
               total_revenue_pc                   5050
              total_spending_pc                   5050
           total_tax_revenue_pc                   5050
                   transport_pc                   5050
                    urbanism_pc                      0
```

### FINBRA vs. Base dos Dados overlap check (2010 and 2012)

```text
 year_election                              old_column                      new_column  n_overlap  correlation
          2010              health_spending_per_capita              health_spending_pc       5459     0.717450
          2010           education_spending_per_capita           education_spending_pc       5459     0.662091
          2010   social_assistance_spending_per_capita            social_assistance_pc       5459     0.691927
          2010              IPTU_collection_per_capita                         IPTU_pc       5460     0.611084
          2010                FPM_transfers_per_capita                FPM_transfers_pc       5460     0.870233
          2010 total_discretionary_spending_per_capita total_discretionary_spending_pc       5460     0.672433
          2012              health_spending_per_capita              health_spending_pc       5141     0.737372
          2012           education_spending_per_capita           education_spending_pc       5141     0.696390
          2012   social_assistance_spending_per_capita            social_assistance_pc       5141     0.738916
          2012              IPTU_collection_per_capita                         IPTU_pc       5141     0.676281
          2012                FPM_transfers_per_capita                FPM_transfers_pc       5141     0.898013
          2012 total_discretionary_spending_per_capita total_discretionary_spending_pc       5141     0.736154
```
