# Report

## LAPOP individual event-time update

I updated the LAPOP trust module with a respondent-level exposure design based on age, municipality, and BVR rollout timing.

Core analysis code:

- `src/analysis/run_lapop_individual_event_time.py`

New data and paper-facing outputs:

- `data/clean/lapop/lapop_brazil_individual_event_time.parquet`
- `resources/tables/lapop_individual_level_main_table.tex`
- `resources/lapop/figures/individual_event_study_trust_all.pdf`
- `resources/lapop/figures/individual_event_study_democracy_all.pdf`
- `resources/lapop/figures/individual_event_study_trust_no_hybrid.pdf`
- `resources/lapop/figures/individual_event_study_democracy_no_hybrid.pdf`
- `paper/sections/bvr_and_political_trust.tex`

Supporting regression artifacts:

- `resources/lapop/regressions/individual_event_time/main_results.csv`
- `resources/lapop/regressions/individual_event_time/event_study_results.csv`
- `resources/lapop/regressions/individual_event_time/sample_summary.csv`
- `resources/lapop/regressions/individual_event_time/model_notes.md`

### What changed in the design

The baseline trust section assigns BVR at the municipality-year level, which means everyone interviewed in a treated municipality gets the same exposure status. The new module instead uses respondent age plus municipality rollout timing to impute when a person first became eligible to vote under BVR.

I define:

- `first_eligible_year = year - floor(age) + 18`
- `T_im = 1` for respondents who only ever became eligible in a municipality already under BVR
- `T_im = -1` for the mixed cohort who were already adult voters when their municipality switched
- `T_im = 0` otherwise
- `registered_under_bvr = 1` for the always-BVR cohort
- `event_time = year - max(year_first_treat, first_eligible_year)`

The script reads treatment timing directly from `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`, uses benchmark LAPOP years `2005 <= year <= 2020`, keeps only municipalities observed in every survey wave in that window, and excludes respondents younger than 18 to match the requested adult-eligibility rule. Because the timing proxy is constructed from age itself, the respondent-level regressions add a cubic in age. The regressions use the same individual controls as the barplot module: low education, female, white, married, working, and age.

### Main findings

The stricter respondent-level design is much thinner than the municipality-level design.

- Balanced regression sample: `2,425` respondents, `8` municipalities, `64` municipality-year cells.
- Always-BVR adults: `28`.
- Low-education always-BVR adults: `2`.
- Mixed-cohort adults: `247`.

The main table shows:

- Municipality-level balanced-sample trust effect: `0.251` with s.e. `0.106`.
- Municipality-level balanced-sample trust interaction with low education: `0.041` with s.e. `0.093`.
- Individual ITT trust effect: `0.235` with s.e. `0.184`, `p = 0.206`.
- Individual trust triple-difference: `-0.310` with s.e. `0.219`, `p = 0.162`.
- Municipality-level balanced-sample democracy effect: `0.428` with s.e. `0.146`.
- Individual ITT democracy effect: `0.097` with s.e. `0.243`, `p = 0.689`.
- Individual democracy triple-difference: `0.358` with s.e. `0.370`, `p = 0.337`.

The respondent-level design therefore does not support a clean low-education cohort mechanism. The age-based individual treatment proxy is useful as a diagnostic, but it is too thinly supported to replace the municipality-level specification.

### Event study and hybrid exclusion

The event-study uses bins from `-8` to `+8`, with `-2` omitted as the reference. Never-treated municipalities are retained as controls with all event-time dummies equal to zero. The all-sample and no-hybrid figures are identical in this balanced-wave sample because none of the eight retained municipalities is marked as hybrid.

The event-study paths are not clean dynamic evidence. For trust, some leads are already positive and several post-treatment bins are also positive. For democracy, the `-4` lead is negative while later post-treatment bins turn positive. I would use these plots as a warning about the noisiness of age-imputed exposure timing, not as evidence of a sharp registration-cohort treatment path.

### How I would use this in the paper

I would present the respondent-level module as a transparent stress test of the municipality-level assignment critique, not as a replacement for the main trust specification.

- It helps because it explicitly constructs within-municipality exposure variation from age and rollout timing.
- It hurts because the balanced-wave, adult-only support is extremely sparse, especially for low-education always-BVR respondents.
- The safest interpretation is therefore the one already suggested by Proposition 3: the LAPOP trust pattern is consistent with compositional selection into compliance and should not be read as a clean within-person attitudinal effect.

## Registry identification robustness update

I added a full appendix robustness module for the registry event studies.

Core analysis code:

- `src/analysis/run_registry_identification_robustness.R`
- `src/analysis/build_did_estimator_comparison.py` updated to add Sun-Abraham

New paper-facing outputs:

- `resources/robustness/honestdid/{outcome}/sensitivity_plot.pdf`
- `resources/robustness/honestdid/{outcome}/results_table.tex`
- `resources/robustness/state_year_fe/{outcome}/event_study_plot.pdf`
- `resources/robustness/permutation/{outcome}/permutation_distribution.pdf`
- `resources/robustness/balance/cohort_balance_table.tex`
- `resources/robustness/dcdh_diagnostic/negative_weights_table.tex`
- `paper/appendix/appendix_honestdid.tex`
- `paper/appendix/appendix_additional_robustness.tex`

