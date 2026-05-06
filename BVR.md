# BVR Registry Effects: Voters, Education Composition, and Related Findings

This memo documents the administrative-data section of the project that estimates how biometric voter registration (BVR) affected the municipal voter registry in Brazil. It focuses on the number of registered voters, the education composition of the electorate, and several related diagnostics and side findings that are useful even when they are not all emphasized in the paper.

The core result is simple and robust: when BVR first entered a municipality's election administration, the registered electorate fell sharply, and the remaining electorate became substantially more educated. The impact-period estimate is approximately an 11 percent decline in registered voters, an 8.9 percentage-point decline in the low-education voter share, and an 8.9 percentage-point increase in the high-education voter share. These effects are visible in the baseline two-way fixed effects event study, remain similar under modern staggered-adoption estimators, survive state-by-year fixed effects, and are far outside placebo permutation distributions.

## 1. Data Sources and Panel Construction

The main administrative panel is:

```text
data/clean/tse/tse_clean_panel_2000_2018.parquet
```

The panel contains municipality-by-election-year observations for every even-year Brazilian election from 2000 through 2018:

```text
year_election in {2000, 2002, 2004, 2006, 2008, 2010, 2012, 2014, 2016, 2018}
```

The final panel has 55,661 municipality-election observations covering 5,571 municipalities. The key columns are:

```text
municipality_id
municipality_name
state
year_election
num_voters
log_num_voters
num_voters_low_ed
log_num_voters_low_ed
num_voters_high_ed
log_num_voters_high_ed
pct_voters_low_ed
pct_voters_high_ed
num_voters_men
num_voters_women
pct_voters_men
pct_voters_women
year_treated
dist_treatment
hybrid
```

The clean panel combines three major inputs:

```text
data/clean/tse_eleitorado/eleitorado_education_gender_2000_2018.parquet
data/clean/tse_bvr/municipality_bvr_first_treat.parquet
data/raw/ibge/bd-tse_mun_ids.csv
```

The first file provides the TSE electorate counts by municipality, election year, education, and gender. The second file provides the first verified election year in which each municipality used biometric voter authentication. The third file provides the municipality-code harmonization needed to align TSE and IBGE municipal identifiers.

The treatment file is built from official TSE sources for the staggered rollout: the 2008 pilot resolution, official 2010 and 2012 rollout files, 2014 electorate files calibrated to official benchmarks, 2016 electorate open data calibrated to the official count of full-biometric municipalities, and 2018 municipal labels. It identifies first verified BVR election-use years in:

```text
2008, 2010, 2012, 2014, 2016, 2018
```

The cohort sizes are:

| First BVR election year | Municipalities |
|---:|---:|
| 2008 | 3 |
| 2010 | 57 |
| 2012 | 239 |
| 2014 | 465 |
| 2016 | 779 |
| 2018 | 1,251 |
| Never treated by 2018 | 2,777 |

The treatment variable in the panel is `year_treated`. Never-treated municipalities are coded as `9999` in the analysis file. The event-time variable is:

```text
dist_treatment_mt = year_election_t - year_treated_m
```

For never-treated municipalities, `dist_treatment` is coded as `-9999` so that they can be retained as controls but do not enter any treated event-time dummy.

## 2. Outcome Definitions

### 2.1 Registered electorate size

The primary scale outcome is the log number of registered voters:

```math
y_{mt}^{voters} = \log(\text{num\_voters}_{mt})
```

where `m` indexes municipality and `t` indexes election year.

The impact coefficient can be read approximately as a percentage change. More exactly, a coefficient `beta` implies:

```math
100 \times [\exp(\beta) - 1]
```

percent change in registered voters.

### 2.2 Low-education voter share

The low-education electorate combines four TSE education categories:

```text
illiterate
reads_and_writes
incomplete_primary
complete_primary
```

The low-education share is:

```math
y_{mt}^{low} =
\frac{\text{num\_voters\_low\_ed}_{mt}}
     {\text{num\_voters}_{mt}}
```

The denominator is the total electorate, including voters with unknown education. This means the low-education and high-education shares need not sum exactly to one, although unknown education is very small in the clean panel.

### 2.3 High-education voter share

The high-education electorate combines:

