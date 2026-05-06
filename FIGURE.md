# Figure Guide for Section 5.5 Decomposition Outputs

This file describes the five municipality-level decomposition figures generated for Section 5.5. It is intended to let a reader, reviewer, or LLM understand the content of each image without seeing the image itself.

All figures use v2 decomposition outputs from `data/clean/decomposition/`, which incorporate the pct-BVR backfill correction.

Unless stated otherwise, rates are fractions of the treated municipality baseline electorate and are displayed in the figure as percentages.

## Where the Figure Files Live

The canonical figure image directory is:

- `resources/decomposition/figures/`

Each figure is saved there in four image variants:

- `resources/decomposition/figures/<figure_name>.pdf`: titled vector version for screen inspection.
- `resources/decomposition/figures/<figure_name>.png`: titled 300dpi raster version for screen inspection.
- `resources/decomposition/figures/<figure_name>_notitle.pdf`: no-title vector version for the paper, where captions provide the title.
- `resources/decomposition/figures/<figure_name>_notitle.png`: no-title 300dpi raster version.

The figure inventory file is also in the same directory:

- `resources/decomposition/figures/figures_metadata.csv`

The old location `paper/figures/decomposition/` is not the canonical location for these decomposition figures. If an editor tab still points to `paper/figures/decomposition/figures_metadata.csv`, use `resources/decomposition/figures/figures_metadata.csv` instead.

Underlying plotted data remain separate from the images:

- `data/clean/decomposition/figure_data/figure_01_data.parquet`
- `data/clean/decomposition/figure_data/figure_02_data.parquet`
- `data/clean/decomposition/figure_data/figure_03_data.parquet`
- `data/clean/decomposition/figure_data/figure_04_data.parquet`
- `data/clean/decomposition/figure_data/figure_05_data.parquet`
- `data/clean/decomposition/figure_data/table_compositional_regressions_coefficients.parquet`

The Figure 4 regression table remains a paper table, not a figure image:

- `paper/tables/decomposition/table_compositional_regressions.tex`

The code that regenerates all figures is:

- `src/decomposition/figures/run_all_decomposition_figures.py`

## Figure 1: Stacked Decomposition by Regime

Files:

- Image base name: `figure_01_stacked_decomposition_by_regime`
- Figure data: `data/clean/decomposition/figure_data/figure_01_data.parquet`
- Source input: `data/clean/decomposition/decomposition_final_aggregate_v2.parquet`

Title:

- `Registry impacts decompose into exit and re-labeling`

What the figure shows:

- This is a two-bar stacked bar chart.
- The x-axis has two bars: `Strict` and `Hybrid`.
- The y-axis is percent of the 2008 baseline electorate in treated municipalities of that first-regime type.
- Each bar is split into two stacked components:
  - Bottom segment: exit.
  - Top segment: Scenario B re-labeling.
- The figure is the headline visual summary of the decomposition by first BVR regime.

Exact plotted values:

| Regime | Component | Rate | Displayed percent |
| --- | --- | ---: | ---: |
| Strict | Exit | 0.136450 | 13.64% |
| Strict | Re-labeling, Scenario B | 0.079267 | 7.93% |
| Strict | Total exit plus re-labeling | 0.215716 | 21.57% |
| Hybrid | Exit | 0.032804 | 3.28% |
| Hybrid | Re-labeling, Scenario B | 0.011562 | 1.16% |
| Hybrid | Total exit plus re-labeling | 0.044367 | 4.44% |

Visual reading:

- The strict bar is much taller than the hybrid bar.
- In strict-first municipalities, exit is the larger component: 13.64 percentage points out of a 21.57 percent total.
- In hybrid-first municipalities, the total is only 4.44 percent, with exit again larger than re-labeling.
- Strict total impact is about 4.86 times the hybrid total impact.

Substantive reading:

- The figure shows that the municipality-level framework attributes much larger registry effects to strict-first BVR municipalities than to hybrid-first municipalities.
- The strict/hybrid difference appears in both channels: exit and Scenario B re-labeling.

## Figure 2: Binned Scatter, Exit Rate vs. Baseline Low-Education Share

Files:

- Image base name: `figure_02_binned_scatter_exit_lowed`
- Figure data: `data/clean/decomposition/figure_data/figure_02_data.parquet`
- Source inputs:
  - `data/clean/decomposition/decomposition_final_municipality_v2.parquet`
  - `data/clean/decomposition/decomposition_panel_main_v2.parquet`

Title:

- `Municipal exit rises with baseline low-education share`

