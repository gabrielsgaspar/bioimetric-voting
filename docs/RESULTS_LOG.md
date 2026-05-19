# Results Log

Every result should be traceable to code, data, and specification. Do not record speculative claims as verified results.

## Template

### R-YYYY-MM-DD-001: [Result title]
- Date:
- Owner:
- Code:
- Data:
- Specification:
- Output file:
- Main estimate / pattern:
- Interpretation:
- What it shows:
- What it does not show:
- Robustness:
- Concerns:
- Paper claim supported:
- Status: exploratory / draft / verified / rejected

## Existing Results To Verify And Preserve

### R-2026-05-19-001: Base dos Dados health-outcome screen
- Date: 2026-05-19
- Owner: Administrative Data Lead
- Code: `src/analysis/build_bdd_health_outcomes_bvr_panel.py`; `src/analysis/run_bdd_health_callaway_santanna_screen.py`
- Data: `data/clean/downstream/bdd_health_bvr_screen_panel_2000_2020.parquet`, built from Base dos Dados SINASC, SIM, MS population, immunization, primary-care, and IEPS municipal health tables.
- Specification: Callaway-Sant'Anna event studies using strict first-BVR timing, never-treated controls, event time -2 as reference through `anticipation = 1` and universal base period, hybrid municipalities excluded, and municipality-clustered standard errors.
- Output file: `resources/tables/bdd_health_callaway_santanna_screen/screening_results.csv`; ranked screen at `resources/tables/bdd_health_callaway_santanna_screen/screening_results_ranked.csv`; plots under `resources/figures/bdd_health_callaway_santanna_screen/`.
- Main estimate / pattern: 78 of 81 outcomes estimated. Outcomes with pass/near pretrend diagnostics and p < 0.10 include teen-mother share among low-education-proxy mothers (+1.43 pp), IEPS avoidable mortality (+5.01 per 100k), 1-3 prenatal visits among all mothers (-0.34 pp), high-education 1-3 prenatal visits (-0.20 pp), low Apgar 1 among all mothers (+0.24 pp, p = 0.052), all-mother low-birthweight share (+0.17 pp, p = 0.086), BCG coverage (+2.60 pp, near pretrend), and SUS ICU beds (+0.23 per 100k, p = 0.092).
- Interpretation: exploratory downstream screen. The most promising health-related signal is a compositional shift in SINASC maternal-age outcomes, especially teen mothers among the low-education proxy. Prenatal-visit categories are also worth follow-up. Avoidable mortality has a strong statistical pattern but is broader, starts only in 2010 through IEPS, and is less directly tied to the BVR mechanism.
- What it shows: several outcomes survive a simple pretrend screen and merit closer diagnostic work.
- What it does not show: a final causal health effect, a family-wise-error-adjusted discovery, or a mechanism disentangling maternal composition from health production.
- Robustness: needs cohort-support checks, not-yet-treated controls, alternative pretrend tests, population/birth weighting, and sensitivity to dropping early BVR cohorts and 2020.
- Concerns: multiple testing; education split is a full-period proxy because `escolaridade_mae` pools 8-11 completed years; congenital-anomaly variants failed in the R estimator; IEPS and some vaccine/adequacy series have shorter support windows.
- Paper claim supported: none yet; candidate appendix/downstream-outcome screen only.
- Status: exploratory.

### R-EXISTING-001: Registry contraction and education-composition effects
- Source docs: `BVR.md`, `PAPER.md`, `paper/sections/bvr_and_electorate_size.tex`
- Code/output: existing event-study outputs under `resources/regressions/bvr/` and legacy outputs under `_legacy_resources/`
- Main pattern: BVR adoption is associated with an immediate registry contraction and a large shift away from low recorded education and toward high recorded education.
- Interpretation: strongest administrative evidence in the project.
- Status: existing result; verify exact preferred output paths before citing in new docs or paper revisions.

### R-EXISTING-002: Decomposition and education-record updating bounds
- Source docs: `PROMPT_REPORT.md`, `PROMPT_REPORT_v2.md`, `paper/sections/decomposition.tex`
- Code/output: `src/decomposition/`, `data/clean/decomposition/`, `resources/regressions/decomposition/`
- Main pattern: positive high-education stock effects imply positive re-labeling/updating under the accounting logic.
- Interpretation: administrative accounting, not person-level proof of education updating.
- Status: existing result; verify final v2 output paths before treating as final.