I also updated:

- `paper/appendix/appendix_main.tex`
- `paper/sections/bvr_and_electorate_size.tex`
- `paper/references/references.bib`

### Main findings

The strongest reviewer-facing result is that the impact estimates are hard to kill under the relative-magnitudes version of HonestDiD. For `log_num_voters`, `pct_voters_low_ed`, and `pct_voters_high_ed`, the breakdown value is `> 2.0`. In plain language, the impact effect survives post-treatment violations more than twice as large as the largest pre-treatment discrepancy visible in the event study. The smoothness restriction is much harsher: once one allows modest curvature in the latent untreated trend, the identified set widens quickly and can include zero. I think the right way to present this is that the results are robust to proportional extrapolations of the observed pre-trend behavior, but not to extremely flexible counterfactual paths.

The state-level robustness checks are unusually clean. Adding `state x election-year` fixed effects changes the impact coefficient by only about `1.5%` for `log_num_voters`, `2.0%` for `pct_voters_low_ed`, and `2.1%` for `pct_voters_high_ed`. Restricting further to state-year cells with both treated and control municipalities changes the impact coefficient by only about `0.2%`, `1.2%`, and `1.0%`, respectively. That is comfortably inside the `±20%` benchmark from the prompt.

The placebo-style checks also come out strongly in the paper's favor. The permutation p-value is `0.001996` for all three outcomes, so the actual impact estimates sit far in the tails of the placebo timing distribution. The de Chaisemartin-D'Haultfoeuille weight diagnostic is also reassuring: only `3` of `5,460` ATT components receive negative weight, a share of `0.055%`, and the absolute negative-weight mass is essentially zero (`0.000004`).

### Interpretation

These new checks do not change the substantive story of the paper. They harden it. The registry and education-composition results are not being driven by hybrid municipalities, by the particular staggered-DiD estimator, by state-level election shocks, by unusual TWFE weighting, or by arbitrary treatment-timing assignments.

The one nuance worth preserving in the write-up is the distinction inside HonestDiD. The relative-magnitudes results are very strong, but the smoothness bound is intentionally severe and expands quickly. I would not hide that. Instead, I would frame it as: the estimates are robust to confounding proportional to what we actually observe before treatment, but not to highly curved latent counterfactuals that are not visible in the pre-period.

### Balance table

The cohort-balance table confirms that simple treated-versus-never-treated comparisons in levels would be misleading. Early adopters are sometimes richer and more educated than never-treated municipalities, while some middle and late adopters are poorer or less educated. That pattern is useful in the paper because it justifies the municipality fixed-effects/event-study design rather than weakening it.

## Formal model update

I added a new formal-theory module to the paper:

- `paper/sections/model.tex`
- `paper/appendix/appendix_proofs.tex`

and wired it into:

- `paper/main.tex`
- `paper/appendix/appendix_main.tex`
- `paper/sections/introduction.tex`
- `paper/sections/bvr_and_electorate_size.tex`
- `paper/sections/bvr_and_political_trust.tex`

### What the model does

The model is intentionally minimal. It treats biometric voter registration as a security technology that raises the cost of staying on the rolls, lets those costs differ by education, and then maps the post-registration electorate into a standard one-dimensional policy-competition stage.

The four propositions are:

1. `Heterogeneous compliance`: if low-education citizens face a right-shifted compliance-cost distribution, BVR reduces their registration more than it reduces high-education registration.
2. `Median-voter shift`: if education and income are positively correlated and richer or more educated citizens prefer less redistribution, selective registration shifts the post-reform median voter toward lower redistribution.
3. `Trust selection`: if the latent value a citizen places on remaining in the electorate is positively related to trust, the post-reform electorate will look more trusting even without any within-person attitudinal treatment effect.
4. `Welfare ambiguity`: the planner's preferred biometric intensity is interior and depends on how much weight is placed on integrity relative to inclusion.

### Why Proposition 3 matters

This is the most important payoff from the model for the existing paper.

Before the model, the LAPOP trust results were vulnerable to the objection that they might just be compositional artifacts. The new section turns that objection into the mechanism. The claim is no longer that BVR necessarily made particular individuals more trusting. The cleaner claim is that BVR can raise observed trust in post-reform samples by selectively retaining citizens with higher latent attachment to the electoral system. That is a much safer and more defensible way to interpret the survey evidence.

### How the model fits the current evidence

- The administrative registry and education-composition results line up directly with Proposition 1.
- The downstream-outcomes module gives the natural empirical target for Proposition 2, but the current evidence there is restrained: the sign prediction is clear, while the realized policy effects are mostly null or fragile.
- The LAPOP section now explicitly leans on Proposition 3 as the main interpretive frame.
- Proposition 4 gives the conclusion a cleaner normative language: electoral modernization is a tradeoff, not a monotone improvement.

### Writing choices