```text
incomplete_secondary
complete_secondary
incomplete_higher
complete_higher
```

The high-education share is:

```math
y_{mt}^{high} =
\frac{\text{num\_voters\_high\_ed}_{mt}}
     {\text{num\_voters}_{mt}}
```

The high-education share is close to the mirror image of the low-education share because unknown education is rare, especially after the early waves.

### 2.4 Gender side outcomes

The same panel also contains gender outcomes:

```math
\log(\text{num\_voters\_men}_{mt}), \quad
\log(\text{num\_voters\_women}_{mt})
```

and:

```math
\text{pct\_voters\_men}_{mt}
=
\frac{\text{num\_voters\_men}_{mt}}
     {\text{num\_voters}_{mt}}
```

```math
\text{pct\_voters\_women}_{mt}
=
\frac{\text{num\_voters\_women}_{mt}}
     {\text{num\_voters}_{mt}}
```

These are not the main outcomes in the registry section, but they are useful diagnostics because they show whether the registry contraction was demographically symmetric.

## 3. Descriptive Trends

The national electorate grew from about 109.8 million registered voters in 2000 to about 146.8 million in 2018. Over the same period, the education composition changed substantially:

| Election year | Registered voters | Low-education share | High-education share | Male share | Female share |
|---:|---:|---:|---:|---:|---:|
| 2000 | 109,782,873 | 0.728 | 0.270 | 0.493 | 0.505 |
| 2008 | 128,806,592 | 0.639 | 0.360 | 0.482 | 0.517 |
| 2018 | 146,805,548 | 0.461 | 0.538 | 0.475 | 0.525 |

These national trends are important because the event-study design is not estimating a raw before-after change. It compares treated municipalities to municipalities not yet treated or never treated while absorbing municipality fixed effects and election-year shocks.

Unknown education and gender are small. In the validation notes, residual unknown education falls from about 0.25 percent of the electorate in 2000 to about 0.05 percent in 2018. Residual unknown gender falls from about 0.16 percent in 2000 to about 0.03 percent in 2018.

## 4. Baseline Dynamic TWFE Event Study

The baseline specification in the paper is a dynamic two-way fixed effects event study:

```math
y_{mt}
=
\sum_{k \in \mathcal{K}}
\beta_k \mathbf{1}\{t - g_m = k\}
+ \alpha_m
+ \lambda_t
+ \varepsilon_{mt}.
```

Here:

```text
m = municipality
t = election year
g_m = first election year in which municipality m used BVR
alpha_m = municipality fixed effect
lambda_t = election-year fixed effect
epsilon_mt = error term
```

The event-time set follows the paper's two-year election-cycle convention:

```text
K = {-8, -6, -4, 0, 2, 4, 6, 8}
```

The omitted reference period is:

```text
k = -2
```

Thus every coefficient is interpreted relative to the election immediately before BVR first appears in the municipality. Never-treated municipalities are retained as controls. Their event-time dummies are zero because they do not have a finite treatment cohort.

Standard errors in the main table are clustered two ways:

```text
municipality_id and year_election
```

In implementation terms, the baseline is equivalent to:

```text
y ~ event-time dummies + municipality fixed effects + election-year fixed effects
```

with the event-time `-2` bin omitted.

The configuration used by the estimator infrastructure is stored under:

```text
resources/did/twfe_dynamic/log_num_voters/config_used.yml
resources/did/twfe_dynamic/pct_voters_low_ed/config_used.yml
resources/did/twfe_dynamic/pct_voters_high_ed/config_used.yml
```

The core output table is:

```text
resources/tables/twfe_dynamic_main_table.tex
```

## 5. Main Baseline Estimates

The main TWFE event-study estimates are:

| Event time | Log voters | Low-ed share | High-ed share |
|---:|---:|---:|---:|
| -8 | -0.016 | -0.004 | 0.004 |
| -6 | -0.008 | -0.001 | 0.002 |
| -4 | -0.003 | -0.001 | 0.001 |
| 0 | -0.115 | -0.089 | 0.089 |
| 2 | -0.070 | -0.078 | 0.079 |
| 4 | -0.044 | -0.065 | 0.065 |
| 6 | -0.002 | -0.061 | 0.061 |
| 8 | 0.027 | -0.054 | 0.054 |