### R-EXISTING-003: LAPOP trust interactions
- Source docs: `docs/LAPOP_TRUST_REPLICATION_DEBUG_NOTES.md`, `paper/sections/perceived_integrity_trust.tex`
- Code/output: `src/analysis/run_lapop_trust_regressions_replicated.py`, LAPOP resources in legacy and active output folders.
- Main pattern: existing paper text emphasizes a positive institutional-trust association among lower-education respondents.
- Interpretation: secondary and suggestive.
- Status: existing result; structural interpretation requires LAPOP comparability audit.

### R-2026-05-12-001: Current-data LAPOP trust/democracy replication
- Date: 2026-05-12
- Owner: Survey/LAPOP Lead
- Code: `scripts/replicate_lapop_trust_outputs.py`
- Data: `data/clean/lapop/lapop_brazil_analysis_2007_2021.parquet`; `data/clean/ibge/municipality_gdp_population_lapop_years.parquet`
- Specification: comparable official public LAPOP waves with the full eight-item trust block and three-item democracy block: 2008, 2010, 2012, 2014, 2017, 2019. PCA outcomes use median imputation, standardization, and PC1. Regressions use `any_bvr`, respondent controls, municipality fixed effects, survey-year fixed effects, and two-way clustered standard errors by municipality and survey year where numerically feasible.
- Output file: `resources/logs/lapop_trust_replication_log.md`; paper-facing plots at `resources/lapop/figures/trust_interactions_barplot.pdf` and `resources/lapop/figures/democracy_interactions_barplot.pdf`; PCA table at `resources/tables/lapop_pca_decomposition_main.tex`.
- Main estimate / pattern: trust PC1 explains 49.09 percent of variance; democracy PC1 explains 41.04 percent. In current-data regressions, the low-education interaction is positive for institutional trust (0.149, s.e. 0.045) and positive but not significant for democracy (0.042, s.e. 0.035). The married interaction for institutional trust is negative (-0.109, s.e. 0.048).
- Interpretation: current organized LAPOP data reproduce the broad paper pattern that the low-education interaction is strongest for institutional trust and weaker for democracy, but exact paper numbers are stale.
- What it shows: the paper-facing PCA plots/table and trust/democracy interaction plots can be regenerated from the current clean LAPOP panel.
- What it does not show: a structural survey calibration result, an exact recovery of the older notebook/paper sample, or a clean individual-level exposure design.
- Robustness: TBD.
- Concerns: paper text still describes 2006, 2016, and 2018 survey years, while the current official public file uses actual LAPOP years 2008, 2010, 2012, 2014, 2017, and 2019 for the comparable trust/democracy block.
- Paper claim supported: suggestive secondary evidence on BVR exposure and institutional trust among lower-education respondents, with updated sample caveat.
- Status: draft; ready for PI review before paper text is updated.

### R-2026-05-12-002: Combined society-trust PCA and interactions
- Date: 2026-05-12
- Owner: Survey/LAPOP Lead
- Code: `scripts/replicate_lapop_trust_outputs.py`
- Data: `data/clean/lapop/lapop_brazil_analysis_2007_2021.parquet`; `data/clean/ibge/municipality_gdp_population_lapop_years.parquet`
- Specification: combines the eight institutional-trust items and three democracy items into one 11-item PCA. `democracy_satisfaction` is reverse-coded before PCA. The standardized first principal component is saved as `society_trust`.
- Output file: `resources/lapop/figures/society_trust_interactions_barplot.pdf`; `resources/lapop/pca/society_trust_explained_variance.pdf`; `resources/lapop/regressions/society_trust_interactions/regression_table.parquet`.
- Main estimate / pattern: society-trust PC1 explains 38.61 percent of total variance. The low-education interaction is positive (0.145, s.e. 0.045); the married interaction is negative (-0.102, s.e. 0.044).
- Interpretation: the combined index preserves the same broad heterogeneity pattern as the institutional-trust-only outcome, but blends institutional confidence with broader democratic attitudes.
- What it shows: the combined PCA is feasible and produces paper-style interaction and variance plots.
- What it does not show: that the 11-item object is conceptually superior to keeping institutional trust and democracy separate.
- Robustness: TBD.
- Concerns: PC1 explains less variance than the trust-only PC1, consistent with the democracy items adding a less one-dimensional block.
- Paper claim supported: draft alternative summary outcome for survey appendix or robustness section.
- Status: draft; PI review needed before replacing the two-index presentation.

### R-EXISTING-004: 2021 backlash/integrity regressions
- Source docs: `docs/LAPOP_BACKLASH_REGRESSIONS_NOTES.md`, `paper/sections/perceived_integrity_trust.tex`
- Code/output: `src/analysis/run_lapop_backlash_regressions.py`
- Main pattern: existing paper text reports skepticism among Bolsonaro-aligned respondents but limited evidence that BVR amplified backlash.
- Interpretation: descriptive/reduced-form cross-section.
- Status: existing result; keep secondary.