- I kept the model compact and purely analytical.
- I used a stripped-down Downsian setup rather than a richer political-selection model because the empirical object is pre-election compliance, not candidate entry.
- I cited the core theory references the section needs: `Downs (1957)`, `Meltzer and Richard (1981)`, `Rosenstone and Wolfinger (1978)`, `Besley and Coate (1997)`, and `Feddersen and Pesendorfer (1996)`.
- I did not rewrite the empirical results. The edits in the empirical sections are only interpretive cross-references to the new propositions.

## Downstream Outcomes Report

## What I built

I added a downstream-outcomes module that extends the existing municipality-election panel beyond registry size and composition.

Core data products:

- `data/clean/downstream/downstream_outcomes_panel.parquet`
- `docs/DOWNSTREAM_OUTCOMES_NOTES.md`

Core scripts:

- `src/analysis/build_downstream_outcomes_panel.py`
- `src/analysis/export_datasus_downstream_outcomes.R`
- `src/analysis/update_downstream_outcomes_with_tse.py`
- `src/analysis/refresh_downstream_population_panel.py`
- `src/analysis/run_downstream_outcomes_estimators.py`
- `src/analysis/build_downstream_outcomes_table.py`
- `src/analysis/build_downstream_estimator_comparison.py`
- `src/analysis/mirror_downstream_twfe_plots.py`

Paper-facing outputs:

- `resources/tables/downstream_outcomes_table.tex`
- `resources/images/regressions/estimator_comparison/downstream/downstream_estimator_comparison.pdf`
- `resources/images/regressions/twfe_dynamic/<outcome>/event_study_plot.pdf`
- `paper/sections/downstream_outcomes.tex`

## Data coverage

The current panel is keyed on `(year_election, municipality_id)` and covers election years `2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022`.

Completed outcome blocks:

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

Still incomplete:

- `effective_number_of_candidates_mayor`
- `margin_of_victory_mayor`
- `incumbent_mayor_reelection`
- `neonatal_mortality_rate` as a distinct usable series
- `bolsa_familia_coverage`

Important source notes:

- TSE turnout and blank/null outcomes are built from `detalhe_votacao_munzona`.
- PT and PSDB vote shares are built from official TSE `votacao_partido_munzona` files.
- Fiscal outcomes currently come from historical FINBRA publication archives through 2012 only.
- DATASUS outcomes come from the official TabNet interface via the `datasus` R package.
- Population now comes from IBGE SIDRA. Years `2000` and `2010` use census table `202`; non-census election years use SIDRA table `6579`, variable `9324`; `2022` currently reuses the `2021` municipal estimate because the public SIDRA endpoint did not return a 2022 municipal panel in this environment.

## Estimation setup

For the downstream panel, I used the same treatment-timing file as the main paper:

- `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`

Main estimator choices:

- Dynamic TWFE event study with event time `-8` to `+8`, omitting `-2`
- Callaway-Sant'Anna with never-treated comparison group
- Borusyak-Jaravel-Spiess imputation estimator

Implementation note:

- TWFE and BJS use municipality and election-year clustering.
- The current Callaway-Sant'Anna wrapper cannot handle two-way clustering, so those runs use municipality clustering only.

Fiscal-outcome note:

- The panel stores both raw per-capita fiscal variables and winsorized `log(1 + x)` versions.
- The downstream regressions use the logged fiscal outcomes.

Weighted robustness note:

- After fixing the population panel, I reran population-weighted TWFE for the available outcomes.
- I did not finish a complete population-weighted CS/BJS grid for every outcome because that batch is materially slower and not required for the paper-facing table or the estimator-comparison figure.

## Main findings

### 1. Political downstream effects are weak once we move beyond the turnout ratio

The strongest political result is a mechanical one: turnout defined as `valid_votes / registered_voters` rises sharply after BVR adoption.

- Unweighted TWFE: event-time `0` coefficient is about `0.079`
- Population-weighted TWFE: event-time `0` coefficient is about `0.072`

That is consistent with a tighter registry denominator rather than a clean increase in participation conditional on eligibility.

Blank/null voting is basically flat.

- Unweighted TWFE: near zero throughout, with only a small negative estimate at `+4`
- Population-weighted TWFE: also small on impact, but with some noisy positive pre-trends

### 2. PT vote-share results do not survive stronger robustness checks

The reviewer-facing question was whether the more educated post-BVR electorate becomes systematically less favorable to the PT.

The answer from the current downstream module is: not robustly.

Unweighted PT-share event studies:

- TWFE is mildly negative at some horizons, including about `-0.025` at event time `0` and about `-0.048` at `+4`
- Callaway-Sant'Anna and BJS do not show the same sustained negative pattern
- Population-weighted TWFE is close to zero at the main post-treatment horizons

Most importantly, a direct state-by-year FE robustness check changes the interpretation. When I re-estimate the PT event study with municipality FE plus `state x year` FE, the event-time `0` coefficient becomes positive rather than negative:

- `dist_treatment::0 = 0.0268` with clustered SE `0.0046`

That makes the PT result look much more like a national-cycle composition problem than a stable downstream BVR effect. I therefore would not write a strong partisan-realignment claim into the paper.

PSDB vote share is also unstable across estimators and horizons and does not provide a clearer counterpoint.