The impact-period coefficients at event time 0 are the headline:

```math
\hat{\beta}_0^{voters} = -0.115
```

```math
\hat{\beta}_0^{low} = -0.089
```

```math
\hat{\beta}_0^{high} = 0.089
```

The log-voters estimate corresponds to:

```math
100 \times [\exp(-0.115) - 1] \approx -10.9\%.
```

So, on impact, BVR is associated with roughly an 11 percent decline in registered voters.

For education composition, the coefficients are in share units. Therefore:

```text
-0.089 = -8.9 percentage points in the low-education voter share
 0.089 =  8.9 percentage points in the high-education voter share
```

The total electorate effect fades over later horizons: by event time +6, the log-voter coefficient is close to zero. The composition effect is more persistent. Even by event time +8, the low-education share remains about 5.4 percentage points lower and the high-education share about 5.4 percentage points higher than in the reference period.

## 6. Interpretation of the Main Results

The first-order interpretation is that BVR tightened the registry. Municipalities entering the biometric regime experienced an immediate decline in registered voters, consistent with the reform removing inactive, duplicate, deceased, or otherwise non-updated registrations.

The second result is compositional. The registry decline was not neutral with respect to education. The electorate became substantially more educated at the moment of BVR adoption. This is consistent with two non-exclusive channels:

1. lower-education voters were more likely to be removed or fail to complete biometric recadastramento;
2. the administrative updating process corrected stale education information in ways that mechanically shifted some registrants from lower to higher education categories.

The paper should therefore avoid presenting the education result as pure differential turnout or pure differential compliance. The data show a registry composition shift. The exact mix of voter noncompliance, outdated records, and administrative recoding is harder to separate.

## 7. Counts by Education: A Useful Side Finding

The share effects are easier to interpret alongside the log count effects by education group.

We do have dynamic TWFE DiD results for both:

```text
log_num_voters_low_ed
log_num_voters_high_ed
```

The result directories are:

```text
resources/did/twfe_dynamic/log_num_voters_low_ed/
resources/did/twfe_dynamic/log_num_voters_high_ed/
```

The corresponding event-study estimate files are:

```text
resources/did/twfe_dynamic/log_num_voters_low_ed/event_study_estimates.csv
resources/did/twfe_dynamic/log_num_voters_high_ed/event_study_estimates.csv
```

The plot files are saved in the estimator-output directories:

```text
resources/did/twfe_dynamic/log_num_voters_low_ed/event_study_plot.pdf
resources/did/twfe_dynamic/log_num_voters_high_ed/event_study_plot.pdf
```

and mirrored into the paper-style regression image directory:

```text
resources/images/regressions/twfe_dynamic/log_num_voters_low_ed/event_study_plot.pdf
resources/images/regressions/twfe_dynamic/log_num_voters_high_ed/event_study_plot.pdf
```

These are dynamic TWFE estimates with municipality fixed effects, election-year fixed effects, reference event time `-2`, and standard errors clustered by municipality and election year. I found TWFE dynamic results for these two log education-count outcomes; the multi-estimator comparison runs are available for total log voters and education shares, but not for these education-specific log counts.

The full event-time paths are:

| Event time | Low-ed log count coefficient | 95% CI | High-ed log count coefficient | 95% CI |
|---:|---:|---:|---:|---:|
| -8 | -0.027 | [-0.042, -0.013] | -0.040 | [-0.071, -0.010] |
| -6 | -0.014 | [-0.025, -0.002] | -0.020 | [-0.048, 0.008] |
| -4 | -0.005 | [-0.019, 0.009] | -0.010 | [-0.028, 0.008] |
| -2 | 0.000 | reference | 0.000 | reference |
| 0 | -0.259 | [-0.274, -0.244] | 0.155 | [0.113, 0.197] |
| 2 | -0.196 | [-0.209, -0.184] | 0.173 | [0.099, 0.247] |
| 4 | -0.149 | [-0.174, -0.125] | 0.155 | [0.013, 0.297] |
| 6 | -0.092 | [-0.122, -0.062] | 0.246 | [0.173, 0.319] |
| 8 | -0.068 | [-0.104, -0.033] | 0.162 | [0.117, 0.206] |

At event time 0:

| Outcome | Coefficient | Approximate percent change |
|---|---:|---:|
| `log_num_voters_low_ed` | -0.259 | -22.8% |
| `log_num_voters_high_ed` | 0.155 | 16.8% |

This is one of the most interesting side findings. The low-education electorate falls very sharply, while the high-education count rises at adoption. The impact-period 95 percent confidence interval for the low-education count is entirely negative, and the interval for the high-education count is entirely positive. That means the high-education share increase is not only a denominator artifact from low-education voters dropping out of the registry. The high-education category itself expands.

This supports the idea that the BVR update may have done more than delete records. It may also have updated old education classifications for voters who remained in the registry. That interpretation is plausible because TSE voter records are administrative records that can become stale over time.

## 8. Gender Side Findings

The gender effects are smaller than the education effects but point in a consistent direction.

At event time 0:

| Outcome | Coefficient | Interpretation |
|---|---:|---|
| `log_num_voters_men` | -0.131 | about -12.3% |
| `log_num_voters_women` | -0.099 | about -9.5% |
| `pct_voters_men` | -0.0077 | -0.77 percentage points |
| `pct_voters_women` | 0.0080 | +0.80 percentage points |

The registry contraction appears somewhat larger among men than women. This is not the central claim of the registry section, but it is a useful demographic diagnostic and may be worth preserving in appendix or robustness material.

## 9. Modern Staggered-Adoption Estimators

Because BVR adoption is staggered across municipalities, the paper does not rely only on TWFE. The project also estimates the same dynamic effects using alternative estimators designed for staggered adoption.

The key alternative estimators are:

```text
Callaway-Sant'Anna
Sun-Abraham
Borusyak-Jaravel-Spiess
```

The appendix uses these estimators to verify that the headline registry effects are not artifacts of TWFE weighting under heterogeneous treatment effects.

### 9.1 Callaway-Sant'Anna

The Callaway-Sant'Anna estimator targets group-time average treatment effects:

```math
ATT(g,t)
=
E[Y_t(g) - Y_t(0) \mid G = g],
```

where `G = g` means a municipality first adopts BVR in election year `g`. The estimator compares treated cohorts to an explicit comparison group, here never-treated municipalities, and then aggregates the group-time effects into event-time effects:

```math
ATT(k)
=
\sum_g w_{gk} ATT(g, g+k).
```

This avoids the problem that a TWFE event study can use already-treated units as implicit controls for later-treated units.

### 9.2 Sun-Abraham

The Sun-Abraham interaction-weighted estimator estimates cohort-specific event-time effects:

```math
y_{mt}
=
\sum_g \sum_k \delta_{gk}
\mathbf{1}\{G_m = g\}
\mathbf{1}\{t - g = k\}
+ \alpha_m
+ \lambda_t
+ \varepsilon_{mt}.
```

The event-time coefficients are then aggregated across cohorts using transparent cohort weights. This prevents contamination of lead and lag coefficients from treatment-effect heterogeneity across cohorts.

### 9.3 Borusyak-Jaravel-Spiess

The Borusyak-Jaravel-Spiess imputation estimator first fits an untreated potential-outcome model using untreated observations:

```math
Y_{mt}
=
\alpha_m
+ \lambda_t
+ u_{mt}
\quad \text{for untreated municipality-years}.
```

It then predicts untreated counterfactual outcomes for treated municipality-years:

```math
\widehat{Y}_{mt}(0)
=
\widehat{\alpha}_m
+ \widehat{\lambda}_t.
```

Treatment effects are imputed as:

```math
\widehat{\tau}_{mt}
=
Y_{mt} - \widehat{Y}_{mt}(0),
```

and then averaged by event time.

### 9.4 Impact estimates across estimators

At event time 0, the estimators give very similar results:

| Outcome | TWFE | Callaway-Sant'Anna | Sun-Abraham | BJS |
|---|---:|---:|---:|---:|
| Log voters | -0.115 | -0.113 | -0.113 | -0.107 |
| Low-ed share | -0.089 | -0.087 | -0.083 | -0.086 |
| High-ed share | 0.089 | 0.088 | 0.083 | 0.086 |

This agreement is important. It suggests the main registry effects are not being generated by pathological TWFE comparisons. Some long-horizon coefficients become noisier across estimators, but the impact-period decline in registry size and the education-composition shift are highly stable.