### R-2026-05-15-001: Paper-facing BVR registry plots restored
- Date: 2026-05-15
- Owner: Administrative Data Lead
- Code: `scripts/rebuild_bvr_paper_figures.py`
- Data: existing Callaway-Sant'Anna event-study outputs under `resources/regressions/bvr/`; current clean TSE panel `data/clean/tse/tse_municipality_year_2000_2020.parquet` for TWFE robustness plots.
- Specification: main paper-facing Callaway-Sant'Anna plots use strict BVR, exclude ever-hybrid municipalities, use never-treated controls, event window `[-8, 8]`, event time `-2` as reference, and municipality-clustered standard errors inherited from the available `did` outputs. Hybrid-inclusive appendix plots use strict-or-hybrid treatment and never-treated controls. Dynamic TWFE robustness plots use municipality and election-year clustered standard errors.
- Output file: paper-facing plots under `resources/regressions/bvr/*/{strict_bvr,including_hybrid}/`, robustness plots under `resources/robustness/`, and audit files `resources/logs/bvr_paper_figure_rebuild_audit.csv` and `resources/logs/paper_figure_path_audit_after_bvr_rebuild.csv`.
- Main estimate / pattern: the restored main plots support the paper claims of an adoption-time registry contraction and a shift away from low-education registrants toward high-education registrants. Hybrid-inclusive estimates preserve signs with attenuated impact magnitudes.
- Interpretation: administrative event-study evidence; the high-/low-education log-count figure is added as appendix support for the composition discussion.
- What it shows: the BVR registry figures and robustness plots referenced in the registry section and registry robustness appendix now resolve to generated files.
- What it does not show: a successful R `reg-did` rerun on this machine, because `Rscript` is not installed locally; the available `did` outputs also document that year clustering is not supported by that `att_gt()` interface.
- Robustness: state-year FE, within-state-support, permutation, HonestDiD sensitivity, alternative-estimator comparison, and hybrid-inclusive plots are present.
- Concerns: non-BVR missing figure slots remain for decomposition, downstream estimator comparison, and LAPOP individual event-study figures.
- Paper claim supported: registry-size and education-composition figure references in the main text and BVR robustness appendix.
- Status: generated; needs a full LaTeX build on a machine with `latexmk` or equivalent TeX tooling.

## Calibration-Note Prototype Moments

These values come from `calibration_master.pdf` and must be verified against code/output before being treated as final.

### R-2026-05-19-001: SICONFI tax-capacity and financing screen audit
- Date: 2026-05-19
- Owner: Administrative Data Lead / Skeptical Replicator
- Code: `src/analysis/build_siconfi_tax_capacity.py`; `src/analysis/run_siconfi_tax_capacity_callaway_santanna.py`; `src/analysis/run_siconfi_financing_callaway_santanna.py`
- Data: `data/clean/downstream/siconfi_tax_capacity_annual_2000_2022.parquet`; `data/clean/downstream/siconfi_tax_capacity_cycle2_2000_2022.parquet`; `data/clean/downstream/siconfi_spending_categories_cycle2_2000_2022.parquet`
- Specification: exploratory Callaway-Sant'Anna screens using forward two-year cycles, strict BVR timing, hybrids excluded, event time -2 as anchor, and municipality-clustered standard errors.
- Output file: tax-capacity outputs under `resources/did/siconfi_tax_capacity_callaway_santanna/`; financing outputs under `resources/did/siconfi_financing_callaway_santanna/`; audit files `resources/logs/siconfi_financing_category_audit.csv`, `resources/logs/siconfi_financing_raw_account_support.csv`, and `resources/logs/siconfi_financing_identity_checks_by_cycle.csv`.
- Main estimate / pattern: own-tax revenue shares fall after BVR and total revenue/spending rise together in the first-pass screen, but financing-category shares have important pre-trends and accounting-denominator concerns.
- Interpretation: tax-capacity and financing outcomes are exploratory only. Broad SICONFI account codes are correctly mapped, but current-plus-capital revenue does not consistently equal the total-revenue line in 2002-2012, and some borrowing-related categories are sparse.
- What it shows: credit-operation revenue is the correct revenue-flow proxy for new borrowing, but it is zero for most municipality-cycle observations; debt-service expenditure rises in the screen but measures payments, not debt stock.
- What it does not show: evidence that municipalities finance post-BVR expenditure increases through new debt issuance, or a validated revenue-composition mechanism ready for the paper.
- Robustness: use combined categories such as total transfers, non-tax revenue, and aggregate debt service; avoid standalone credit operations, asset sales, loan-amortization receipts, and individual interest/amortization components as primary event-study outcomes.
- Concerns: pre-trends remain; revenue-share denominators are affected by hierarchy/reporting changes; debt stock must be measured from SICONFI fiscal-management/balance-sheet data rather than expenditure flows.
- Paper claim supported: no paper claim yet.
- Status: exploratory; use as diagnostic only pending category redesign and debt-stock data.