### 3. Fiscal outcomes are mostly null

Across the logged per-capita fiscal outcomes, I do not find clean post-adoption declines in health, education, social assistance, or total discretionary spending.

Examples from unweighted TWFE:

- Health spending: event-time `0` about `-0.024`, imprecise
- Education spending: event-time `0` about `-0.002`, imprecise
- Social assistance spending: event-time `0` about `-0.020`, imprecise
- Total discretionary spending: event-time `0` about `-0.029`, imprecise

Population-weighted TWFE actually tilts positive for these fiscal outcomes, but the estimates are noisy and not statistically persuasive.

The two revenue-side outcomes are useful diagnostics:

- `IPTU_collection_per_capita` has strong negative pre-trends before turning positive later
- `FPM_transfers_per_capita` is the intended placebo and does not show a clean post-treatment break, but it also exhibits noticeable pre-trend movement in some specifications

My interpretation is that the fiscal evidence does not support a strong reverse Meltzer-Richard story. If BVR changed representation, constitutional spending floors and transfer rules likely limited the amount of observable short-run budget reallocation.

### 4. Real outcomes are essentially null

The DATASUS block does not show a clean service-delivery effect.

Unweighted TWFE:

- Infant mortality: near zero on impact and early post-treatment
- Prenatal 7+ visits share: essentially flat

Population-weighted TWFE:

- Infant mortality becomes more negative at long horizons, but it also shows pre-treatment movement, so the late negative coefficients are not clean causal evidence

The safest summary is that I do not see strong evidence that BVR changed municipal health delivery in a way detectable through infant mortality or prenatal care.

## What I think the paper should say

The downstream module closes the "so what?" gap, but in a restrained way.

The strongest conclusion is not that BVR changed policy. It is that BVR clearly changed the electorate, clearly tightened the registry, and mechanically changed turnout-style ratios, yet those shifts do not translate into a robust municipality-level partisan or policy realignment in the downstream outcomes I could assemble.

That is a meaningful finding. It implies:

- the reform mattered for electoral access and representation,
- but the resulting changes were either too small, too offsetting, or too institutionally constrained to generate a clear local-policy response.

In other words, the paper can now say:

- BVR changed who was represented in the formal electorate.
- It did not obviously remap municipal spending or municipal health outcomes.
- The partisan downstream evidence is too fragile to support a strong claim once state-specific national cycles are absorbed.

That strikes me as a credible and reviewer-resistant conclusion.

## Remaining issues

### Still unfinished

- The mayoral competition outcomes are not yet filled because the municipal `votacao_candidato_munzona` extraction was still running when I stopped to stabilize the rest of the module.
- The neonatal mortality series is currently withheld from interpretation because the first public DATASUS extraction returned the same series as total under-one mortality; that needs a cleaner age-band extraction before it is publishable.
- Bolsa Família municipal coverage is still blank because the public municipal bulk extract path from the Cidadania explorer was not yet stable enough to document reproducibly.

### Important caveats

- Fiscal coverage currently ends at election year 2012 because the historical FINBRA archive is straightforward but the post-2012 public Siconfi bulk path is brittle.
- Weighted robustness currently exists as population-weighted TWFE, not a complete weighted estimator grid for every outcome.
- The PT downstream result is not robust to state-by-year fixed effects and should not be presented as a headline partisan effect.

## Recommended next steps

1. Finish the municipal candidate-only updater cleanly so the mayoral competition block is available.
2. Decide whether to invest in post-2012 municipal fiscal extraction from Siconfi or explicitly frame the fiscal panel as historical-through-2012.
3. If the paper keeps the PT result in the main text, report the state-by-year FE robustness check directly to avoid over-claiming.
4. Keep the main narrative centered on registry composition and administrative access, with downstream policy nulls as an important boundary condition rather than a disappointment.

## Agent simulation status

I built the full LLM-agent simulation pipeline in `src/analysis/run_agent_simulation.py`, added the missing Horton reference to `paper/references/references.bib`, and validated the full round-trip on reduced smoke-test runs.

### What is implemented

- Official IBGE 2010 Census microdata download from the public FTP directory, with archive validation and restart-safe `.partial` handling.
- Fixed-width parsing of the person sample files using the official layout.
- Persona construction with the requested fields and a balanced stratification target over education, age, sex, region, and municipality-size cells.
- LLM batching through the local `codex exec` path using `gpt-5.4-mini` for the main run and `gpt-5.4` for a 200-persona validation subsample.
- Prompt-sensitivity, Portuguese-language, and voluntary-plus-tax-credit stress-test branches.
- Municipality-level aggregation, comparison to observed TSE rollout drops, and the requested table/figure writers.
- Cache keys for each model batch so reruns do not repeat completed API work.

### What I validated

- The batch parser works on real model output and correctly normalizes decisions into dropout probabilities.
- Reduced end-to-end runs on small archive subsets complete and write:
  - `data/clean/agent_sim/personas.parquet`
  - `data/clean/agent_sim/persona_responses.parquet`
  - `data/clean/agent_sim/municipality_predicted_dropout.parquet`
  - `resources/tables/agent_sim_validation_table.tex`
  - `resources/tables/agent_sim_prompt_sensitivity.tex`
  - `docs/AGENT_SIMULATION_NOTES.md`