What the figure shows:

- This is a weighted binned scatter plot with two regime-specific series.
- The x-axis is the municipality's baseline low-education share in the electorate.
- The y-axis is the municipality's exit rate, measured as percent of the municipality's baseline electorate.
- Only treated municipalities are included.
- Municipalities are binned separately by first regime into weighted deciles of the baseline low-education share. Weights are the baseline electorate.
- Each regime has:
  - Connected decile means.
  - A shaded 95 percent confidence ribbon around the decile mean exit rate.
  - A dashed weighted regression line.
- Strict is plotted in teal/dark blue. Hybrid is plotted in peach/orange.

Regression line information:

- The regression slope is from a weighted municipality-level regression of `exit_rate_2008` on `baseline_low_ed_share_2008`, with state fixed effects partialed out.
- Standard errors are clustered at the state level.
- The strict slope is 0.186397 with SE 0.044265.
- The hybrid slope is 0.048644 with SE 0.012325.
- Interpreted in percentage-point terms, moving from 0 to 100 percent low-education share is associated with:
  - 18.64 percentage points higher exit in strict municipalities.
  - 4.86 percentage points higher exit in hybrid municipalities.
- A 10 percentage-point higher low-education share corresponds to:
  - About 1.86 percentage points higher exit in strict municipalities.
  - About 0.49 percentage points higher exit in hybrid municipalities.

Regime means used to anchor the regression lines:

| Regime | Weighted mean low-ed share | Weighted mean exit rate |
| --- | ---: | ---: |
| Strict | 0.670824 | 0.136450 |
| Hybrid | 0.637204 | 0.032804 |

Exact binned values:

| Regime | Decile | Municipalities | Weighted low-ed share | Weighted exit rate | 95% CI lower | 95% CI upper |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Strict | 1 | 13 | 44.53% | 12.42% | 9.99% | 14.84% |
| Strict | 2 | 14 | 51.87% | 9.05% | 6.23% | 11.88% |
| Strict | 3 | 29 | 55.14% | 10.82% | 6.74% | 14.89% |
| Strict | 4 | 73 | 59.68% | 11.82% | 9.32% | 14.33% |
| Strict | 5 | 218 | 65.03% | 13.34% | 11.46% | 15.23% |
| Strict | 6 | 335 | 69.82% | 14.96% | 13.21% | 16.72% |
| Strict | 7 | 425 | 74.13% | 14.32% | 13.26% | 15.38% |
| Strict | 8 | 465 | 78.62% | 15.17% | 14.20% | 16.14% |
| Strict | 9 | 423 | 83.30% | 16.26% | 15.46% | 17.06% |
| Strict | 10 | 480 | 88.42% | 18.16% | 17.46% | 18.86% |
| Hybrid | 1 | 5 | 45.33% | 2.44% | 2.01% | 2.86% |
| Hybrid | 2 | 3 | 48.59% | 2.88% | 2.24% | 3.51% |
| Hybrid | 3 | 19 | 53.20% | 2.96% | 2.58% | 3.33% |
| Hybrid | 4 | 73 | 57.82% | 2.78% | 2.31% | 3.25% |
| Hybrid | 5 | 96 | 61.69% | 2.87% | 2.49% | 3.24% |
| Hybrid | 6 | 108 | 64.91% | 3.03% | 2.56% | 3.50% |
| Hybrid | 7 | 231 | 68.36% | 3.14% | 2.74% | 3.53% |
| Hybrid | 8 | 396 | 72.96% | 4.06% | 3.65% | 4.46% |
| Hybrid | 9 | 493 | 79.67% | 4.42% | 4.11% | 4.72% |
| Hybrid | 10 | 422 | 86.34% | 4.43% | 4.13% | 4.73% |

Visual reading:

- The strict series sits far above the hybrid series over the whole support.
- Both series slope upward, but the strict slope is much steeper.
- The strict binned exit rate rises from roughly 9 to 12 percent in the lowest low-ed-share bins to 18.16 percent in the highest bin.
- The hybrid binned exit rate ranges from roughly 2.4 to 4.4 percent.

Substantive reading:

- The model's compositional prediction is supported: municipalities with larger baseline low-education electorates have higher estimated exit.
- The relationship is substantially stronger under strict-first BVR than under hybrid-first BVR.

## Figure 3: State-Level Scatter, Exit Rate vs. Low-Education Share

Files:

- Image base name: `figure_03_state_scatter_exit_lowed`
- Figure data: `data/clean/decomposition/figure_data/figure_03_data.parquet`
- Source inputs:
  - `data/clean/decomposition/decomposition_final_municipality_v2.parquet`
  - `data/clean/decomposition/decomposition_panel_main_v2.parquet`

Title:

- `State exit rates track baseline low-education shares`

What the figure shows:

- This is a state-level scatter plot.
- Each point is a Brazilian state represented in the final v2 municipality-level decomposition outputs.
- The x-axis is the state's low-education share in the 2008 electorate, aggregating treated municipalities in that state.
- The y-axis is the state's exit rate, aggregating treated municipalities in that state.
- Points are colored by region.
- Bubble size is proportional to the treated-municipality baseline electorate in the state.
- Each point is labeled with the two-letter state code.
- A weighted regression line is overlaid.

Important data caveat:

- The prompt requested 26 states plus DF, but DF is absent from `decomposition_final_municipality_v2.parquet`, `decomposition_exit_municipality.parquet`, and `decomposition_relabel_cohort_v2.parquet`.
- Therefore this figure has 26 plotted state points, not 27.
- DF belongs to Center-West conceptually, but it has no final v2 decomposition estimate to plot.

Regression line information:

- Regression: `state_exit_rate ~ state_low_ed_share_2008`.
- Weighted by state baseline electorate.
- Slope: 0.250958.
- SE: 0.130465.
- R-squared: 0.173769.
- Interpreted in percentage-point terms, moving from 0 to 100 percent low-education share is associated with about 25.10 percentage points higher state exit.
- A 10 percentage-point higher low-education share corresponds to about 2.51 percentage points higher state exit.

Exact state-level plotted values:

| State | Region | Baseline electorate | Low-ed share | Exit rate |
| --- | --- | ---: | ---: | ---: |
| AC | North | 419,964 | 72.53% | 5.41% |
| AL | Northeast | 1,974,873 | 78.16% | 16.09% |
| AM | North | 1,260,683 | 60.84% | 9.24% |
| AP | North | 384,703 | 61.27% | 8.27% |
| BA | Northeast | 9,135,992 | 72.43% | 5.17% |
| CE | Northeast | 5,452,728 | 72.32% | 9.52% |
| ES | Southeast | 983,732 | 56.25% | 14.98% |
| GO | Center-West | 3,873,328 | 64.08% | 13.38% |
| MA | Northeast | 3,415,585 | 75.06% | 16.00% |
| MG | Southeast | 12,824,255 | 64.75% | 3.74% |
| MS | Center-West | 589,990 | 55.10% | 6.47% |
| MT | Center-West | 1,273,755 | 61.51% | 7.37% |
| PA | North | 2,430,017 | 66.00% | 10.75% |
| PB | Northeast | 2,653,958 | 75.71% | 12.41% |
| PE | Northeast | 4,681,148 | 69.90% | 14.56% |
| PI | Northeast | 2,183,294 | 78.45% | 13.98% |
| PR | South | 6,490,657 | 59.71% | 11.72% |
| RJ | Southeast | 11,228,591 | 56.45% | 3.89% |
| RN | Northeast | 2,170,031 | 70.65% | 10.53% |
| RO | North | 809,479 | 70.13% | 8.40% |
| RR | North | 247,757 | 60.93% | 7.55% |
| RS | South | 7,921,995 | 61.58% | 6.39% |
| SC | South | 4,354,622 | 59.77% | 5.32% |
| SE | Northeast | 1,369,303 | 73.12% | 9.44% |
| SP | Southeast | 4,059,857 | 55.57% | 10.32% |
| TO | North | 926,625 | 69.08% | 10.02% |

Visual reading:

- Northeast states generally occupy the right side of the plot because they have high low-education shares.
- High-exit Northeast states include AL at 16.09 percent, MA at 16.00 percent, PE at 14.56 percent, and PI at 13.98 percent.
- Some states are notable departures from a simple regional story:
  - ES has a high exit rate of 14.98 percent despite a low-ed share of only 56.25 percent.
  - RJ and MG have low exit rates, 3.89 percent and 3.74 percent, respectively.
  - BA has a high low-ed share of 72.43 percent but a relatively low exit rate of 5.17 percent.
- The fitted line slopes upward, but the R-squared is modest at 0.17.

Substantive reading:

- The state-level relationship is positive but noisier than the municipality-level binned relationship in Figure 2.
- Regional composition helps explain some of the spatial pattern, but there are important state-specific deviations.

## Figure 4: Coefficient Plot, Strict x Low-Education Interaction

Files:

- Image base name: `figure_04_interaction_coefficients`
- Figure data: `data/clean/decomposition/figure_data/figure_04_data.parquet`
- Full coefficient data: `data/clean/decomposition/figure_data/table_compositional_regressions_coefficients.parquet`
- Regression table: `paper/tables/decomposition/table_compositional_regressions.tex`
- Source inputs:
  - `data/clean/decomposition/decomposition_final_municipality_v2.parquet`
  - `data/clean/decomposition/decomposition_panel_main_v2.parquet`
  - `data/clean/decomposition/decomposition_relabel_cohort_v2.parquet`

Title:

- `Strict x low-ed coefficients`

What the figure shows:

- This is a horizontal coefficient plot.
- The y-axis lists three regression specifications.
- The x-axis is the interaction coefficient.
- Each row has:
  - A point estimate.
  - A horizontal 95 percent confidence interval.
  - A vertical reference line at zero.
  - A text label showing coefficient and standard error.
- The plotted coefficient is the strict x low-education-share interaction.

Exact plotted values:

| Specification | Coefficient | SE | 95% CI lower | 95% CI upper | Observations |
| --- | ---: | ---: | ---: | ---: | ---: |
| Spec 1: Pooled | 0.119868 | 0.039186 | 0.043063 | 0.196674 | 4,321 |
| Spec 2: State FE | 0.134383 | 0.042293 | 0.051488 | 0.217278 | 4,321 |
| Spec 3: Municipality x cohort | 0.292553 | 0.014858 | 0.263431 | 0.321676 | 93,484 |

Regression specifications:

- Spec 1 is a pooled cross-municipality regression:
  - Outcome: `exit_rate_2008`.
  - Regressors: low-ed share, strict indicator, strict x low-ed share, log baseline electorate.
  - Weights: 2008 baseline electorate.
  - SEs: clustered by state.
  - Interaction coefficient: 0.119868.
- Spec 2 is the same as Spec 1 plus state fixed effects:
  - Outcome: `exit_rate_2008`.
  - Weights: 2008 baseline electorate.
  - SEs: clustered by state.
  - Interaction coefficient: 0.134383.
- Spec 3 is a within-municipality cross-cohort regression:
  - Outcome: cohort exit rate.
  - Regressors: cohort low-ed share and strict x cohort low-ed share.
  - Fixed effects: municipality and cohort band.
  - Weights: cohort baseline electorate.
  - SEs: clustered by municipality.
  - Interaction coefficient: 0.292553.

Other coefficients from the LaTeX regression table:

| Variable | Spec 1: Pooled | Spec 2: State FE | Spec 3: Municipality x cohort |
| --- | ---: | ---: | ---: |
| Constant | 0.0456 | omitted | omitted |
| Low-ed share, 2008 | 0.0210 | -0.0110 | omitted |
| Strict | 0.0213 | 0.0298 | omitted |
| Strict x low-ed share | 0.1199 | 0.1344 | omitted |
| Log 2008 baseline | -0.0023 | -0.0045 | omitted |
| Cohort low-ed share | omitted | omitted | -0.1582 |
| Strict x cohort low-ed share | omitted | omitted | 0.2926 |

Fit statistics:

| Statistic | Spec 1 | Spec 2 | Spec 3 |
| --- | ---: | ---: | ---: |
| Observations | 4,321 | 4,321 | 93,484 |
| R-squared | 0.59650 | 0.66372 | 0.56112 |
| Within R-squared | not applicable | 0.49456 | 0.10070 |

Visual reading:

- All three interaction estimates are positive.
- All three confidence intervals are entirely above zero.
- Spec 3 is farthest to the right and most precisely estimated.
- Spec 1 and Spec 2 are similar in magnitude, with Spec 2 slightly larger.

Substantive reading:

- The positive interaction is stable across the pooled, state fixed-effect, and within-municipality cohort specifications.
- This supports the prediction that exit is more compositionally sensitive to low-education baseline shares in strict-first municipalities than in hybrid-first municipalities.

## Figure 5: Share of Total Exit and Scenario B Re-labeling by Age Band

Files:

- Image base name: `figure_05_share_by_age_band`
- Figure data: `data/clean/decomposition/figure_data/figure_05_data.parquet`
- Source inputs:
  - `data/clean/decomposition/decomposition_relabel_cohort_v2.parquet`
  - `data/clean/decomposition/decomposition_panel_main_v2.parquet`
  - `data/clean/decomposition/decomposition_final_municipality_v2.parquet`

Title:

- `Exit and re-labeling concentrate in different age bands`