### R-2026-05-19-002: SICONFI consistent spending-category revenue-share screen
- Date: 2026-05-19
- Owner: Administrative Data Lead / Skeptical Replicator
- Code: `src/analysis/run_siconfi_spending_revenue_share_callaway_santanna.py`
- Data: `data/clean/downstream/siconfi_spending_categories_annual_2000_2022.parquet`; `data/clean/downstream/siconfi_spending_categories_cycle2_2000_2022.parquet`; `data/clean/downstream/siconfi_tax_capacity_cycle2_2000_2022.parquet`
- Specification: Callaway-Sant'Anna event studies using forward two-year cycles from 2000-2020, strict BVR timing, hybrids excluded, not-yet-treated controls, event time -2 anchor, and municipality-clustered standard errors. The `did` package rejected year clustering because year is time-varying in the panel interface.
- Output file: `resources/did/siconfi_spend_revshare_cs/forward_two_year_nonhybrid_2000_2020_notyettreated_control/spending_revenue_share_estimate_summary.csv`; figures under `resources/figures/siconfi_spend_revshare_cs_notyettreated_control/`; quality audit at `resources/logs/siconfi_spending_category_quality_audit_2000_2020.csv`.
- Main estimate / pattern: 17 categories pass the 2000-2020 support and scale screen. Log per-capita expenditure rises after strict BVR for total/current spending, personnel, infrastructure/urbanism/transport/agriculture, and aggregate debt service; education, health, social assistance, and social policy rise more modestly. Revenue-share estimates are noisier, especially for broad aggregates, but infrastructure and urbanism have the clearest positive share-to-total-revenue patterns among smaller categories.
- Interpretation: a stricter category-quality screen keeps the broad spending expansion pattern while removing sparse or unstable standalone accounts such as debt amortization, interest charges, special charges, and other current spending.
- What it shows: the spending patterns are not driven solely by very sparse SICONFI accounts; several large and consistently observed categories move in the expected direction.
- What it does not show: a final paper-ready mechanism for revenue composition or debt financing; some broad revenue-share plots have high variance due denominator/reporting issues.
- Robustness: compare with the earlier spending-share-to-total-spending plots and redesign revenue-share outcomes around broader revenue bins before making paper claims.
- Concerns: 2000-2001 function labels are historically broader for education, health, social assistance, and urbanism, so those categories are marked with a source-label caveat in the generated plots.
- Paper claim supported: preliminary support for an expenditure expansion after BVR, strongest for total/current spending and infrastructure/urban functions, not a final fiscal-mechanism claim.
- Status: diagnostic; ready for PI review.

### R-2026-05-19-003: Base dos Dados education-outcome screen
- Date: 2026-05-19
- Owner: Administrative Data Lead / Skeptical Replicator
- Code: `src/analysis/build_bdd_education_outcomes_bvr_panel.py`; `src/analysis/run_bdd_education_callaway_santanna_screen.py`
- Data: `data/clean/downstream/bdd_education_bvr_screen_panel_2000_2020.parquet`
- Specification: exploratory Callaway-Sant'Anna event studies using strict BVR timing, excluding municipalities ever flagged as hybrid, never-treated controls, and municipality-clustered standard errors. Annual INEP indicators, transition rates, and SICONFI spending use event time -2 as the reference. Biennial odd-year IDEB and SAEB outcomes use event time -1 as the reference because strict BVR cohorts are even election years and event time -2 is not an observed assessment year.
- Output file: ranked screen at `resources/tables/bdd_education_callaway_santanna_screen/screening_results_ranked.csv`; candidate plots under `resources/figures/bdd_education_callaway_santanna_screen/`; estimator outputs under `resources/did/bdd_education_callaway_santanna_screen/`.
- Main estimate / pattern: 140 of 146 outcomes estimated successfully. Only 32 have pass/near pretrends; 108 fail the pretrend screen. Among pass/near outcomes with p < 0.10, achievement estimates are positive, including municipal final-years IDEB approval (+1.52 pp), municipal grade-5 Portuguese SAEB score (+1.96), municipal initial-years IDEB math score (+2.24), and municipal final-years IDEB flow indicator (+0.014). The only clean dropout/flow signal is lower municipal final-years elementary abandonment (-0.40 pp). Students per class in municipal final-years elementary also falls (-0.36 students).
- Interpretation: this screen does not support the mechanism that the teen-mother increase is mediated by worse school dropout or lower achievement in treated municipalities. The cleaner education results lean toward improved measured achievement/flow or lower abandonment, not deterioration.
- What it shows: Base dos Dados has usable municipality-year education outcomes for testing education mechanisms: INEP annual indicators, INEP transition/evasion rates, IDEB, SAEB, and SICONFI education spending.
- What it does not show: a mother-education split in school outcomes, a validated education-spending effect, or a final causal mechanism. Spending proxies fail the pretrend screen, and many significant education outcomes also fail pretrends.
- Robustness: prioritize pass/near outcomes; inspect public versus municipal network sensitivity; consider dropping 2020 for annual school indicators because of COVID schooling disruptions.
- Concerns: multiple-outcome screening is exploratory; IDEB/SAEB are biennial and use a different reference period; six sparse municipal secondary-school indicators failed the estimator.
- Paper claim supported: no paper claim yet; useful diagnostic evidence against the "worse education investment/achievement" channel for the teen-mother result.
- Status: exploratory; ready for PI review.