- I fixed several bugs during those smoke tests:
  - `state` merge collisions in the validation step
  - incomplete-observation handling for partial test runs
  - restart safety for interrupted zip downloads
  - archive-level parallelization for the census pass

### What is still running

The full national `2000`-persona build is substantially more expensive than the smoke tests because the official census person file must be parsed across all state archives before the LLM calls begin. The long-running national job is currently still in the census-processing stage, working through the largest remaining archives (`MG`, `SP1`, `SP2_RM`, `RS` at the time of this note).

Because the full run has not completed yet, I have **not** updated:

- `paper/sections/08_agent_simulation.tex` or `paper/appendix/appendix_agent_simulation.tex`
- the abstract or introduction
- the final agent-simulation figures and tables with national numbers

### Why I stopped here

The bottleneck is computational rather than conceptual. The exact design requested in the prompt is implemented, but the combination of:

- a national fixed-width census microdata pass, and
- roughly 150 cached LLM batch calls for the full design

pushes the run beyond a single fast interactive cycle in this environment.

### Recommended next step

Let the current national run finish, then write the paper module conditional on the observed fit:

- If predicted-observed correlation exceeds `0.3` and the education-gradient direction is right, write a main-text Section `08_agent_simulation`.
- Otherwise write `paper/appendix/appendix_agent_simulation.tex` as a cautious validation / failure-of-forecasting appendix and keep the contribution framed as a methodological stress test.

## Party affiliation flow analysis (Outcome 1)

I added the first party-affiliation outcome module: the flow of new TSE party affiliations by municipality and election cycle.

### What was built

Core scripts:

- `src/analysis/build_tse_filiacao_flow_panel.py`
- `src/analysis/run_tse_filiacao_flow_estimators.py`
- `src/analysis/build_tse_filiacao_flow_outputs.py`

Core data and diagnostics:

- `data/interim/tse_filiacao/flow_counts_election_years.parquet`
- `data/clean/tse_filiacao/new_affiliations_election_year_panel.parquet`
- `docs/TSE_FILIACAO_BDD_SCHEMA_EXPLORATION.md`
- `docs/FILIACAO_ADMIN_CLEANUP_DIAGNOSTIC.md`
- `resources/logs/tse_filiacao_flow_build_log.md`

Paper-facing outputs:

- `resources/tables/filiacao_flow_main_table.tex`
- `resources/tables/filiacao_flow_robustness_table.tex`
- `resources/images/regressions/twfe_dynamic/log_new_affiliations/event_study_plot.pdf`
- `resources/images/regressions/twfe_dynamic/new_affiliations_per_pop/event_study_plot.pdf`
- `resources/images/regressions/twfe_dynamic/new_affiliations_per_adult_pop/event_study_plot.pdf`
- `resources/images/regressions/estimator_comparison/filiacao_flow/comparison.pdf`
- `paper/sections/09_filiacao_flow.tex`

### Schema discovery summary

The Base dos Dados dataset is `basedosdados.br_tse_filiacao_partidaria`. It contains two relevant tables:

- `microdados`: 17,442,753 rows
- `microdados_antigos`: 24,666,625 rows

The prompt's metadata query needed small BigQuery adjustments: `__TABLES__` exposes `table_id`, not `table_name`, and the local `INFORMATION_SCHEMA.COLUMNS` output did not expose `description`. The verified analytical columns are:

- start date: `data_filiacao`
- end dates / invalidation dates: `data_desfiliacao`, `data_cancelamento`, `data_exclusao`
- status: `situacao_registro`
- municipality: `id_municipio`
- state: `sigla_uf`
- party sigla: `sigla_partido`

`numero_partido` is not present in either table. The deduplicated union has 30,858,989 records overall and 17,943,919 records in the 1998-12-01 to 2018-11-30 flow window. Non-missing `id_municipio` values are seven-digit IBGE codes; the spot checks for Sao Paulo, Rio de Janeiro, Brasilia, and Salvador matched the expected IDs.

### Administrative cleanup events flagged

The disaffiliation diagnostic flags 25 months from 1998-2019 where monthly `data_desfiliacao` counts exceed five times the median monthly count. The largest spikes are September-October 2007, September-October 2011, September-October 2015, and March-April 2016. These are documented in `docs/FILIACAO_ADMIN_CLEANUP_DIAGNOSTIC.md`.

This matters more for future stock outcomes than for this flow outcome. Still, I retained a cleanup-window exclusion as a robustness check for the primary log-count specification.

### Construction decisions

The panel follows the paper's election-year convention: 2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, and 2018. Each observation counts new affiliations from December 1 of year `t-2` through November 30 of election year `t`.

The main count applies a six-month minimum-duration filter. Records cancelled, disaffiliated, or excluded within six months of `data_filiacao` are treated as administrative noise rather than durable party entry. The unfiltered count is also saved in the clean panel.