The relevant estimator outputs live under:

```text
resources/did/twfe_dynamic/
resources/did/callaway_santanna/
resources/did/sun_abraham/
resources/did/bjs/
resources/images/regressions/estimator_comparison/
```

## 10. State-by-Year Fixed Effects

A central robustness check replaces national election-year fixed effects with state-by-election-year fixed effects:

```math
y_{mt}
=
\sum_{k \in \mathcal{K}}
\beta_k \mathbf{1}\{t - g_m = k\}
+ \alpha_m
+ \delta_{s(m)t}
+ \varepsilon_{mt}.
```

Here:

```text
delta_{s(m)t} = state-by-election-year fixed effect
```

This specification compares treated and untreated municipalities within the same state and election year. It is especially useful because BVR rollout and political dynamics may both vary across states.

The event-time-zero estimates are nearly unchanged:

| Outcome | Baseline TWFE | State-by-year FE | Within-state support sample |
|---|---:|---:|---:|
| Log voters | -0.115 | -0.117 | -0.115 |
| Low-ed share | -0.089 | -0.090 | -0.088 |
| High-ed share | 0.089 | 0.091 | 0.088 |

All three impact estimates remain within about 2.1 percent of the baseline estimates. This is one of the strongest pieces of evidence that the registry effects are not driven by broad state-level election-year shocks.

## 11. Hybrid Municipalities

The rollout includes municipalities with partial or hybrid biometric coverage, especially in 2018. The clean treatment file preserves this information through the `hybrid` flag.

Hybrid municipalities are analytically important because partial BVR coverage can blur the treatment definition. The project therefore checks robustness to excluding hybrid municipalities. The main registry results remain substantively similar, which suggests the headline effects are not an artifact of ambiguous partial-treatment cases.

## 12. Permutation Tests

The project also runs placebo permutations that preserve the treatment cohort-size distribution. In each placebo draw, municipalities are reassigned to placebo cohorts while keeping the number of municipalities in each cohort fixed. The same event-study estimate is then recomputed.

The empirical p-value is:

```math
p =
\frac{1 + \#\{|\widehat{\beta}^{placebo}_0| \geq |\widehat{\beta}^{actual}_0|\}}
     {1 + B},
```

where `B = 500` placebo draws.

For the three main outcomes, the actual impact estimate lies far outside the placebo distribution:

| Outcome | Actual event-time-0 estimate | Placebo range | Permutation p-value |
|---|---:|---:|---:|
| Log voters | -0.115 | [-0.003, 0.005] | 0.002 |
| Low-ed share | -0.089 | [-0.002, 0.002] | 0.002 |
| High-ed share | 0.089 | [-0.002, 0.002] | 0.002 |

The p-value equals roughly 0.002 because with 500 draws the smallest possible two-sided finite-sample value under this formula is:

```math
\frac{1}{501} \approx 0.001996.
```

## 13. TWFE Weight Diagnostics

The project also checks whether the TWFE event-study estimates are vulnerable to negative-weight pathologies using a de Chaisemartin and D'Haultfoeuille-style diagnostic.

The diagnostic finds:

```text
3 negative-weight ATT components out of 5,460
negative-weight share = 0.055%
negative-weight mass = 0.000004
```

This does not prove that TWFE is always harmless, but it is reassuring for this specific design. The main event-time-zero coefficients are also confirmed by Callaway-Sant'Anna, Sun-Abraham, and BJS estimators, so the paper does not depend on the TWFE diagnostic alone.

## 14. HonestDiD Sensitivity

The project uses Rambachan-Roth HonestDiD sensitivity analysis for the event-time-zero effect. The purpose is to ask how much violation of parallel trends would be needed to overturn the conclusion.

Two types of sensitivity restrictions are considered:

1. smoothness restrictions on deviations from parallel trends;
2. relative-magnitude restrictions, where post-treatment violations are bounded relative to pre-treatment deviations.

Under smoothness restrictions, intervals become wide quickly and include zero by moderate values of the smoothness parameter. Under relative-magnitude restrictions, the event-time-zero conclusions remain signed through `Mbar = 2` for all three main outcomes:

| Outcome | Relative-magnitude interval at Mbar = 2 |
|---|---:|
| Log voters | [-0.142, -0.087] |
| Low-ed share | [-0.099, -0.077] |
| High-ed share | [0.078, 0.100] |

This means that, under the relative-magnitude sensitivity framework, violations of parallel trends would have to be more than twice the observed pre-treatment deviations to include zero.

## 15. Balance and Support

The staggered rollout was not random across municipalities. Cohorts differ in population, GDP per capita, and baseline education composition. For example, treated and never-treated municipalities in the cohort-balance tables differ in pre-treatment population and low-education shares.

This is why the paper emphasizes:

```text
municipality fixed effects
election-year fixed effects
state-by-year fixed effects
within-state support checks
staggered-adoption estimators
permutation tests
HonestDiD sensitivity
```

The identifying assumption is not that treated and untreated municipalities are identical in levels. It is that, absent BVR, treated municipalities would have followed comparable trends after accounting for the included fixed effects and comparison structure. The small pre-treatment event-study coefficients for the main outcomes help support this assumption, but the assumption remains substantive and should be stated carefully.

## 16. Connection to the Paper's Theory

The registry results are the administrative foundation for the rest of the paper. They show that BVR did not merely change a back-office procedure. It changed the measured electorate.

The model's Proposition 2 predicts that changing the electorate can change the perceived constituency faced by politicians. The empirical registry section provides the first step in that chain: the reform reduced the registered electorate and shifted its education composition.

The rest of the paper asks whether this registry shift propagated into political attitudes, candidate entry, party affiliation, vote shares, or municipal policy. The downstream evidence is much weaker than the registry evidence. That contrast matters: BVR clearly reshaped the voter registry, but the paper generally finds more muted evidence that it reshaped the broader political landscape.

## 17. Related Findings Not Central to the Main Registry Section

### 17.1 The high-education count increase is substantively important

The positive effect on `log_num_voters_high_ed` is not just a share effect. It suggests the BVR update process may have reclassified or updated education records. This interpretation is especially plausible because education is a voter characteristic that can change after initial registration.

This is worth mentioning cautiously. It does not invalidate the main composition result, but it complicates a pure "low-education voters were removed" interpretation.

### 17.2 The gender composition effect is smaller but present

Men decline somewhat more than women in the registry. The effect is much smaller than the education effect, but it is consistent with BVR producing demographic selection rather than a purely random registry cleanup.

### 17.3 Agent-simulation validation was weaker than the main registry estimates

The project also contains an exploratory agent-style simulation that attempted to predict municipal dropout patterns from individual-level or demographic structure. The validation table reports:

```text
predicted-observed correlation = 0.067
population-weighted correlation = 0.297
R-squared = 0.004
mean predicted dropout = 0.405
mean observed dropout = 0.092
```

The simulation predicted stronger dropout than observed and only weakly matched municipal variation. It should be treated as exploratory and not as part of the causal registry evidence. Its main value is diagnostic: it shows that simple demographic simulation does not recover the observed municipal pattern very well.

### 17.4 Upstream and downstream political outcomes appear more muted

Separate analyses in the project suggest that BVR's registry effects do not automatically translate into large downstream political changes. For example, the party-affiliation flow exercise finds a mostly null immediate effect once state-by-year fixed effects are included. The downstream fiscal and policy sections are also muted.

This creates an important paper-level interpretation: BVR strongly reshaped the administrative voter registry, but political parties, candidates, and local governments did not respond in equally large or robust ways.

## 18. Files to Check When Reproducing

Core data:

```text
data/clean/tse/tse_clean_panel_2000_2018.parquet
data/clean/tse/tse_clean_panel_2000_2018.csv
data/clean/tse_bvr/municipality_bvr_first_treat.parquet
```

Data notes:

```text
docs/TSE_CLEAN_PANEL_NOTES.md
docs/TSE_BVR_DATASET_NOTES.md
```

Paper sections:

```text
paper/sections/bvr_and_electorate_size.tex
paper/appendix/appendix_main.tex
paper/appendix/appendix_additional_robustness.tex
paper/appendix/appendix_honestdid.tex
```

Main tables:

```text
resources/tables/twfe_dynamic_main_table.tex
resources/tables/agent_sim_validation_table.tex
```