### R-2026-05-19-004: Base dos Dados adult/EJA education-resource screen
- Date: 2026-05-19
- Owner: Administrative Data Lead / Skeptical Replicator
- Code: `src/analysis/build_bdd_adult_education_bvr_panel.py`; `src/analysis/run_bdd_adult_education_callaway_santanna.py`
- Data: `data/clean/downstream/bdd_adult_education_bvr_panel_2000_2020.parquet`
- Specification: exploratory Callaway-Sant'Anna event studies using strict BVR timing, excluding municipalities ever flagged as hybrid, never-treated controls, event time -2 as the reference, and municipality-clustered standard errors. Outcomes compare EJA/adult enrollment, EJA teachers, and SICONFI EJA subfunction spending against regular child/basic education measures.
- Output file: ranked screen at `resources/tables/bdd_adult_education_callaway_santanna/screening_results_ranked.csv`; candidate plots under `resources/figures/bdd_adult_education_callaway_santanna/`; estimator outputs under `resources/did/bdd_adult_education_callaway_santanna/`.
- Main estimate / pattern: all 23 focused outcomes estimated after adding cleaned SICONFI spending-share ratios. The clean ratio estimates show lower EJA budget weight after BVR: EJA as a share of total education spending falls by 0.190 pp (s.e. 0.057, p < 0.001, pretrend near because event time -8 is positive), and EJA relative to child/basic education spending falls by 0.386 pp (s.e. 0.082, p < 0.001, pretrend pass). Child/basic education as a share of total education spending rises by 0.522 pp but is not statistically significant (s.e. 0.482, p = 0.279, pretrend pass). EJA spending per capita is negative but not significant (-0.033 log points, p = 0.143, pretrend near). Child/basic education spending per capita has a pass pretrend but no clear effect (-0.032 log points, p = 0.439). Enrollment and teacher-count outcomes mostly fail pretrend checks.
- Interpretation: there is stronger diagnostic evidence that EJA loses relative budget share after BVR, especially compared with child/basic education. The evidence still does not cleanly establish that child/basic education gained resources in levels or as a total-education share. Enrollment and teacher-count patterns cannot be interpreted causally because treated municipalities were already on different trajectories.
- What it shows: Base dos Dados contains direct adult-education/EJA measures: INEP EJA enrollment and teachers from 2007 onward and SICONFI subfunction `3.12.366 Educação de Jovens e Adultos` spending from 2004 onward.
- What it does not show: a confirmed "adult-to-child" resource shift, or a mechanism linking BVR education-record updating to teen motherhood.
- Robustness: next version should test state-by-year support, drop 2020, and compare spending shares using a denominator that explicitly separates broad/uncategorized SICONFI education subfunctions. The current cleaned ratios drop municipality-years where reported total education spending is positive but smaller than EJA plus child/basic subfunction spending.
- Concerns: EJA program participation may be affected by broader secular decline and state/municipal policy changes; most count outcomes fail pretrends. The EJA-total cleaned share has a near rather than pass pretrend screen because of one distant lead at event time -8.
- Paper claim supported: possible diagnostic claim only: EJA spending share declines in treated municipalities, but evidence for child-resource reallocation is weak.
- Status: exploratory; ready for PI review.