The full grid contains 55,710 municipality-election rows: 5,571 municipalities by 10 election years. Missing flow cells are filled with zero. Treatment timing comes from `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`, and the municipal universe plus hybrid flag come from `data/clean/tse/tse_clean_panel_2000_2018.parquet`.

The three outcomes are:

- `log_new_affiliations`: `log(1 + n_new_affiliations)`, primary
- `new_affiliations_per_pop`: affiliations per 1,000 IBGE residents
- `new_affiliations_per_adult_pop`: affiliations per 1,000 interpolated adults age 15+

I did not normalize by registered voters because registered voters are mechanically affected by BVR. Total population comes from `basedosdados.br_ibge_populacao.municipio`. Adult population uses official SIDRA census tables: table 200 for 2000 and 2010, and table 9514 for 2022, with linear interpolation to election years.

### Main findings

The adoption-period estimates are null.

- Log count: TWFE `0.036` (s.e. `0.082`); Callaway-Sant'Anna `0.031` (s.e. `0.022`)
- Per 1,000 residents: TWFE `-0.465` (s.e. `0.716`); Callaway-Sant'Anna `-0.813` (s.e. `0.457`)
- Per 1,000 adults: TWFE `-0.463` (s.e. `1.089`); Callaway-Sant'Anna `-0.969` (s.e. `0.604`)

The baseline log-count path has positive coefficients at later horizons, especially event time `+4`, but the rate outcomes do not tell the same story and the state-year FE robustness check removes the positive interpretation.

### Robustness assessment

For the primary log-count outcome:

- State x year FE: event-time `0` is `-0.015` (s.e. `0.027`)
- Population-weighted TWFE: `0.062` (s.e. `0.127`)
- Excluding hybrid municipalities: `0.044` (s.e. `0.089`)
- Excluding flagged cleanup windows: `-0.373` (s.e. `0.267`), with weaker timing support
- Dropping 2000 and 2002: `0.032` (s.e. `0.081`)

The most important check is the state x year FE specification. It turns the adoption estimate slightly negative and imprecise, and it eliminates the positive event-time `+4` pattern. Following the convention from the downstream PT vote-share case, the credible headline is therefore the null.

### Surprises and unresolved issues

The main schema surprise is that the historical flow requires a deduplicated union of `microdados` and `microdados_antigos`; either table alone is incomplete for the purpose of counting historical start events. Another surprise is uneven annual coverage. Many even years from 2000-2018 fall below the prompt's 500,000-affiliation heuristic, although the two-year election windows have plausible national totals.

The cleanup diagnostic flags several pre-2018 administrative disaffiliation waves. Since this module studies inflow, that is not fatal, but stock-style affiliation outcomes should account for these events directly.

### Recommended primary variant

Use `log_new_affiliations` as the primary paper outcome. It avoids denominator bias and is most consistent with the main registry specification. The population-rate outcome is the best companion result, because IBGE population is not mechanically affected by BVR. The adult-population rate should remain a robustness check because it relies on interpolation between census years.

### Limitations

The affiliation data are administrative and municipally attributed, but the source is not a single clean longitudinal event table. The deduplication rule is therefore a substantive construction choice. Early years, especially the 2000 and 2002 election windows, should be treated cautiously. The Callaway-Sant'Anna paths show nonzero pre-period estimates, so they are useful as robustness evidence but not as a clean dynamic validation. Most importantly, this module covers only affiliation volume. It does not yet test ideological composition, gender composition, or concentration of new affiliations.

## Regional decomposition and exit/re-labeling bounds

I built a regional extension of the main BVR registry event studies and an accounting decomposition that separates exit from education-record re-labeling.

### What was built

Core script:

- `scripts/run_regional_decomposition.py`

Data products:

- `data/clean/region_mapping/state_to_region.csv`
- `data/clean/tse/tse_clean_panel_2000_2018_with_region.parquet`
- `data/clean/tse/tse_clean_panel_2000_2018_with_region.csv`
- `resources/decomposition/baseline_shares_by_region.csv`
- `resources/decomposition/regional_event_time0_coefficients.csv`
- `resources/decomposition/regional_event_study_estimates_all.csv`
- `resources/decomposition/bounds_by_region.csv`
- `resources/decomposition/bounds_by_region_and_event_time.csv`

Estimator outputs:

- `resources/did/regional_decomposition/{region}/{outcome}/`
- regions: `norte`, `nordeste`, `centro_oeste`, `sudeste`, `sul`, `national`
- outcomes: `log_num_voters`, `pct_voters_low_ed`, `pct_voters_high_ed`, `log_num_voters_low_ed`, `log_num_voters_high_ed`

Paper-facing tables and figures:

- `resources/tables/regional_event_time0_coefficients.tex`
- `resources/tables/decomposition_bounds_by_region.tex`
- `resources/tables/decomposition_vs_adpf541.tex`
- `resources/images/regressions/regional_decomposition/{region}/{outcome}_event_study.pdf`
- `resources/images/decomposition/regional_event_time0_coefficients.pdf`
- `resources/images/decomposition/regional_decomposition_bounds.pdf`
- `resources/images/decomposition/dynamic_bounds_by_region.pdf`
- `resources/images/decomposition/decomposition_schematic_{region}.pdf`
- `paper/figures/decomposition_schematic.tex`
- `paper/figures/decomposition_schematic_{region}.tex`
- `paper/sections/decomposition.tex`