What the figure shows:

- This is a grouped bar chart by age band.
- The x-axis has six age bands:
  - 16-24
  - 25-34
  - 35-44
  - 45-54
  - 55-64
  - 65+
- Each age band has two bars:
  - Share of total exit.
  - Share of total Scenario B re-labeling, labeled `R_B`.
- A short dashed gray horizontal reference segment marks each age band's share of the baseline electorate.
- The y-axis is percent of the total.
- The shares of total exit sum to 100 percent across age bands.
- The shares of total Scenario B re-labeling sum to 100 percent across age bands.
- The population-share reference also sums to 100 percent across age bands.

Age-band construction:

- `16-24`: 16, 17, 18, 19, 20, and 21-24.
- `25-34`: 25-29 and 30-34.
- `35-44`: 35-39 and 40-44.
- `45-54`: 45-49 and 50-54.
- `55-64`: 55-59 and 60-64.
- `65+`: 65-69 through 100+.

Exact plotted values:

| Age band | 2008 population share | Exit count | Share of total exit | R_B count | Share of total R_B |
| --- | ---: | ---: | ---: | ---: | ---: |
| 16-24 | 19.77% | 1,710,898 | 22.01% | 381,844 | 9.18% |
| 25-34 | 24.21% | 1,801,327 | 23.18% | 1,136,125 | 27.32% |
| 35-44 | 19.80% | 1,067,231 | 13.73% | 1,679,655 | 40.39% |
| 45-54 | 15.86% | 781,835 | 10.06% | 662,678 | 15.94% |
| 55-64 | 10.39% | 445,297 | 5.73% | 218,903 | 5.26% |
| 65+ | 9.97% | 1,965,436 | 25.29% | 78,970 | 1.90% |

Visual reading:

- Re-labeling is strongly concentrated in prime adult and middle-age cohorts:
  - The 35-44 band alone accounts for 40.39 percent of total Scenario B re-labeling.
  - The 25-34 band accounts for 27.32 percent.
  - Together, 25-44 accounts for 67.71 percent of Scenario B re-labeling.
- Exit is more dispersed:
  - 65+ accounts for 25.29 percent of exit.
  - 25-34 accounts for 23.18 percent.
  - 16-24 accounts for 22.01 percent.
  - 35-44 accounts for 13.73 percent.
- Compared with baseline population shares:
  - 65+ is only 9.97 percent of the baseline electorate but accounts for 25.29 percent of exit.
  - 35-44 is 19.80 percent of the baseline electorate but accounts for 40.39 percent of R_B.
  - 16-24 is 19.77 percent of the baseline electorate but only 9.18 percent of R_B.

Substantive reading:

- The re-labeling pattern supports the claim that Scenario B re-labeling is concentrated in age ranges where natural education progression should be smaller than among the youngest voters.
- The exit pattern is not confined to working-age cohorts in the v2 outputs. The 65+ band is the largest exit-share band at 25.29 percent, reflecting the large older-cohort exit counts in the saved decomposition outputs.
- This older-age exit concentration should be read together with the diagnostic report's cautions about survival-rate assumptions and older-cohort behavior.

## Cross-Figure Notes

Common palette and encodings:

- Strict regime: teal/dark blue.
- Hybrid regime: peach/orange.
- Exit: dark blue.
- Scenario B re-labeling: orange.
- Population-share references: dashed light gray.
- Continuous color scales are not used in these five figures.

Baseline and sample notes:

- Municipality-level figures use treated municipalities from the v2 final decomposition output.
- The final v2 municipality file has 4,321 treated municipalities.
- Four treated municipalities lack exact 2008 age-by-education baselines. The scripts follow the v2 final table and use `baseline_year_used` for those cases when composition is needed.
- DF is present in the panel timing data but absent from the final v2 decomposition outputs; therefore it is not plotted in Figure 3.

Main empirical takeaways:

- Figure 1: Strict-first BVR municipalities have much larger total decomposed registry impacts than hybrid-first municipalities: 21.57 percent versus 4.44 percent.
- Figure 2: Exit rises with baseline low-education share in both regimes, with a much steeper strict slope: 0.186 versus 0.049.
- Figure 3: State-level exit and low-education share are positively related, but with modest explanatory power: slope 0.251, R-squared 0.174.
- Figure 4: The strict x low-education interaction is positive in all three specifications and statistically above zero.
- Figure 5: Scenario B re-labeling is concentrated in 25-44, especially 35-44; exit is more dispersed and includes a large 65+ component in the v2 outputs.