### R-2026-05-19-005: BVR education-complement and school-access mechanism screen
- Date: 2026-05-19
- Owner: Administrative Data Lead / Skeptical Replicator
- Code: `src/analysis/build_bdd_school_access_bvr_panel.py`; `src/analysis/run_bdd_school_access_callaway_santanna.py`; focused summary tables derived from `src/analysis/run_siconfi_spending_revenue_share_callaway_santanna.py` outputs.
- Data: `data/clean/downstream/bdd_school_access_bvr_panel_2000_2020.parquet`; existing SICONFI forward-two-year outputs under `resources/did/siconfi_spend_revshare_cs/forward_two_year_nonhybrid_2000_2020_notyettreated_control/`.
- Specification: exploratory Callaway-Sant'Anna screens using strict BVR timing, excluding municipalities ever flagged as hybrid, never-treated controls, event time -2 as the reference, and municipality-clustered standard errors. School-access outcomes use annual 2008-2020 Censo Escolar `matricula` records for regular non-EJA students ages 6-17. SICONFI complement outcomes use forward two-year spending cycles from the existing screen.
- Output file: school-access ranked screen at `resources/tables/bdd_school_access_callaway_santanna/screening_results_ranked.csv`; school-access plots under `resources/figures/bdd_school_access_callaway_santanna/`; focused complementarity table at `resources/tables/siconfi_complementarity_bvr_screen/complementarity_spending_results.csv`; complementarity plot at `resources/figures/siconfi_complementarity_bvr_screen/infrastructure_urbanism_transport_event_studies.png`.
- Main estimate / pattern: transport/access proxies move strongly in the intuitive direction after BVR, but all fail pretrend checks. Public-school municipal-transport share rises by 3.23 pp, public-transport share rises by 1.75 pp, and bus/van transport rises by 0.96 pp, but each has large pre-BVR trends. Infrastructure, urbanism, and transport spending also rise in log per-capita and revenue-share screens, but most pretrends fail; the only near-clean complement is infrastructure's share of total revenue (+0.408 pp, p < 0.001, pretrend near).
- Interpretation: the access/complement channel is plausible descriptively but not identified in the current event-study design. Treated municipalities were already on different transport/access and infrastructure trajectories before strict BVR, so these variables cannot yet explain the cleaner child education improvements causally.
- What it shows: Base dos Dados contains useful school-access proxies in Censo Escolar `matricula`: public transport use, municipal/state responsibility for student transport, bus/van and boat transport, rural residence, and residence outside the school municipality. SICONFI contains complementary spending proxies for infrastructure, urbanism, transport, capital transfers, debt-service payments, and credit operations.
- What it does not show: literal home-to-school distance, a clean access-treatment effect, or clean evidence that new municipal debt financed education-complement investment. Existing debt proxies are flow/payment measures; debt stock should be built from `basedosdados.br_me_siconfi.municipio_balanco_patrimonial` before making a debt claim.
- Robustness: try state-by-year or municipality-specific trend adjustments, two-year school-access cycles, cohort restrictions with more symmetric support, and rural/low-connectivity heterogeneity. Build debt-stock outcomes from balance-sheet accounts rather than relying on credit-operation revenues and debt-service payments.
- Concerns: Censo Escolar transport measures have strong secular adoption patterns; access variables are annual and begin in 2008, leaving thin pre-periods for early strict-BVR cohorts.
- Paper claim supported: no paper claim yet; useful diagnostic evidence that the missing mechanism is more likely complementary municipal capacity/access than education-budget levels, but current access proxies do not pass pretrend screens.
- Status: exploratory; needs robustness before mechanism claims.