I also inserted `\input{sections/decomposition}` into `paper/main.tex` after `sections/bvr_and_electorate_size`.

### Regional event-study coefficients

Event-time-zero TWFE estimates, with 95% CIs:

| Region | Log voters | Low-ed share | High-ed share | Log low-ed voters | Log high-ed voters |
|---|---:|---:|---:|---:|---:|
| Norte | -0.096 [-0.158, -0.034] | -0.107 [-0.133, -0.080] | 0.107 [0.080, 0.133] | -0.285 [-0.324, -0.247] | 0.128 [0.036, 0.220] |
| Nordeste | -0.125 [-0.144, -0.106] | -0.109 [-0.118, -0.100] | 0.109 [0.100, 0.118] | -0.291 [-0.317, -0.264] | 0.226 [0.185, 0.267] |
| Centro-Oeste | -0.100 [-0.138, -0.061] | -0.095 [-0.103, -0.086] | 0.095 [0.086, 0.103] | -0.275 [-0.302, -0.248] | 0.107 [0.057, 0.158] |
| Sudeste | -0.138 [-0.145, -0.130] | -0.075 [-0.087, -0.063] | 0.076 [0.064, 0.088] | -0.281 [-0.346, -0.217] | 0.042 [-0.087, 0.171] |
| Sul | -0.115 [-0.147, -0.084] | -0.049 [-0.055, -0.044] | 0.050 [0.045, 0.056] | -0.201 [-0.224, -0.178] | 0.021 [0.000, 0.041] |
| National | -0.115 [-0.128, -0.102] | -0.089 [-0.094, -0.083] | 0.089 [0.084, 0.095] | -0.259 [-0.274, -0.244] | 0.155 [0.113, 0.197] |

The national sanity check passed: the rerun national event-time-zero estimates for `log_num_voters_low_ed` and `log_num_voters_high_ed` exactly reproduce the coefficients already documented in `BVR.md` within the requested 0.01 tolerance.

### Baseline shares and decomposition bounds

Baseline shares are computed at event time `-2` among eventually treated municipalities, weighted by `num_voters`. The national shares under this rule are `s_L = 0.591`, `s_H = 0.408`, and unknown education is `0.001`. These differ from the rough 2008 national shares in the prompt because the reference-period sample pools treated cohorts in different calendar years.

Event-time-zero bounds as percent of baseline electorate:

| Region | R_min | R_min 95% CI | R_max | R_max 95% CI | Scenario B R | Scenario B exit | Scenario C R |
|---|---:|---:|---:|---:|---:|---:|---:|
| Norte | 5.8 | [1.9, 9.6] | 14.3 | [12.9, 15.7] | 5.8 | 9.1 | 9.6 |
| Nordeste | 8.7 | [7.2, 10.2] | 16.6 | [15.4, 17.7] | 8.7 | 11.8 | 12.7 |
| Centro-Oeste | 5.2 | [3.0, 7.5] | 13.0 | [12.0, 13.9] | 5.2 | 9.5 | 9.6 |
| Sudeste | 2.2 | [0.0, 8.3] | 11.8 | [9.8, 13.8] | 2.2 | 12.9 | 8.9 |
| Sul | 1.0 | [0.1, 1.8] | 9.8 | [8.9, 10.7] | 1.0 | 10.9 | 6.0 |
| National | 6.9 | [5.1, 8.6] | 13.5 | [12.9, 14.1] | 6.9 | 10.9 | 11.3 |

The pure-exit scenario is infeasible in every region at the point estimates because every region has a positive high-education count coefficient. The evidence is strongest in the Northeast, North, and Center-West, where the high-education count coefficient is positive and statistically separated from zero. In the Southeast the high-education count coefficient is positive but imprecise, so the re-labeling lower-bound CI includes zero. In the South, the coefficient is small but barely positive.

### Comparison to ADPF 541

The results support one part of the ADPF 541 concern and complicate another.

The supportive part: the Northeast shows the largest lower bound on re-labeling, `8.7%` of the baseline electorate, and the largest upper bound, `16.6%`. This means the region most emphasized in the constitutional dispute experienced the largest education-record updating channel.

The complicating part: the direct total registry contraction is not four times larger in the Northeast than in the Southeast. The point estimate is `11.8%` in the Northeast and `12.9%` in the Southeast. In levels, the Northeast has many more affected voters because the treated baseline electorate is larger: about `3.31 million` implied exits using the direct total contraction, compared with `0.90 million` in the Southeast. But as rates, these event-study estimates do not reproduce the litigation shorthand of roughly 4% Northeast versus 1% Southeast.

The national event-study estimand implies about `6.71 million` fewer registered voters at adoption among the eventually treated baseline electorate. This is larger than the `3.3 million` cancelled-title figure cited for 2016-2018 because the estimands are different: the event-study average covers all treated cohorts and measures the adoption-period registry effect relative to event time `-2`, not the administrative cancellation count in one late rollout window.