Estimator output directories:

```text
resources/did/twfe_dynamic/log_num_voters/
resources/did/twfe_dynamic/pct_voters_low_ed/
resources/did/twfe_dynamic/pct_voters_high_ed/
resources/did/callaway_santanna/
resources/did/sun_abraham/
resources/did/bjs/
```

Figures:

```text
resources/images/regressions/twfe_dynamic/
resources/images/regressions/estimator_comparison/
```

## 19. Bottom Line

The BVR registry section establishes three durable facts:

1. BVR caused a large immediate decline in the registered electorate, about 11 percent in the impact election.
2. BVR sharply changed the education composition of the registry, lowering the low-education share and raising the high-education share by about 8.9 percentage points.
3. These registry effects are much stronger and more robust than most downstream political or policy effects in the project.

The best interpretation is that BVR was a powerful administrative reform of the voter registry. It cleaned and updated the electorate in a demographically uneven way. The evidence is strongest for the registry itself; claims about broader political consequences should be more cautious and should be tied to the weaker downstream evidence.

## 20. Regional Decomposition Update

I added a regional decomposition module that takes the log-count results seriously as accounting evidence. The key premise is that pure exit cannot increase the high-education voter count. Since the national `log_num_voters_high_ed` coefficient is positive at adoption, re-labeling from low to high education is empirically nonzero.

Main files:

```text
scripts/run_regional_decomposition.py
data/clean/region_mapping/state_to_region.csv
data/clean/tse/tse_clean_panel_2000_2018_with_region.parquet
resources/decomposition/bounds_by_region.csv
resources/decomposition/bounds_by_region_and_event_time.csv
resources/tables/regional_event_time0_coefficients.tex
resources/tables/decomposition_bounds_by_region.tex
resources/tables/decomposition_vs_adpf541.tex
paper/sections/decomposition.tex
```

Regional event-time-zero log-count estimates:

| Region | Log voters | Log low-ed voters | Log high-ed voters |
|---|---:|---:|---:|
| Norte | -0.096 [-0.158, -0.034] | -0.285 [-0.324, -0.247] | 0.128 [0.036, 0.220] |
| Nordeste | -0.125 [-0.144, -0.106] | -0.291 [-0.317, -0.264] | 0.226 [0.185, 0.267] |
| Centro-Oeste | -0.100 [-0.138, -0.061] | -0.275 [-0.302, -0.248] | 0.107 [0.057, 0.158] |
| Sudeste | -0.138 [-0.145, -0.130] | -0.281 [-0.346, -0.217] | 0.042 [-0.087, 0.171] |
| Sul | -0.115 [-0.147, -0.084] | -0.201 [-0.224, -0.178] | 0.021 [0.000, 0.041] |
| National | -0.115 [-0.128, -0.102] | -0.259 [-0.274, -0.244] | 0.155 [0.113, 0.197] |

The national decomposition uses event-time `-2` baseline shares among eventually treated municipalities, weighted by registered voters: `s_L = 0.591`, `s_H = 0.408`. Under those shares, the adoption-period re-labeling bounds are:

```text
National R_min = 6.9% of baseline electorate, 95% CI [5.1, 8.6]
National R_max = 13.5% of baseline electorate, 95% CI [12.9, 14.1]
```

Regional lower bounds on re-labeling are largest in the Northeast:

```text
Nordeste:     8.7%
Norte:        5.8%
Centro-Oeste: 5.2%
Sudeste:      2.2%
Sul:          1.0%
```

The ADPF 541 comparison is mixed. The Northeast has the largest re-labeling lower bound and the largest number of affected voters in levels, but the direct total registry contraction is not larger than the Southeast in rate terms: `11.8%` in the Northeast versus `12.9%` in the Southeast. So the results support regional disproportionality in administrative education updating, but they do not reproduce a simple four-to-one Northeast-versus-Southeast exit-rate claim.

One caveat: the transformed log-count event-study coefficients are estimated separately, so they do not obey an exact raw-count identity. The decomposition therefore reports a residual. Nationally, this residual is `-4.3` percentage points of the baseline electorate. The impact-period bounds are still informative because the lower bound on re-labeling follows directly from the positive high-education count effect.