### R-2026-05-19-006: Annual SICONFI complementarity spending screen
- Date: 2026-05-19
- Owner: Administrative Data Lead / Skeptical Replicator
- Code: `src/analysis/run_siconfi_complementarity_annual_callaway_santanna.py`.
- Data: annual SICONFI spending and revenue panels at `data/clean/downstream/siconfi_spending_categories_annual_2000_2022.parquet` and `data/clean/downstream/siconfi_tax_capacity_annual_2000_2022.parquet`.
- Specification: annual 2000-2020 Callaway-Sant'Anna event studies using strict BVR timing, excluding municipalities ever flagged as hybrid, never-treated controls, event time -2 as the reference, and municipality-clustered standard errors. Outcomes cover infrastructure, urbanism, and transport spending as log real per-capita spending in December 2008 BRL and as percentage-point shares of total municipal revenue.
- Output file: event-study outputs under `resources/did/siconfi_complementarity_annual_callaway_santanna/`; summary table at `resources/tables/siconfi_complementarity_annual_callaway_santanna/annual_complementarity_results.csv`; combined plot at `resources/figures/siconfi_complementarity_annual_callaway_santanna/annual_infrastructure_urbanism_transport_event_studies.png`.
- Main estimate / pattern: the annual per-capita screen gives positive post-BVR point estimates for infrastructure (+0.043 log points, p = 0.057, pretrend near), urbanism (+0.089, p < 0.001, pretrend fail), and transport (+0.038, p = 0.319, pretrend fail). The annual share-of-revenue outcomes all pass pretrend checks but have imprecise and statistically null aggregate effects: infrastructure -7.30 pp, urbanism -3.54 pp, and transport -0.39 pp.
- Follow-up plot: `src/analysis/run_siconfi_spending_pc_annual_window_plots.py` adds annual log per-capita education and health spending to the infrastructure/urbanism comparison and plots the event window from -6 to +6. The output is `resources/figures/siconfi_spending_pc_annual_callaway_santanna/annual_log_pc_spending_infra_urbanism_education_health_m6_p6.png`; the summary table is `resources/tables/siconfi_spending_pc_annual_callaway_santanna/annual_log_pc_spending_results.csv`. Education remains small and statistically null (+0.007 log points, p = 0.578, pretrend fail); health is positive but imprecise (+0.025 log points, p = 0.126, pretrend near).
- Ref -1 / two-way-cluster follow-up: `src/analysis/run_sunab_ref_m1_twcluster_transport_spending_plots.py` reruns the school-transport and annual SICONFI log per-capita spending event studies with event time -1 as the reference and standard errors clustered by municipality and calendar year. The installed `did::att_gt()` implementation rejects time-varying cluster variables, so this rerun uses Sun-Abraham/fixest rather than Callaway-Sant'Anna. Outputs are under `resources/figures/bdd_school_access_sunab_ref_m1_twcluster/`, `resources/figures/siconfi_spending_pc_annual_sunab_ref_m1_twcluster/`, and `resources/tables/sunab_ref_m1_twcluster_transport_spending/sunab_ref_m1_twcluster_results.csv`. The post-treatment event-mean over 0 through 6 is +0.013 for public school transport, +0.072 for infrastructure, +0.084 for urbanism, +0.028 for education, and +0.011 for health; only infrastructure has near-clean pretrends under this diagnostic.
- C&S versus BJS transport comparison: `src/analysis/run_school_transport_cs_bjs_ref0_comparison.py` compares Callaway-Sant'Anna and Borusyak-Jaravel-Spiess estimates for the share of public-school students using public school transport, clustered at municipality level. Since neither estimator treats event time 0 as an omitted pre-treatment base, the side-by-side figure normalizes each estimated path to zero at event time 0. Outputs are at `resources/figures/bdd_school_transport_cs_bjs_ref0/public_school_transport_cs_bjs_ref0_m6_p6.png` and `resources/tables/bdd_school_transport_cs_bjs_ref0/public_school_transport_cs_bjs_ref0_summary.csv`. Both estimators fail pretrend checks in the -6 to -1 window; normalized post means over event times 1 through 6 are +0.0069 for C&S and +0.0030 for BJS.
- Interpretation: relative to the earlier forward-two-year complementarity screen, annual data weaken the case that BVR clearly raised the budget share going to complementary infrastructure/transport functions. There is suggestive evidence of higher urbanism spending per capita, and weaker near-clean evidence for infrastructure per capita, but the cleanest annual share specifications do not show a detectable post-BVR reallocation.
- What it does not show: clean evidence that municipalities financed the education gains through higher complementary spending shares, or that debt funded the channel. Debt stock still requires a balance-sheet outcome from `basedosdados.br_me_siconfi.municipio_balanco_patrimonial`.
- Status: exploratory; useful robustness update to the complementarity mechanism screen.