### Dynamic decomposition

The dynamic decomposition is most reliable at event time `0`. At event time `+2`, the national re-labeling bounds remain non-empty and are roughly `7.7%` to `10.5%`. At event time `+4`, they narrow to roughly `6.8%` to `8.2%`.

At longer horizons, some regional cells have `R_min > R_max`. That means the nonnegative-exit accounting restrictions are not jointly satisfied by separately estimated log-count event studies. This is not surprising: total registry size can recover while high-education counts remain elevated, and the semi-elasticities are estimated independently rather than from a raw-count accounting system. The dynamic figure shades only horizons where the bounds are non-empty.

### What this adds to the paper narrative

This module strengthens the interpretation of Proposition 2 by showing that BVR changed not only the size and education shares of the registry, but also the underlying education counts in a way that requires education-record re-labeling. Pure exit cannot explain a rising high-education count.

It also tempers the stronger representation claim linked to Proposition 2'. Exit is present through the total registry contraction, but the decomposition shows that part of the education-composition shock is administrative reclassification rather than removal from the electorate. This helps explain why downstream political and policy responses remain muted in later sections: the registry composition changes sharply, but not all of that change corresponds to newly excluded voters.

### Remaining uncertainty and next steps

The decomposition is bounded rather than point identified. Scenario B and Scenario C are useful reference cases, but the bounds are the identified object. The delta-method confidence intervals treat the baseline shares as fixed because they are measured from administrative counts, but a cluster bootstrap could be added later as a confirmatory robustness check.

The regional regressions rely on within-region comparisons and are smaller than the national design. `fixest` adjusted several two-way clustered variance matrices to be positive definite, and the Center-West regional runs dropped one singleton observation. These warnings do not change the point estimates, but they should be disclosed if the regional results become a main-text claim.

Finally, the independently estimated log-count event studies do not obey an exact raw-count identity. I added a residual column to the decomposition tables. Nationally, this residual is `-4.3` percentage points of the baseline electorate. It reflects both the small unknown-education category and the fact that separate TWFE semi-elasticities do not aggregate mechanically.

## Section 5 revision: removing regional and litigation framing

I rewrote `paper/sections/decomposition.tex` to make Section 5 a compact national accounting exercise rather than a regional or case-specific analysis.

### What was removed

The revised section removes the three previously embedded regional/legal tables:

- Table 1: `resources/tables/regional_event_time0_coefficients.tex`
- Table 2: `resources/tables/decomposition_bounds_by_region.tex`
- Table 3: `resources/tables/decomposition_vs_adpf541.tex`

It also removes the three regional figures previously referenced in the section:

- Figure 6: regional event-time-zero registry effects
- Figure 7: regional bounds on re-labeling at adoption
- Figure 8: dynamic regional decomposition bounds

The prose paragraphs about regional heterogeneity across macroregions and the specific legal framing were deleted from the paper section. The generated regional resources remain on disk as archival outputs from the prior exercise, but they are no longer referenced in Section 5.

### What was kept

The revised section keeps:

- Figure 5, the TikZ stacked-flow schematic in `paper/figures/decomposition_schematic.tex`
- the accounting equations for `D_L = -E_L - R` and `D_H = -E_H + R`
- the bounded-identification logic from non-negativity of exits
- national event-time-zero decomposition numbers:
  - `R_min = 6.9%`, 95% CI `[5.1, 8.6]`
  - `R_max = 13.5%`, 95% CI `[12.9, 14.1]`
  - pure exit infeasible
  - Scenario B: `R = 6.9%`, `E_L = 10.9%`
  - Scenario C: `R = 11.3%`, `E_L = 6.4%`, `E_H = 4.4%`
- the dynamic national interpretation: the first post-treatment horizons remain informative, while longer horizons are diagnostic rather than sharp.

### What was added

I added a short spatial-application paragraph explaining how the national coefficients can be combined with municipality-specific baseline education shares `s_L` and `s_H` plus each municipality's treatment distance in 2018. This motivates a forthcoming municipality-level map without reintroducing macroregional comparisons.

I also added a placeholder Figure 6 with label `fig:decomposition_map`. The `\includegraphics` line is commented out so the paper compiles before the map exists. The caption describes the planned two-panel municipality-level map: implied Scenario B exit and implied re-labeling.

The section now reports the aggregate magnitudes implied by the municipality-level application: about `6.7 million` voters removed under Scenario B and `4.2` to `8.3 million` education records updated under the lower and upper re-labeling bounds.

### Length and cross-references

The section is reduced from roughly six pages to about three pages. The new structure is:

- motivation
- identifying insight from the positive high-education count effect
- accounting equations and bounds
- national event-time-zero decomposition
- dynamic national decomposition
- spatial application preview
- limitations

I also updated `paper/sections/introduction.tex` so the roadmap now mentions Section 5 as the decomposition section between the registry evidence and the LAPOP trust evidence.

### Remaining placeholder

Figure 6 is intentionally a placeholder. The municipality-level map itself still needs to be generated in a subsequent task and saved to `resources/images/decomposition/municipal_decomposition_map.pdf`.
