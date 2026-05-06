# Compliance Descriptives

The strict-vs-hybrid regression in `resources/regressions/reg_fe_compare/` found a very small hybrid-first registry-count effect at event time 0. This descriptive pass looks directly at biometric compliance rates to see whether that small coefficient reflects low voluntary uptake, regime transitions, or some other pattern in the observed compliance variables.

I use the full clean municipality-year panel, restrict to 2014, 2016, and 2018 because the compliance variables are intentionally missing before 2014, and merge in the previously constructed `first_regime` labels where available. Municipalities not present in the restricted regression panel are assigned the same first-regime rule from the clean-panel treatment-year variables. The output panel contains 16,708 municipality-year observations across 5,570 municipalities.

This is descriptive only. The compliance rate measures the share of currently registered voters with biometric data on file; in strict municipalities, high compliance after cancellation is partly mechanical and should not be read as voluntary uptake.

## Data Coverage

|   year_election |   n_observations |   n_municipalities |   n_nonmissing_pct_with_bvr |   n_missing_pct_with_bvr | mean_pct_with_bvr   | all_zero_pct_with_bvr   |   n_nonmissing_pct_low_ed_with_bvr |   n_missing_pct_low_ed_with_bvr | mean_pct_low_ed_with_bvr   | all_zero_pct_low_ed_with_bvr   |   n_nonmissing_pct_high_ed_with_bvr |   n_missing_pct_high_ed_with_bvr | mean_pct_high_ed_with_bvr   | all_zero_pct_high_ed_with_bvr   |
|----------------:|-----------------:|-------------------:|----------------------------:|-------------------------:|:--------------------|:------------------------|-----------------------------------:|--------------------------------:|:---------------------------|:-------------------------------|------------------------------------:|---------------------------------:|:----------------------------|:--------------------------------|
|            2014 |             5570 |               5570 |                        5570 |                        0 | 14.04%              | False                   |                               5570 |                               0 | 13.93%                     | False                          |                                5570 |                                0 | 14.29%                      | False                           |
|            2016 |             5568 |               5568 |                        5568 |                        0 | 32.16%              | False                   |                               5568 |                               0 | 30.99%                     | False                          |                                5568 |                                0 | 34.27%                      | False                           |
|            2018 |             5570 |               5570 |                        5570 |                        0 | 63.05%              | False                   |                               5570 |                               0 | 61.11%                     | False                          |                                5570 |                                0 | 66.03%                      | False                           |

No compliance variables had values below 0 or above 1.

## Voluntary Uptake in Hybrid Municipalities

At event time 0, hybrid-first municipalities have mean overall biometric uptake of 19.5%, with 16.4% among low-education voters and 25.5% among high-education voters. By the thresholds in the prompt, this is low voluntary uptake, though not near-zero. The key nuance is heterogeneity: the event-time-0 mean hides many low-activity municipalities alongside a substantial set with active biometric capture.

## Compliance Evolution

Hybrid-first municipalities rise from 19.5% at event time 0 to 57.9% at event time 2. Strict-first municipalities start much higher at 99.8% at event time 0 and reach 99.8% by event time 2 and 99.8% by event time 4. Within the observed 2014-2018 window, hybrid municipalities remain persistently below strict municipalities rather than catching up to the same compliance level.

## Compliance Gap

Using first-treatment regime, the mean high-minus-low education compliance gap is 5.5% in hybrid-first municipality-years and 0.7% in strict-first municipality-years. Using observation-year status, the corresponding gap is 10.5% for hybrid-status municipality-years and 0.1% for strict-status municipality-years. The gap is positive in both cases, meaning high-education voters are more likely to have biometric data on file, and it is much larger in hybrid-status observations than in strict-status observations in this descriptive window.

## Hybrid Intensity Screening

At event time 0, 11.2% of hybrid-first municipalities are dormant, 55.8% are low intensity, 25.0% are moderate intensity, and 8.0% are active. This means the binary hybrid indicator is not simply zero-treatment for most municipalities, but it does combine a nontrivial dormant/low-intensity group with a large moderate/active group. That mixture can attenuate binary hybrid comparisons even when many hybrid municipalities have meaningful voluntary uptake.

## Implications for the Next Phase

The descriptive evidence suggests that a binary hybrid indicator is too coarse for the next decomposition exercise. Useful next steps could include redefining hybrid exposure using a minimum intensity threshold, using compliance as a continuous treatment intensity, or using the within-municipality low-versus-high compliance gap to discipline a compliance-cost parameter. The present outputs do not choose among those options; they show that compliance intensity and education-specific uptake are empirically important margins to carry forward.