### R-2026-05-19-007: BJS ref-0 downstream nonhybrid screen
- Date: 2026-05-19
- Owner: Administrative Data Lead / Skeptical Replicator
- Code: `src/analysis/run_downstream_bjs_ref0_nonhybrid_screen.py`
- Data: existing clean downstream panels: `data/clean/downstream/sinasc_birthweight_bvr_panel_2000_2020.parquet`; `data/clean/downstream/sinasc_birthweight_by_mother_education_bvr_panel_2000_2020.parquet`; `data/clean/downstream/bdd_health_bvr_screen_panel_2000_2020.parquet`; `data/clean/downstream/bdd_education_bvr_screen_panel_2000_2020.parquet`; `data/clean/downstream/bdd_adult_education_bvr_panel_2000_2020.parquet`; `data/clean/downstream/bdd_school_access_bvr_panel_2000_2020.parquet`; `data/clean/downstream/siconfi_spending_categories_annual_2000_2022.parquet`; `data/clean/downstream/siconfi_spending_categories_cycle2_2000_2022.parquet`; `data/clean/downstream/siconfi_tax_capacity_annual_2000_2022.parquet`; and `data/clean/downstream/siconfi_tax_capacity_cycle2_2000_2022.parquet`.
- Specification: Borusyak-Jaravel-Spiess / imputation DID through the `reg-did` skill, strict BVR timing, observations with `ever_hybrid_bvr == 1` excluded, no added controls, and standard errors clustered at `municipality_id`. Event-study window is -8 to +8. Paths are normalized to event time 0 by subtracting the event-time-0 estimate from every reported event-time coefficient and setting event time 0 to zero. Annual screens use one-year steps; biennial IDEB/SAEB screens shift assessment year to `year - 1` and use two-year steps; two-year SICONFI cycle screens also use two-year steps. School-access and derived SICONFI shares are kept in 0-1 units; existing explicit `_pp` variables remain in percentage points.
- Output file: estimator outputs under `resources/did/downstream_bjs_ref0_nonhybrid/`; master ranking at `resources/tables/downstream_bjs_ref0_nonhybrid/master_bjs_ref0_nonhybrid_ranking.csv`; stacked event-study table at `resources/tables/downstream_bjs_ref0_nonhybrid/master_bjs_ref0_nonhybrid_event_study.csv`; run summary at `resources/tables/downstream_bjs_ref0_nonhybrid/run_summary.json`; combined plots under `resources/figures/downstream_bjs_ref0_nonhybrid/`; interpretive notes at `docs/BJS_REF0_DOWNSTREAM_FINDINGS.md` and `docs/BJS_REF0_DOWNSTREAM_NULL_RESULTS.md`.
- Main estimate / pattern: 298 specifications were screened and all 298 produced usable ref-0-normalized BJS paths. Among the usable paths, 42 pass the pretrend screen, 20 are near, and 236 fail. Pass/near patterns are concentrated in a small number of IEPS mortality/beds and immunization outcomes, selected SINASC birth outcomes, selected teacher-profile and achievement outcomes, two adult/EJA child-spending outcomes, infrastructure/urbanism log per-capita spending, and several SICONFI spending-share or school-access outcomes with only near pretrends.
- Interpretation: this is an exploratory all-downstream BJS robustness screen, not a paper-ready causal claim. The large number of failed pretrend screens is the main result: most downstream outcomes should not be interpreted causally in the current design.
- What it shows: the BJS/imputation estimator can reproduce broad downstream screens under the strict nonhybrid sample and ref-0 normalization, while preserving previous outputs in a separate `bjs_ref0_nonhybrid` namespace.
- What it does not show: clean evidence for a single downstream mechanism. The cleaner outcomes are candidates for targeted robustness checks, not final mechanism estimates.
- Robustness: compare promising pass/near outcomes with existing Callaway-Sant'Anna screens; inspect state-by-year support, COVID-period sensitivity, and category-specific denominator choices for spending shares before writing paper claims.
- Concerns: multiple-outcome screening creates false-positive risk; biennial achievement outcomes require period alignment; several promising school-access and spending-share patterns are only near-pretrend rather than pass.
- Paper claim supported: no new paper claim yet; candidate robustness evidence for follow-up.
- Status: generated; ready for PI review.

### R-CALNOTE-001: Prototype administrative moments
- Date: 2026-05-12 note reviewed
- Owner: Calibration Lead
- Code: TBD
- Data: strict-BVR stock results and municipality-year RAE panel, per calibration note
- Specification: TBD; verify before use
- Output file: `calibration_master.pdf`
- Main estimate / pattern: impact missing mass about 13.06 points of 2006 electorate; re-labeling lower and upper bounds about 5.24 and 18.21 points; recovery about 4.70, 6.76, 9.54, and 12.41 points by k = 2, 4, 6, 8; revision spike about 72.94 at k = -1 and 19.57 at k = 0.
- Interpretation: strong enough to motivate a first-pass administrative calibration.
- What it shows: the current files likely support prototype administrative SMM/GMM.
- What it does not show: verified final estimates, net-of-mobility exclusion, or structural survey effects.
- Robustness: TBD.
- Concerns: must trace every moment to scripts and output files.
- Paper claim supported: calibration feasibility, not final substantive claim.
- Status: draft, verify before use.
